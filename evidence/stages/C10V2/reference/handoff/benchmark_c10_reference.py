#!/usr/bin/env python3
"""Benchmark the frozen C10/P12 selected production configuration."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import sys
from pathlib import Path


EXPECTED_SOURCE_COMMIT = "0f38760b4daba3acbfd4b658c9ac522523b5c69b"
ARMS = {"low": 1.61e-8, "high": 4.52e-8}
JMAX = 2.95949412514e-12
N_CELL = 8
DT_S = 1800.0
STEPS = 96
PLOT_INTERVAL = 1
CHECKPOINT_STEP = 48
CONFIGURATIONS = 151
CONCURRENT_INSTANCES = 9


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--mpiexec", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    source = args.source.resolve()
    exe = args.exe.resolve()
    mpiexec = args.mpiexec.resolve()
    root = args.run_root.resolve()
    if args.repeats < 1:
        raise SystemExit("repeats must be positive")
    if root.exists():
        raise SystemExit(f"benchmark run root already exists: {root}")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source, text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=source, text=True
    ).strip()
    if head != EXPECTED_SOURCE_COMMIT or dirty:
        raise SystemExit(
            f"benchmark source identity failed: head={head}, dirty={bool(dirty)}"
        )

    sys.path.insert(0, str(source / "tools/repro"))
    from run_c10_p12_48h import run_case, set_value  # pylint: disable=import-error
    from run_c10_p12_v2_48h import summarize_run  # pylint: disable=import-error
    from run_c10_uptake_runtime import uptake_input  # pylint: disable=import-error

    root.mkdir(parents=True)
    fixture = root / "fixture"
    fixture.mkdir()
    network = source / "contracts/p12/network/P12_FIXED_NETWORK_V1.dat"
    shutil.copy2(network, fixture / network.name)
    base = (source / "exec/fungi/input_fungi").read_text(encoding="utf-8")

    arms: dict[str, dict] = {}
    all_pass = True
    for arm, concentration in ARMS.items():
        input_text = uptake_input(
            base,
            mesh_d=concentration,
            j_max=JMAX,
            d_diff=5.0e-6,
            dt=DT_S,
            ncell=N_CELL,
        )
        input_text = set_value(input_text, "amr.plt_D", "0")
        input_text = set_value(input_text, "amr.plt_grad_X", "0")
        wall_seconds = []
        summaries = []
        for repeat in range(1, args.repeats + 1):
            run = run_case(
                exe,
                fixture,
                root / arm / f"repeat_{repeat:02d}",
                input_text,
                steps=STEPS,
                plot_int=PLOT_INTERVAL,
                check_int=CHECKPOINT_STEP,
                ranks=1,
                mpiexec=mpiexec,
            )
            summary = summarize_run(
                run,
                expected_rows=STEPS,
                expected_total_updates=STEPS,
            )
            summaries.append(summary)
            wall_seconds.append(run["wall_s"])
            all_pass = all_pass and summary["status"] == "PASS"
        arms[arm] = {
            "status": "PASS" if all(
                item["status"] == "PASS" for item in summaries
            ) else "FAIL",
            "wall_s": wall_seconds,
            "minimum_wall_s": min(wall_seconds),
            "maximum_wall_s": max(wall_seconds),
            "mean_wall_s": statistics.fmean(wall_seconds),
            "median_wall_s": statistics.median(wall_seconds),
            "repeat_summaries": summaries,
        }

    arm_medians = [arms[name]["median_wall_s"] for name in sorted(arms)]
    lower = min(arm_medians)
    upper = max(arm_medians)
    representative = statistics.fmean(arm_medians)
    projections = {}
    for replicate_count in (5, 10, 20):
        total_runs = CONFIGURATIONS * replicate_count
        waves = math.ceil(total_runs / CONCURRENT_INSTANCES)
        projections[f"n={replicate_count}"] = {
            "total_runs": total_runs,
            "nine_instance_waves": waves,
            "aggregate_instance_hours_representative":
                total_runs * representative / 3600.0,
            "nine_instance_elapsed_hours_representative":
                waves * representative / 3600.0,
            "nine_instance_elapsed_hours_arm_median_range": [
                waves * lower / 3600.0,
                waves * upper / 3600.0,
            ],
        }

    report = {
        "artifact_type": "C10_REFERENCE_HOST_TIMING_AND_PROJECTIONS",
        "status": "PASS" if all_pass else "FAIL",
        "claim_boundary": (
            "Reference-host timing of the frozen C10/P12 uptake-only selected "
            "configuration; not a P15 science-campaign runtime guarantee."
        ),
        "source_commit": head,
        "executable_sha256": sha256(exe),
        "benchmark_configuration": {
            "selected_grid": "L0",
            "n_cell": [8, 8, 4],
            "dt_s": DT_S,
            "duration_s": 172800,
            "updates": STEPS,
            "mpi_ranks": 1,
            "plot_interval_updates": PLOT_INTERVAL,
            "checkpoint_step": CHECKPOINT_STEP,
            "repeats_per_arm": args.repeats,
        },
        "arms": arms,
        "projection_basis": {
            "configurations": CONFIGURATIONS,
            "concurrent_n2_standard_8_instances": CONCURRENT_INSTANCES,
            "scheduling_model": (
                "one run per instance at a time; perfect wave scheduling; "
                "excludes queue, provisioning, transfer, and retry overhead"
            ),
            "representative_wall_s": representative,
            "conservative_wall_s": upper,
        },
        "projections": projections,
    }
    output = args.json_out.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "status": report["status"],
        "representative_wall_s": representative,
        "conservative_wall_s": upper,
        "json_out": str(output),
    }, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
