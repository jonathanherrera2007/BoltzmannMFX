#!/usr/bin/env python3
"""Run the frozen C10/P12 48 h grid/time study and primary arms."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import time
from pathlib import Path

from run_c10_uptake_runtime import (CONTRACT_SHA, ledger_rows, sha256,
                                     uptake_input, uptake_rows)

LEVELS = (
    ("L0", 8, 1800.0),
    ("L1", 16, 900.0),
    ("L2", 32, 450.0),
)
ARMS = {"low": 1.61e-8, "high": 4.52e-8}
OBSERVATIONS = (0, 1800, 3600, 7200, 14400, 28800, 43200,
                86400, 129600, 172800)
JMAX = 2.95949412514e-12
KM = 1.00084710414e-9


def set_value(source: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=.*$", re.MULTILINE)
    replacement = f"{key} = {value}"
    return (pattern.sub(replacement, source, count=1) if pattern.search(source)
            else source.rstrip() + "\n" + replacement + "\n")


def run_case(exe: Path, case_dir: Path, run_dir: Path, text: str, *,
             steps: int, plot_int: int, check_int: int, ranks: int,
             mpiexec: Path, restart: str | None = None) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input_fungi").write_text(text, encoding="utf-8")
    shutil.copy2(case_dir / "P12_FIXED_NETWORK_V1.dat",
                 run_dir / "fungi_init_cfg.dat")
    command = [] if ranks == 1 else [str(mpiexec), "-n", str(ranks)]
    command += [str(exe), "input_fungi", f"bmx.max_step={steps}",
                f"amr.plot_int={plot_int}", "amr.plot_file=plt",
                f"amr.check_int={check_int}", "amr.check_file=chk",
                f"amr.par_ascii_int={plot_int}", "amr.par_ascii_file=par"]
    if restart: command.append(f"amr.restart={restart}")
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=run_dir, capture_output=True,
                               text=True, timeout=3600)
    wall = time.perf_counter() - started
    output = completed.stdout + completed.stderr
    (run_dir / "stdout.log").write_text(output, encoding="utf-8")
    (run_dir / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8")
    rows = uptake_rows(completed)
    ledgers = ledger_rows(completed)
    return {"completed": completed, "wall_s": wall, "uptake": rows,
            "ledgers": ledgers, "command": command}


def extract_field(tool: Path, plot: Path, destination: Path) -> dict:
    completed = subprocess.run([str(tool), str(plot), "X_P_D", str(destination)],
                               capture_output=True, text=True, timeout=300)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    lines = destination.read_text(encoding="utf-8").splitlines()
    header = lines[0].split()
    shape = tuple(int(value) for value in header[1:4])
    return {"shape": shape, "time": float(header[4]),
            "values": [float(value) for value in lines[1:]]}


def average_fine(fine: dict, coarse_shape: tuple[int, int, int]) -> list[float]:
    fx, fy, fz = fine["shape"]
    cx, cy, cz = coarse_shape
    ratio = fx // cx
    if (fx, fy, fz) != (cx*ratio, cy*ratio, cz*ratio):
        raise ValueError("non-nested fields")
    result = [0.0] * (cx*cy*cz)
    values = fine["values"]
    for k in range(cz):
        for j in range(cy):
            for i in range(cx):
                total = 0.0
                for dk in range(ratio):
                    for dj in range(ratio):
                        for di in range(ratio):
                            fi, fj, fk = i*ratio+di, j*ratio+dj, k*ratio+dk
                            total += values[fi + fx*fj + fx*fy*fk]
                result[i + cx*j + cx*cy*k] = total / ratio**3
    return result


def relative_l1(coarse: dict, fine: dict) -> float:
    averaged = average_fine(fine, coarse["shape"])
    numerator = sum(abs(a-b) for a, b in zip(coarse["values"], averaged))
    denominator = sum(abs(value) for value in averaged)
    return numerator / denominator if denominator else 0.0


def summarize(run: dict, fields: dict[int, dict], steps: int) -> dict:
    uptake = run["uptake"]
    o10 = [row for row in run["ledgers"]
           if row["boundary"] == "O10_POST_UPDATE_LEDGER"]
    checks = {
        "exit_zero": run["completed"].returncode == 0,
        "all_updates_recorded": len(uptake) == steps,
        "all_o10_ledgers_recorded": len(o10) == steps,
        "conservation": bool(o10) and all(
            abs(row["residual"]) <= row["tolerance"] for row in o10),
        "field_positivity": all(min(field["values"]) >= 0.0
                                for field in fields.values()),
        "all_observations_present": tuple(fields) == OBSERVATIONS,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks, "wall_s": run["wall_s"],
            "final": uptake[-1], "final_ledger": o10[-1],
            "field_minimum": min(min(f["values"]) for f in fields.values())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--mpiexec", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    source, root = args.source.resolve(), args.run_root.resolve()
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True)
    base = (source / "exec/fungi/input_fungi").read_text(encoding="utf-8")
    network = source / "contracts/p12/network/P12_FIXED_NETWORK_V1.dat"
    case_dir = root / "fixture"
    case_dir.mkdir()
    shutil.copy2(network, case_dir / network.name)
    results, field_cache = {}, {}
    for level_id, ncell, dt in LEVELS:
        steps, plot_int = int(172800/dt), int(1800/dt)
        for arm, concentration in ARMS.items():
            text = uptake_input(base, mesh_d=concentration, j_max=JMAX,
                                d_diff=5e-6, dt=dt, ncell=ncell)
            text = set_value(text, "amr.plt_D", "0")
            text = set_value(text, "amr.plt_grad_X", "0")
            run_dir = root / f"{level_id}_{arm}"
            run = run_case(args.exe.resolve(), case_dir, run_dir, text,
                           steps=steps, plot_int=plot_int,
                           check_int=steps//2, ranks=1,
                           mpiexec=args.mpiexec.resolve())
            fields = {}
            for observation in OBSERVATIONS[1:]:
                step = int(observation/dt)
                output = run_dir / f"field_{step:05d}.txt"
                fields[observation] = extract_field(
                    args.extractor.resolve(), run_dir / f"plt{step:05d}", output)
            first = fields[OBSERVATIONS[1]]
            fields[0] = {"shape": first["shape"], "time": 0.0,
                         "values": [concentration] * len(first["values"])}
            fields = dict(sorted(fields.items()))
            field_cache[(level_id, arm)] = fields
            results[f"{level_id}_{arm}"] = summarize(run, fields, steps)
    comparisons = {}
    for arm in ARMS:
        for coarse_id, fine_id in (("L0", "L1"), ("L1", "L2")):
            coarse, fine = field_cache[(coarse_id, arm)], field_cache[(fine_id, arm)]
            profile = {str(t): relative_l1(coarse[t], fine[t]) for t in OBSERVATIONS}
            cu = results[f"{coarse_id}_{arm}"]["final"]["cum_accepted"]
            fu = results[f"{fine_id}_{arm}"]["final"]["cum_accepted"]
            uptake_difference = abs(cu-fu) / max(abs(fu), 1e-300)
            comparisons[f"{coarse_id}_vs_{fine_id}_{arm}"] = {
                "profile_l1": profile, "max_profile_l1": max(profile.values()),
                "cumulative_uptake_relative_difference": uptake_difference,
                "status": "PASS" if max(profile.values()) <= 0.05 and
                    uptake_difference <= 0.02 else "FAIL"}
    selected = None
    if all(comparisons[f"L0_vs_L1_{arm}"]["status"] == "PASS" and
           comparisons[f"L1_vs_L2_{arm}"]["status"] == "PASS" for arm in ARMS):
        selected = "L0"
    elif all(comparisons[f"L1_vs_L2_{arm}"]["status"] == "PASS" for arm in ARMS):
        selected = "L1"
    low = results["L2_low"]["final"]["cum_accepted"]
    high = results["L2_high"]["final"]["cum_accepted"]
    saturation = {arm: value/(KM+value) for arm, value in ARMS.items()}
    report = {
        "artifact_type": "C10_P12_48H_GRID_TIME_STUDY",
        "status": "PASS" if selected and all(r["status"] == "PASS" for r in results.values()) else "FAIL",
        "executable": {"path": str(args.exe.resolve()), "sha256": sha256(args.exe.resolve())},
        "contract_sha256": CONTRACT_SHA,
        "runs": results, "comparisons": comparisons,
        "selected_production_level": selected,
        "saturation_prediction": {"fractions": saturation,
            "initial_flux_ratio_high_over_low": saturation["high"]/saturation["low"],
            "concentration_ratio_high_over_low": ARMS["high"]/ARMS["low"]},
        "measured_48h_contrast_at_L2": {"high_over_low_cumulative_uptake": high/low,
            "low_cumulative_uptake_mol": low, "high_cumulative_uptake_mol": high},
        "claim_boundary": "User-authorized engineering outcome; provisional parameters, Windows development host, and no independent numerical/release review."
    }
    args.json_out.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.json_out.resolve().write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "selected": selected,
                      "predicted_initial_ratio": report["saturation_prediction"]["initial_flux_ratio_high_over_low"],
                      "measured_48h_ratio": high/low}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
