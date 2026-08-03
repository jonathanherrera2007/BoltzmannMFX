#!/usr/bin/env python3
"""C09 checkpoint-v3 identity, rank-change restart, and corruption tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from pathlib import Path

from run_c09_geometry_runtime import (
    CONTRACT_ID,
    event_rows,
    geometry_input,
    particle_fixture,
    run_case,
)


RELATIVE_TOLERANCE = 1.0e-12
GEOMETRY_HASH = "6a4329f013c857c664a11d669747845006a6c0c9d34f568625b6939d1462acba"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_particle_ascii(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    particle_count = int(lines[0])
    nsr, nsi, nrc, nic = (int(lines[index]) for index in range(1, 5))
    records = {}
    expected_columns = 3 + nsr + 2 + nsi + nrc + nic
    for line in lines[5:]:
        if not line.strip():
            continue
        columns = line.split()
        if len(columns) != expected_columns:
            raise ValueError(
                f"{path}: expected {expected_columns} columns, got {len(columns)}"
            )
        float_end = 3 + nsr
        floats = [float(value) for value in columns[:float_end]]
        discrete = [int(value) for value in columns[float_end:]]
        key = (discrete[0], discrete[1])
        if key in records:
            raise ValueError(f"{path}: duplicate particle key {key}")
        records[key] = {"floats": floats, "discrete": discrete}
    if len(records) != particle_count:
        raise ValueError(
            f"{path}: header has {particle_count} particles, parsed {len(records)}"
        )
    return {"header": [particle_count, nsr, nsi, nrc, nic], "records": records}


def compare_particle_ascii(reference: Path, restarted: Path) -> dict:
    lhs = parse_particle_ascii(reference)
    rhs = parse_particle_ascii(restarted)
    exact_schema = lhs["header"] == rhs["header"]
    exact_identifiers = set(lhs["records"]) == set(rhs["records"])
    exact_discrete = True
    floating_failures = 0
    max_relative_difference = 0.0
    first_difference = None
    if exact_identifiers:
        for key in sorted(lhs["records"]):
            left = lhs["records"][key]
            right = rhs["records"][key]
            if left["discrete"] != right["discrete"]:
                exact_discrete = False
                first_difference = first_difference or f"particle {key} discrete fields"
            for index, (a, b) in enumerate(zip(left["floats"], right["floats"])):
                scale = max(abs(a), abs(b))
                relative = abs(a - b) / scale if scale else 0.0
                max_relative_difference = max(max_relative_difference, relative)
                if not (math.isfinite(a) and math.isfinite(b)) or relative > RELATIVE_TOLERANCE:
                    floating_failures += 1
                    first_difference = first_difference or (
                        f"particle {key} float[{index}] {a} != {b}"
                    )
    passed = (
        exact_schema and exact_identifiers and exact_discrete
        and floating_failures == 0
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "exact_schema": exact_schema,
        "exact_identifiers": exact_identifiers,
        "exact_discrete_fields": exact_discrete,
        "floating_tolerance": RELATIVE_TOLERANCE,
        "floating_failures": floating_failures,
        "max_relative_difference": max_relative_difference,
        "first_difference": first_difference,
    }


def selected_checkpoint_hashes(checkpoint: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(item for item in checkpoint.rglob("*") if item.is_file()):
        relative = path.relative_to(checkpoint).as_posix()
        if (
            relative == "Header"
            or relative.startswith("particles/")
            or "/X_k" in relative
            or "/volfrac" in relative
        ):
            hashes[relative] = sha256(path)
    return hashes


def mutate_checkpoint(source: Path, destination: Path, transform) -> None:
    shutil.copytree(source, destination)
    header = destination / "Header"
    original = header.read_text(encoding="utf-8")
    modified = transform(original)
    if modified == original:
        raise ValueError(f"corruption transform made no change for {destination.name}")
    header.write_text(modified, encoding="utf-8", newline="\n")


def replace_once(old: str, new: str):
    def transform(text: str) -> str:
        if text.count(old) != 1:
            raise ValueError(f"expected exactly one occurrence of {old!r}")
        return text.replace(old, new, 1)
    return transform


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--mpiexec", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    exe = args.exe.resolve()
    source = args.source.resolve()
    run_root = args.run_root.resolve()
    json_out = args.json_out.resolve()
    mpiexec = args.mpiexec.resolve()
    case_dir = source / "exec/fungi"
    for required in (
        exe,
        mpiexec,
        case_dir / "input_fungi",
        case_dir / "fungi_init_cfg.dat",
    ):
        if not required.is_file():
            raise SystemExit(f"required file not found: {required}")
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True)

    base = (case_dir / "input_fungi").read_text(encoding="utf-8")
    particle_base = (case_dir / "fungi_init_cfg.dat").read_text(encoding="utf-8")
    enabled = geometry_input(base)
    particle = particle_fixture(particle_base)

    continuous_dir = run_root / "continuous_rank1"
    staged_dir = run_root / "staged_rank1"
    restart_dir = run_root / "restart_1_to_1"
    continuous = run_case(
        exe, continuous_dir, enabled, particle, args.timeout,
        max_step=2, check_int=1,
    )
    staged = run_case(
        exe, staged_dir, enabled, particle, args.timeout,
        max_step=1, check_int=1,
    )
    shutil.copytree(staged_dir / "chk00001", restart_dir / "chk00001")
    restarted = run_case(
        exe, restart_dir, enabled, particle, args.timeout,
        max_step=2, check_int=1, restart="chk00001",
    )

    valid_checkpoint = staged_dir / "chk00001"
    header_text = (valid_checkpoint / "Header").read_text(encoding="utf-8")
    required_header_tokens = [
        "Checkpoint version: 3",
        "BMX_SCHEMA_V3_BEGIN",
        "mesh_mode enabled",
        "mesh_component_names A B C D F P_D P_F",
        "particle_component_names A B C D F P_D P_E P_F",
        "operator_order_id bmx-p10-global-order-v1",
        "p11_geometry_enabled 1",
        "p11_geometry_schema_version 1",
        f"p11_geometry_contract_id {CONTRACT_ID}",
        f"p11_geometry_contract_sha256 {GEOMETRY_HASH}",
        "p11_geometry_stage local_quasi_2d_interface",
        "p11_geometry_prob_lo_x -1",
        "p11_geometry_prob_hi_x 1",
        "p11_geometry_periodic_x 0",
        "p11_geometry_prob_lo_y 0",
        "p11_geometry_periodic_y 1",
        "p11_geometry_prob_lo_z 0",
        "p11_geometry_prob_hi_z 1.2",
        "p11_geometry_periodic_z 0",
        "BMX_SCHEMA_V3_END",
    ]
    header_missing = [token for token in required_header_tokens if token not in header_text]
    particle_compare = compare_particle_ascii(
        continuous_dir / "par00002", restart_dir / "par00002"
    )
    continuous_hashes = selected_checkpoint_hashes(continuous_dir / "chk00002")
    restarted_hashes = selected_checkpoint_hashes(restart_dir / "chk00002")
    continuous_events = event_rows(continuous)
    restart_events = event_rows(restarted)
    valid_checks = {
        "continuous_exit_zero": continuous.returncode == 0,
        "staged_exit_zero": staged.returncode == 0,
        "restart_exit_zero": restarted.returncode == 0,
        "schema_header_complete": not header_missing,
        "particle_restart_equivalent": particle_compare["status"] == "PASS",
        "selected_checkpoint_payload_exact": continuous_hashes == restarted_hashes,
        "restart_update_event_identity_exact": (
            len(continuous_events) == 2 and len(restart_events) == 1
            and continuous_events[-1] == restart_events[-1]
        ),
        "restart_completed_deserialization": (
            "Finished reading particle data" in (restarted.stdout + restarted.stderr)
        ),
    }

    launcher_2 = [str(mpiexec), "-n", "2"]
    mpi_continuous_dir = run_root / "continuous_rank2"
    mpi_staged_dir = run_root / "staged_rank2"
    mpi_restart_2_dir = run_root / "restart_2_to_2"
    mpi_restart_1_dir = run_root / "restart_2_to_1"
    mpi_continuous = run_case(
        exe, mpi_continuous_dir, enabled, particle, args.timeout,
        max_step=2, check_int=1, launcher=launcher_2,
    )
    mpi_staged = run_case(
        exe, mpi_staged_dir, enabled, particle, args.timeout,
        max_step=1, check_int=1, launcher=launcher_2,
    )
    mpi_checkpoint = mpi_staged_dir / "chk00001"
    shutil.copytree(mpi_checkpoint, mpi_restart_2_dir / "chk00001")
    shutil.copytree(mpi_checkpoint, mpi_restart_1_dir / "chk00001")
    mpi_restart_2 = run_case(
        exe, mpi_restart_2_dir, enabled, particle, args.timeout,
        max_step=2, check_int=1, restart="chk00001", launcher=launcher_2,
    )
    mpi_restart_1 = run_case(
        exe, mpi_restart_1_dir, enabled, particle, args.timeout,
        max_step=2, check_int=1, restart="chk00001",
    )
    mpi_compare_2 = compare_particle_ascii(
        mpi_continuous_dir / "par00002", mpi_restart_2_dir / "par00002"
    )
    mpi_compare_1 = compare_particle_ascii(
        mpi_continuous_dir / "par00002", mpi_restart_1_dir / "par00002"
    )
    mpi_hashes = selected_checkpoint_hashes(mpi_continuous_dir / "chk00002")
    mpi_restart_hashes = selected_checkpoint_hashes(mpi_restart_2_dir / "chk00002")
    mpi_continuous_events = event_rows(mpi_continuous)
    mpi_restart_2_events = event_rows(mpi_restart_2)
    mpi_restart_1_events = event_rows(mpi_restart_1)
    mpi_checks = {
        "continuous_rank2_exit_zero": mpi_continuous.returncode == 0,
        "checkpoint_rank2_exit_zero": mpi_staged.returncode == 0,
        "restart_2_to_2_exit_zero": mpi_restart_2.returncode == 0,
        "restart_2_to_1_exit_zero": mpi_restart_1.returncode == 0,
        "restart_2_to_2_particle_equivalent": mpi_compare_2["status"] == "PASS",
        "restart_2_to_1_particle_equivalent": mpi_compare_1["status"] == "PASS",
        "restart_2_to_2_selected_payload_exact": mpi_hashes == mpi_restart_hashes,
        "rank_change_event_identity_exact": (
            len(mpi_continuous_events) == 2
            and len(mpi_restart_2_events) == 1
            and len(mpi_restart_1_events) == 1
            and mpi_continuous_events[-1] == mpi_restart_2_events[-1]
            and mpi_continuous_events[-1] == mpi_restart_1_events[-1]
        ),
        "both_restarts_completed_deserialization": (
            "Finished reading particle data" in (
                mpi_restart_2.stdout + mpi_restart_2.stderr
            )
            and "Finished reading particle data" in (
                mpi_restart_1.stdout + mpi_restart_1.stderr
            )
        ),
    }

    corruptions = [
        (
            "legacy_version",
            replace_once("Checkpoint version: 3", "Checkpoint version: 2"),
            "expected 'Checkpoint version: 3'",
        ),
        (
            "geometry_enabled",
            replace_once("p11_geometry_enabled 1", "p11_geometry_enabled 0"),
            "p11 geometry enabled state mismatch",
        ),
        (
            "geometry_contract_hash",
            replace_once(
                f"p11_geometry_contract_sha256 {GEOMETRY_HASH}",
                "p11_geometry_contract_sha256 " + "0" + GEOMETRY_HASH[1:],
            ),
            "P11 geometry contract identity mismatch",
        ),
        (
            "geometry_stage",
            replace_once(
                "p11_geometry_stage local_quasi_2d_interface",
                "p11_geometry_stage full_plate",
            ),
            "P11 geometry contract identity mismatch",
        ),
        (
            "geometry_domain",
            replace_once("p11_geometry_prob_hi_x 1", "p11_geometry_prob_hi_x 2"),
            "P11 geometry domain or periodicity mismatch",
        ),
        (
            "geometry_periodicity",
            replace_once("p11_geometry_periodic_y 1", "p11_geometry_periodic_y 0"),
            "P11 geometry domain or periodicity mismatch",
        ),
        (
            "generic_geometry_lines",
            replace_once("-1 0 0 \n", "-0.5 0 0 \n"),
            "checkpoint geometry lines differ from serialized P11 identity",
        ),
        (
            "schema_marker",
            replace_once("BMX_SCHEMA_V3_END", "BMX_SCHEMA_V2_END"),
            "missing BMX_SCHEMA_V3_END marker",
        ),
    ]
    corruption_rows = []
    for case_id, transform, expected in corruptions:
        case_dir_run = run_root / f"corrupt_{case_id}"
        mutate_checkpoint(valid_checkpoint, case_dir_run / "chk_bad", transform)
        completed = run_case(
            exe, case_dir_run, enabled, particle, args.timeout,
            max_step=1, check_int=-1, restart="chk_bad",
        )
        output = completed.stdout + completed.stderr
        checks = {
            "exit_nonzero": completed.returncode != 0,
            "clear_reason": expected in output,
            "before_field_deserialization": "Restart from checkpoint" not in output,
            "before_particle_deserialization": "Finished reading particle data" not in output,
        }
        corruption_rows.append({
            "id": case_id,
            "exit_code": completed.returncode,
            "expected_token": expected,
            "checks": checks,
            "status": "PASS" if all(checks.values()) else "FAIL",
            "log": str(case_dir_run / "stdout.log"),
        })

    disabled_write_dir = run_root / "disabled_write"
    disabled_restart_dir = run_root / "disabled_restart"
    disabled_write = run_case(
        exe, disabled_write_dir, base, particle_base, args.timeout,
        max_step=0, check_int=1,
    )
    shutil.copytree(
        disabled_write_dir / "chk00000", disabled_restart_dir / "chk00000"
    )
    disabled_restart = run_case(
        exe, disabled_restart_dir, base, particle_base, args.timeout,
        max_step=0, check_int=-1, restart="chk00000",
    )
    disabled_header = (
        disabled_write_dir / "chk00000/Header"
    ).read_text(encoding="utf-8")
    disabled_checks = {
        "write_exit_zero": disabled_write.returncode == 0,
        "restart_exit_zero": disabled_restart.returncode == 0,
        "schema_v3": disabled_header.startswith("Checkpoint version: 3\n"),
        "p11_disabled": "p11_geometry_enabled 0" in disabled_header,
        "p11_disabled_identity_canonical": all(
            token in disabled_header for token in (
                "p11_geometry_schema_version 0",
                "p11_geometry_contract_id DISABLED",
                "p11_geometry_contract_sha256 DISABLED",
                "p11_geometry_stage DISABLED",
            )
        ),
        "no_p11_event": "P11_GEOMETRY_EVENTS" not in (
            disabled_write.stdout + disabled_write.stderr
            + disabled_restart.stdout + disabled_restart.stderr
        ),
    }

    passed = (
        all(valid_checks.values())
        and all(mpi_checks.values())
        and all(row["status"] == "PASS" for row in corruption_rows)
        and all(disabled_checks.values())
    )
    report = {
        "artifact_type": "C09_CHECKPOINT_RESTART_TEST",
        "stage": "C09/P11",
        "status": "PASS" if passed else "FAIL",
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "valid_rank1": {
            "checks": valid_checks,
            "header_missing": header_missing,
            "particle_comparison": particle_compare,
            "continuous_selected_payload_hashes": continuous_hashes,
            "restarted_selected_payload_hashes": restarted_hashes,
            "continuous_events": continuous_events,
            "restart_events": restart_events,
        },
        "mpi_rank_change": {
            "ranks": {
                "continuous": 2,
                "checkpoint_write": 2,
                "same_rank_restart": 2,
                "rank_change_restart": 1,
            },
            "checks": mpi_checks,
            "particle_comparison_2_to_2": mpi_compare_2,
            "particle_comparison_2_to_1": mpi_compare_1,
        },
        "corruptions": corruption_rows,
        "feature_off_checkpoint": {
            "checks": disabled_checks,
            "status": "PASS" if all(disabled_checks.values()) else "FAIL",
        },
        "method": (
            "Checkpoint/restart continuous-versus-staged comparison at one and two "
            "ranks, two-to-one rank-change restart, exact once-per-update event "
            "identity, schema-v3 mutation rejection before field/particle reads, "
            "and canonical feature-off checkpoint roundtrip."
        ),
        "claim_boundary": (
            "Windows CPU engineering restart evidence; not release-host evidence or "
            "independent numerical review."
        ),
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "valid_rank1": "PASS" if all(valid_checks.values()) else "FAIL",
        "mpi_rank_change": "PASS" if all(mpi_checks.values()) else "FAIL",
        "corruptions": {row["id"]: row["status"] for row in corruption_rows},
        "feature_off_checkpoint": report["feature_off_checkpoint"]["status"],
        "json_out": str(json_out),
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
