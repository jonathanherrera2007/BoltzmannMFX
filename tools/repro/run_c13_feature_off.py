#!/usr/bin/env python3
"""Compare C13 with P15 absent/default-off against qualified C12 bytes."""

from __future__ import annotations

import argparse
import json
import os
import sys

import analyze_p07_geometry as geom
import run_c09_feature_off as semantic


C12_EXE_SHA = "910425149ee025d4701d8a42525e3c3ffdc03489284e3b537afadf0945633540"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c12-exe", required=True)
    parser.add_argument("--c13-exe", required=True)
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    for path in (args.c12_exe, args.c13_exe):
        if not os.path.isfile(path):
            raise SystemExit(f"executable not found: {path}")
    if semantic.sha256(args.c12_exe) != C12_EXE_SHA:
        raise SystemExit("C12 reference executable hash mismatch")
    if os.path.exists(args.out_dir):
        raise SystemExit(f"output directory already exists: {args.out_dir}")
    os.makedirs(args.out_dir)

    fixtures = []
    for fixture in semantic.FIXTURES:
        fixture_root = os.path.join(args.out_dir, fixture["id"])
        reference_dir = os.path.join(fixture_root, "c12_reference")
        candidate_dir = os.path.join(fixture_root, "c13_p15_default_off")
        reference_exit = semantic.run_case(
            os.path.abspath(args.c12_exe), os.path.abspath(args.case_dir),
            reference_dir, fixture["args"], args.timeout,
        )
        candidate_exit = semantic.run_case(
            os.path.abspath(args.c13_exe), os.path.abspath(args.case_dir),
            candidate_dir, fixture["args"], args.timeout,
        )
        reference = geom.analyze(
            reference_dir, fixture["radius_max"], fixture["length_max"]
        )
        candidate = geom.analyze(
            candidate_dir, fixture["radius_max"], fixture["length_max"]
        )
        trajectory = semantic.compare_trajectories(reference_dir, candidate_dir)
        candidate_log = open(
            os.path.join(candidate_dir, "stdout.log"), encoding="utf-8"
        ).read().splitlines()
        branch_count = candidate["observed_branch_counts"].get(
            fixture["branch"], 0
        )
        split_count = candidate["split_or_new_particle_events"]
        checks = {
            "both_exits_zero": reference_exit == 0 and candidate_exit == 0,
            "both_particle_layouts_are_8": (
                reference["particle_storage_components_seen"] == [8] and
                candidate["particle_storage_components_seen"] == [8]
            ),
            "target_branch_exercised": branch_count > 0,
            "split_exercised_when_required": (
                not fixture["require_split"] or split_count > 0
            ),
            "semantic_trajectory_identical": trajectory["identical"],
            "P15_not_activated": not any(
                line.startswith("P15_") for line in candidate_log
            ),
        }
        fixtures.append({
            "id": fixture["id"],
            "engineering_overrides": fixture["args"],
            "target_branch": fixture["branch"],
            "target_branch_count": branch_count,
            "split_or_new_particle_events": split_count,
            "trajectory": trajectory,
            "checks": checks,
            "status": "PASS" if all(checks.values()) else "FAIL",
        })
    status = "PASS" if all(
        row["status"] == "PASS" for row in fixtures
    ) else "FAIL"
    report = {
        "artifact_type": "C13_FEATURE_OFF_SEMANTIC_TEST",
        "stage": "C13/P15 Stage 0",
        "status": status,
        "particle_ascii_precision_digits": 15,
        "c12_executable": {
            "path": os.path.abspath(args.c12_exe),
            "sha256": semantic.sha256(args.c12_exe),
        },
        "c13_executable": {
            "path": os.path.abspath(args.c13_exe),
            "sha256": semantic.sha256(args.c13_exe),
        },
        "fixtures": fixtures,
        "method": (
            "Exact comparison of every semantic particle field in every G1/G4 "
            "15-digit dump between qualified C12 and C13 with p15.enabled "
            "absent/default-off; growth and split paths execute."
        ),
        "external_resources": "none",
        "external_spend_usd": 0,
        "claim_boundary": (
            "Windows CPU feature-off engineering regression; not mentor "
            "approval, calibration, predictive validation, a 216-hour "
            "qualification outcome, or P15 science."
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({
        "status": status,
        "fixtures": [{"id": row["id"], "status": row["status"]}
                     for row in fixtures],
    }, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
