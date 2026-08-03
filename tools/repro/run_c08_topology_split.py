#!/usr/bin/env python3
"""Exercise enabled pure-volume growth, split, and D/E/F preservation.

Two one-step runs are identical except for the split threshold.  The control
keeps the initial segment intact; the topology case forces the isolated tip to
split after the same fluid/chemistry update.  Comparing their post-step amount
vectors therefore isolates the topology transform from earlier operators in
the step.  Input values are engineering branch-forcing fixtures, not biological
settings or scientific evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import analyze_p07_geometry as geom


BLOCKS = ("committed", "working", "increment")
STATES = ("P_D", "P_E", "P_F")
COMPONENTS = {"P_D": 5, "P_E": 6, "P_F": 7}
DOUBLE_EPSILON = sys.float_info.epsilon


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_value(source: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=.*$", re.MULTILINE)
    replacement = f"{key} = {value}"
    if not pattern.search(source):
        return source.rstrip() + "\n" + replacement + "\n"
    return pattern.sub(replacement, source, count=1)


def enabled_input(base: str, max_length: str, kv: str = "0.0") -> str:
    result = set_value(base, "fluid.chem_species", "A B C D F P_D P_F")
    result = set_value(
        result,
        "fluid.chem_species_diff",
        "6.0e-10 0.0 6.0e-10 6.0e-10 0.0 0.0 0.0",
    )
    result = set_value(
        result,
        "fluid.init_conc_species",
        "2.0e-5 0.0 2.0e-6 2.0e-5 0.0 0.0 0.0",
    )
    result = set_value(
        result, "chem_species.initial_particle_P", "2.0e-5 3.0e-5 5.0e-5"
    )
    result = set_value(result, "chem_species.kP", "0.0")
    result = set_value(result, "chem_species.krP", "0.0")
    result = set_value(result, "chem_species.mass_transfer_P", "0.0")
    result = set_value(result, "chem_species.p_growth_limit", "0.0")
    result = set_value(result, "chem_species.kv", kv)
    result = set_value(result, "chem_species.branching_probability", "0.0")
    result = set_value(result, "chem_species.splitting_probability", "0.0")
    result = set_value(result, "chem_species.fusion_probability", "0.0")
    result = set_value(result, "chem_species.max_seg_length", max_length)
    result = set_value(result, "chem_species.seg_split_length", "1.5e-3")
    return result


def run_case(
    exe: Path,
    case_dir: Path,
    run_dir: Path,
    input_text: str,
    timeout: int,
    launcher: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_dir.mkdir(parents=True)
    (run_dir / "input_fungi").write_text(input_text, encoding="utf-8")
    shutil.copy2(case_dir / "fungi_init_cfg.dat", run_dir / "fungi_init_cfg.dat")
    command = [
        *(launcher or []),
        str(exe),
        "input_fungi",
        "bmx.max_step=1",
        "amr.plot_int=-1",
        "amr.check_int=-1",
        "amr.par_ascii_int=1",
        "amr.par_ascii_file=par",
    ]
    completed = subprocess.run(
        command,
        cwd=run_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    (run_dir / "stdout.log").write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )
    (run_dir / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8"
    )
    return completed


def component_value(particle: geom.Particle, block: str, component: int) -> float:
    values = getattr(particle, block) if component < 6 else particle.reserved[block]
    return values[component] if component < 6 else values[component - 6]


def amount_vector(particles: dict) -> tuple[dict, dict]:
    totals: dict[str, dict[str, float]] = {}
    l1: dict[str, dict[str, float]] = {}
    for block in BLOCKS:
        totals[block] = {}
        l1[block] = {}
        for state in STATES:
            component = COMPONENTS[state]
            contributions = []
            for particle in particles.values():
                value = component_value(particle, block, component)
                contribution = value if block == "increment" else value * particle.vol
                if not math.isfinite(contribution):
                    raise ValueError(
                        f"nonfinite {block}.{state} contribution for particle {particle.key}"
                    )
                contributions.append(contribution)
            totals[block][state] = math.fsum(contributions)
            l1[block][state] = math.fsum(abs(value) for value in contributions)
    return totals, l1


def compare_amounts(control: dict, split: dict) -> tuple[list[dict], bool]:
    rows = []
    passed = True
    control_totals, control_l1 = amount_vector(control)
    split_totals, split_l1 = amount_vector(split)
    for block in BLOCKS:
        for state in STATES:
            lhs = split_totals[block][state]
            rhs = control_totals[block][state]
            residual = lhs - rhs
            s_l1 = split_l1[block][state] + control_l1[block][state]
            tolerance = 64.0 * DOUBLE_EPSILON * s_l1
            ok = math.isfinite(residual) and abs(residual) <= tolerance
            passed = passed and ok
            rows.append(
                {
                    "field": f"{block}.{state}",
                    "control_amount": rhs,
                    "split_amount": lhs,
                    "residual": residual,
                    "s_l1": s_l1,
                    "tolerance": tolerance,
                    "status": "PASS" if ok else "FAIL",
                }
            )
    return rows, passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--mpiexec", type=Path)
    args = parser.parse_args()

    exe = args.exe.resolve()
    source = args.source.resolve()
    run_root = args.run_root.resolve()
    json_out = args.json_out.resolve()
    case_dir = source / "exec" / "fungi"
    for required in (exe, case_dir / "input_fungi", case_dir / "fungi_init_cfg.dat"):
        if not required.is_file():
            raise SystemExit(f"required file not found: {required}")
    if args.mpiexec is not None and not args.mpiexec.resolve().is_file():
        raise SystemExit(f"mpiexec not found: {args.mpiexec.resolve()}")

    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True)
    base = (case_dir / "input_fungi").read_text(encoding="utf-8")
    control_text = enabled_input(base, "1.0e-2")
    split_text = enabled_input(base, "2.5e-3")
    growth_text = enabled_input(base, "1.0e-2", "40000.0")

    cases = [
        ("control_1_rank", control_text, None, False, False),
        ("growth_1_rank", growth_text, None, False, True),
        ("split_1_rank", split_text, None, True, False),
    ]
    if args.mpiexec is not None:
        cases.append(
            (
                "split_2_rank",
                split_text,
                [str(args.mpiexec.resolve()), "-n", "2"],
                True,
                False,
            )
        )

    runs = {}
    for case_id, text, launcher, expect_split, expect_growth in cases:
        directory = run_root / case_id
        completed = run_case(exe, case_dir, directory, text, args.timeout, launcher)
        dumps = geom.dumps_in(str(directory))
        initial = geom.load_dump(dumps[0]) if dumps else {}
        final = geom.load_dump(dumps[-1]) if dumps else {}
        output = completed.stdout + completed.stderr
        checks = {
            "exit_zero": completed.returncode == 0,
            "two_dumps": len(dumps) == 2,
            "enabled_particle_layout": bool(initial)
            and bool(final)
            and all(p.storage_components == 8 for p in [*initial.values(), *final.values()]),
            "initial_particle_count_one": len(initial) == 1,
            "expected_final_particle_count": len(final) == (2 if expect_split else 1),
            "split_marker_matches_case":
                ("Generating new growth tip" in output) == expect_split,
            "bound_initial_ledger": "P10_LEDGER boundary=O01_PRE_UPDATE_LEDGER"
                in output and "reference_bound=1" in output,
            "post_update_ledger": "P10_LEDGER boundary=O10_POST_UPDATE_LEDGER"
                in output,
        }
        if initial and final and expect_growth:
            checks["owning_volume_changed"] = not math.isclose(
                next(iter(initial.values())).vol,
                next(iter(final.values())).vol,
                rel_tol=0.0,
                abs_tol=0.0,
            )
        runs[case_id] = {
            "exit_code": completed.returncode,
            "dump_count": len(dumps),
            "initial_particle_count": len(initial),
            "final_particle_count": len(final),
            "checks": checks,
            "status": "PASS" if all(checks.values()) else "FAIL",
            "initial": initial,
            "final": final,
            "log": str(directory / "stdout.log"),
        }

    comparisons = {}
    control_final = runs["control_1_rank"]["final"]
    for split_id in (key for key in runs if key.startswith("split_")):
        rows, amount_pass = compare_amounts(control_final, runs[split_id]["final"])
        comparisons[split_id] = {
            "reference": "control_1_rank",
            "frozen_tolerance": "abs(residual) <= 64 * eps_double * S_L1",
            "rows": rows,
            "status": "PASS" if amount_pass else "FAIL",
        }

    growth_rows, growth_amount_pass = compare_amounts(
        runs["growth_1_rank"]["initial"], runs["growth_1_rank"]["final"]
    )
    comparisons["growth_1_rank"] = {
        "reference": "same particle before the enabled pure-volume update",
        "frozen_tolerance": "abs(residual) <= 64 * eps_double * S_L1",
        "rows": growth_rows,
        "status": "PASS" if growth_amount_pass else "FAIL",
    }

    serial_initial_equal = amount_vector(runs["control_1_rank"]["initial"])[0] == \
        amount_vector(runs["split_1_rank"]["initial"])[0]
    run_records = {}
    for key, value in runs.items():
        run_records[key] = {name: field for name, field in value.items()
                            if name not in ("initial", "final")}

    passed = (
        all(run["status"] == "PASS" for run in runs.values())
        and all(item["status"] == "PASS" for item in comparisons.values())
        and serial_initial_equal
    )
    report = {
        "artifact_type": "C08_TOPOLOGY_AMOUNT_TEST",
        "stage": "C08",
        "status": "PASS" if passed else "FAIL",
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "particle_ascii_precision_digits": 15,
        "runs": run_records,
        "initial_amount_vectors_identical": serial_initial_equal,
        "comparisons": comparisons,
        "engineering_overrides": {
            "initial_particle_P": [2.0e-5, 3.0e-5, 5.0e-5],
            "kv": 0.0,
            "pure_volume_kv": 40000.0,
            "kP": 0.0,
            "krP": 0.0,
            "mass_transfer_P": 0.0,
            "p_growth_limit": 0.0,
            "fusion_probability": 0.0,
            "control_max_seg_length": 1.0e-2,
            "split_max_seg_length": 2.5e-3,
        },
        "method": (
            "compare global committed/working concentration-owned D/E/F amounts "
            "and signed extensive transfer amounts for a nonzero owning-volume "
            "change and between a no-split control and an otherwise identical "
            "forced isolated-tip split"
        ),
        "claim_boundary": (
            "engineering pure-volume, topology, bound-ledger, and MPI plumbing test; "
            "does not select biological values or provide independent operator-order review"
        ),
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "runs": {key: value["status"] for key, value in run_records.items()},
        "comparisons": {key: value["status"] for key, value in comparisons.items()},
        "json_out": str(json_out),
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
