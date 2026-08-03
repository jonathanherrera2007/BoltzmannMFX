#!/usr/bin/env python3
"""Reissue C08 checkpoint/restart invariants against the current bound schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path


RELATIVE_TOLERANCE = 1.0e-12


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


def enabled_input(base: str) -> str:
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
    for key in (
        "chem_species.kP",
        "chem_species.krP",
        "chem_species.mass_transfer_P",
        "chem_species.p_growth_limit",
        "chem_species.kv",
        "chem_species.branching_probability",
        "chem_species.splitting_probability",
        "chem_species.fusion_probability",
        "cell_force.fluctuation_scale",
    ):
        result = set_value(result, key, "0.0")
    result = set_value(result, "chem_species.max_seg_length", "1.0e-2")
    return result


def run_case(
    exe: Path,
    case_dir: Path,
    run_dir: Path,
    input_text: str,
    max_step: int,
    check_int: int,
    timeout: int,
    restart: str | None = None,
    launcher: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input_fungi").write_text(input_text, encoding="utf-8")
    shutil.copy2(case_dir / "fungi_init_cfg.dat", run_dir / "fungi_init_cfg.dat")
    command = [
        *(launcher or []),
        str(exe),
        "input_fungi",
        f"bmx.max_step={max_step}",
        "amr.plot_int=-1",
        f"amr.check_int={check_int}",
        "amr.check_file=chk",
        "amr.par_ascii_int=1",
        "amr.par_ascii_file=par",
    ]
    if restart is not None:
        command.append(f"amr.restart={restart}")
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
    return {
        "header": [particle_count, nsr, nsi, nrc, nic],
        "records": records,
    }


def compare_particle_ascii(reference: Path, restarted: Path) -> dict:
    lhs = parse_particle_ascii(reference)
    rhs = parse_particle_ascii(restarted)
    exact_schema = lhs["header"] == rhs["header"]
    exact_identifiers = set(lhs["records"]) == set(rhs["records"])
    exact_discrete = True
    float_failures = 0
    max_relative_difference = 0.0
    first_difference = None
    if exact_identifiers:
        for key in sorted(lhs["records"]):
            left = lhs["records"][key]
            right = rhs["records"][key]
            if left["discrete"] != right["discrete"]:
                exact_discrete = False
                first_difference = first_difference or f"particle {key} discrete fields"
            if len(left["floats"]) != len(right["floats"]):
                float_failures += 1
                first_difference = first_difference or f"particle {key} float field count"
                continue
            for index, (a, b) in enumerate(zip(left["floats"], right["floats"])):
                scale = max(abs(a), abs(b))
                relative = abs(a - b) / scale if scale else 0.0
                max_relative_difference = max(max_relative_difference, relative)
                if not (math.isfinite(a) and math.isfinite(b)) or relative > RELATIVE_TOLERANCE:
                    float_failures += 1
                    first_difference = first_difference or (
                        f"particle {key} float[{index}] {a} != {b}"
                    )
    passed = exact_schema and exact_identifiers and exact_discrete and float_failures == 0
    return {
        "status": "PASS" if passed else "FAIL",
        "exact_schema": exact_schema,
        "exact_identifiers": exact_identifiers,
        "exact_discrete_fields": exact_discrete,
        "floating_tolerance": RELATIVE_TOLERANCE,
        "floating_failures": float_failures,
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
    parser.add_argument("--timeout", type=int, default=900)
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
    enabled = enabled_input(base)

    continuous_dir = run_root / "continuous"
    staged_dir = run_root / "staged"
    restart_dir = run_root / "restarted"
    continuous = run_case(
        exe, case_dir, continuous_dir, enabled, 2, 1, args.timeout
    )
    staged = run_case(exe, case_dir, staged_dir, enabled, 1, 1, args.timeout)
    shutil.copytree(staged_dir / "chk00001", restart_dir / "chk00001")
    restarted = run_case(
        exe, case_dir, restart_dir, enabled, 2, 1, args.timeout, "chk00001"
    )

    valid_checkpoint = staged_dir / "chk00001"
    header_text = (valid_checkpoint / "Header").read_text(encoding="utf-8")
    required_header_tokens = [
        "Checkpoint version: 5",
        "BMX_SCHEMA_V5_BEGIN",
        "mesh_mode enabled",
        "mesh_component_count 7",
        "mesh_component_names A B C D F P_D P_F",
        "particle_component_count 8",
        "particle_component_names A B C D F P_D P_E P_F",
        "particle_block_count 3",
        "layout_hash_sha256 522cb38eacea08c97093860e26b34973b0b0e945545aef54adbd032946d8d669",
        "operator_order_id bmx-p10-global-order-v1",
        "topology_event_contract_id bmx-p10-topology-event-v1",
        "decision_contract_id P09-U01+P09-U02+P09-U03+UDC-20260801-P10-U01+UDC-20260801-MENTOR-DECISION-FREEZE-V2",
        "decision_contract_sha256 34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066",
        "global_ledger_schema_id bmx-p10-global-ledger-v1",
        "p12_uptake_enabled 0",
        "p12_uptake_contract_id DISABLED",
        "p12_numerical_contract_id DISABLED",
        "p12_numerical_contract_sha256 DISABLED",
        "p12_uptake_run_minimum_donor_scale 1",
        "p12_uptake_run_maximum_donor_eta 0",
        "p12_uptake_positive_request_updates 0",
        "p12_uptake_zero_inventory_positive_request_updates 0",
        "ledger_reference_bound 1",
        "BMX_SCHEMA_V5_END",
    ]
    header_missing = [token for token in required_header_tokens if token not in header_text]
    reference_match = re.search(
        r"^ledger_reference_total_p\s+([^\s]+)$", header_text, re.MULTILINE
    )
    reference_total = float(reference_match.group(1)) if reference_match else math.nan

    particle_compare = compare_particle_ascii(
        continuous_dir / "par00002", restart_dir / "par00002"
    )
    continuous_hashes = selected_checkpoint_hashes(continuous_dir / "chk00002")
    restarted_hashes = selected_checkpoint_hashes(restart_dir / "chk00002")
    payload_exact = continuous_hashes == restarted_hashes

    valid_checks = {
        "continuous_exit_zero": continuous.returncode == 0,
        "staged_exit_zero": staged.returncode == 0,
        "restart_exit_zero": restarted.returncode == 0,
        "schema_header_complete": not header_missing,
        "bound_nonzero_reference": math.isfinite(reference_total)
        and reference_total > 0.0,
        "particle_restart_equivalent": particle_compare["status"] == "PASS",
        "selected_checkpoint_payload_exact": payload_exact,
    }

    mpi_roundtrip = {
        "status": "NOT_RUN",
        "checks": {},
        "particle_comparison_2_to_2": None,
        "particle_comparison_2_to_1": None,
    }
    if args.mpiexec is not None:
        launcher_2 = [str(args.mpiexec.resolve()), "-n", "2"]
        mpi_continuous_dir = run_root / "mpi_continuous_2_rank"
        mpi_staged_dir = run_root / "mpi_staged_2_rank"
        mpi_restart_2_dir = run_root / "mpi_restart_2_to_2"
        mpi_restart_1_dir = run_root / "mpi_restart_2_to_1"
        mpi_continuous = run_case(
            exe, case_dir, mpi_continuous_dir, enabled, 2, 1, args.timeout,
            launcher=launcher_2,
        )
        mpi_staged = run_case(
            exe, case_dir, mpi_staged_dir, enabled, 1, 1, args.timeout,
            launcher=launcher_2,
        )
        mpi_checkpoint = mpi_staged_dir / "chk00001"
        shutil.copytree(mpi_checkpoint, mpi_restart_2_dir / "chk00001")
        shutil.copytree(mpi_checkpoint, mpi_restart_1_dir / "chk00001")
        mpi_restart_2 = run_case(
            exe, case_dir, mpi_restart_2_dir, enabled, 2, 1, args.timeout,
            "chk00001", launcher_2,
        )
        mpi_restart_1 = run_case(
            exe, case_dir, mpi_restart_1_dir, enabled, 2, 1, args.timeout,
            "chk00001",
        )
        mpi_compare_2 = compare_particle_ascii(
            mpi_continuous_dir / "par00002", mpi_restart_2_dir / "par00002"
        )
        mpi_compare_1 = compare_particle_ascii(
            mpi_continuous_dir / "par00002", mpi_restart_1_dir / "par00002"
        )
        mpi_continuous_hashes = selected_checkpoint_hashes(
            mpi_continuous_dir / "chk00002"
        )
        mpi_restarted_hashes = selected_checkpoint_hashes(
            mpi_restart_2_dir / "chk00002"
        )
        mpi_restart_2_output = mpi_restart_2.stdout + mpi_restart_2.stderr
        mpi_restart_1_output = mpi_restart_1.stdout + mpi_restart_1.stderr
        mpi_checks = {
            "continuous_2_rank_exit_zero": mpi_continuous.returncode == 0,
            "checkpoint_write_2_rank_exit_zero": mpi_staged.returncode == 0,
            "restart_2_to_2_exit_zero": mpi_restart_2.returncode == 0,
            "restart_2_to_1_exit_zero": mpi_restart_1.returncode == 0,
            "restart_2_to_2_particle_equivalent":
                mpi_compare_2["status"] == "PASS",
            "restart_2_to_1_particle_equivalent":
                mpi_compare_1["status"] == "PASS",
            "restart_2_to_2_selected_payload_exact":
                mpi_continuous_hashes == mpi_restarted_hashes,
            "restart_2_to_2_completed_deserialization":
                "Finished reading particle data" in mpi_restart_2_output,
            "restart_2_to_1_completed_deserialization":
                "Finished reading particle data" in mpi_restart_1_output,
            "no_guard_abort":
                "P10_ABORT_" not in mpi_restart_2_output and
                "P10_ABORT_" not in mpi_restart_1_output,
        }
        mpi_roundtrip = {
            "status": "PASS" if all(mpi_checks.values()) else "FAIL",
            "ranks": {
                "continuous": 2,
                "checkpoint_write": 2,
                "same_rank_restart": 2,
                "rank_change_restart": 1,
            },
            "checks": mpi_checks,
            "particle_comparison_2_to_2": mpi_compare_2,
            "particle_comparison_2_to_1": mpi_compare_1,
            "continuous_selected_payload_hashes": mpi_continuous_hashes,
            "restarted_2_rank_selected_payload_hashes": mpi_restarted_hashes,
        }

    corruptions = [
        (
            "legacy_version",
            replace_once("Checkpoint version: 5", "Checkpoint version: 4"),
            "expected 'Checkpoint version: 5'",
        ),
        (
            "layout_hash",
            replace_once(
                "layout_hash_sha256 522cb38eacea08c97093860e26b34973b0b0e945545aef54adbd032946d8d669",
                "layout_hash_sha256 022cb38eacea08c97093860e26b34973b0b0e945545aef54adbd032946d8d669",
            ),
            "layout_hash_sha256 mismatch",
        ),
        (
            "mesh_count",
            replace_once("mesh_component_count 7", "mesh_component_count 6"),
            "mesh_component_count mismatch",
        ),
        (
            "particle_names",
            replace_once(
                "particle_component_names A B C D F P_D P_E P_F",
                "particle_component_names A B C D F P_D P_X P_F",
            ),
            "particle_component_names mismatch",
        ),
        (
            "operator_order",
            replace_once(
                "operator_order_id bmx-p10-global-order-v1",
                "operator_order_id bmx-p10-global-order-v0",
            ),
            "operator_order_id mismatch",
        ),
        (
            "decision_contract_hash",
            replace_once(
                "decision_contract_sha256 34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066",
                "decision_contract_sha256 04e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066",
            ),
            "decision_contract_sha256 mismatch",
        ),
        (
            "topology_contract",
            replace_once(
                "topology_event_contract_id bmx-p10-topology-event-v1",
                "topology_event_contract_id bmx-p10-topology-event-v0",
            ),
            "topology_event_contract_id mismatch",
        ),
        (
            "negative_ledger",
            replace_once("ledger_structural_p 0", "ledger_structural_p -1"),
            "nonfinite or negative cumulative ledger amount",
        ),
        (
            "negative_event_count",
            replace_once(
                "ledger_other_exit_events 0", "ledger_other_exit_events -1"
            ),
            "malformed unsigned field ledger_other_exit_events",
        ),
        (
            "nonzero_other_exit",
            replace_once("ledger_other_exit_d 0", "ledger_other_exit_d 1"),
            "v1 other_exit_d/e/f/events must be exactly zero",
        ),
        (
            "truncated_schema",
            lambda text: text[: text.index("ledger_other_exit_events")],
            "missing ledger_other_exit_events",
        ),
        (
            "extra_schema_field",
            replace_once(
                "BMX_SCHEMA_V5_END\n",
                "BMX_SCHEMA_V5_END\nunexpected_schema_field 1\n",
            ),
            "malformed level count",
        ),
    ]

    corruption_rows = []
    for case_id, transform, expected_token in corruptions:
        case_run = run_root / f"corrupt_{case_id}"
        mutate_checkpoint(valid_checkpoint, case_run / "chk_bad", transform)
        completed = run_case(
            exe,
            case_dir,
            case_run,
            enabled,
            1,
            -1,
            args.timeout,
            "chk_bad",
        )
        output = completed.stdout + completed.stderr
        checks = {
            "exit_nonzero": completed.returncode != 0,
            "clear_reason": expected_token in output,
            "before_particle_deserialization": "Finished reading particle data" not in output,
        }
        corruption_rows.append(
            {
                "id": case_id,
                "exit_code": completed.returncode,
                "expected_token": expected_token,
                "checks": checks,
                "status": "PASS" if all(checks.values()) else "FAIL",
                "log": str(case_run / "stdout.log"),
            }
        )

    disabled_write_dir = run_root / "disabled_write"
    disabled_restart_dir = run_root / "disabled_restart"
    disabled_write = run_case(
        exe, case_dir, disabled_write_dir, base, 0, 1, args.timeout
    )
    shutil.copytree(
        disabled_write_dir / "chk00000", disabled_restart_dir / "chk00000"
    )
    disabled_restart = run_case(
        exe,
        case_dir,
        disabled_restart_dir,
        base,
        0,
        -1,
        args.timeout,
        "chk00000",
    )
    disabled_header = (disabled_write_dir / "chk00000" / "Header").read_text(
        encoding="utf-8"
    )
    disabled_checks = {
        "write_exit_zero": disabled_write.returncode == 0,
        "restart_exit_zero": disabled_restart.returncode == 0,
        "schema_v5": disabled_header.startswith("Checkpoint version: 5\n"),
        "disabled_mode": "mesh_mode disabled" in disabled_header,
        "disabled_mesh_names": "mesh_component_names A B C D F P" in disabled_header,
        "reserved_particle_names": (
            "particle_component_names A B C D F P reserved_P_E reserved_P_F"
            in disabled_header
        ),
    }

    passed = (
        all(valid_checks.values())
        and all(row["status"] == "PASS" for row in corruption_rows)
        and all(disabled_checks.values())
        and (args.mpiexec is None or mpi_roundtrip["status"] == "PASS")
    )
    report = {
        "artifact_type": "C08_CHECKPOINT_RESTART_REISSUE",
        "stage": "C10_REISSUE_OF_C08_INVARIANTS",
        "status": "PASS" if passed else "FAIL",
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "valid_roundtrip": {
            "checks": valid_checks,
            "missing_header_tokens": header_missing,
            "particle_comparison": particle_compare,
            "continuous_selected_payload_hashes": continuous_hashes,
            "restarted_selected_payload_hashes": restarted_hashes,
            "status": "PASS" if all(valid_checks.values()) else "FAIL",
        },
        "corrupted_schema_cases": corruption_rows,
        "disabled_feature_off_roundtrip": {
            "checks": disabled_checks,
            "status": "PASS" if all(disabled_checks.values()) else "FAIL",
        },
        "mpi_roundtrip": mpi_roundtrip,
        "claim_boundary": (
            "engineering reissue of the C08 checkpoint/restart integrity test "
            "against schema v5, P12 numerical preregistration V2, and decision-contract SHA-256 "
            "34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066, with a bound nonzero "
            "global ledger and exact topology-contract identity; when --mpiexec is "
            "provided it includes 2-rank checkpoint/restart and 2-to-1 rank-change "
            "restart through pinned AMReX's internal redistribution"
        ),
        "raw_run_root": str(run_root),
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "valid_roundtrip": report["valid_roundtrip"]["status"],
                "corruptions": {
                    row["id"]: row["status"] for row in corruption_rows
                },
                "disabled_roundtrip": report["disabled_feature_off_roundtrip"][
                    "status"
                ],
                "mpi_roundtrip": report["mpi_roundtrip"]["status"],
                "json_out": str(json_out),
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
