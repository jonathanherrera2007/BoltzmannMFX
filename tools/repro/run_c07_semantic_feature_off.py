#!/usr/bin/env python3
"""C07 feature-off semantic qualification across the 46/52-real particle ABIs.

The original C07 comparator used no-trigger controls and normalized stdout.
That is useful provenance evidence, but it cannot exercise or observe the
widened particle blocks.  This follow-up runs the frozen P07 executable and the
C07 executable on the C04 G1 and G4 growth/split fixtures, then compares the
observable semantic particle trajectory at AMReX's 15-digit ASCII precision.

The C07-only particle slots 6 and 7 are audited in committed, working, and
increment blocks at every dump and must remain exactly zero in feature-off
mode.  Test overrides are engineering branch-forcing values, not biological
parameters and not scientific evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

import analyze_p07_geometry as geom


FIXTURES = [
    {
        "id": "G1_tip_length_only",
        "branch": geom.TIP_LENGTH_ONLY,
        "args": ["bmx.max_step=40"],
        "radius_max": 2.5e-4,
        "length_max": 35.0e-4,
        "require_split": False,
    },
    {
        "id": "G4_nontip_rejected",
        "branch": geom.NONTIP_REJECTED,
        "args": [
            "bmx.max_step=30",
            "chem_species.max_seg_length=6.0e-4",
            "chem_species.seg_split_length=3.0e-4",
        ],
        "radius_max": 2.5e-4,
        "length_max": 6.0e-4,
        "require_split": True,
    },
]

SEMANTIC_SCALARS = ("r", "L", "area", "vol", "dadt", "dvdt")
SEMANTIC_BLOCKS = ("committed", "working", "increment")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_case(exe, case_dir, run_dir, model_args, timeout):
    os.makedirs(run_dir)
    shutil.copy2(os.path.join(case_dir, "input_fungi"), run_dir)
    shutil.copy2(os.path.join(case_dir, "fungi_init_cfg.dat"), run_dir)
    cmd = [
        exe,
        "input_fungi",
        *model_args,
        "amr.plot_int=-1",
        "amr.check_int=-1",
        "amr.par_ascii_int=1",
        "amr.par_ascii_file=par",
    ]
    proc = subprocess.run(
        cmd, cwd=run_dir, capture_output=True, text=True, timeout=timeout
    )
    with open(os.path.join(run_dir, "stdout.log"), "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
        fh.write(proc.stderr)
    with open(os.path.join(run_dir, "command.json"), "w", encoding="utf-8") as fh:
        json.dump(cmd, fh, indent=2)
        fh.write("\n")
    return proc.returncode


def relative_error(a, b):
    scale = max(abs(a), abs(b))
    return abs(a - b) / scale if scale else 0.0


def compare_trajectories(base_dir, c07_dir):
    base_files = geom.dumps_in(base_dir)
    c07_files = geom.dumps_in(c07_dir)
    result = {
        "baseline_dumps": len(base_files),
        "c07_dumps": len(c07_files),
        "dumps_compared": 0,
        "particle_records_compared": 0,
        "differing_values": 0,
        "fields_differing": [],
        "max_relative_difference": 0.0,
        "first_difference": None,
        "identical": True,
    }
    if [os.path.basename(p) for p in base_files] != [os.path.basename(p) for p in c07_files]:
        result["identical"] = False
        result["first_difference"] = "dump file sequences differ"
        return result

    differing_fields = set()
    for base_path, c07_path in zip(base_files, c07_files):
        dump_name = os.path.basename(base_path)
        base = geom.load_dump(base_path)
        c07 = geom.load_dump(c07_path)
        result["dumps_compared"] += 1
        if set(base) != set(c07):
            result["identical"] = False
            result["first_difference"] = result["first_difference"] or (
                f"{dump_name}: particle identity sets differ"
            )
            continue
        for key in sorted(base):
            bp, cp = base[key], c07[key]
            result["particle_records_compared"] += 1
            discrete = {
                "position": (bp.position, cp.position),
                "cell_type": (bp.cell_type, cp.cell_type),
                "n_bnds": (bp.n_bnds, cp.n_bnds),
                "is_tip": (bp.is_tip, cp.is_tip),
                "pos": (bp.pos, cp.pos),
            }
            for field, (bv, cv) in discrete.items():
                if bv != cv:
                    result["differing_values"] += 1
                    differing_fields.add(field)
                    result["first_difference"] = result["first_difference"] or (
                        f"{dump_name} particle {key} {field}: {bv!r} != {cv!r}"
                    )
            for field in SEMANTIC_SCALARS:
                bv, cv = getattr(bp, field), getattr(cp, field)
                if bv != cv:
                    result["differing_values"] += 1
                    differing_fields.add(field)
                    result["max_relative_difference"] = max(
                        result["max_relative_difference"], relative_error(bv, cv)
                    )
                    result["first_difference"] = result["first_difference"] or (
                        f"{dump_name} particle {key} {field}: {bv!r} != {cv!r}"
                    )
            for block in SEMANTIC_BLOCKS:
                for index, (bv, cv) in enumerate(
                    zip(getattr(bp, block), getattr(cp, block))
                ):
                    if bv != cv:
                        label = f"{block}.{geom.SPECIES[index]}"
                        result["differing_values"] += 1
                        differing_fields.add(label)
                        result["max_relative_difference"] = max(
                            result["max_relative_difference"], relative_error(bv, cv)
                        )
                        result["first_difference"] = result["first_difference"] or (
                            f"{dump_name} particle {key} {label}: {bv!r} != {cv!r}"
                        )

    result["fields_differing"] = sorted(differing_fields)
    result["identical"] = result["identical"] and result["differing_values"] == 0
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p07-exe", required=True)
    parser.add_argument("--c07-exe", required=True)
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    for path in (args.p07_exe, args.c07_exe):
        if not os.path.isfile(path):
            raise SystemExit(f"executable not found: {path}")
    for name in ("input_fungi", "fungi_init_cfg.dat"):
        if not os.path.isfile(os.path.join(args.case_dir, name)):
            raise SystemExit(f"case input not found: {os.path.join(args.case_dir, name)}")
    if os.path.exists(args.out_dir):
        raise SystemExit(f"output directory already exists: {args.out_dir}")
    os.makedirs(args.out_dir)

    fixture_results = []
    for fixture in FIXTURES:
        fixture_root = os.path.join(args.out_dir, fixture["id"])
        p07_dir = os.path.join(fixture_root, "p07_46_real")
        c07_dir = os.path.join(fixture_root, "c07_52_real")
        p07_exit = run_case(
            os.path.abspath(args.p07_exe), os.path.abspath(args.case_dir), p07_dir,
            fixture["args"], args.timeout,
        )
        c07_exit = run_case(
            os.path.abspath(args.c07_exe), os.path.abspath(args.case_dir), c07_dir,
            fixture["args"], args.timeout,
        )
        p07_analysis = geom.analyze(
            p07_dir, fixture["radius_max"], fixture["length_max"]
        )
        c07_analysis = geom.analyze(
            c07_dir, fixture["radius_max"], fixture["length_max"]
        )
        trajectory = compare_trajectories(p07_dir, c07_dir)
        branch_count = c07_analysis["observed_branch_counts"].get(fixture["branch"], 0)
        split_count = c07_analysis["split_or_new_particle_events"]
        reserved = c07_analysis["reserved_slot_audit"]
        checks = {
            "both_exits_zero": p07_exit == 0 and c07_exit == 0,
            "baseline_layout_is_6": p07_analysis["particle_storage_components_seen"] == [6],
            "c07_layout_is_8": c07_analysis["particle_storage_components_seen"] == [8],
            "target_branch_exercised": branch_count > 0,
            "split_exercised_when_required": not fixture["require_split"] or split_count > 0,
            "semantic_trajectory_identical": trajectory["identical"],
            "c07_reserved_slots_observed": reserved["observations"] > 0,
            "c07_reserved_slots_exact_zero": reserved["nonzero"] == 0,
        }
        fixture_results.append({
            "id": fixture["id"],
            "engineering_overrides": fixture["args"],
            "target_branch": fixture["branch"],
            "target_branch_count": branch_count,
            "split_or_new_particle_events": split_count,
            "p07_exit": p07_exit,
            "c07_exit": c07_exit,
            "p07_particle_storage_components": p07_analysis["particle_storage_components_seen"],
            "c07_particle_storage_components": c07_analysis["particle_storage_components_seen"],
            "c07_reserved_slot_audit": reserved,
            "trajectory": trajectory,
            "checks": checks,
            "status": "PASS" if all(checks.values()) else "FAIL",
        })

    result = {
        "artifact_type": "C07_SEMANTIC_FEATURE_OFF_FOLLOWUP",
        "finding": "REVIEW-C07-001",
        "status": "PASS" if all(r["status"] == "PASS" for r in fixture_results) else "FAIL",
        "particle_ascii_precision_digits": 15,
        "method": (
            "exact comparison of every G1/G4 particle dump across the 46-real P07 and "
            "52-real C07 ABIs for topology, geometry, and the first six values in each "
            "chemistry block; exact-zero audit of C07 slots 6/7 in all three blocks"
        ),
        "p07_executable": {"path": os.path.abspath(args.p07_exe), "sha256": sha256(args.p07_exe)},
        "c07_executable": {"path": os.path.abspath(args.c07_exe), "sha256": sha256(args.c07_exe)},
        "case_dir": os.path.abspath(args.case_dir),
        "raw_run_root": os.path.abspath(args.out_dir),
        "fixtures": fixture_results,
        "claim_boundary": (
            "engineering feature-off semantic regression with branch-forcing values; "
            "not release-host evidence and not scientific validation"
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")
    print(json.dumps({
        "status": result["status"],
        "json_out": os.path.abspath(args.json_out),
        "fixtures": [{"id": r["id"], "status": r["status"]} for r in fixture_results],
    }, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
