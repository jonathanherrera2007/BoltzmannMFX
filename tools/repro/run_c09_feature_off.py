#!/usr/bin/env python3
"""C09 default-off semantic comparison against the qualified C08 source."""

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


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(source: str, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={os.path.abspath(source)}", *args],
        cwd=source,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def run_case(exe: str, case_dir: str, run_dir: str,
             model_args: list[str], timeout: int) -> int:
    os.makedirs(run_dir)
    shutil.copy2(os.path.join(case_dir, "input_fungi"), run_dir)
    shutil.copy2(os.path.join(case_dir, "fungi_init_cfg.dat"), run_dir)
    command = [
        exe,
        "input_fungi",
        *model_args,
        "amr.plot_int=-1",
        "amr.check_int=-1",
        "amr.par_ascii_int=1",
        "amr.par_ascii_file=par",
    ]
    completed = subprocess.run(
        command, cwd=run_dir, capture_output=True, text=True, timeout=timeout
    )
    with open(os.path.join(run_dir, "stdout.log"), "w", encoding="utf-8") as stream:
        stream.write(completed.stdout + completed.stderr)
    with open(os.path.join(run_dir, "command.json"), "w", encoding="utf-8") as stream:
        json.dump(command, stream, indent=2)
        stream.write("\n")
    return completed.returncode


def compare_trajectories(reference_dir: str, c09_dir: str) -> dict:
    reference_files = geom.dumps_in(reference_dir)
    c09_files = geom.dumps_in(c09_dir)
    result = {
        "reference_dumps": len(reference_files),
        "c09_dumps": len(c09_files),
        "dumps_compared": 0,
        "particle_records_compared": 0,
        "differing_values": 0,
        "fields_differing": [],
        "first_difference": None,
        "identical": True,
    }
    if [os.path.basename(path) for path in reference_files] != [
        os.path.basename(path) for path in c09_files
    ]:
        result["identical"] = False
        result["first_difference"] = "dump file sequences differ"
        return result

    differing_fields = set()
    for reference_path, c09_path in zip(reference_files, c09_files):
        dump_name = os.path.basename(reference_path)
        reference = geom.load_dump(reference_path)
        c09 = geom.load_dump(c09_path)
        result["dumps_compared"] += 1
        if set(reference) != set(c09):
            result["identical"] = False
            result["first_difference"] = result["first_difference"] or (
                f"{dump_name}: particle identity sets differ"
            )
            continue
        for key in sorted(reference):
            left = reference[key]
            right = c09[key]
            result["particle_records_compared"] += 1
            discrete = {
                "position_coordinates": (left.pos, right.pos),
                "cell_type": (left.cell_type, right.cell_type),
                "n_bnds": (left.n_bnds, right.n_bnds),
                "site_position": (left.position, right.position),
            }
            for field, (a, b) in discrete.items():
                if a != b:
                    result["differing_values"] += 1
                    differing_fields.add(field)
                    result["first_difference"] = result["first_difference"] or (
                        f"{dump_name} particle {key} {field}: {a!r} != {b!r}"
                    )
            for field in SEMANTIC_SCALARS:
                a, b = getattr(left, field), getattr(right, field)
                if a != b:
                    result["differing_values"] += 1
                    differing_fields.add(field)
                    result["first_difference"] = result["first_difference"] or (
                        f"{dump_name} particle {key} {field}: {a!r} != {b!r}"
                    )
            for block in SEMANTIC_BLOCKS:
                for index, (a, b) in enumerate(
                    zip(getattr(left, block), getattr(right, block))
                ):
                    if a != b:
                        label = f"{block}.{geom.SPECIES[index]}"
                        result["differing_values"] += 1
                        differing_fields.add(label)
                        result["first_difference"] = result["first_difference"] or (
                            f"{dump_name} particle {key} {label}: {a!r} != {b!r}"
                        )
            for block in SEMANTIC_BLOCKS:
                left_reserved = left.reserved[block]
                right_reserved = right.reserved[block]
                for index, (a, b) in enumerate(zip(left_reserved, right_reserved)):
                    if a != b:
                        label = f"{block}.reserved_{index}"
                        result["differing_values"] += 1
                        differing_fields.add(label)
                        result["first_difference"] = result["first_difference"] or (
                            f"{dump_name} particle {key} {label}: {a!r} != {b!r}"
                        )

    result["fields_differing"] = sorted(differing_fields)
    result["identical"] = result["identical"] and result["differing_values"] == 0
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c08-exe", required=True)
    parser.add_argument("--c08-source", required=True)
    parser.add_argument("--c09-exe", required=True)
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    for path in (args.c08_exe, args.c09_exe):
        if not os.path.isfile(path):
            raise SystemExit(f"executable not found: {path}")
    c08_source = os.path.abspath(args.c08_source)
    c08_head = git(c08_source, "rev-parse", "HEAD")
    c08_tree = git(c08_source, "rev-parse", "HEAD^{tree}")
    c08_status = git(c08_source, "status", "--porcelain=v1", "-uno")
    if c08_head != "a33e37749450432fb15c1021fc554a26f4e3fc7d":
        raise SystemExit(f"C08 reference source has unexpected HEAD: {c08_head}")
    if c08_tree != "333613990076476707f7e8aa82b1119e2d9a3f58":
        raise SystemExit(f"C08 reference source has unexpected tree: {c08_tree}")
    if c08_status:
        raise SystemExit("C08 reference source is dirty")
    if os.path.exists(args.out_dir):
        raise SystemExit(f"output directory already exists: {args.out_dir}")
    os.makedirs(args.out_dir)

    fixture_results = []
    for fixture in FIXTURES:
        fixture_root = os.path.join(args.out_dir, fixture["id"])
        reference_dir = os.path.join(fixture_root, "c08_reference")
        c09_dir = os.path.join(fixture_root, "c09_default_off")
        c08_exit = run_case(
            os.path.abspath(args.c08_exe), os.path.abspath(args.case_dir),
            reference_dir, fixture["args"], args.timeout,
        )
        c09_exit = run_case(
            os.path.abspath(args.c09_exe), os.path.abspath(args.case_dir),
            c09_dir, fixture["args"], args.timeout,
        )
        c08_analysis = geom.analyze(
            reference_dir, fixture["radius_max"], fixture["length_max"]
        )
        c09_analysis = geom.analyze(
            c09_dir, fixture["radius_max"], fixture["length_max"]
        )
        trajectory = compare_trajectories(reference_dir, c09_dir)
        branch_count = c09_analysis["observed_branch_counts"].get(
            fixture["branch"], 0
        )
        split_count = c09_analysis["split_or_new_particle_events"]
        c08_reserved = c08_analysis["reserved_slot_audit"]
        c09_reserved = c09_analysis["reserved_slot_audit"]
        checks = {
            "both_exits_zero": c08_exit == 0 and c09_exit == 0,
            "both_particle_layouts_are_8": (
                c08_analysis["particle_storage_components_seen"] == [8]
                and c09_analysis["particle_storage_components_seen"] == [8]
            ),
            "target_branch_exercised": branch_count > 0,
            "split_exercised_when_required": (
                not fixture["require_split"] or split_count > 0
            ),
            "semantic_trajectory_identical": trajectory["identical"],
            "c08_reserved_slots_exact_zero": (
                c08_reserved["observations"] > 0 and c08_reserved["nonzero"] == 0
            ),
            "c09_reserved_slots_exact_zero": (
                c09_reserved["observations"] > 0 and c09_reserved["nonzero"] == 0
            ),
        }
        fixture_results.append({
            "id": fixture["id"],
            "engineering_overrides": fixture["args"],
            "target_branch": fixture["branch"],
            "target_branch_count": branch_count,
            "split_or_new_particle_events": split_count,
            "c08_exit": c08_exit,
            "c09_exit": c09_exit,
            "trajectory": trajectory,
            "checks": checks,
            "status": "PASS" if all(checks.values()) else "FAIL",
        })

    status = "PASS" if all(
        result["status"] == "PASS" for result in fixture_results
    ) else "FAIL"
    report = {
        "artifact_type": "C09_FEATURE_OFF_SEMANTIC_TEST",
        "stage": "C09/P11",
        "status": status,
        "particle_ascii_precision_digits": 15,
        "c08_executable": {
            "path": os.path.abspath(args.c08_exe),
            "sha256": sha256(args.c08_exe),
        },
        "c08_reference_source": {
            "path": c08_source,
            "commit": c08_head,
            "tree": c08_tree,
            "clean": True,
        },
        "c09_executable": {
            "path": os.path.abspath(args.c09_exe),
            "sha256": sha256(args.c09_exe),
        },
        "fixtures": fixture_results,
        "method": (
            "Exact comparison of every G1/G4 particle dump between the qualified "
            "C08 source and C09 with p11_geometry absent/default-off, covering "
            "growth, split, topology, geometry, all six legacy chemistry values, "
            "and both reserved slots in all three particle blocks."
        ),
        "claim_boundary": (
            "Windows CPU engineering feature-off regression at 15-digit AMReX "
            "particle-output precision; not bitwise executable identity or release "
            "host evidence."
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({
        "status": status,
        "fixtures": [
            {"id": row["id"], "status": row["status"]}
            for row in fixture_results
        ],
        "json_out": os.path.abspath(args.json_out),
    }, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
