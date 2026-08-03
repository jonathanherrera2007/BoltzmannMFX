#!/usr/bin/env python3
"""Runtime C07 enabled/disabled schema and rejection tests.

All generated values are zero-valued plumbing fixtures except the deliberate
nonzero-P_F negative test. They are engineering tests, not biological settings.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def set_value(source: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=.*$", re.MULTILINE)
    replacement = f"{key} = {value}"
    if not pattern.search(source):
        return source.rstrip() + "\n" + replacement + "\n"
    return pattern.sub(replacement, source, count=1)


def make_case(base: str, species: str, diffusion: str, initial: str,
              particle_p: str | None = None) -> str:
    result = set_value(base, "fluid.chem_species", species)
    result = set_value(result, "fluid.chem_species_diff", diffusion)
    result = set_value(result, "fluid.init_conc_species", initial)
    if particle_p is not None:
        result = set_value(result, "chem_species.initial_particle_P", particle_p)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    exe = args.exe.resolve()
    source = args.source.resolve()
    run_root = args.run_root.resolve()
    case_dir = source / "exec/fungi"
    base = (case_dir / "input_fungi").read_text(encoding="utf-8")

    enabled = make_case(
        base,
        "A B C D F P_D P_F",
        "6.0e-10 0.0 6.0e-10 6.0e-10 0.0 0.0 0.0",
        "2.0e-5 0.0 2.0e-6 2.0e-5 0.0 0.0 0.0",
        "0.0 0.0 0.0",
    )
    enabled = set_value(enabled, "chem_species.kP", "0.0")
    enabled = set_value(enabled, "chem_species.krP", "0.0")
    enabled = set_value(enabled, "chem_species.mass_transfer_P", "0.0")
    enabled = set_value(enabled, "chem_species.p_growth_limit", "0.0")

    cases = [
        {"id": "disabled_valid", "text": base, "exit": 0,
         "contains": ["[P]:"],
         "excludes": ["BMX_P09_LAYOUT", "[P_D]:", "[P_E]:", "[P_F]:"]},
        {"id": "enabled_valid", "text": enabled, "exit": 0,
         "contains": ["BMX_P09_LAYOUT mode=enabled", "[P_D]:", "[P_E]:", "[P_F]:"],
         "max_step": 1},
        {"id": "enabled_plot_metadata", "text": enabled, "exit": 0,
         "contains": ["BMX_P09_LAYOUT mode=enabled"], "plot_int": 1,
         "file_contains": {
             "plt00000/Header": ["X_P_D", "X_P_F", "D_P_D", "D_P_F"],
             "plt00000/particles/Header": [
                 "chem_committed_P_D", "chem_committed_P_E", "chem_committed_P_F",
                 "chem_working_P_D", "chem_working_P_E", "chem_working_P_F",
                 "chem_increment_P_D", "chem_increment_P_E", "chem_increment_P_F",
             ],
         },
         "file_excludes": {"plt00000/Header": ["X_P_E", "D_P_E"]}},
        {"id": "reject_simultaneous_P_PD",
         "text": make_case(base, "A B C D F P P_D P_F",
                           "0 0 0 0 0 0 0 0", "0 0 0 0 0 0 0 0"),
         "exit": "nonzero", "contains": ["cannot contain both P and P_D"]},
        {"id": "reject_mesh_PE",
         "text": make_case(base, "A B C D F P_D P_E P_F",
                           "0 0 0 0 0 0 0 0", "0 0 0 0 0 0 0 0"),
         "exit": "nonzero", "contains": ["P_E is internal-only"]},
        {"id": "reject_missing_PF",
         "text": make_case(base, "A B C D F P_D",
                           "0 0 0 0 0 0", "0 0 0 0 0 0"),
         "exit": "nonzero", "contains": ["requires mesh P_F"]},
        {"id": "reject_reordered",
         "text": make_case(base, "A B C F D P_D P_F",
                           "0 0 0 0 0 0 0", "0 0 0 0 0 0 0"),
         "exit": "nonzero", "contains": ["phosphorus layout must be exactly"]},
        {"id": "reject_nonzero_PF_diffusion",
         "text": make_case(enabled, "A B C D F P_D P_F",
                           "0 0 0 0 0 0 1.0e-12", "0 0 0 0 0 0 0",
                           "0 0 0"),
         "exit": "nonzero", "contains": ["P_F diffusion must be exactly zero"]},
        {"id": "reject_missing_internal_initialization",
         "text": make_case(base, "A B C D F P_D P_F",
                           "0 0 0 0 0 0 0", "0 0 0 0 0 0 0"),
         "exit": "nonzero", "contains": ["initial_particle_P"]},
    ]

    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True)
    rows = []
    for case in cases:
        work = run_root / str(case["id"])
        work.mkdir()
        (work / "input_fungi").write_text(str(case["text"]), encoding="utf-8")
        shutil.copy2(case_dir / "fungi_init_cfg.dat", work / "fungi_init_cfg.dat")
        command = [str(exe), "input_fungi",
                   f"bmx.max_step={case.get('max_step', 0)}",
                   f"amr.plot_int={case.get('plot_int', -1)}",
                   "amr.check_int=-1"]
        proc = subprocess.run(command, cwd=work, capture_output=True, text=True,
                              timeout=180)
        output = proc.stdout + proc.stderr
        (work / "stdout.log").write_text(output, encoding="utf-8")
        want_exit = case["exit"]
        exit_ok = proc.returncode == want_exit if isinstance(want_exit, int) else proc.returncode != 0
        missing = [token for token in case["contains"] if token not in output]
        unexpected = [token for token in case.get("excludes", []) if token in output]
        missing_file_tokens = []
        unexpected_file_tokens = []
        for relative, tokens in case.get("file_contains", {}).items():
            target = work / relative
            file_text = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
            missing_file_tokens.extend(
                f"{relative}:{token}" for token in tokens if token not in file_text
            )
        for relative, tokens in case.get("file_excludes", {}).items():
            target = work / relative
            file_text = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
            unexpected_file_tokens.extend(
                f"{relative}:{token}" for token in tokens if token in file_text
            )
        passed = (exit_ok and not missing and not unexpected and
                  not missing_file_tokens and not unexpected_file_tokens)
        rows.append({
            "id": case["id"], "status": "PASS" if passed else "FAIL",
            "exit_code": proc.returncode, "expected_exit": want_exit,
            "missing_output_tokens": missing,
            "unexpected_output_tokens": unexpected,
            "missing_file_tokens": missing_file_tokens,
            "unexpected_file_tokens": unexpected_file_tokens,
            "log": str(work / "stdout.log"),
        })
        print(f"{case['id']:40s} {'PASS' if passed else 'FAIL'} exit={proc.returncode}")

    report = {
        "stage": "C07", "test": "runtime_schema_matrix",
        "executable": str(exe), "cases": rows,
        "passed": all(row["status"] == "PASS" for row in rows),
        "claim_boundary": "engineering plumbing tests only; no biological values or scientific result",
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
