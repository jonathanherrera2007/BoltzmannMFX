#!/usr/bin/env python3
"""Exercise the C08 pre-redistribution deletion and boundary guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import struct
import subprocess
from pathlib import Path


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


def move_particle(config: str, coordinate: int, value: float) -> str:
    lines = config.splitlines()
    if len(lines) != 2 or int(lines[0].strip()) != 1:
        raise ValueError("guard fixture requires exactly one ASCII input particle")
    fields = lines[1].split()
    fields[coordinate] = f"{value:.17g}"
    return lines[0] + "\n" + " ".join(fields) + "\n"


def run_case(
    exe: Path,
    run_dir: Path,
    input_text: str,
    particle_config: str,
    timeout: int,
    *,
    check_int: int = -1,
    restart: str | None = None,
    launcher: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input_fungi").write_text(input_text, encoding="utf-8")
    (run_dir / "fungi_init_cfg.dat").write_text(
        particle_config, encoding="utf-8"
    )
    command = [
        *(launcher or []),
        str(exe),
        "input_fungi",
        "bmx.max_step=0",
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


def particle_ascii_positions(path: Path) -> list[tuple[float, float, float]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    count = int(lines[0])
    positions = [tuple(float(value) for value in line.split()[:3])
                 for line in lines[5:] if line.strip()]
    if len(positions) != count:
        raise ValueError(f"{path}: header count {count}, parsed {len(positions)}")
    return positions


def first_particle_record(checkpoint: Path) -> dict:
    particle_dir = checkpoint / "particles"
    tokens = iter((particle_dir / "Header").read_text(encoding="utf-8").split())
    version = next(tokens)
    dimension = int(next(tokens))
    real_components = int(next(tokens))
    for _ in range(real_components):
        next(tokens)
    int_components = int(next(tokens))
    for _ in range(int_components):
        next(tokens)
    if int(next(tokens)) != 1:
        raise ValueError("particle payload is not a checkpoint")
    particle_count = int(next(tokens))
    next(tokens)  # max_next_id
    finest_level = int(next(tokens))
    grid_counts = [int(next(tokens)) for _ in range(finest_level + 1)]
    records = []
    for level, grid_count in enumerate(grid_counts):
        for _ in range(grid_count):
            records.append(
                {
                    "level": level,
                    "file_number": int(next(tokens)),
                    "count": int(next(tokens)),
                    "offset": int(next(tokens)),
                }
            )
    try:
        trailing = next(tokens)
    except StopIteration:
        trailing = None
    if trailing is not None or sum(record["count"] for record in records) != particle_count:
        raise ValueError("malformed particle Header in guard fixture")
    record = next((record for record in records if record["count"] > 0), None)
    if record is None:
        raise ValueError("guard fixture contains no particle payload")
    precision_bytes = 8 if version.endswith("_double") else 4
    data_file = (
        particle_dir
        / f"Level_{record['level']}"
        / f"DATA_{record['file_number']:05d}"
    )
    return {
        **record,
        "path": data_file,
        "dimension": dimension,
        "real_components": real_components,
        "int_components": int_components,
        "precision_bytes": precision_bytes,
    }


def make_first_particle_id_negative(checkpoint: Path) -> dict:
    record = first_particle_record(checkpoint)
    data_file = record["path"]
    payload = bytearray(data_file.read_bytes())
    identity_offset = record["offset"]
    if len(payload) < identity_offset + 8:
        raise ValueError(f"particle data file is too short: {data_file}")
    high_word = int.from_bytes(
        payload[identity_offset : identity_offset + 4], "little", signed=False
    )
    if not high_word & 0x80000000:
        raise ValueError("fixture particle identity is not positive before corruption")
    corrupted_high_word = high_word & 0x7FFFFFFF
    payload[identity_offset : identity_offset + 4] = corrupted_high_word.to_bytes(
        4, "little", signed=False
    )
    data_file.write_bytes(payload)
    return {
        "path": str(data_file),
        "before_high_word_hex": f"0x{high_word:08x}",
        "after_high_word_hex": f"0x{corrupted_high_word:08x}",
        "mutation": "clear the AMReX m_idcpu positive-sign bit for particle 0",
    }


def move_first_checkpoint_particle(checkpoint: Path, coordinate: int, value: float) -> dict:
    record = first_particle_record(checkpoint)
    if coordinate < 0 or coordinate >= record["dimension"]:
        raise ValueError("checkpoint coordinate is out of range")
    data_file = record["path"]
    payload = bytearray(data_file.read_bytes())
    integer_chunk = 2 + record["int_components"]
    real_offset = (
        record["offset"]
        + record["count"] * integer_chunk * 4
        + coordinate * record["precision_bytes"]
    )
    format_code = "<d" if record["precision_bytes"] == 8 else "<f"
    if len(payload) < real_offset + record["precision_bytes"]:
        raise ValueError(f"particle data file is too short: {data_file}")
    previous = struct.unpack_from(format_code, payload, real_offset)[0]
    struct.pack_into(format_code, payload, real_offset, value)
    data_file.write_bytes(payload)
    return {
        "path": str(data_file),
        "previous_coordinate": previous,
        "new_coordinate": value,
        "coordinate_index": coordinate,
        "mutation": "replace the first serialized particle coordinate",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--mpiexec", type=Path)
    parser.add_argument("--ranks", type=int, default=1)
    parser.add_argument(
        "--restart-ranks",
        type=int,
        help="rank count for checkpoint restarts; defaults to --ranks",
    )
    args = parser.parse_args()

    exe = args.exe.resolve()
    source = args.source.resolve()
    run_root = args.run_root.resolve()
    json_out = args.json_out.resolve()
    case_dir = source / "exec" / "fungi"
    input_path = case_dir / "input_fungi"
    config_path = case_dir / "fungi_init_cfg.dat"
    for required in (exe, input_path, config_path):
        if not required.is_file():
            raise SystemExit(f"required file not found: {required}")
    restart_ranks = args.restart_ranks if args.restart_ranks is not None else args.ranks
    if args.ranks < 1 or restart_ranks < 1:
        raise SystemExit("--ranks and --restart-ranks must be positive")
    if (args.ranks > 1 or restart_ranks > 1) and args.mpiexec is None:
        raise SystemExit("--mpiexec is required for a rank count above one")
    if args.mpiexec is not None and not args.mpiexec.resolve().is_file():
        raise SystemExit(f"mpiexec not found: {args.mpiexec.resolve()}")
    launcher = (
        [str(args.mpiexec.resolve()), "-n", str(args.ranks)]
        if args.ranks > 1
        else None
    )
    restart_launcher = (
        [str(args.mpiexec.resolve()), "-n", str(restart_ranks)]
        if restart_ranks > 1
        else None
    )
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True)

    enabled = enabled_input(input_path.read_text(encoding="utf-8"))
    particle_config = config_path.read_text(encoding="utf-8")

    nonperiodic_dir = run_root / "nonperiodic_out_of_domain"
    nonperiodic = run_case(
        exe,
        nonperiodic_dir,
        enabled,
        move_particle(particle_config, 2, 0.1001),
        args.timeout,
        launcher=launcher,
    )
    nonperiodic_output = nonperiodic.stdout + nonperiodic.stderr
    nonperiodic_checks = {
        "exit_nonzero": nonperiodic.returncode != 0,
        "exact_reason": "P10_ABORT_OUT_OF_DOMAIN_PARTICLE" in nonperiodic_output,
        "not_misclassified_as_deletion":
            "P10_ABORT_UNMAPPED_PARTICLE_DELETION" not in nonperiodic_output,
        "aborted_before_initial_ledger": "P10_LEDGER" not in nonperiodic_output,
        "no_particle_output_after_abort": not (nonperiodic_dir / "par00000").exists(),
    }

    periodic_dir = run_root / "periodic_wrap"
    periodic = run_case(
        exe,
        periodic_dir,
        enabled,
        move_particle(particle_config, 0, 0.2001),
        args.timeout,
        launcher=launcher,
    )
    periodic_output = periodic.stdout + periodic.stderr
    periodic_ascii = periodic_dir / "par00000"
    positions = particle_ascii_positions(periodic_ascii) \
        if periodic_ascii.is_file() else []
    wrapped_x = positions[0][0] if len(positions) == 1 else math.nan
    periodic_checks = {
        "exit_zero": periodic.returncode == 0,
        "one_particle_retained": len(positions) == 1,
        "wrapped_inside_domain": math.isfinite(wrapped_x) and 0.0 <= wrapped_x < 0.2,
        "expected_periodic_coordinate": math.isclose(
            wrapped_x, 0.0001, rel_tol=0.0, abs_tol=1.0e-12
        ),
        "no_guard_abort": "P10_ABORT_" not in periodic_output,
    }

    seed_dir = run_root / "negative_id_seed"
    seed = run_case(
        exe,
        seed_dir,
        enabled,
        particle_config,
        args.timeout,
        check_int=1,
        launcher=launcher,
    )
    seed_checkpoint = seed_dir / "chk00000"
    negative_dir = run_root / "negative_id_restart"
    negative_checkpoint = negative_dir / "chk_bad"
    if seed_checkpoint.is_dir():
        shutil.copytree(seed_checkpoint, negative_checkpoint)
        mutation = make_first_particle_id_negative(negative_checkpoint)
        negative = run_case(
            exe,
            negative_dir,
            enabled,
            particle_config,
            args.timeout,
            restart="chk_bad",
            launcher=restart_launcher,
        )
    else:
        mutation = {"error": "seed checkpoint missing"}
        negative = subprocess.CompletedProcess([], 999, "", "seed checkpoint missing")
    negative_output = negative.stdout + negative.stderr
    negative_checks = {
        "seed_exit_zero": seed.returncode == 0,
        "seed_checkpoint_exists": seed_checkpoint.is_dir(),
        "restart_exit_nonzero": negative.returncode != 0,
        "exact_reason": "P10_ABORT_UNMAPPED_PARTICLE_DELETION" in negative_output,
        "not_misclassified_as_boundary":
            "P10_ABORT_OUT_OF_DOMAIN_PARTICLE" not in negative_output,
        "before_particle_deserialization":
            "Finished reading particle data" not in negative_output,
        "aborted_before_update_ledger":
            "P10_LEDGER boundary=O01_PRE_UPDATE_LEDGER" not in negative_output,
    }

    checkpoint_ood_dir = run_root / "checkpoint_out_of_domain_restart"
    checkpoint_ood = checkpoint_ood_dir / "chk_bad"
    if seed_checkpoint.is_dir():
        shutil.copytree(seed_checkpoint, checkpoint_ood)
        checkpoint_ood_mutation = move_first_checkpoint_particle(
            checkpoint_ood, 2, 0.1001
        )
        checkpoint_ood_run = run_case(
            exe,
            checkpoint_ood_dir,
            enabled,
            particle_config,
            args.timeout,
            restart="chk_bad",
            launcher=restart_launcher,
        )
    else:
        checkpoint_ood_mutation = {"error": "seed checkpoint missing"}
        checkpoint_ood_run = subprocess.CompletedProcess(
            [], 999, "", "seed checkpoint missing"
        )
    checkpoint_ood_output = checkpoint_ood_run.stdout + checkpoint_ood_run.stderr
    checkpoint_ood_checks = {
        "seed_exit_zero": seed.returncode == 0,
        "restart_exit_nonzero": checkpoint_ood_run.returncode != 0,
        "exact_reason":
            "P10_ABORT_OUT_OF_DOMAIN_PARTICLE" in checkpoint_ood_output,
        "not_misclassified_as_deletion":
            "P10_ABORT_UNMAPPED_PARTICLE_DELETION" not in checkpoint_ood_output,
        "before_particle_deserialization":
            "Finished reading particle data" not in checkpoint_ood_output,
        "aborted_before_update_ledger":
            "P10_LEDGER boundary=O01_PRE_UPDATE_LEDGER"
            not in checkpoint_ood_output,
    }

    rows = {
        "nonperiodic_out_of_domain": {
            "exit_code": nonperiodic.returncode,
            "checks": nonperiodic_checks,
            "status": "PASS" if all(nonperiodic_checks.values()) else "FAIL",
            "log": str(nonperiodic_dir / "stdout.log"),
        },
        "periodic_wrap": {
            "exit_code": periodic.returncode,
            "wrapped_x": wrapped_x,
            "checks": periodic_checks,
            "status": "PASS" if all(periodic_checks.values()) else "FAIL",
            "log": str(periodic_dir / "stdout.log"),
        },
        "negative_id": {
            "exit_code": negative.returncode,
            "mutation": mutation,
            "checks": negative_checks,
            "status": "PASS" if all(negative_checks.values()) else "FAIL",
            "log": str(negative_dir / "stdout.log"),
        },
        "checkpoint_out_of_domain": {
            "exit_code": checkpoint_ood_run.returncode,
            "mutation": checkpoint_ood_mutation,
            "checks": checkpoint_ood_checks,
            "status": "PASS" if all(checkpoint_ood_checks.values()) else "FAIL",
            "log": str(checkpoint_ood_dir / "stdout.log"),
        },
    }
    passed = all(row["status"] == "PASS" for row in rows.values())
    report = {
        "artifact_type": "C08_REDISTRIBUTION_GUARD_TEST",
        "stage": "C08",
        "status": "PASS" if passed else "FAIL",
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "mpi": {
            "seed_and_direct_ranks": args.ranks,
            "checkpoint_restart_ranks": restart_ranks,
            "mpiexec": str(args.mpiexec.resolve()) if args.mpiexec else None,
        },
        "cases": rows,
        "method": (
            "exercise an enabled nonperiodic escape through unguarded-at-call-site "
            "ASCII initialization, retain and wrap an enabled periodic escape, and "
            "restart checkpoints whose first AMReX identity sign bit or first "
            "nonperiodic coordinate was corrupted"
        ),
        "claim_boundary": (
            "engineering pre-invalidation routing test; runtime evidence covers both "
            "derived Redistribute routing and prevalidation before pinned Restart's "
            "internal redistribution, including the recorded MPI rank counts; static "
            "source ordering covers every base Redistribute/Regrid delegation"
        ),
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "cases": {key: value["status"] for key, value in rows.items()},
        "json_out": str(json_out),
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
