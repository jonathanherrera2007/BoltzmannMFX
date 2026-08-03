#!/usr/bin/env python3
"""Diagnose P15 stochastic-topology identity across one and two MPI ranks.

This is a one-update engineering diagnostic, never a 216-hour qualification
outcome.  It deliberately places one split-eligible connected TIP on the
positive-x half of the central domain so ownership moves from rank 0 in P0 to
rank 1 in a two-box x decomposition.  The exact adopted seed is held fixed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import run_c13_stage0_runtime as c13
from run_c08_checkpoint_tests import compare_particle_ascii
from run_c09_geometry_runtime import set_value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def particle_rows(path: Path) -> list[dict[str, object]]:
    """Read the AoS ASCII dump fields needed to diagnose topology identity."""
    lines = path.read_text(encoding="utf-8").splitlines()
    count = int(lines[0])
    nreal = int(lines[1])
    nint = int(lines[2])
    rows: list[dict[str, object]] = []
    for line in lines[5:5 + count]:
        fields = line.split()
        reals = [float(value) for value in fields[3:3 + nreal]]
        amrex_id = int(fields[3 + nreal])
        amrex_cpu = int(fields[4 + nreal])
        integer_start = 5 + nreal
        integers = [
            int(value)
            for value in fields[integer_start:integer_start + nint]
        ]
        rows.append({
            "stable_id": integers[33],
            "stable_cpu": integers[34],
            "amrex_id": amrex_id,
            "amrex_cpu": amrex_cpu,
            "position_cm": [float(value) for value in fields[:3]],
            "radius_cm": reals[0],
            "length_cm": reals[1],
            "theta": reals[2],
            "phi": reals[3],
            "bond_count": integers[6],
            "bond_ids": integers[7:11],
            "bond_cpus": integers[11:15],
            "bond_sites": integers[15:19],
        })
    return rows


def created_rows(initial: Path, final: Path) -> list[dict[str, object]]:
    initial_keys = {
        (row["stable_id"], row["stable_cpu"])
        for row in particle_rows(initial)
    }
    return [
        row for row in particle_rows(final)
        if (row["stable_id"], row["stable_cpu"]) not in initial_keys
    ]


def topology_log_lines(path: Path) -> list[str]:
    needles = (
        "LENGTH:", "SPLIT LENGTH:", "SIDE BRANCH WILL BE CREATED",
        "Generating new growth tip.", "New tip parent id:",
        "Adding new segments",
    )
    return [
        line.strip() for line in path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        if any(needle in line for needle in needles)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--mpiexec", type=Path, required=True)
    args = parser.parse_args()
    exe = args.exe.resolve()
    source = args.source.resolve()
    run_root = args.run_root.resolve()
    if run_root.exists():
        raise SystemExit(f"run root already exists: {run_root}")
    run_root.mkdir(parents=True)

    base_input = (source / "exec/fungi/input_fungi").read_text(encoding="utf-8")
    base_particle = (source / "exec/fungi/fungi_init_cfg.dat").read_text(
        encoding="utf-8"
    )
    # Segment 0 is connected, split-eligible, and in the positive-x box.
    # Segment 1 has a smaller radius and is deliberately ineligible.
    segments = [
        c13.Segment(0.20, 0.05, 0.90, 5.0e-4, 0.02,
                    c13.PI/2.0, 0.0, 1),
        c13.Segment(0.22, 0.05, 0.90, 3.0e-4, 0.02,
                    c13.PI/2.0, 0.0, 1),
    ]
    particle_text = c13.network_text(base_particle, segments)
    network_sha = hashlib.sha256(particle_text.encode()).hexdigest()
    generator_sha = c13.sha256(Path(__file__).resolve())

    def make_input(max_grid_x: int) -> str:
        text = c13.integrated_input(
            base_input, network_sha=network_sha,
            generator_sha=generator_sha,
            diffusivity=0.0, max_grid_x=max_grid_x,
        )
        values = {
            "chem_species.max_seg_radius": "4.0e-4",
            "chem_species.max_seg_length": "1.0e-2",
            "chem_species.seg_split_length": "5.0e-3",
            "chem_species.splitting_probability": "0.5",
            "chem_species.branching_probability": "0",
            "chem_species.fusion_probability": "0",
        }
        for key, value in values.items():
            text = set_value(text, key, value)
        return text

    one = c13.run_case(
        exe, run_root / "p0_rank1", make_input(40), particle_text,
        steps=1, ranks=1, mpiexec=args.mpiexec.resolve(),
    )
    two = c13.run_case(
        exe, run_root / "p1_rank2_xslab", make_input(20), particle_text,
        steps=1, ranks=2, mpiexec=args.mpiexec.resolve(),
    )
    comparison = (
        compare_particle_ascii(
            run_root / "p0_rank1" / "par00001",
            run_root / "p1_rank2_xslab" / "par00001",
        )
        if (run_root / "p0_rank1" / "par00001").exists()
        and (run_root / "p1_rank2_xslab" / "par00001").exists()
        else {"status": "FAIL", "reason": "missing post-update particle dump"}
    )
    exact = one.returncode == 0 and two.returncode == 0 and (
        comparison.get("status") == "PASS"
    )
    p0_dump = run_root / "p0_rank1" / "par00001"
    p1_dump = run_root / "p1_rank2_xslab" / "par00001"
    p0_created = created_rows(
        run_root / "p0_rank1" / "par00000", p0_dump
    ) if p0_dump.exists() else []
    p1_created = created_rows(
        run_root / "p1_rank2_xslab" / "par00000", p1_dump
    ) if p1_dump.exists() else []
    topology_evidence = {
        "P0_created_particles": p0_created,
        "P1_created_particles": p1_created,
        "P0_post_update_sha256": sha256(p0_dump) if p0_dump.exists() else None,
        "P1_post_update_sha256": sha256(p1_dump) if p1_dump.exists() else None,
        "P0_topology_log": topology_log_lines(
            run_root / "p0_rank1" / "stdout.log"
        ),
        "P1_topology_log": topology_log_lines(
            run_root / "p1_rank2_xslab" / "stdout.log"
        ),
    }
    report = {
        "artifact_type": "C13_P15_STOCHASTIC_TOPOLOGY_DIAGNOSTIC",
        "stage": "C13/P15 Stage 0",
        "status": "PASS" if exact else "BLOCKED",
        "classification": "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE",
        "purpose": (
            "One-update pre-review diagnostic of the preregistered exact RNG "
            "and topology-event identity requirement across P0/P1 ownership."
        ),
        "seed": c13.SEED,
        "initial_network_sha256": network_sha,
        "generator_sha256": generator_sha,
        "cases": {
            "P0": {"mpi_ranks": 1, "box_array": [1, 1, 1],
                   "returncode": one.returncode},
            "P1": {"mpi_ranks": 2, "box_array": [2, 1, 1],
                   "returncode": two.returncode},
        },
        "particle_comparison": comparison,
        "topology_evidence": topology_evidence,
        "root_cause": {
            "observed": (
                "The same parent and one-update split predicate generated a "
                "different child stable key and different child geometry when "
                "particle ownership moved from MPI rank 0 to rank 1."
            ),
            "inherited_stream_initialization": (
                "src/setup/bmx_init.cpp resets AMReX with bmx.seed plus the "
                "current MPI rank plus one; frozen checkSplit/setNewSegment "
                "then consume that rank-local stream."
            ),
            "missing_binding": (
                "The numerical preregistration requires an exact RNG key/draw "
                "ledger but does not bind the stateless key tuple, key-to-seed "
                "hash/PRNG, draw domains/order, deterministic child-ID allocation, "
                "or checkpoint representation. Selecting those bytes would alter "
                "stochastic topology outcomes."
            ),
        },
        "diagnosis": (
            "Exact post-update state is invariant for this forced stochastic "
            "topology fixture."
            if exact else
            "The inherited per-rank AMReX stream does not satisfy the frozen "
            "cross-decomposition RNG/event identity requirement on this "
            "non-outcome fixture; source freeze must remain blocked pending a "
            "stateless canonical RNG/event implementation."
        ),
        "qualification_outcomes_enabled": False,
        "outcome_hours": 0,
        "external_resources": "none",
        "external_spend_usd": 0,
        "claim_boundary": (
            "Engineering diagnostic only; not independent review, a 216-hour "
            "qualification outcome, mentor approval, calibration, predictive "
            "validation, or P15 science."
        ),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "returncodes": [one.returncode, two.returncode],
        "particle_comparison": comparison,
    }, indent=2))
    # A diagnosed mismatch is the expected fail-closed result and is encoded
    # as BLOCKED evidence; return nonzero so automation cannot mistake it for
    # qualification PASS.
    return 0 if exact else 2


if __name__ == "__main__":
    raise SystemExit(main())
