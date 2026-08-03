#!/usr/bin/env python3
"""Static scope, freeze, authority, and fail-closed checks for C11/P13."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


STAGE_BASE = "f60bfb2412f7cba4dd0160f48f7c54ac41e2d007"
KERNEL_SHA = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
ORDER_SHA = "bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6"
CONTRACT_SHA = "06f575a09b56178d74f809003fec532d6d3d509b972e62c29da21754cab0d26d"
FIT_SHA = "ea6e8dc2ca3f69fe2f366801c9df8ec9832b58f399d605c88d91527ff2098407"
AUTHORITY_SHA = "283eace4f34e0a3d6961d49db2ab2c75ac6e384a9077a7044313a20f7bd4bc93"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("."))
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()

    contract_path = root / "contracts/p13/REACTION_LIEBIG_CONTRACT_V1.json"
    fit_path = root / "contracts/p13/OPERATOR_FIT_V1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    fit = json.loads(fit_path.read_text(encoding="utf-8"))
    header = (root / "src/chemistry/bmx_phosphorus_reactions_K.H").read_text(
        encoding="utf-8"
    )
    source = (root / "src/chemistry/bmx_phosphorus_reactions.cpp").read_text(
        encoding="utf-8"
    )
    transfer = (root / "src/des/bmx_calc_txfr.cpp").read_text(encoding="utf-8")
    ledger = (root / "src/des/bmx_pc_phosphorus.cpp").read_text(encoding="utf-8")
    checkpoint = (root / "src/io/bmx_checkpoint_schema.cpp").read_text(
        encoding="utf-8"
    )
    checkpoint_h = (root / "src/io/bmx_checkpoint_schema.H").read_text(
        encoding="utf-8"
    )
    layout = (root / "src/chemistry/bmx_chem_layout.H").read_text(encoding="utf-8")

    tracked = subprocess.check_output(
        ["git", "diff", "--name-only", STAGE_BASE, "--"], cwd=root, text=True
    ).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, text=True,
    ).splitlines()
    changed = sorted(set(tracked + untracked))
    allowed_exact = {
        "contracts/decision_reconciliation.json",
        "contracts/decision_reconciliation.md",
        "contracts/release_blockers.json",
        "src/chemistry/CMakeLists.txt",
        "src/chemistry/Make.package",
        "src/chemistry/bmx_chem_layout.H",
        "src/chemistry/bmx_phosphorus_reactions.cpp",
        "src/chemistry/bmx_phosphorus_reactions_K.H",
        "src/des/bmx_calc_txfr.cpp",
        "src/des/bmx_pc_phosphorus.H",
        "src/des/bmx_pc_phosphorus.cpp",
        "src/io/bmx_checkpoint_schema.H",
        "src/io/bmx_checkpoint_schema.cpp",
        "tools/repro/c11_reaction_unit.cpp",
        "tools/repro/run_c11_feature_off.py",
        "tools/repro/run_c11_native_build.ps1",
        "tools/repro/run_c11_reaction_runtime.py",
        "tools/repro/run_c11_reaction_unit.ps1",
        "tools/repro/run_c11_static_test.py",
    }
    allowed_prefixes = ("contracts/p13/", "evidence/stages/C11/")
    out_of_scope = [
        path for path in changed
        if path not in allowed_exact
        and not any(path.startswith(prefix) for prefix in allowed_prefixes)
    ]

    checks = {
        "stage_base_exact": subprocess.check_output(
            ["git", "rev-parse", f"{STAGE_BASE}^{{commit}}"], cwd=root, text=True
        ).strip() == STAGE_BASE,
        "ownership_scope_clean": not out_of_scope,
        "frozen_kernel_exact": sha256(root / "src/chemistry/bmx_chem_K.H") == KERNEL_SHA,
        "global_order_exact": sha256(root / "contracts/p10/OPERATOR_ORDER_V1.json") == ORDER_SHA,
        "contract_hash_exact": sha256(contract_path) == CONTRACT_SHA,
        "operator_fit_hash_exact": sha256(fit_path) == FIT_SHA,
        "authority_source_hash_exact": (
            sha256(root / "contracts/USER_APPROVED_DECISION_CONTRACT_20260801.txt")
            == AUTHORITY_SHA
        ),
        "authority_classification_honest": (
            contract["authority"]["classification"]
            == "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE"
            and contract["authority"]["mentor_approval_claimed_by_user_adoption"] is False
            and "CLOSED_SCIENTIFIC" not in json.dumps(contract)
        ),
        "O02_fit_without_new_order": (
            fit["p13_u05_disposition"]
            == "CLOSED_TECHNICAL_EXISTING_O02_SLOT"
            and fit["global_operator_order"]["sha256"] == ORDER_SHA
            and fit["global_operator_order"]["changed"] is False
            and fit["global_operator_order"]["slot"]
            == "O02_LOCAL_MESH_PARTICLE_UPDATE"
        ),
        "common_prestate_reaction_and_caps": all(token in header for token in (
            "result.reaction_forward = smaller(",
            "k_de * amount[BMXChemLayout::P_D] * dt",
            "result.reaction_reverse = smaller(",
            "k_ed * amount[BMXChemLayout::P_E] * dt",
            "result.reaction_reverse - result.reaction_forward",
            "result.reaction_forward - result.reaction_reverse",
        )),
        "liebig_min_and_donor_caps": all(token in header for token in (
            "result.carbon_supported_growth = dt * k_vb * amount[1]",
            "dt * (k_gp / q_p) * amount[BMXChemLayout::P_E]",
            "result.requested_growth = smaller(result.carbon_supported_growth",
            "amount[1] / q_b", "amount[BMXChemLayout::P_E] / q_p",
        )),
        "geometry_before_debit_and_atomic_commit": (
            header.index("native_geometry_eligible")
            < header.index("result.b_debit = q_b * accepted_volume")
            < header.index("amount[1] -= result.b_debit")
            and "result.structuralized_p = result.e_debit" in header
            and "BMXPhosphorus::creditStructuralP(global.structuralized_p)" in source
        ),
        "rejected_growth_consumes_nothing": (
            "if (!native_geometry_eligible) accepted_volume = 0.0" in header
            and "result.rejected_growth = result.requested_growth - accepted_volume" in header
        ),
        "nonfinite_negative_and_conservation_fail_closed": all(token in header for token in (
            "StepStatus::nonfinite", "StepStatus::negative_amount",
            "StepStatus::invalid_parameter", "StepStatus::invalid_geometry",
            "StepStatus::conservation_failure", "BMXPhosphorus::localTolerance",
            "BMXPhosphorus::integratedTolerance",
        )),
        "F_inert_and_working_P_zero": (
            "amount[BMXChemLayout::P_F]" in header
            and "values[NUM_PARTICLE_CHEM_COMPONENTS + BMXChemLayout::P_F] = 0.0" in header
            and "result.f_debit" not in header
            and "P_F] +=" not in header
            and "P_F] -=" not in header
        ),
        "feature_off_kernel_bytes_and_arguments_unchanged": (
            "Real* kernel_parameters = chempar" in transfer
            and "if (p13_enabled &&" in transfer
            and "xferMeshToParticleAndUpdateChem(" in transfer
            and "kernel_parameters" in transfer
        ),
        "feature_on_legacy_growth_disabled_once": all(token in transfer for token in (
            "p13_kernel_parameters[14] = 0.0",
            "p13_kernel_parameters[15] = 0.0",
            "p13_kernel_parameters[23] = 0.0",
            "p13_kernel_parameters[24] = 0.0",
            "BMXPhosphorusReactions::apply(",
            "BMXPhosphorusReactions::recordStep(",
        )),
        "P12_P13_combination_fails_closed": (
            "if (p12_enabled && p13_enabled)" in transfer
            and "cannot be enabled in the same run" in transfer
        ),
        "allowed_sensitivity_values_exact": all(token in source for token in (
            "forward == 1.0e-5 && reverse == 0.0",
            "forward == 1.0e-6 && reverse == 1.0e-6",
            "forward == 1.0e-5 && reverse == 1.0e-5",
            "forward == 1.0e-4 && reverse == 1.0e-4",
            "value == 3.0e-6 || value == 3.0e-5 || value == 3.0e-4",
            "value == 0.1 || value == 1.0 || value == 10.0",
        )),
        "legacy_P_operators_required_zero": all(token in source for token in (
            'chemistry.query("p_growth_limit"', 'chemistry.query("qP"',
            'chemistry.query("kP"', 'chemistry.query("krP"',
            'chemistry.query("mass_transfer_P"',
            "P13 requires every superseded legacy inert-P operator exactly zero",
        )),
        "checkpoint_schema_v6": (
            'version_line = "Checkpoint version: 6"' in checkpoint_h
            and "BMX_SCHEMA_V6_BEGIN" in checkpoint
            and "BMX_SCHEMA_V6_END" in checkpoint
        ),
        "checkpoint_binds_config_fit_and_cumulative": all(token in checkpoint for token in (
            "p13_contract_sha256", "p13_operator_fit_sha256", "p13_k_de",
            "p13_k_ed", "p13_q_p", "p13_k_gP_over_k_gB",
            "p13_cumulative_reaction_forward", "p13_cumulative_requested_growth",
            "p13_cumulative_structuralized_p", "p13_updates",
            "P13 contract, O02 fit, or parameter identity mismatch",
            "P13 structuralized ledger differs from global structural P",
        )),
        "decision_binding_extended_not_replaced": (
            "UDC-20260801-P10-U01" in layout
            and "UDC-20260801-MENTOR-DECISION-FREEZE-V2" in layout
            and "UDC-20260801-P13-V1" in layout
            and AUTHORITY_SHA in header
        ),
        "no_C12_or_later_source_behavior": all(
            token not in header + source + transfer + checkpoint
            for token in ("p14.", "P14_", "k_export", "carbon_reward", "P15_")
        ),
    }
    report = {
        "artifact_type": "C11_STATIC_QUALIFICATION",
        "stage": "C11/P13",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "stage_base": STAGE_BASE,
        "changed_paths": changed,
        "out_of_scope_paths": out_of_scope,
        "checks": checks,
        "hashes": {
            "kernel": KERNEL_SHA,
            "global_order": ORDER_SHA,
            "contract": CONTRACT_SHA,
            "operator_fit": FIT_SHA,
            "authority_source": AUTHORITY_SHA,
        },
        "external_resources": "none",
        "external_spend_usd": 0,
        "claim_boundary": (
            "Static C11 software/numerical qualification; not mentor approval, "
            "biological calibration, predictive validity, or C12+ evidence."
        ),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "checks": checks,
        "out_of_scope": out_of_scope,
    }, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
