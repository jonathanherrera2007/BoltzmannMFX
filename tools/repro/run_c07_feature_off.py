#!/usr/bin/env python3
"""Compare C07 feature-off execution with the frozen P07 reference.

The authoritative C03 normalizer is reused unchanged.  As in the reviewed C04
comparator, only the unavoidable ``BMX git hash:`` provenance line is removed
after normalization, and that removal is reported explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_baseline import diff_count, normalize, read_text  # noqa: E402


RE_BUILD_ID = re.compile(r"BMX git hash:")


def comparable(path: Path) -> str:
    return "\n".join(
        line for line in normalize(read_text(path)).splitlines()
        if not RE_BUILD_ID.search(line)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p07-exe", type=Path, required=True)
    parser.add_argument("--c07-exe", type=Path, required=True)
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--mpiexec", type=Path, required=True)
    args = parser.parse_args()

    p07_exe = args.p07_exe.resolve()
    c07_exe = args.c07_exe.resolve()
    case_dir = args.case_dir.resolve()
    run_root = args.run_root.resolve()
    mpiexec = args.mpiexec.resolve()
    for path in (p07_exe, c07_exe, mpiexec,
                 case_dir / "input_fungi", case_dir / "fungi_init_cfg.dat"):
        if not path.exists():
            raise FileNotFoundError(path)

    fixtures = [
        {"id": "N2_init_only", "args": ["bmx.max_step=0"], "ranks": 1},
        {"id": "N1_no_growth", "args": ["bmx.max_step=20", "chem_species.kv=0.0"], "ranks": 1},
        {"id": "N3_no_growth_2rank", "args": ["bmx.max_step=20", "chem_species.kv=0.0"], "ranks": 2},
    ]

    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True)

    rows = []
    for fixture in fixtures:
        logs = {}
        exits = {}
        for label, exe in (("p07", p07_exe), ("c07", c07_exe)):
            work = run_root / fixture["id"] / label
            work.mkdir(parents=True)
            shutil.copy2(case_dir / "input_fungi", work / "input_fungi")
            shutil.copy2(case_dir / "fungi_init_cfg.dat", work / "fungi_init_cfg.dat")
            model_args = ["input_fungi", *fixture["args"],
                          "amr.plot_int=-1", "amr.check_int=-1"]
            command = ([str(mpiexec), "-n", str(fixture["ranks"]), str(exe), *model_args]
                       if fixture["ranks"] > 1 else [str(exe), *model_args])
            proc = subprocess.run(command, cwd=work, capture_output=True,
                                  timeout=180)
            log = work / "stdout.log"
            log.write_bytes(proc.stdout + proc.stderr)
            logs[label] = log
            exits[label] = proc.returncode

        p07 = comparable(logs["p07"])
        c07 = comparable(logs["c07"])
        same = p07 == c07
        clean = exits["p07"] == 0 and exits["c07"] == 0
        rows.append({
            "id": fixture["id"],
            "arguments": fixture["args"],
            "ranks": fixture["ranks"],
            "p07_exit": exits["p07"],
            "c07_exit": exits["c07"],
            "normalized_equal": same,
            "differing_lines": diff_count(p07, c07),
            "p07_normalized_sha256": hashlib.sha256(p07.encode()).hexdigest(),
            "c07_normalized_sha256": hashlib.sha256(c07.encode()).hexdigest(),
            "status": "PASS" if clean and same else "FAIL",
            "p07_log": str(logs["p07"]),
            "c07_log": str(logs["c07"]),
        })
        print(f"{fixture['id']:24s} {'PASS' if clean and same else 'FAIL'} "
              f"diff_lines={diff_count(p07, c07)}")

    report = {
        "stage": "C07",
        "test": "feature_off_p07_frozen_comparator",
        "method": "C03 normalize() unchanged, followed only by the C04-reviewed build identity removal",
        "build_identity_line_stripped": "BMX git hash: (different commits necessarily report different provenance)",
        "p07_executable": str(p07_exe),
        "c07_executable": str(c07_exe),
        "fixtures": rows,
        "passed": all(row["status"] == "PASS" for row in rows),
        "claim_boundary": "engineering feature-off regression only; not scientific validation",
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(rendered, encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
