#!/usr/bin/env python3
"""Static scope, provenance, freeze, and fail-closed checks for C10/P12."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


STAGE_BASE = "ff315c5eb139c824bc40dbc3bfb2b0922fffa9db"
KERNEL_SHA = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
CONTRACT_SHA = "2094aed3c8ef21a257d2c597352793384d01a1efc3d72936d5c5108d308f8804"
NUMERICAL_V1_SHA = "dc5af4ff51cf077e9d494ae7d87c7d0a01ec51887101bd63764b0abc4460ce0e"
NUMERICAL_V2_SHA = "43d64a8f4ec6c8c00379fc3d9605441cb900479fcdd8db9e78e6fc1edd28f81f"
SOURCE_SHA = "34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066"
NETWORK_SHA = "1f2294613b8a608b068d60269ff8eb29990210d3a1bc6d8142d4f840aa292702"
PRESERVED_V1_EVIDENCE = {
    "evidence/stages/C10/P12_48H_GRID_TIME.json":
        "edeb759d86979f8b6077ba41cc8b9f07988d0f4162e7b39240008fa1dd0a4157",
    "evidence/stages/C10/BLOCKER_REPORT.json":
        "b7a39a388a1016604608ae4d2df163f4444a53ebf968ddc9f3822e4c14760bf3",
    "evidence/stages/C10/BLOCKER_REPORT.md":
        "3397ea6b6784625b06fe7a164b646fb3c35a3992504ca97c03ab144c29e897bf",
    "evidence/stages/C10/STAGE_REPORT.json":
        "6699679fba747586937ab0832aa7b2dad2c771ac45366398fa44f192e995684b",
    "evidence/stages/C10/STAGE_REPORT.md":
        "b7b7df0d7bba082fcc73823e5770f3e80c8796002386ab84307d0aff2838bc4f",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("."))
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()

    contract_path = root/"contracts/p12/UPTAKE_ONLY_CONTRACT_V1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    numerical_v2_path = root/"contracts/p12/NUMERICAL_PREREGISTRATION_V2.json"
    numerical_v2 = json.loads(numerical_v2_path.read_text(encoding="utf-8"))
    decision = json.loads((root/"contracts/decision_reconciliation.json").read_text(encoding="utf-8"))
    blockers = json.loads((root/"contracts/release_blockers.json").read_text(encoding="utf-8"))
    header = (root/"src/chemistry/bmx_phosphorus_uptake_K.H").read_text(encoding="utf-8")
    source = (root/"src/chemistry/bmx_phosphorus_uptake.cpp").read_text(encoding="utf-8")
    transfer = (root/"src/des/bmx_calc_txfr.cpp").read_text(encoding="utf-8")
    checkpoint = (root/"src/io/bmx_checkpoint_schema.cpp").read_text(encoding="utf-8")
    checkpoint_h = (root/"src/io/bmx_checkpoint_schema.H").read_text(encoding="utf-8")
    v2_runner = (root/"tools/repro/run_c10_p12_v2_48h.py").read_text(
        encoding="utf-8")

    tracked_changed = subprocess.check_output(
        ["git", "diff", "--name-only", STAGE_BASE, "--"], cwd=root, text=True
    ).splitlines()
    untracked_changed = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, text=True
    ).splitlines()
    changed = sorted(set(tracked_changed + untracked_changed))
    allowed_exact = {
        ".gitattributes",
        "contracts/decision_reconciliation.json",
        "contracts/decision_reconciliation.md",
        "contracts/release_blockers.json",
        "contracts/USER_ADOPTED_DECISION_CONTRACT_20260801_V2.json",
        "contracts/USER_ADOPTED_DECISION_CONTRACT_20260801_V2.sha256",
        "contracts/USER_ADOPTED_DECISION_CONTRACT_20260801_V2.txt",
        "src/chemistry/CMakeLists.txt",
        "src/chemistry/Make.package",
        "src/chemistry/bmx_chem_layout.H",
        "src/chemistry/bmx_phosphorus_uptake.cpp",
        "src/chemistry/bmx_phosphorus_uptake_K.H",
        "src/des/bmx_calc_txfr.cpp",
        "src/io/bmx_checkpoint_schema.H",
        "src/io/bmx_checkpoint_schema.cpp",
        "src/timestepping/bmx_evolve.cpp",
        "tools/repro/c10_uptake_unit.cpp",
        "tools/repro/c10_plot_extract.cpp",
        "tools/repro/build_c10_plot_extract.ps1",
        "tools/repro/run_c08_checkpoint_tests.py",
        "tools/repro/run_c08_static_test.py",
        "tools/repro/run_c10_p12_48h.py",
        "tools/repro/run_c10_p12_v2_48h.py",
        "tools/repro/run_c10_uptake_unit.ps1",
        "tools/repro/run_c10_uptake_runtime.py",
        "tools/repro/run_c10_static_test.py",
    }
    allowed_prefixes = ("contracts/p12/", "evidence/stages/C10/",
                        "evidence/stages/C10V2/")
    out_of_scope = sorted(path for path in changed if path not in allowed_exact and
                          not path.startswith(allowed_prefixes))

    p12_fields = {field["unknown_id"]: field for field in decision["fields"]
                  if field["phase"] == "P12_UPTAKE_ONLY_DEPLETION"}
    remaining_ids = {row["id"] for row in blockers["blockers"]}
    checks = {
        "stage_base_exact": subprocess.check_output(
            ["git", "rev-parse", f"{STAGE_BASE}^{{commit}}"], cwd=root, text=True
        ).strip() == STAGE_BASE,
        "ownership_scope_clean": not out_of_scope,
        "kernel_frozen": sha256(root/"src/chemistry/bmx_chem_K.H") == KERNEL_SHA,
        "contract_hash_exact": sha256(contract_path) == CONTRACT_SHA,
        "failed_v1_preregistration_preserved": (
            sha256(root/"contracts/p12/NUMERICAL_PREREGISTRATION_V1.json") ==
            NUMERICAL_V1_SHA
        ),
        "failed_v1_evidence_preserved": all(
            sha256(root/path) == expected
            for path, expected in PRESERVED_V1_EVIDENCE.items()
        ),
        "numerical_v2_hash_exact": (
            sha256(numerical_v2_path) == NUMERICAL_V2_SHA and
            (root/"contracts/p12/NUMERICAL_PREREGISTRATION_V2.sha256")
                .read_text(encoding="utf-8").split()[0] == NUMERICAL_V2_SHA
        ),
        "numerical_v2_review_pending": (
            numerical_v2["execution_and_review_gate"]["review_status"] == "PENDING"
            and numerical_v2["execution_and_review_gate"]
                ["v2_48h_outcome_execution"] ==
                "PROHIBITED_PENDING_INDEPENDENT_REVIEW"
        ),
        "numerical_v2_schedule_exact": (
            numerical_v2["coupled_grid_time_levels"] == [
                {"id": "L0", "n_cell": [8, 8, 4], "dt_s": 1800.0,
                 "updates_48h": 96},
                {"id": "L1", "n_cell": [16, 16, 8], "dt_s": 225.0,
                 "updates_48h": 768},
                {"id": "L2", "n_cell": [32, 32, 16], "dt_s": 28.125,
                 "updates_48h": 6144},
            ]
        ),
        "v2_outcome_runner_fail_closed": all(token in v2_runner for token in (
            "validate_prerequisites", "reviewer_is_implementation_writer",
            "reviewed_source_commit", "outcome_execution_authorized",
            "source worktree is not clean", NUMERICAL_V2_SHA,
        )),
        "v2_runner_volume_scaled_schedule": all(token in v2_runner for token in (
            '("L0", 8, 1800.0, 96)',
            '("L1", 16, 225.0, 768)',
            '("L2", 32, 28.125, 6144)',
        )),
        "v2_runner_no_clipping_gates": all(token in v2_runner for token in (
            "ETA_LIMIT = 0.25", "SCALE_LIMIT = 1.0 - 64.0 * math.ulp(1.0)",
            "cumulative_rejection_roundoff_only",
            "zero_inventory_positive_request_absent",
            "checkpoint_restart_2_to_1",
        )),
        "authority_hash_exact": contract["authority"]["source_sha256"] == SOURCE_SHA,
        "authority_classification_honest": (
            contract["authority"]["classification"] ==
            "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE"
            and contract["authority"]["mentor_approval_claimed"] is False
        ),
        "p12_only_contract_scope": "P13 and later" in contract["authority"]["scope_consumed"],
        "header_contract_binding": (
            CONTRACT_SHA in header and SOURCE_SHA in header and
            NUMERICAL_V2_SHA in header and
            "USER-DIRECTED-20260801-P12-NUMERICAL-V2" in header
        ),
        "fixed_network_hash_exact": (
            sha256(root/"contracts/p12/network/P12_FIXED_NETWORK_V1.dat") == NETWORK_SHA
            and NETWORK_SHA in header and 'parameters.get("network_sha256"' in source
        ),
        "inward_only_michaelis_menten": all(token in header for token in (
            "surfaceFlux", "requestedAmount", "mesh_d > 0.0", "eligible_area * surfaceFlux"
        )),
        "shared_donor_two_pass": all(token in transfer for token in (
            "p12_request_sum", "Pass one sums all requests", "donorScale",
            "Atomic::AddNoRet", "accepted / cell_par[realIdx::vol]"
        )),
        "accepted_only_mesh_debit": (
            "BMXChemLayout::P_D] = -accepted" in transfer
            and "recordAcceptedStep" in transfer
        ),
        "transient_increment_cleared_before_o10": (
            transfer.index("O03 has now committed") < transfer.index("bmx_calc_txfr_particle")
            and "particle.rdata(base + BMXChemLayout::P_D) = 0.0" in transfer
        ),
        "f_and_e_never_activated": all(token not in source+transfer for token in (
            "P_E] +=", "P_F] +=", "P_E] = -", "P_F] = -"
        )),
        "uptake_only_zero_guards": all(token in source for token in (
            'requiredZero(chemistry, "kP")', 'requiredZero(chemistry, "krP")',
            'requiredZero(chemistry, "mass_transfer_P")',
            'requiredZero(chemistry, "p_growth_limit")',
            'requiredZero(chemistry, "kg")', 'requiredZero(chemistry, "kv")',
            'requiredZero(chemistry, "branching_probability")',
            'requiredZero(chemistry, "splitting_probability")',
            'requiredZero(chemistry, "fusion_probability")'
        )),
        "tip_modes_fixed_network_only": all(token in source for token in (
            'mode == "TIP_005"', 'mode == "TIP_010"',
            'mode == "TIP_020"', 'mode == "TIP_010_AREA_MATCHED"'))
            and "segment_length > terminal_distance" in header
            and "!is_live_tip" in header
            and "partial-segment" in header,
        "solver_conservation_guard": "diffusion.rtol <= 1e-13" in source,
        "checkpoint_schema_v5": (
            "BMX_SCHEMA_V5_BEGIN" in checkpoint and "BMX_SCHEMA_V5_END" in checkpoint
            and 'version_line = "Checkpoint version: 5"' in checkpoint_h
        ),
        "checkpoint_binds_config_and_cumulative": all(token in checkpoint for token in (
            "p12_uptake_contract_sha256", "p12_uptake_j_max", "p12_uptake_k_m",
            "p12_numerical_contract_id", "p12_numerical_contract_sha256",
            "p12_uptake_network_sha256",
            "p12_uptake_mesh_d_diffusivity", "p12_uptake_solver_rtol",
            "p12_uptake_cumulative_requested", "p12_uptake_updates",
            "p12_uptake_run_minimum_donor_scale",
            "p12_uptake_run_maximum_donor_eta",
            "p12_uptake_zero_inventory_positive_request_updates",
            "P12 uptake contract or parameter identity mismatch"
        )),
        "run_wide_clipping_diagnostics": all(token in source+transfer+header for token in (
            "maximum_donor_eta", "minimum_donor_scale",
            "zero_inventory_positive_request_updates", "donorDemandRatio"
        )),
        "p12_u01_u04_closed_user_only": all(
            p12_fields[f"P12-U0{i}-" + suffix]["status"] == "CLOSED_USER_ADOPTED"
            for i, suffix in ((1,"EXPERIMENT-CONTRACT"),(2,"CONTROLS"),
                              (3,"REPLICATES"),(4,"SEEDS"))
        ),
        "p12_release_blockers_removed_only": (
            blockers["count"] == len(blockers["blockers"]) == 25
            and "D-C10-02-NUMERICAL-CONVERGENCE" in remaining_ids
            and not any(identifier.startswith("P12-U0") and identifier[:7] in
                        {"P12-U01","P12-U02","P12-U03","P12-U04"}
                        for identifier in remaining_ids)
        ),
        "no_c11_or_later_source_behavior": all(token not in source+transfer for token in (
            "P13_", "P14_", "P15_", "q_P", "k_export", "carbon_reward",
            "structuralization"
        )),
    }
    report = {
        "artifact_type": "C10_V2_PREREVIEW_STATIC_QUALIFICATION",
        "stage": "C10/P12",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "stage_base": STAGE_BASE,
        "changed_paths": changed,
        "out_of_scope_paths": out_of_scope,
        "checks": checks,
        "hashes": {"kernel": KERNEL_SHA, "contract": CONTRACT_SHA,
                   "numerical_v1": NUMERICAL_V1_SHA,
                   "numerical_v2": NUMERICAL_V2_SHA,
                   "authority_source": SOURCE_SHA, "fixed_network": NETWORK_SHA},
        "external_resources": "none", "external_spend_usd": 0,
        "claim_boundary": "Static engineering qualification; not independent numerical, release-host, mentor-approved, calibrated, or predictive evidence.",
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": checks,
                      "out_of_scope": out_of_scope}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
