#!/usr/bin/env python3
"""Run the independently approved C10/P12 V2 numerical qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from run_c08_checkpoint_tests import compare_particle_ascii
from run_c10_p12_48h import extract_field, relative_l1, run_case, set_value
from run_c10_uptake_runtime import (
    CONTRACT_ID,
    CONTRACT_SHA,
    NUMERICAL_CONTRACT_ID,
    NUMERICAL_CONTRACT_SHA,
    ledger_rows,
    sha256,
    uptake_input,
    uptake_rows,
)


LEVELS = (
    ("L0", 8, 1800.0, 96),
    ("L1", 16, 225.0, 768),
    ("L2", 32, 28.125, 6144),
)
ARMS = {"low": 1.61e-8, "high": 4.52e-8}
OBSERVATIONS = (0, 1800, 3600, 7200, 14400, 28800, 43200,
                86400, 129600, 172800)
JMAX = 2.95949412514e-12
KM = 1.00084710414e-9
UPTAKE_LIMIT = 0.02
PROFILE_LIMIT = 0.05
ETA_LIMIT = 0.25
FLOAT_COMPARATOR = 1.0e-12
SCALE_LIMIT = 1.0 - 64.0 * math.ulp(1.0)
V1_SHA = "dc5af4ff51cf077e9d494ae7d87c7d0a01ec51887101bd63764b0abc4460ce0e"
EXPECTED_NUMERICAL_CONTRACT_SHA = (
    "43d64a8f4ec6c8c00379fc3d9605441cb900479fcdd8db9e78e6fc1edd28f81f"
)
PRESERVED_EVIDENCE = {
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


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_value(source: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=source, text=True
    ).strip()


def validate_prerequisites(source: Path, review_path: Path) -> dict:
    if NUMERICAL_CONTRACT_SHA != EXPECTED_NUMERICAL_CONTRACT_SHA:
        raise SystemExit(
            "V2 outcome execution refused: runner numerical binding mismatch"
        )
    contract_path = source / "contracts/p12/NUMERICAL_PREREGISTRATION_V2.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    actual_contract_sha = sha256(contract_path)
    if actual_contract_sha != NUMERICAL_CONTRACT_SHA:
        raise SystemExit(
            "V2 outcome execution refused: numerical contract SHA-256 mismatch"
        )
    if contract["contract_id"] != NUMERICAL_CONTRACT_ID:
        raise SystemExit(
            "V2 outcome execution refused: numerical contract ID mismatch"
        )
    if sha256(source / "contracts/p12/NUMERICAL_PREREGISTRATION_V1.json") != V1_SHA:
        raise SystemExit(
            "V2 outcome execution refused: failed V1 preregistration changed"
        )
    changed_evidence = [
        path for path, expected in PRESERVED_EVIDENCE.items()
        if sha256(source / path) != expected
    ]
    if changed_evidence:
        raise SystemExit(
            "V2 outcome execution refused: failed V1 evidence changed: "
            + ", ".join(changed_evidence)
        )
    head = git_value(source, "rev-parse", "HEAD")
    tree = git_value(source, "rev-parse", "HEAD^{tree}")
    dirty = bool(git_value(source, "status", "--porcelain"))
    if dirty:
        raise SystemExit(
            "V2 outcome execution refused: source worktree is not clean"
        )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    confirmations = review.get("confirmations", {})
    checks = {
        "status_pass": review.get("status") == "PASS",
        "contract_id_exact":
            review.get("reviewed_contract_id") == NUMERICAL_CONTRACT_ID,
        "contract_sha256_exact":
            review.get("reviewed_contract_sha256") == NUMERICAL_CONTRACT_SHA,
        "source_commit_exact": review.get("reviewed_source_commit") == head,
        "reviewer_identified": bool(review.get("reviewer_identity")),
        "reviewer_independent":
            review.get("reviewer_is_implementation_writer") is False,
        "read_only_or_detached":
            review.get("read_only_worktree_or_detached_commit") is True,
        "all_confirmations_pass": bool(confirmations) and
            all(value is True for value in confirmations.values()),
        "outcome_execution_authorized":
            review.get("outcome_execution_authorized") is True,
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise SystemExit(
            "V2 outcome execution refused: independent review gate failed: "
            + ", ".join(failed)
        )
    return {
        "contract": contract,
        "review": review,
        "review_sha256": sha256(review_path),
        "checks": checks,
        "source_head": head,
        "source_tree": tree,
    }


def finite_row(row: dict) -> bool:
    return all(
        math.isfinite(value)
        for key, value in row.items()
        if key not in {
            "update", "zero_inventory_positive_request",
            "run_positive_request_updates",
            "run_zero_inventory_positive_request_updates",
        }
    )


def summarize_run(run: dict, *, expected_rows: int,
                  expected_total_updates: int,
                  require_all_observations: bool = False,
                  fields: dict[int, dict] | None = None) -> dict:
    uptake = run["uptake"]
    o01 = [row for row in run["ledgers"]
           if row["boundary"] == "O01_PRE_UPDATE_LEDGER"]
    o10 = [row for row in run["ledgers"]
           if row["boundary"] == "O10_POST_UPDATE_LEDGER"]
    checkpoint_ledgers = [row for row in run["ledgers"]
                          if row["boundary"] == "CHECKPOINT_WRITE"]
    last = uptake[-1] if uptake else None
    positive = [row for row in uptake if row["requested"] > 0.0]
    rejection_tolerance = (
        max(1.0e-28, 64.0 * math.ulp(1.0) * last["cum_requested"])
        if last else math.nan
    )
    extrema_consistent = bool(last and positive) and (
        last["update"] == expected_total_updates
        and last["run_min_scale"] <= min(row["min_scale"] for row in positive)
        and last["run_max_eta"] >= max(row["max_eta"] for row in positive)
        and len(positive) <= last["run_positive_request_updates"] <=
            expected_total_updates
        and last["run_zero_inventory_positive_request_updates"] >=
            sum(row["zero_inventory_positive_request"] for row in positive)
    )
    output = run["completed"].stdout + run["completed"].stderr
    checks = {
        "exit_zero": run["completed"].returncode == 0,
        "all_uptake_rows": len(uptake) == expected_rows,
        "all_o01_ledgers": len(o01) == expected_rows,
        "all_o10_ledgers": len(o10) == expected_rows,
        "positive_uptake_activity": bool(last) and
            last["cum_accepted"] > 0.0 and
            last["run_positive_request_updates"] > 0,
        "finite_diagnostics": bool(uptake) and all(finite_row(row) for row in uptake),
        "all_recorded_boundary_conservation": bool(run["ledgers"]) and all(
            abs(row["residual"]) <= row["tolerance"]
            for row in run["ledgers"]
        ),
        "internal_e_f_zero": bool(run["ledgers"]) and all(
            row["internal_e"] == 0.0 and row["internal_f"] == 0.0
            for row in run["ledgers"]
        ),
        "explicit_inactive_ledgers_zero": output.count(
            "E=0 F=0 structural=0 export=0 reward=0 growth=0"
        ) == expected_rows,
        "trajectory_extrema_consistent": extrema_consistent,
        "eta_headroom": bool(last) and last["run_max_eta"] <= ETA_LIMIT,
        "scale_never_clipped": bool(last) and
            last["run_min_scale"] >= SCALE_LIMIT,
        "zero_inventory_positive_request_absent": bool(last) and
            last["run_zero_inventory_positive_request_updates"] == 0,
        "cumulative_rejection_roundoff_only": bool(last) and
            last["cum_rejected"] <= rejection_tolerance,
    }
    if require_all_observations:
        checks["checkpoint_ledgers_present"] = bool(checkpoint_ledgers)
        checks["all_observations"] = bool(fields) and tuple(fields) == OBSERVATIONS
        checks["field_positivity"] = bool(fields) and all(
            min(field["values"]) >= 0.0 for field in fields.values()
        )
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "wall_s": run["wall_s"],
        "last_uptake": last,
        "last_o10": o10[-1] if o10 else None,
        "rejection_tolerance_mol": rejection_tolerance,
    }


def same_shape_relative_max(left: dict, right: dict) -> float:
    if left["shape"] != right["shape"] or len(left["values"]) != len(right["values"]):
        return math.inf
    result = 0.0
    for a, b in zip(left["values"], right["values"]):
        scale = max(abs(a), abs(b))
        result = max(result, abs(a-b) / scale if scale else 0.0)
    return result


def last_state_equivalence(reference: dict, candidate: dict,
                           reference_field: dict | None,
                           candidate_field: dict | None) -> dict:
    lhs = reference["uptake"][-1] if reference["uptake"] else None
    rhs = candidate["uptake"][-1] if candidate["uptake"] else None
    keys = (
        "cum_requested", "cum_accepted", "cum_rejected", "cum_area_time",
        "run_min_scale", "run_max_eta",
        "run_positive_request_updates",
        "run_zero_inventory_positive_request_updates",
    )
    metrics = bool(lhs and rhs) and all(
        lhs[key] == rhs[key] if isinstance(lhs[key], int)
        else abs(lhs[key]-rhs[key]) <= FLOAT_COMPARATOR *
             max(abs(lhs[key]), abs(rhs[key]), 1.0e-300)
        for key in keys
    )
    field_relative = (
        same_shape_relative_max(reference_field, candidate_field)
        if reference_field and candidate_field else math.inf
    )
    return {
        "uptake_ledger_equivalent": metrics,
        "field_max_relative_difference": field_relative,
        "field_equivalent": field_relative <= FLOAT_COMPARATOR,
    }


def fields_for_observations(extractor: Path, run_dir: Path, *,
                            ncell: int, dt: float,
                            initial_concentration: float) -> dict[int, dict]:
    fields: dict[int, dict] = {}
    for observation in OBSERVATIONS[1:]:
        step = int(round(observation / dt))
        destination = run_dir / f"field_{step:05d}.txt"
        fields[observation] = extract_field(
            extractor, run_dir / f"plt{step:05d}", destination
        )
    first = fields[OBSERVATIONS[1]]
    fields[0] = {
        "shape": first["shape"],
        "time": 0.0,
        "values": [initial_concentration] * len(first["values"]),
    }
    return dict(sorted(fields.items()))


def final_field(extractor: Path, run_dir: Path, steps: int) -> dict | None:
    plot = run_dir / f"plt{steps:05d}"
    if not plot.exists():
        return None
    return extract_field(
        extractor, plot, run_dir / f"field_final_{steps:05d}.txt"
    )


def particle_comparison(reference_dir: Path, candidate_dir: Path,
                        steps: int) -> dict:
    left = reference_dir / f"par{steps:05d}"
    right = candidate_dir / f"par{steps:05d}"
    if not left.is_file() or not right.is_file():
        return {"status": "FAIL", "reason": "final particle ASCII missing"}
    return compare_particle_ascii(left, right)


def execute_case_group(*, exe: Path, extractor: Path, mpiexec: Path,
                       case_dir: Path, root: Path, text: str,
                       ncell: int, dt: float, steps: int,
                       concentration: float) -> dict:
    plot_int = int(round(1800.0 / dt))
    checkpoint_step = int(round(86400.0 / dt))
    canonical_dir = root / "canonical_1_rank"
    rerun_dir = root / "deterministic_rerun_1_rank"
    mpi_dir = root / "decomposition_2_rank"
    restart_dir = root / "restart_1_rank"
    mpi_restart_1_dir = root / "restart_2_to_1_rank"

    canonical = run_case(
        exe, case_dir, canonical_dir, text, steps=steps,
        plot_int=plot_int, check_int=checkpoint_step, ranks=1,
        mpiexec=mpiexec,
    )
    canonical_fields = (
        fields_for_observations(
            extractor, canonical_dir, ncell=ncell, dt=dt,
            initial_concentration=concentration,
        ) if canonical["completed"].returncode == 0 else {}
    )
    canonical_summary = summarize_run(
        canonical, expected_rows=steps, expected_total_updates=steps,
        require_all_observations=True,
        fields=canonical_fields,
    )

    rerun = run_case(
        exe, case_dir, rerun_dir, text, steps=steps,
        plot_int=plot_int, check_int=-1, ranks=1, mpiexec=mpiexec,
    )
    mpi = run_case(
        exe, case_dir, mpi_dir, text, steps=steps,
        plot_int=plot_int, check_int=checkpoint_step, ranks=2, mpiexec=mpiexec,
    )
    checkpoint = canonical_dir / f"chk{checkpoint_step:05d}"
    restart = run_case(
        exe, case_dir, restart_dir, text, steps=steps,
        plot_int=plot_int, check_int=-1, ranks=1, mpiexec=mpiexec,
        restart=str(checkpoint.resolve()),
    )
    mpi_checkpoint = mpi_dir / f"chk{checkpoint_step:05d}"
    mpi_restart_1 = run_case(
        exe, case_dir, mpi_restart_1_dir, text, steps=steps,
        plot_int=plot_int, check_int=-1, ranks=1, mpiexec=mpiexec,
        restart=str(mpi_checkpoint.resolve()),
    )

    rerun_summary = summarize_run(
        rerun, expected_rows=steps, expected_total_updates=steps)
    mpi_summary = summarize_run(
        mpi, expected_rows=steps, expected_total_updates=steps)
    restart_summary = summarize_run(
        restart, expected_rows=steps-checkpoint_step,
        expected_total_updates=steps,
    )
    mpi_restart_1_summary = summarize_run(
        mpi_restart_1, expected_rows=steps-checkpoint_step,
        expected_total_updates=steps,
    )
    rerun_fields = (
        fields_for_observations(
            extractor, rerun_dir, ncell=ncell, dt=dt,
            initial_concentration=concentration,
        ) if rerun["completed"].returncode == 0 else {}
    )
    mpi_fields = (
        fields_for_observations(
            extractor, mpi_dir, ncell=ncell, dt=dt,
            initial_concentration=concentration,
        ) if mpi["completed"].returncode == 0 else {}
    )
    canonical_final = canonical_fields.get(OBSERVATIONS[-1])
    rerun_final = final_field(extractor, rerun_dir, steps)
    mpi_final = final_field(extractor, mpi_dir, steps)
    restart_final = final_field(extractor, restart_dir, steps)
    mpi_restart_1_final = final_field(
        extractor, mpi_restart_1_dir, steps)
    rerun_equivalence = last_state_equivalence(
        canonical, rerun, canonical_final, rerun_final
    )
    mpi_equivalence = last_state_equivalence(
        canonical, mpi, canonical_final, mpi_final
    )
    restart_equivalence = last_state_equivalence(
        canonical, restart, canonical_final, restart_final
    )
    mpi_restart_1_equivalence = last_state_equivalence(
        canonical, mpi_restart_1, canonical_final, mpi_restart_1_final
    )
    rerun_particles = particle_comparison(canonical_dir, rerun_dir, steps)
    mpi_particles = particle_comparison(canonical_dir, mpi_dir, steps)
    restart_particles = particle_comparison(canonical_dir, restart_dir, steps)
    mpi_restart_1_particles = particle_comparison(
        canonical_dir, mpi_restart_1_dir, steps)

    deterministic_exact = bool(
        canonical["uptake"] == rerun["uptake"] and
        canonical_fields and tuple(rerun_fields) == OBSERVATIONS and
        all(canonical_fields[time]["values"] == rerun_fields[time]["values"]
            for time in OBSERVATIONS)
    )
    mpi_trajectory_relative = (
        max(same_shape_relative_max(canonical_fields[time], mpi_fields[time])
            for time in OBSERVATIONS)
        if canonical_fields and tuple(mpi_fields) == OBSERVATIONS else math.inf
    )
    equivalence_pass = (
        deterministic_exact and
        rerun_equivalence["uptake_ledger_equivalent"] and
        rerun_equivalence["field_equivalent"] and
        mpi_equivalence["uptake_ledger_equivalent"] and
        mpi_equivalence["field_equivalent"] and
        mpi_trajectory_relative <= FLOAT_COMPARATOR and
        restart_equivalence["uptake_ledger_equivalent"] and
        restart_equivalence["field_equivalent"] and
        mpi_restart_1_equivalence["uptake_ledger_equivalent"] and
        mpi_restart_1_equivalence["field_equivalent"] and
        rerun_particles.get("status") == "PASS" and
        mpi_particles.get("status") == "PASS" and
        restart_particles.get("status") == "PASS"
        and mpi_restart_1_particles.get("status") == "PASS"
    )
    status = "PASS" if (
        canonical_summary["status"] == "PASS" and
        rerun_summary["status"] == "PASS" and
        mpi_summary["status"] == "PASS" and
        restart_summary["status"] == "PASS" and
        mpi_restart_1_summary["status"] == "PASS" and equivalence_pass
    ) else "FAIL"
    return {
        "status": status,
        "configuration_sha256": hash_text(text),
        "canonical": canonical_summary,
        "deterministic_rerun": {
            "summary": rerun_summary,
            "bit_exact_uptake_and_observation_meshes": deterministic_exact,
            "equivalence": rerun_equivalence,
            "particle_comparison": rerun_particles,
        },
        "mpi_decomposition": {
            "summary": mpi_summary,
            "equivalence": mpi_equivalence,
            "trajectory_field_max_relative_difference":
                mpi_trajectory_relative,
            "trajectory_field_equivalent":
                mpi_trajectory_relative <= FLOAT_COMPARATOR,
            "particle_comparison": mpi_particles,
        },
        "checkpoint_restart": {
            "checkpoint_step": checkpoint_step,
            "summary": restart_summary,
            "equivalence": restart_equivalence,
            "particle_comparison": restart_particles,
        },
        "checkpoint_restart_2_to_1": {
            "checkpoint_step": checkpoint_step,
            "summary": mpi_restart_1_summary,
            "equivalence": mpi_restart_1_equivalence,
            "particle_comparison": mpi_restart_1_particles,
        },
        "raw_root": str(root),
        "_fields": canonical_fields,
    }


def comparison(coarse: dict, fine: dict) -> dict:
    profile = {
        str(observation): relative_l1(
            coarse["_fields"][observation], fine["_fields"][observation]
        )
        for observation in OBSERVATIONS
    }
    coarse_uptake = coarse["canonical"]["last_uptake"]["cum_accepted"]
    fine_uptake = fine["canonical"]["last_uptake"]["cum_accepted"]
    uptake_difference = abs(coarse_uptake-fine_uptake) / max(
        abs(fine_uptake), 1.0e-300
    )
    checks = {
        "both_cases_pass": coarse["status"] == "PASS" and fine["status"] == "PASS",
        "uptake_within_2_percent": uptake_difference <= UPTAKE_LIMIT,
        "profile_within_5_percent_every_observation":
            max(profile.values()) <= PROFILE_LIMIT,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "cumulative_uptake_relative_difference": uptake_difference,
        "mesh_profile_l1_relative_by_observation": profile,
        "maximum_mesh_profile_l1_relative": max(profile.values()),
    }


def public_case(case: dict) -> dict:
    return {key: value for key, value in case.items() if key != "_fields"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--mpiexec", type=Path, required=True)
    parser.add_argument("--independent-review", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    source = args.source.resolve()
    exe = args.exe.resolve()
    extractor = args.extractor.resolve()
    mpiexec = args.mpiexec.resolve()
    review_path = args.independent_review.resolve()
    prerequisites = validate_prerequisites(source, review_path)
    for required in (exe, extractor, mpiexec):
        if not required.is_file():
            raise SystemExit(f"required executable not found: {required}")

    root = args.run_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    fixture = root / "fixture"
    fixture.mkdir()
    network = source / "contracts/p12/network/P12_FIXED_NETWORK_V1.dat"
    (fixture / network.name).write_bytes(network.read_bytes())
    base = (source / "exec/fungi/input_fungi").read_text(encoding="utf-8")

    coupled: dict[str, dict] = {}
    for level_id, ncell, dt, steps in LEVELS:
        for arm, concentration in ARMS.items():
            text = uptake_input(
                base, mesh_d=concentration, j_max=JMAX,
                d_diff=5.0e-6, dt=dt, ncell=ncell,
            )
            text = set_value(text, "amr.plt_D", "0")
            text = set_value(text, "amr.plt_grad_X", "0")
            coupled[f"{level_id}_{arm}"] = execute_case_group(
                exe=exe, extractor=extractor, mpiexec=mpiexec,
                case_dir=fixture, root=root/"coupled"/f"{level_id}_{arm}",
                text=text, ncell=ncell, dt=dt, steps=steps,
                concentration=concentration,
            )

    coupled_comparisons = {}
    for arm in ARMS:
        coupled_comparisons[f"L0_vs_L1_{arm}"] = comparison(
            coupled[f"L0_{arm}"], coupled[f"L1_{arm}"]
        )
        coupled_comparisons[f"L1_vs_L2_{arm}"] = comparison(
            coupled[f"L1_{arm}"], coupled[f"L2_{arm}"]
        )
    selected_grid = None
    if all(row["status"] == "PASS" for row in coupled.values()):
        if all(item["status"] == "PASS" for item in coupled_comparisons.values()):
            selected_grid = "L0"
        elif all(
            coupled_comparisons[f"L1_vs_L2_{arm}"]["status"] == "PASS"
            for arm in ARMS
        ):
            selected_grid = "L1"

    temporal: dict[str, dict] = {}
    temporal_comparisons: dict[str, dict] = {}
    selected_dt = None
    if selected_grid is not None:
        level = next(row for row in LEVELS if row[0] == selected_grid)
        _, ncell, base_dt, base_steps = level
        for arm in ARMS:
            temporal[f"T0_{arm}"] = coupled[f"{selected_grid}_{arm}"]
        for temporal_id, divisor in (("T1", 2), ("T2", 4)):
            dt = base_dt/divisor
            steps = base_steps*divisor
            for arm, concentration in ARMS.items():
                text = uptake_input(
                    base, mesh_d=concentration, j_max=JMAX,
                    d_diff=5.0e-6, dt=dt, ncell=ncell,
                )
                text = set_value(text, "amr.plt_D", "0")
                text = set_value(text, "amr.plt_grad_X", "0")
                temporal[f"{temporal_id}_{arm}"] = execute_case_group(
                    exe=exe, extractor=extractor, mpiexec=mpiexec,
                    case_dir=fixture,
                    root=root/"temporal"/f"{temporal_id}_{arm}",
                    text=text, ncell=ncell, dt=dt, steps=steps,
                    concentration=concentration,
                )
        for arm in ARMS:
            temporal_comparisons[f"T0_vs_T1_{arm}"] = comparison(
                temporal[f"T0_{arm}"], temporal[f"T1_{arm}"]
            )
            temporal_comparisons[f"T1_vs_T2_{arm}"] = comparison(
                temporal[f"T1_{arm}"], temporal[f"T2_{arm}"]
            )
        if (all(row["status"] == "PASS" for row in temporal.values()) and
                all(row["status"] == "PASS"
                    for row in temporal_comparisons.values())):
            selected_dt = base_dt

    qualified = selected_grid is not None and selected_dt is not None
    saturation = {
        arm: concentration/(KM+concentration)
        for arm, concentration in ARMS.items()
    }
    report = {
        "artifact_type": "C10_P12_V2_GRID_AND_TIME_QUALIFICATION",
        "stage": "C10/P12",
        "status": "PASS" if qualified else "FAIL",
        "claim_boundary": "Independently prereviewed engineering numerical qualification; not yet reference-host reproduction, final independent acceptance, mentor approval, calibration, predictive validation, or C10 blocker closure.",
        "numerical_contract": {
            "id": NUMERICAL_CONTRACT_ID,
            "sha256": NUMERICAL_CONTRACT_SHA,
        },
        "scientific_uptake_contract": {
            "id": CONTRACT_ID,
            "sha256": CONTRACT_SHA,
        },
        "independent_prerun_review": {
            "path": str(review_path),
            "sha256": prerequisites["review_sha256"],
            "checks": prerequisites["checks"],
        },
        "source": {
            "commit": prerequisites["source_head"],
            "tree": prerequisites["source_tree"],
            "clean_before_run": True,
        },
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "runner_sha256": sha256(Path(__file__).resolve()),
        "case_registry_sha256": sha256(
            source/"contracts/p12/CASE_REGISTRY_V1.json"),
        "fixed_network_sha256": sha256(network),
        "coupled_cases": {key: public_case(value)
                          for key, value in coupled.items()},
        "coupled_comparisons": coupled_comparisons,
        "selected_production_grid": selected_grid,
        "temporal_cases": {key: public_case(value)
                           for key, value in temporal.items()},
        "temporal_comparisons": temporal_comparisons,
        "selected_production_dt_s": selected_dt,
        "saturation_prediction": {
            "fractions": saturation,
            "initial_flux_ratio_high_over_low":
                saturation["high"]/saturation["low"],
            "concentration_ratio_high_over_low": ARMS["high"]/ARMS["low"],
        },
        "raw_run_root": str(root),
        "external_resources": "none",
        "external_spend_usd": 0,
    }
    output = args.json_out.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "selected_grid": selected_grid,
        "selected_dt_s": selected_dt,
        "json_out": str(output),
    }, indent=2))
    return 0 if qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
