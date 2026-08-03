#!/usr/bin/env python3
"""Static scope, freeze, contract, and fail-closed checks for C12/P14."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


STAGE_BASE = "5afe3298823011a3506d3799ccdbe815f162a227"
KERNEL_SHA = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
ORDER_SHA = "bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6"
CONTRACT_SHA = "01a9d6eb7291cc8bc0c98f52afbf3c5ea1c86da4fd3f992a02665e283f81ff4e"
FIT_SHA = "72193a1034d4148d167f059c347053d2206fa580cce9a156ec705304e7f378e7"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("."))
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    contract_path = root / "contracts/p14/EXPORT_REWARD_CONTRACT_V1.json"
    fit_path = root / "contracts/p14/OPERATOR_FIT_V1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    fit = json.loads(fit_path.read_text(encoding="utf-8"))
    header = (root / "src/chemistry/bmx_phosphorus_export_K.H").read_text(
        encoding="utf-8"
    )
    source = (root / "src/chemistry/bmx_phosphorus_export.cpp").read_text(
        encoding="utf-8"
    )
    traversal = (root / "src/des/bmx_pc_export.cpp").read_text(encoding="utf-8")
    evolve = (root / "src/timestepping/bmx_evolve.cpp").read_text(encoding="utf-8")
    checkpoint = (root / "src/io/bmx_checkpoint_schema.cpp").read_text(
        encoding="utf-8"
    )
    checkpoint_h = (root / "src/io/bmx_checkpoint_schema.H").read_text(
        encoding="utf-8"
    )
    ledger = (root / "src/des/bmx_pc_phosphorus.cpp").read_text(encoding="utf-8")
    layout = (root / "src/chemistry/bmx_chem_layout.H").read_text(encoding="utf-8")
    unit = (root / "tools/repro/c12_export_unit.cpp").read_text(encoding="utf-8")
    runtime = (root / "tools/repro/run_c12_export_runtime.py").read_text(
        encoding="utf-8"
    )

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
        "src/chemistry/bmx_phosphorus_export.cpp",
        "src/chemistry/bmx_phosphorus_export_K.H",
        "src/des/CMakeLists.txt",
        "src/des/Make.package",
        "src/des/bmx_pc.H",
        "src/des/bmx_pc_export.cpp",
        "src/des/bmx_pc_phosphorus.H",
        "src/des/bmx_pc_phosphorus.cpp",
        "src/io/bmx_checkpoint_schema.H",
        "src/io/bmx_checkpoint_schema.cpp",
        "src/timestepping/bmx_evolve.cpp",
        "tools/repro/c12_export_unit.cpp",
        "tools/repro/run_c12_export_runtime.py",
        "tools/repro/run_c12_export_unit.ps1",
        "tools/repro/run_c12_feature_off.py",
        "tools/repro/run_c12_native_build.ps1",
        "tools/repro/run_c12_static_test.py",
    }
    allowed_prefixes = (
        "contracts/p14/", "evidence/stages/C12/", "evidence/stages/C12V2/"
    )
    out_of_scope = [
        path for path in changed
        if path not in allowed_exact and
        not any(path.startswith(prefix) for prefix in allowed_prefixes)
    ]
    changed_source = "\n".join(
        (root / path).read_text(encoding="utf-8", errors="replace")
        for path in changed if path.startswith("src/") and (root / path).is_file()
    )

    checks = {
        "stage_base_exact": subprocess.check_output(
            ["git", "rev-parse", f"{STAGE_BASE}^{{commit}}"], cwd=root,
            text=True,
        ).strip() == STAGE_BASE,
        "ownership_scope_clean": not out_of_scope,
        "frozen_kernel_exact": sha256(root / "src/chemistry/bmx_chem_K.H") == KERNEL_SHA,
        "global_order_exact": sha256(root / "contracts/p10/OPERATOR_ORDER_V1.json") == ORDER_SHA,
        "contract_hash_exact": sha256(contract_path) == CONTRACT_SHA,
        "operator_fit_hash_exact": sha256(fit_path) == FIT_SHA,
        "authority_classification_honest": (
            contract["status"] ==
            "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE" and
            contract["authority"]["mentor_approval"] is False and
            contract["authority"]["calibration"] is False and
            contract["authority"]["closed_scientific"] is False and
            contract["authority"]["predictive_validation"] is False
        ),
        "O09_fit_without_new_order": (
            fit["p14_u07_disposition"] ==
            "CLOSED_TECHNICAL_EXISTING_O09_SLOT" and
            fit["global_operator_order"]["sha256"] == ORDER_SHA and
            fit["global_operator_order"]["changed"] is False and
            fit["global_operator_order"]["slot"] ==
            "O09_INTERFACE_EXPORT_TRANSACTION"
        ),
        "continuous_finite_radius_measure": all(token in header for token in (
            "continuousAxialFraction", "rectangleInterval", "circleInterval",
            "pointRectangleDistanceSquared2D", "active_radius",
            "measure += current_upper - current_lower",
        )),
        "p11_snapping_tangency_and_solid_precedence": all(
            token in header for token in (
                "classifyCapsule", "classification.solid_contact",
                "!classification.window_contact", "capsuleTolerance",
                "snapToBoundary", "original.radius - tolerance",
                "zero discriminant is tangency",
            )
        ),
        "true_crossing_diagnostic_not_gate": (
            "result.true_crossing = classification.true_crossing" in header and
            "classification.window_contact && !classification.solid_contact" in header and
            "classification.true_crossing &&" not in header
        ),
        "fraction_has_no_mesh_or_decomposition_input": all(
            token not in header[header.index("continuousAxialFraction"):
                                header.index("transactAmounts")]
            for token in ("mesh_cell", "amr_level", "rank", "tile",
                          "decomposition")
        ),
        "final_owned_once_per_update": all(token in traversal for token in (
            "tile.numRealParticles()", "amrex::ParallelFor(",
            "BMXPhosphorusExport::apply(",
            "BMXPhosphorusExport::requireUpdateAvailable(update_id)",
            "BMXPhosphorusExport::recordStep(",
        )) and traversal.count("BMXPhosphorusExport::apply(") == 1,
        "exact_reward_without_atomic_mass_derivation": (
            "amrex::Real(967.0) / amrex::Real(125.0)" in header and
            "reward_molar_multiplier == amrex::Real(7.736)" in header and
            "result.reward = reward_molar_multiplier * result.accepted" in header and
            all(token not in changed_source for token in
                ("atomic_mass", "molar_mass", "periodic_table"))
        ),
        "caps_before_atomic_local_commit": (
            header.index("transactAmounts(") <
            header.index("values[BMXChemLayout::P_D] =") <
            header.index("values[BMXChemLayout::A] =") and
            "result.exported_p = transaction.accepted" in header and
            "BMXPhosphorus::creditExportedP(global.exported_p)" in source
        ),
        "five_rates_exact_and_zero_included": all(token in source for token in (
            "value == 0.0", "value == 1.0e-6",
            "value == 5.26977773579e-6", "value == 1.0e-5",
            "value == 1.0e-4",
        )),
        "nonfinite_negative_geometry_and_conservation_fail_closed": all(
            token in header for token in (
                "StepStatus::nonfinite", "StepStatus::invalid_geometry",
                "StepStatus::invalid_parameter", "StepStatus::negative_amount",
                "StepStatus::fraction_out_of_range",
                "StepStatus::conservation_failure",
                "BMXPhosphorus::localTolerance",
            )
        ),
        "F_inactive_and_unchanged": (
            "F_active=0" in source and
            "values[BMXChemLayout::P_F] =" not in header and
            "values[BMXChemLayout::P_F] +=" not in header and
            "values[BMXChemLayout::P_F] -=" not in header
        ),
        "O09_after_final_topology_before_O10": (
            evolve.index("pc->AuditP11GeometryEvents(nstep)") <
            evolve.index("pc->ApplyP14Export(nstep, dt)") <
            evolve.index('AuditP10Ledger("O10_POST_UPDATE_LEDGER"')
        ),
        "feature_off_default_and_no_call_effect": (
            "bool enabled = false" in header and
            "if (!binding.enabled) return" in traversal and
            "BMXPhosphorusExport::enabled()" in evolve
        ),
        "checkpoint_schema_v7": (
            'version_line = "Checkpoint version: 7"' in checkpoint_h and
            "BMX_SCHEMA_V7_BEGIN" in checkpoint and
            "BMX_SCHEMA_V7_END" in checkpoint
        ),
        "checkpoint_binds_contract_parameter_and_ledgers": all(
            token in checkpoint for token in (
                "p14_contract_sha256", "p14_operator_fit_sha256",
                "p14_interface_fraction", "p14_reward_molar_multiplier",
                "p14_k_export", "p14_cumulative_requested_p",
                "p14_cumulative_accepted_p", "p14_cumulative_rejected_p",
                "p14_cumulative_exported_p",
                "p14_cumulative_exchange_derived_a",
                "p14_cumulative_bootstrap_a_credit", "p14_last_update_id",
                "P14 export ledger differs from global exported P",
            )
        ),
        "bootstrap_and_exchange_provenance_separate": (
            "exchange_derived_a" in header and "bootstrap_a_credit" in header and
            "ledger.bootstrap_a_credit != 0.0" in source and
            "bootstrap_a_credit=0" in source
        ),
        "global_exported_p_credit_fail_closed": all(token in ledger for token in (
            "void creditExportedP", "P14 exported-P credit",
            "ledger_state.exported_p + amount",
        )),
        "decision_binding_extended_not_replaced": all(token in layout for token in (
            "UDC-20260801-P10-U01", "UDC-20260801-P13-V1",
            "UDC-20260802-P14-C12-BINDINGS-V1",
        )),
        "qualification_matrix_named": all(token in unit + runtime for token in (
            "no_contact", "tangency", "partial_contact", "full_contact",
            "oblique_contact", "solid_edge", "window_contact_only",
            "true_crossing", "{2, 4, 8}", "analytical_exponential",
            "restart_2_to_1", "decomposition_rank2",
            "checkpoint_algebra_mutation",
        )),
        "no_C13_or_later_new_behavior": all(
            token not in changed_source for token in
            ("P15_", "p15.", "P16_", "p16.", "P17_", "p17.")
        ),
    }
    report = {
        "artifact_type": "C12_STATIC_QUALIFICATION",
        "stage": "C12/P14",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "stage_base": STAGE_BASE,
        "changed_paths": changed,
        "out_of_scope_paths": out_of_scope,
        "checks": checks,
        "hashes": {
            "kernel": KERNEL_SHA, "global_order": ORDER_SHA,
            "contract": CONTRACT_SHA, "operator_fit": FIT_SHA,
        },
        "external_resources": "none",
        "external_spend_usd": 0,
        "claim_boundary": "Static C12 software/numerical qualification under USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE; not mentor approval, calibration, predictive validity, or C13 science.",
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "checks": checks,
        "out_of_scope": out_of_scope,
    }, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
