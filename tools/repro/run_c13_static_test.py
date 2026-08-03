#!/usr/bin/env python3
"""Static scope, freeze, contract, and fail-closed checks for C13 Stage 0."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


STAGE_BASE = "7768fc92f683f68b0d282b69e45d079103fc847a"
KERNEL_SHA = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
ORDER_SHA = "bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6"
CONTRACT_HASHES = {
    "binding": ("contracts/p15/C13_BINDING_ADOPTION_V1.json",
                "c726cc575684e078d3c3359ececef28fde91daf5050aec273161b734710875d7"),
    "bonded": ("contracts/p15/BONDED_D_TRANSPORT_CONTRACT_V1.json",
               "e6022bffb56defa13cb31e7c0ac2097dfd197c9513e2f3e2e3a5ade37feeda44"),
    "numerical": ("contracts/p15/NUMERICAL_PREREGISTRATION_V1.json",
                  "c4d8dd50bb9c4b2b945e80410d71c4b822a32b29a325d7bb9ca5a8ec53531182"),
    "terminal": ("contracts/p15/TERMINAL_ZONE_CONTRACT_V1.json",
                 "272106fabb9af9221d13c9f3b82fa9a963bea831c0a983747986789452b1bfe6"),
    "operator_fit": ("contracts/p15/OPERATOR_FIT_V1.json",
                     "4e391b63796f61cade7381a0a4168c6aa2d607272cd0c009cedef5aec4ad7168"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("."))
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()

    contracts = {
        name: json.loads(read(root, path))
        for name, (path, _) in CONTRACT_HASHES.items()
    }
    header = read(root, "src/chemistry/bmx_p15_stage0_K.H")
    binding_source = read(root, "src/chemistry/bmx_p15_stage0.cpp")
    graph = read(root, "src/des/bmx_pc_p15.cpp")
    transfer = read(root, "src/des/bmx_calc_txfr.cpp")
    evolve = read(root, "src/timestepping/bmx_evolve.cpp")
    checkpoint_h = read(root, "src/io/bmx_checkpoint_schema.H")
    checkpoint = read(root, "src/io/bmx_checkpoint_schema.cpp")
    uptake = read(root, "src/chemistry/bmx_phosphorus_uptake.cpp")
    reactions = read(root, "src/chemistry/bmx_phosphorus_reactions.cpp")
    export = read(root, "src/chemistry/bmx_phosphorus_export.cpp")
    seed_parser = read(root, "src/setup/bmx_init.cpp")
    unit = read(root, "tools/repro/c13_p15_unit.cpp")
    runtime = read(root, "tools/repro/run_c13_stage0_runtime.py")
    feature_off = read(root, "tools/repro/run_c13_feature_off.py")

    tracked = subprocess.check_output(
        ["git", "diff", "--name-only", STAGE_BASE, "--"],
        cwd=root, text=True,
    ).splitlines()
    untracked_all = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, text=True,
    ).splitlines()
    workspace_artifact_prefixes = ("build-c13-native-dev/",)
    workspace_artifacts = sorted(
        path for path in untracked_all
        if any(path.startswith(prefix) for prefix in workspace_artifact_prefixes)
    )
    untracked = [path for path in untracked_all if path not in workspace_artifacts]
    changed = sorted(set(tracked + untracked))
    allowed_exact = {
        "contracts/decision_reconciliation.json",
        "contracts/decision_reconciliation.md",
        "contracts/release_blockers.json",
        "src/chemistry/CMakeLists.txt",
        "src/chemistry/Make.package",
        "src/chemistry/bmx_p15_stage0.cpp",
        "src/chemistry/bmx_p15_stage0_K.H",
        "src/chemistry/bmx_phosphorus_export.cpp",
        "src/chemistry/bmx_phosphorus_export_K.H",
        "src/chemistry/bmx_phosphorus_reactions.cpp",
        "src/chemistry/bmx_phosphorus_reactions_K.H",
        "src/chemistry/bmx_phosphorus_uptake.cpp",
        "src/chemistry/bmx_phosphorus_uptake_K.H",
        "src/des/CMakeLists.txt",
        "src/des/Make.package",
        "src/des/bmx_calc_txfr.cpp",
        "src/des/bmx_pc_p15.cpp",
        "src/io/bmx_checkpoint_schema.H",
        "src/io/bmx_checkpoint_schema.cpp",
        "src/setup/bmx_init.cpp",
        "src/timestepping/bmx_evolve.cpp",
        "tools/repro/c13_p15_unit.cpp",
        "tools/repro/run_c13_authority_gate.py",
        "tools/repro/run_c13_feature_off.py",
        "tools/repro/run_c13_native_build.ps1",
        "tools/repro/run_c13_p15_unit.ps1",
        "tools/repro/run_c13_rng_diagnostic.py",
        "tools/repro/run_c13_stage0_runtime.py",
        "tools/repro/run_c13_static_test.py",
    }
    allowed_prefixes = ("contracts/p15/", "evidence/stages/C13/")
    out_of_scope = [
        path for path in changed
        if path not in allowed_exact
        and not any(path.startswith(prefix) for prefix in allowed_prefixes)
    ]

    contract_hash_checks = {
        name: sha256(root / path) == expected
        for name, (path, expected) in CONTRACT_HASHES.items()
    }
    binding = contracts["binding"]
    bonded = contracts["bonded"]
    numerical = contracts["numerical"]
    terminal = contracts["terminal"]
    fit = contracts["operator_fit"]
    checkpoint_tokens = (
        "p15_binding_contract_sha256", "p15_bonded_contract_sha256",
        "p15_numerical_contract_sha256", "p15_terminal_contract_sha256",
        "p15_operator_fit_sha256", "p15_bonded_d_diffusivity",
        "p15_qualification_outcomes_enabled", "p15_initial_network_sha256",
        "p15_generated_configuration_sha256", "p15_independent_review_status",
        "p15_independent_review_sha256", "p15_reviewed_source_commit",
        "p15_area_match_multiplier", "p15_area_match_initial_full_area",
        "p15_area_match_initial_tip010_area", "p15_terminal_current_full_area",
        "p15_terminal_current_tip005_area", "p15_terminal_current_tip010_area",
        "p15_terminal_current_tip020_area", "p15_terminal_current_effective_area",
        "p15_bonded_cumulative_requested", "p15_bonded_cumulative_accepted",
        "p15_bonded_cumulative_rejected",
        "p15_bonded_cumulative_gross_absolute_accepted",
    )
    combined_product = "\n".join((
        header, binding_source, graph, transfer, evolve, checkpoint,
        uptake, reactions, export, seed_parser,
    ))

    checks = {
        "stage_base_exact": subprocess.check_output(
            ["git", "rev-parse", STAGE_BASE], cwd=root, text=True,
        ).strip() == STAGE_BASE,
        "ownership_scope_clean": not out_of_scope,
        "frozen_kernel_exact": (
            sha256(root / "src/chemistry/bmx_chem_K.H") == KERNEL_SHA
        ),
        "global_order_exact": (
            sha256(root / "contracts/p10/OPERATOR_ORDER_V1.json") == ORDER_SHA
        ),
        "all_contract_hashes_exact": all(contract_hash_checks.values()),
        "authority_classification_honest": (
            binding["classification"] ==
            "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE"
            and binding["preserved_classification"]["mentor_approval"] is False
            and binding["preserved_classification"]["closed_scientific"] is False
            and binding["preserved_classification"]["biological_calibration"] is False
            and binding["preserved_classification"]["predictive_validation"] is False
            and "CLOSED_SCIENTIFIC" not in combined_product
        ),
        "operator_fit_uses_existing_order": (
            fit["global_operator_order"]["sha256"] == ORDER_SHA
            and fit["global_operator_order"]["changed"] is False
            and fit["new_order_review_required"] is False
            and {row["slot"] for row in fit["fits"]} == {
                "O02_LOCAL_MESH_PARTICLE_UPDATE",
                "O07_BONDED_TRANSPORT",
                "O09_INTERFACE_EXPORT_TRANSACTION",
            }
        ),
        "bonded_contract_formula_bound": (
            bonded["classification"] ==
            "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE"
            and "halfSegmentConductance" in header
            and "2.0 * diffusivity * crossSectionArea(radius) / length" in header
            and "first_half * second_half / junction_sum" in header
            and "stableSubsteps" in header
            and "maximum_diagonal_rate > amrex::Real(0.25)" in header
            and "BONDED_D_CAP_ACTIVATED" in binding_source
        ),
        "bonded_common_snapshot_atomic_commit": all(token in graph for token in (
            "const std::vector<Real> snapshot = amounts",
            "std::vector<Real> outgoing(snapshot.size(), 0.0)",
            "std::vector<Real> delta(snapshot.size(), 0.0)",
            "delta[connection.first_segment] -= signed_accepted",
            "delta[connection.second_segment] += signed_accepted",
            "commitDAmounts(particles, graph, amounts)",
        )),
        "zero_diffusivity_exact_early_identity": (
            "binding.bonded_d_diffusivity == 0.0" in graph
            and graph.index("binding.bonded_d_diffusivity == 0.0")
            < graph.index("const auto graph = buildGraph(particles)",
                          graph.index("void applyBondedDTransport"))
        ),
        "terminal_metric_graph_and_sites": all(token in graph + header for token in (
            "endpointCoordinate", "site == 1 ? -1.0 : 1.0",
            "std::priority_queue", "terminalEligibleLength",
            "return smaller(length, first + second)",
            "source_nodes", "AMBIGUOUS_TIP_ORIENTATION",
        )),
        "terminal_physical_area_and_match": all(token in graph + header for token in (
            "2.0 * pi * radius * eligible_length",
            "pi * radius * radius * static_cast<amrex::Real>(eligible_free_caps)",
            "state.multiplier = state.initial_full_area /",
            "derived initial area-match fields differ from the hash-bound case configuration",
            "multiplier * record.tip_010_area",
        )),
        "canonical_graph_validates_topology": all(token in graph for token in (
            "missing or duplicate reciprocal bond",
            "duplicate or disagreeing bond record",
            "invalid endpoint site", "inconsistent particle identity",
            "nonpositive fungal geometry or owning volume", "std::sort",
        )),
        "O02_and_O07_placement": (
            transfer.index("prepareTerminalAreas(*pc)")
            < transfer.index("requestedAmount(")
            and evolve.index("pc->split_particles(time)")
            < evolve.index("applyBondedDTransport(*pc, dt)")
            < evolve.index("pc->EvaluateTipFusion")
        ),
        "legacy_bonded_D_coefficient_stays_zero": (
            'requiredZero(chemistry, "mass_transfer_P")' in uptake
            and "evaluateExchange(" not in graph
            and "mass_transfer_P" not in graph
        ),
        "integrated_P12_P13_P14_fail_closed": all(token in transfer for token in (
            "P15 Stage 0 requires P12 uptake, P13 reaction/growth, and P14 export enabled together",
            "p12_enabled && p13_enabled && !p15_enabled",
        )) and all("integrated_p15" in source for source in
                   (uptake, reactions, export)),
        "checkpoint_schema_v8_and_p15_state": (
            'version_line = "Checkpoint version: 8"' in checkpoint_h
            and "BMX_SCHEMA_V8_BEGIN" in checkpoint
            and "BMX_SCHEMA_V8_END" in checkpoint
            and all(token in checkpoint for token in checkpoint_tokens)
        ),
        "outcome_gate_requires_independent_hash_bound_PASS": all(
            token in binding_source for token in (
                "result.qualification_outcomes_enabled &&",
                'result.independent_review_status != "PASS"',
                "!hexadecimalHash(result.independent_review_sha256, 64)",
                "!hexadecimalHash(result.reviewed_source_commit, 40)",
                "qualification outcomes remain prohibited pending a hash-bound independent PASS review",
            )
        ),
        "short_runtime_never_crosses_outcome_gate": all(token in runtime for token in (
            '"p15.qualification_outcomes_enabled": "1" if outcomes else "0"',
            '"independent_review_gate_crossed": False',
            '"qualification_outcomes_executed": False',
            '"outcome_hours": 0',
        )),
        "checkpoint_mutation_and_rank_change_covered": all(token in runtime for token in (
            "checkpoint_contract_mutation", "restart_1_to_1",
            "restart_2_to_1", "decomposition_rank2",
        )),
        "analytical_and_refinement_matrix_named": all(token in unit + runtime for token in (
            "unequal-radius unequal-length degree-two reduction is exact",
            "degree-three/four junction elimination matches the common node",
            "two-segment explicit equilibration converges to the exponential solution",
            "D_bond=0 is an exact arithmetic identity", "{2, 4, 8}",
            "for degree in (3, 4)", "junction_elimination_pair_count",
            "proportional_cap_fault", "invalid_geometry",
            "invalid_stored_area",
        )),
        "feature_off_anchors_qualified_C12_and_checks_P15_absent": (
            "C12_EXE_SHA" in feature_off
            and "910425149ee025d4701d8a42525e3c3ffdc03489284e3b537afadf0945633540"
            in feature_off
            and 'line.startswith("P15_")' in feature_off
            and '"semantic_trajectory_identical"' in feature_off
        ),
        "seed_parser_accepts_exact_uint64_without_truncation": all(
            token in seed_parser for token in (
                "std::stoull", "amrex::ULong", "outside the uint64 range",
                "per-rank stream offset overflows uint64",
            )
        ),
        "prospective_contract_still_pending_review": (
            numerical["review_gate"]["current_status"] == "PENDING"
            and numerical["review_gate"][
                "independent_numerical_review_required_before_any_216h_outcome"
            ] is True
            and numerical["frozen_before_any_216h_qualification_outcome"] is True
            and numerical["outcomes_seen_before_freeze"] is False
        ),
        "terminal_contract_refinement_bound": (
            terminal["classification"] ==
            "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE"
            and terminal["representation_refinement"]["subdivisions"] == [2, 4, 8]
        ),
    }

    report = {
        "artifact_type": "C13_P15_STAGE0_STATIC_QUALIFICATION",
        "stage": "C13/P15 Stage 0",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "classification": "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE",
        "stage_base": STAGE_BASE,
        "changed_paths": changed,
        "out_of_scope_paths": out_of_scope,
        "excluded_untracked_workspace_artifacts": workspace_artifacts,
        "checks": checks,
        "contract_hash_checks": contract_hash_checks,
        "hashes": {
            "kernel": sha256(root / "src/chemistry/bmx_chem_K.H"),
            "global_order": sha256(root / "contracts/p10/OPERATOR_ORDER_V1.json"),
            **{name: sha256(root / path)
               for name, (path, _) in CONTRACT_HASHES.items()},
        },
        "execution_boundary": {
            "short_engineering_fixtures": "AUTHORIZED",
            "216h_qualification_outcomes": "PROHIBITED_PENDING_INDEPENDENT_REVIEW",
            "P15_scientific_outcomes": "PROHIBITED_UNTIL_STAGE0_PASS",
        },
        "external_resources": "none",
        "external_spend_usd": 0,
        "claim_boundary": (
            "Static C13 Stage 0 RG-SW engineering evidence only; not an "
            "independent review, mentor approval, calibration, predictive "
            "validation, 216-hour outcome, or P15 science."
        ),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "checks": checks,
        "out_of_scope": out_of_scope,
    }, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
