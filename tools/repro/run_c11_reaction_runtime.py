#!/usr/bin/env python3
"""C11/P13 native reaction, Liebig growth, MPI, and restart qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path


CONTRACT_ID = "bmx-p13-reaction-liebig-v1"
CONTRACT_SHA = "06f575a09b56178d74f809003fec532d6d3d509b972e62c29da21754cab0d26d"
FIT_ID = "bmx-p13-o02-fit-v1"
FIT_SHA = "ea6e8dc2ca3f69fe2f366801c9df8ec9832b58f399d605c88d91527ff2098407"
KERNEL_SHA = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
LEDGER_RE = re.compile(
    r"^P10_LEDGER boundary=(\S+) reference_bound=\d+ reference_total=(\S+) "
    r"mesh_D=(\S+) mesh_F=(\S+) internal_D=(\S+) "
    r"internal_E=(\S+) internal_F=(\S+) accounted=(\S+) "
    r"residual=(\S+) tolerance=(\S+)$",
    re.MULTILINE,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def set_value(source: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=.*$", re.MULTILINE)
    replacement = f"{key} = {value}"
    if not pattern.search(source):
        return source.rstrip() + "\n" + replacement + "\n"
    return pattern.sub(replacement, source, count=1)


def p13_input(
    base: str,
    *,
    reactions: bool,
    growth: bool,
    k_de: float,
    k_ed: float,
    b_concentration: float,
    d_concentration: float,
    e_concentration: float,
    q_p: float = 0.0,
    growth_ratio: float = 0.0,
    dt: float = 100.0,
) -> str:
    values = {
        "bmx.fixed_dt": f"{dt:.17g}",
        "bmx.substeps": "1",
        "amr.max_level": "0",
        "geometry.is_periodic": "0 1 0",
        "geometry.prob_lo": "0.0 0.0 0.0",
        "geometry.prob_hi": "0.2 0.2 0.1",
        "amr.n_cell": "8 8 4",
        "amr.blocking_factor": "2",
        "amr.max_grid_size_x": "8",
        "amr.max_grid_size_y": "8",
        "amr.max_grid_size_z": "4",
        "bmx.tag_region": "false",
        "amr.regrid_int": "-1",
        "fluid.surface_location": "0.1",
        "fluid.chem_species": "A B C D F P_D P_F",
        "fluid.chem_species_diff": "0 0 0 0 0 0 0",
        "fluid.init_conc_species":
            f"0 {b_concentration:.17g} 0 0 0 0 0",
        "chem_species.initial_particle_P":
            f"{d_concentration:.17g} {e_concentration:.17g} 0",
        "chem_species.k1": "0", "chem_species.kr1": "0",
        "chem_species.k2": "0", "chem_species.kr2": "0",
        "chem_species.k3": "0", "chem_species.kr3": "0",
        "chem_species.k4": "0", "chem_species.kr4": "0",
        "chem_species.k5": "0", "chem_species.kr5": "0",
        "chem_species.k6": "0", "chem_species.kr6": "0",
        "chem_species.k7": "0", "chem_species.kr7": "0",
        "chem_species.kP": "0", "chem_species.krP": "0",
        "chem_species.kg": "1.0e-5", "chem_species.kv": "0.1",
        "chem_species.kb": "0", "chem_species.kbv": "0",
        "chem_species.mass_transfer_A": "0",
        "chem_species.mass_transfer_B": "0",
        "chem_species.mass_transfer_C": "0",
        "chem_species.mass_transfer_P": "0",
        "chem_species.p_growth_limit": "0",
        "chem_species.qP": "0",
        "chem_species.branching_probability": "0",
        "chem_species.splitting_probability": "0",
        "chem_species.fusion_probability": "0",
        "chem_species.max_seg_radius": "2.5e-4",
        "chem_species.max_seg_length": "3.5e-3",
        "chem_species.seg_split_length": "3.5e-3",
        "chem_species.rg_frequency": "1000000",
        "cell_force.gravity": "0",
        "cell_force.fluctuation_scale": "0",
        "p11_geometry.enabled": "0",
        "p12.enabled": "0",
        "p13.enabled": "1",
        "p13.contract": CONTRACT_ID,
        "p13.contract_sha256": CONTRACT_SHA,
        "p13.operator_fit": FIT_ID,
        "p13.operator_fit_sha256": FIT_SHA,
        "p13.stage": "C11",
        "p13.reactions_enabled": "1" if reactions else "0",
        "p13.growth_enabled": "1" if growth else "0",
        "p13.k_de": f"{k_de:.17g}",
        "p13.k_ed": f"{k_ed:.17g}",
        "p13.q_p": f"{q_p:.17g}",
        "p13.k_gP_over_k_gB": f"{growth_ratio:.17g}",
    }
    result = base
    for key, value in values.items():
        result = set_value(result, key, value)
    return result


def run_case(
    exe: Path,
    run_dir: Path,
    input_text: str,
    particle_text: str,
    *,
    steps: int,
    ranks: int,
    mpiexec: Path,
    check_int: int = -1,
    restart: Path | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input_fungi").write_text(input_text, encoding="utf-8")
    (run_dir / "fungi_init_cfg.dat").write_text(particle_text, encoding="utf-8")
    command = [] if ranks == 1 else [str(mpiexec), "-n", str(ranks)]
    command += [
        str(exe), "input_fungi", f"bmx.max_step={steps}",
        "amr.plot_int=-1", f"amr.check_int={check_int}",
        "amr.check_file=chk", "amr.par_ascii_int=1",
        "amr.par_ascii_file=par",
    ]
    if restart is not None:
        command.append(f"amr.restart={restart}")
    completed = subprocess.run(
        command, cwd=run_dir, capture_output=True, text=True, timeout=timeout
    )
    output = completed.stdout + completed.stderr
    (run_dir / "stdout.log").write_text(output, encoding="utf-8")
    (run_dir / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8"
    )
    return completed


def p13_rows(completed: subprocess.CompletedProcess[str]) -> list[dict]:
    output = completed.stdout + completed.stderr
    rows: list[dict] = []
    for line in output.splitlines():
        if not line.startswith("P13_STEP "):
            continue
        row: dict[str, float | int] = {}
        for token in line.split()[1:]:
            key, value = token.split("=", 1)
            row[key] = int(value) if key in {
                "update", "particles", "accepted_events", "roundoff_clamps",
                "cumulative_particles", "cumulative_accepted_events",
                "cumulative_roundoff_clamps",
            } else float(value)
        rows.append(row)
    return rows


def ledger_rows(completed: subprocess.CompletedProcess[str]) -> list[dict]:
    output = completed.stdout + completed.stderr
    return [
        {
            "boundary": match.group(1),
            "reference_total": float(match.group(2)),
            "mesh_d": float(match.group(3)),
            "mesh_f": float(match.group(4)),
            "internal_d": float(match.group(5)),
            "internal_e": float(match.group(6)),
            "internal_f": float(match.group(7)),
            "accounted": float(match.group(8)),
            "residual": float(match.group(9)),
            "tolerance": float(match.group(10)),
        }
        for match in LEDGER_RE.finditer(output)
    ]


def near(first: float, second: float) -> bool:
    return abs(first - second) <= max(
        1.0e-28, 1.0e-10 * (abs(first) + abs(second))
    )


def successful_case(
    completed: subprocess.CompletedProcess[str],
    run_dir: Path,
    *,
    steps: int,
    expect_reaction: bool,
    expect_growth: bool,
) -> dict:
    output = completed.stdout + completed.stderr
    rows = p13_rows(completed)
    ledgers = ledger_rows(completed)
    o10 = [row for row in ledgers if row["boundary"] == "O10_POST_UPDATE_LEDGER"]
    final = rows[-1] if rows else None
    numeric_values = [] if final is None else [
        value for value in final.values() if isinstance(value, float)
    ]
    algebra = bool(final) and near(
        float(final["cumulative_requested_growth"])
        - float(final["cumulative_accepted_growth"]),
        float(final["cumulative_rejected_growth"]),
    ) and near(
        float(final["cumulative_e_debit"]),
        float(final["cumulative_structuralized_p"]),
    )
    implicit_nonmobile_p = None if not o10 else (
        o10[-1]["reference_total"] - o10[-1]["mesh_d"] - o10[-1]["mesh_f"]
        - o10[-1]["internal_d"] - o10[-1]["internal_e"]
        - o10[-1]["internal_f"]
    )
    checks = {
        "exit_zero": completed.returncode == 0,
        "contract_bound": f"contract={CONTRACT_ID}" in output,
        "operator_fit_bound": f"operator_fit={FIT_ID}" in output,
        "global_order_unchanged": "global_order_changed=0" in output,
        "one_record_per_step": len(rows) == steps,
        "o10_record_per_step": len(o10) == steps,
        "expected_particle_evaluation": bool(final) and final["particles"] == (
            1 if expect_reaction or expect_growth else 0
        ),
        "reaction_expectation": bool(final) and (
            float(final["cumulative_reaction_forward"]) > 0.0
            or float(final["cumulative_reaction_reverse"]) > 0.0
        ) == expect_reaction,
        "growth_expectation": bool(final) and (
            float(final["cumulative_accepted_growth"]) > 0.0
        ) == expect_growth,
        "step_algebra": algebra,
        "diagnostics_finite": bool(numeric_values) and all(
            math.isfinite(value) for value in numeric_values
        ),
        "p10_ledgers_within_tolerance": bool(o10) and all(
            abs(row["residual"]) <= row["tolerance"] for row in o10
        ),
        "F_remains_zero": bool(o10) and all(row["internal_f"] == 0.0 for row in o10),
        "structural_ledger_matches_P13": bool(
            final and implicit_nonmobile_p is not None
        ) and near(
            float(implicit_nonmobile_p),
            float(final["cumulative_structuralized_p"]),
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "exit_code": completed.returncode,
        "checks": checks,
        "final": final,
        "last_o10": o10[-1] if o10 else None,
        "log": str(run_dir / "stdout.log"),
    }


def rejected_case(
    completed: subprocess.CompletedProcess[str], run_dir: Path, token: str
) -> dict:
    output = completed.stdout + completed.stderr
    checks = {
        "exit_nonzero": completed.returncode != 0,
        "specific_rejection": token in output,
        "no_P13_step_committed": not p13_rows(completed),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "exit_code": completed.returncode,
        "checks": checks,
        "expected_token": token,
        "log": str(run_dir / "stdout.log"),
    }


def cumulative_equivalent(first: dict | None, second: dict | None) -> bool:
    if not first or not second:
        return False
    keys = (
        "cumulative_reaction_forward", "cumulative_reaction_reverse",
        "cumulative_requested_growth", "cumulative_accepted_growth",
        "cumulative_rejected_growth", "cumulative_b_debit",
        "cumulative_e_debit", "cumulative_structuralized_p",
    )
    count_keys = (
        "update", "cumulative_particles", "cumulative_accepted_events",
        "cumulative_roundoff_clamps",
    )
    return all(near(float(first[key]), float(second[key])) for key in keys) and all(
        first[key] == second[key] for key in count_keys
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--mpiexec", type=Path, required=True)
    args = parser.parse_args()

    exe = args.exe.resolve()
    source = args.source.resolve()
    root = args.run_root.resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    base = (source / "exec/fungi/input_fungi").read_text(encoding="utf-8")
    particle = (source / "contracts/p12/network/P12_FIXED_NETWORK_V1.dat").read_text(
        encoding="utf-8"
    )

    cases: dict[str, dict] = {}
    definitions = [
        ("operators_off", False, False, 0.0, 0.0, 1.0e-3, 2.0e-5, 3.0e-5, 0.0, 0.0, False, False, 1),
        ("reaction_one_way", True, False, 1.0e-5, 0.0, 1.0e-3, 2.0e-5, 0.0, 0.0, 0.0, True, False, 1),
        ("reaction_reversible", True, False, 1.0e-5, 1.0e-5, 1.0e-3, 2.0e-5, 1.0e-5, 0.0, 0.0, True, False, 1),
        ("growth_carbon_limited", False, True, 0.0, 0.0, 1.0e-7, 0.0, 3.0e-3, 3.0e-5, 1.0, False, True, 1),
        ("growth_phosphorus_limited", False, True, 0.0, 0.0, 1.0e-3, 0.0, 3.0e-8, 3.0e-5, 1.0, False, True, 1),
        ("combined_rank1", True, True, 1.0e-5, 0.0, 1.0e-3, 2.0e-5, 3.0e-5, 3.0e-5, 1.0, True, True, 1),
        ("combined_rank2", True, True, 1.0e-5, 0.0, 1.0e-3, 2.0e-5, 3.0e-5, 3.0e-5, 1.0, True, True, 2),
    ]
    for (name, reactions, growth, k_de, k_ed, b, d, e, q_p, ratio,
         expect_reaction, expect_growth, ranks) in definitions:
        text = p13_input(
            base, reactions=reactions, growth=growth, k_de=k_de, k_ed=k_ed,
            b_concentration=b, d_concentration=d, e_concentration=e,
            q_p=q_p, growth_ratio=ratio,
        )
        completed = run_case(
            exe, root / name, text, particle, steps=1, ranks=ranks,
            mpiexec=args.mpiexec,
        )
        cases[name] = successful_case(
            completed, root / name, steps=1,
            expect_reaction=expect_reaction, expect_growth=expect_growth,
        )

    combined = p13_input(
        base, reactions=True, growth=True, k_de=1.0e-5, k_ed=0.0,
        b_concentration=1.0e-3, d_concentration=2.0e-5,
        e_concentration=3.0e-5, q_p=3.0e-5, growth_ratio=1.0,
    )
    continuous = run_case(
        exe, root / "continuous_rank1", combined, particle, steps=4, ranks=1,
        mpiexec=args.mpiexec, check_int=2,
    )
    cases["continuous_rank1"] = successful_case(
        continuous, root / "continuous_rank1", steps=4,
        expect_reaction=True, expect_growth=True,
    )
    checkpoint = root / "continuous_rank1" / "chk00002"
    restarted = run_case(
        exe, root / "restart_1_to_1", combined, particle, steps=4, ranks=1,
        mpiexec=args.mpiexec, restart=checkpoint,
    )
    cases["restart_1_to_1"] = successful_case(
        restarted, root / "restart_1_to_1", steps=2,
        expect_reaction=True, expect_growth=True,
    )
    cases["restart_1_to_1"]["checks"]["cumulative_equivalent"] = cumulative_equivalent(
        cases["continuous_rank1"]["final"], cases["restart_1_to_1"]["final"]
    )
    cases["restart_1_to_1"]["status"] = (
        "PASS" if all(cases["restart_1_to_1"]["checks"].values()) else "FAIL"
    )

    continuous_rank2 = run_case(
        exe, root / "continuous_rank2", combined, particle, steps=4, ranks=2,
        mpiexec=args.mpiexec, check_int=2,
    )
    cases["continuous_rank2"] = successful_case(
        continuous_rank2, root / "continuous_rank2", steps=4,
        expect_reaction=True, expect_growth=True,
    )
    checkpoint_rank2 = root / "continuous_rank2" / "chk00002"
    restart_2_to_1 = run_case(
        exe, root / "restart_2_to_1", combined, particle, steps=4, ranks=1,
        mpiexec=args.mpiexec, restart=checkpoint_rank2,
    )
    cases["restart_2_to_1"] = successful_case(
        restart_2_to_1, root / "restart_2_to_1", steps=2,
        expect_reaction=True, expect_growth=True,
    )
    cases["restart_2_to_1"]["checks"]["cumulative_equivalent"] = cumulative_equivalent(
        cases["continuous_rank1"]["final"], cases["restart_2_to_1"]["final"]
    )
    cases["restart_2_to_1"]["status"] = (
        "PASS" if all(cases["restart_2_to_1"]["checks"].values()) else "FAIL"
    )

    mutated = root / "mutated_checkpoint"
    shutil.copytree(checkpoint, mutated)
    header = mutated / "Header"
    header.write_text(
        header.read_text(encoding="utf-8").replace(CONTRACT_SHA, "0" * 64, 1),
        encoding="utf-8",
    )
    mutation = run_case(
        exe, root / "checkpoint_mutation", combined, particle, steps=4, ranks=1,
        mpiexec=args.mpiexec, restart=mutated,
    )
    cases["checkpoint_mutation"] = rejected_case(
        mutation, root / "checkpoint_mutation",
        "P13 contract, O02 fit, or parameter identity mismatch",
    )

    fit_mutated = root / "mutated_fit_checkpoint"
    shutil.copytree(checkpoint, fit_mutated)
    fit_header = fit_mutated / "Header"
    fit_header.write_text(
        fit_header.read_text(encoding="utf-8").replace(FIT_SHA, "1" * 64, 1),
        encoding="utf-8",
    )
    fit_mutation = run_case(
        exe, root / "checkpoint_fit_mutation", combined, particle,
        steps=4, ranks=1, mpiexec=args.mpiexec, restart=fit_mutated,
    )
    cases["checkpoint_fit_mutation"] = rejected_case(
        fit_mutation, root / "checkpoint_fit_mutation",
        "P13 contract, O02 fit, or parameter identity mismatch",
    )

    parameter_mutated = root / "mutated_parameter_checkpoint"
    shutil.copytree(checkpoint, parameter_mutated)
    parameter_header = parameter_mutated / "Header"
    parameter_header.write_text(
        parameter_header.read_text(encoding="utf-8").replace(
            "p13_k_de 1.0000000000000001e-05",
            "p13_k_de 2.0000000000000002e-05",
            1,
        ),
        encoding="utf-8",
    )
    parameter_mutation = run_case(
        exe, root / "checkpoint_parameter_mutation", combined, particle,
        steps=4, ranks=1, mpiexec=args.mpiexec, restart=parameter_mutated,
    )
    cases["checkpoint_parameter_mutation"] = rejected_case(
        parameter_mutation, root / "checkpoint_parameter_mutation",
        "P13 contract, O02 fit, or parameter identity mismatch",
    )

    algebra_mutated = root / "mutated_algebra_checkpoint"
    shutil.copytree(checkpoint, algebra_mutated)
    algebra_header = algebra_mutated / "Header"
    algebra_text = algebra_header.read_text(encoding="utf-8")
    algebra_text = re.sub(
        r"^p13_cumulative_accepted_growth \S+$",
        "p13_cumulative_accepted_growth 0",
        algebra_text,
        count=1,
        flags=re.MULTILINE,
    )
    algebra_header.write_text(algebra_text, encoding="utf-8")
    algebra_mutation = run_case(
        exe, root / "checkpoint_algebra_mutation", combined, particle,
        steps=4, ranks=1, mpiexec=args.mpiexec, restart=algebra_mutated,
    )
    cases["checkpoint_algebra_mutation"] = rejected_case(
        algebra_mutation, root / "checkpoint_algebra_mutation",
        "P13 checkpoint ledger violates its algebraic identities",
    )

    structural_mutated = root / "mutated_structural_checkpoint"
    shutil.copytree(checkpoint, structural_mutated)
    structural_header = structural_mutated / "Header"
    structural_text = structural_header.read_text(encoding="utf-8")
    structural_text = re.sub(
        r"^ledger_structural_p \S+$",
        "ledger_structural_p 0",
        structural_text,
        count=1,
        flags=re.MULTILINE,
    )
    structural_header.write_text(structural_text, encoding="utf-8")
    structural_mutation = run_case(
        exe, root / "checkpoint_structural_mutation", combined, particle,
        steps=4, ranks=1, mpiexec=args.mpiexec, restart=structural_mutated,
    )
    cases["checkpoint_structural_mutation"] = rejected_case(
        structural_mutation, root / "checkpoint_structural_mutation",
        "P13 structuralized ledger differs from global structural P",
    )

    invalid_rate = set_value(combined, "p13.k_de", "2.0e-5")
    invalid = run_case(
        exe, root / "invalid_rate", invalid_rate, particle, steps=1, ranks=1,
        mpiexec=args.mpiexec,
    )
    cases["invalid_rate"] = rejected_case(
        invalid, root / "invalid_rate",
        "P13 D/E rates are outside the adopted sensitivity set",
    )

    legacy = set_value(combined, "chem_species.kP", "1.0e-9")
    legacy_run = run_case(
        exe, root / "legacy_operator_nonzero", legacy, particle, steps=1, ranks=1,
        mpiexec=args.mpiexec,
    )
    cases["legacy_operator_nonzero"] = rejected_case(
        legacy_run, root / "legacy_operator_nonzero",
        "enabled P09 plumbing requires chem_species.kP",
    )

    combined_rank1 = cases["combined_rank1"]["final"]
    combined_rank2 = cases["combined_rank2"]["final"]
    mpi_one_step = cumulative_equivalent(combined_rank1, combined_rank2)
    mpi_four_step = cumulative_equivalent(
        cases["continuous_rank1"]["final"], cases["continuous_rank2"]["final"]
    )
    overall = (
        all(case["status"] == "PASS" for case in cases.values())
        and mpi_one_step and mpi_four_step
    )
    record = {
        "artifact_type": "C11_P13_NATIVE_RUNTIME",
        "stage": "C11/P13",
        "status": "PASS" if overall else "FAIL",
        "cases": cases,
        "mpi_one_step_equivalent": mpi_one_step,
        "mpi_four_step_equivalent": mpi_four_step,
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "contract": {"id": CONTRACT_ID, "sha256": CONTRACT_SHA},
        "operator_fit": {"id": FIT_ID, "sha256": FIT_SHA},
        "frozen_kernel_sha256": sha256(source / "src/chemistry/bmx_chem_K.H"),
        "frozen_kernel_expected_sha256": KERNEL_SHA,
        "global_order_changed": False,
        "external_resources": "none",
        "external_spend_usd": 0,
        "claim_boundary": (
            "Windows CPU native software/numerical evidence under a provisional "
            "user-adopted contract; not mentor approval, biological calibration, "
            "predictive validity, or C12+ evidence."
        ),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": record["status"],
        "mpi_one_step_equivalent": mpi_one_step,
        "mpi_four_step_equivalent": mpi_four_step,
        "cases": {name: row["status"] for name, row in cases.items()},
    }, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
