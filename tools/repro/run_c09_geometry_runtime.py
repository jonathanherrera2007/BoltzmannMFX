#!/usr/bin/env python3
"""C09 enabled-geometry runtime, decomposition, extent, and rejection tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path


CONTRACT_ID = "bmx-p11-split-plate-geometry-v1"
EVENT_RE = re.compile(
    r"^P11_GEOMETRY_EVENTS contract=(\S+) update_id=(\d+) "
    r"window_contact=(\d+) true_crossing=(\d+) solid_contact=(\d+) "
    r"contact_id_checksum=(-?\d+) attempted_penetration=(\d+) "
    r"projected_motion=(\d+) tangential_motion=(\d+) "
    r"rejected_growth=(\d+)$",
    re.MULTILINE,
)
MASK_RE = re.compile(
    r"^P11_DIVIDER_MASK level=(\d+) masked_faces=(\d+) "
    r"nonzero_faces=(\d+)$",
    re.MULTILINE,
)


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


def geometry_input(
    base: str,
    *,
    xlo: float = -1.0,
    xhi: float = 1.0,
    nx: int = 40,
    max_level: int = 0,
) -> str:
    result = base
    values = {
        "bmx.fixed_dt": "1.0e-5",
        "bmx.substeps": "1",
        "amr.max_level": str(max_level),
        "geometry.coord_sys": "0",
        "geometry.is_periodic": "0 1 0",
        "geometry.prob_lo": f"{xlo:.17g} 0.0 0.0",
        "geometry.prob_hi": f"{xhi:.17g} 0.1 1.2",
        "amr.n_cell": f"{nx} 2 24",
        "amr.blocking_factor": "2",
        "amr.max_grid_size_x": "40",
        "amr.max_grid_size_y": "2",
        "amr.max_grid_size_z": "24",
        "bmx.tag_region": "true" if max_level else "false",
        # The inherited tagger evaluates index*dx without prob_lo.  These
        # coordinates deliberately compensate for that known legacy behavior
        # so the C09 AMR fixture actually refines the x=0 divider.
        "bmx.tag_region_lo": "0.9 0.0 0.75",
        "bmx.tag_region_hi": "1.1 0.1 1.05",
        "fluid.surface_location": "1.2",
        "fluid.chem_species": "A B C D F P_D P_F",
        # P_D is deliberately nonzero in this engineering fixture so the
        # production divider-mask check cannot pass merely because its input
        # coefficient was already zero.  Inactive P_F remains exactly zero.
        "fluid.chem_species_diff": "6.0e-10 0.0 6.0e-10 6.0e-10 0.0 6.0e-10 0.0",
        "fluid.init_conc_species": "2.0e-5 0.0 2.0e-6 2.0e-5 0.0 0.0 0.0",
        "chem_species.initial_particle_P": "2.0e-5 3.0e-5 5.0e-5",
        "chem_species.kP": "0.0",
        "chem_species.krP": "0.0",
        "chem_species.mass_transfer_P": "0.0",
        "chem_species.p_growth_limit": "0.0",
        "chem_species.kv": "0.0",
        "chem_species.branching_probability": "0.0",
        "chem_species.splitting_probability": "0.0",
        "chem_species.fusion_probability": "0.0",
        "chem_species.max_seg_length": "0.2",
        "chem_species.seg_split_length": "0.2",
        "chem_species.rg_frequency": "1000",
        "cell_force.gravity": "0.0",
        "cell_force.fluctuation_scale": "0.0",
        "p11_geometry.enabled": "1",
        "p11_geometry.schema_version": "1",
        "p11_geometry.contract_id": CONTRACT_ID,
        "p11_geometry.stage": "local_quasi_2d_interface",
    }
    for key, value in values.items():
        result = set_value(result, key, value)
    return result


def particle_fixture(
    base: str,
    *,
    x: float = 0.0,
    y: float = 0.05,
    z: float = 0.9,
    radius: float = 0.001,
    length: float = 0.102,
    theta: float = math.pi / 2.0,
    phi: float = 0.0,
    cell_type: int = 1,
) -> str:
    lines = base.splitlines()
    if len(lines) != 2 or int(lines[0].strip()) != 1:
        raise ValueError("C09 fixture requires exactly one ASCII input particle")
    fields = lines[1].split()
    if len(fields) < 27:
        raise ValueError("C09 particle fixture has too few fields")
    if cell_type == 0:
        volume = (4.0 / 3.0) * math.pi * radius**3
        area = 4.0 * math.pi * radius**2
    else:
        volume = math.pi * radius * radius * length
        area = 2.0 * math.pi * radius * length + 2.0 * math.pi * radius * radius
    replacements = {
        0: x,
        1: y,
        2: z,
        3: radius,
        4: length,
        5: theta,
        6: phi,
        7: area,
        8: volume,
        26: cell_type,
    }
    for index, value in replacements.items():
        fields[index] = str(value) if isinstance(value, int) else f"{value:.17g}"
    for index in range(9, 26):
        fields[index] = "0.0"
    return "1\n" + " ".join(fields) + "\n"


def run_case(
    exe: Path,
    run_dir: Path,
    input_text: str,
    particle_text: str,
    timeout: int,
    *,
    max_step: int = 1,
    check_int: int = -1,
    restart: str | None = None,
    launcher: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input_fungi").write_text(input_text, encoding="utf-8")
    (run_dir / "fungi_init_cfg.dat").write_text(particle_text, encoding="utf-8")
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
    output = completed.stdout + completed.stderr
    (run_dir / "stdout.log").write_text(output, encoding="utf-8")
    (run_dir / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8"
    )
    return completed


def event_rows(completed: subprocess.CompletedProcess[str]) -> list[dict]:
    output = completed.stdout + completed.stderr
    rows = []
    for match in EVENT_RE.finditer(output):
        rows.append({
            "contract": match.group(1),
            "update_id": int(match.group(2)),
            "window_contact": int(match.group(3)),
            "true_crossing": int(match.group(4)),
            "solid_contact": int(match.group(5)),
            "contact_id_checksum": int(match.group(6)),
            "attempted_penetration": int(match.group(7)),
            "projected_motion": int(match.group(8)),
            "tangential_motion": int(match.group(9)),
            "rejected_growth": int(match.group(10)),
            "line": match.group(0),
        })
    return rows


def mask_rows(completed: subprocess.CompletedProcess[str]) -> list[dict]:
    output = completed.stdout + completed.stderr
    return [
        {
            "level": int(match.group(1)),
            "masked_faces": int(match.group(2)),
            "nonzero_faces": int(match.group(3)),
            "line": match.group(0),
        }
        for match in MASK_RE.finditer(output)
    ]


def valid_case_row(
    completed: subprocess.CompletedProcess[str], run_dir: Path,
    *, expected_level_one: bool = False,
) -> dict:
    output = completed.stdout + completed.stderr
    rows = event_rows(completed)
    masks = mask_rows(completed)
    required_mask_levels = {0, 1} if expected_level_one else {0}
    observed_positive_mask_levels = {
        row["level"] for row in masks if row["masked_faces"] > 0
    }
    checks = {
        "exit_zero": completed.returncode == 0,
        "one_update_event": len(rows) == 1,
        "contract_exact": len(rows) == 1 and rows[0]["contract"] == CONTRACT_ID,
        "contact_once": len(rows) == 1 and rows[0]["window_contact"] == 1,
        "crossing_once": len(rows) == 1 and rows[0]["true_crossing"] == 1,
        "no_solid_contact": len(rows) == 1 and rows[0]["solid_contact"] == 0,
        "motion_counters_present_and_zero_for_static_fixture": (
            len(rows) == 1
            and rows[0]["attempted_penetration"] == 0
            and rows[0]["projected_motion"] == 0
            and rows[0]["tangential_motion"] == 0
            and rows[0]["rejected_growth"] == 0
        ),
        "no_p11_abort": "P11 particle geometry rejected" not in output
        and "P11 geometry configuration rejected" not in output,
        "required_amr_level_exercised": (
            not expected_level_one
            or (
                "MLMG: # of AMR levels: 2" in output
                and "In Evolve Particles with 1 particles at level 1" in output
            )
        ),
        "production_divider_faces_masked": (
            required_mask_levels.issubset(observed_positive_mask_levels)
            and bool(masks)
            and all(row["nonzero_faces"] == 0 for row in masks)
        ),
    }
    return {
        "exit_code": completed.returncode,
        "events": rows,
        "divider_masks": masks,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "log": str(run_dir / "stdout.log"),
    }


def motion_case_row(
    completed: subprocess.CompletedProcess[str],
    run_dir: Path,
    *,
    expected_solid_contact: int,
    expected_tangential_motion: int,
) -> dict:
    output = completed.stdout + completed.stderr
    rows = event_rows(completed)
    masks = mask_rows(completed)
    event = rows[0] if len(rows) == 1 else None
    checks = {
        "exit_zero": completed.returncode == 0,
        "one_update_event": len(rows) == 1,
        "contract_exact": event is not None and event["contract"] == CONTRACT_ID,
        "projection_exercised_once": (
            event is not None
            and event["attempted_penetration"] == 1
            and event["projected_motion"] == 1
        ),
        "expected_tangential_motion": (
            event is not None
            and event["tangential_motion"] == expected_tangential_motion
        ),
        "expected_final_solid_contact": (
            event is not None
            and event["solid_contact"] == expected_solid_contact
        ),
        "no_interface_event": (
            event is not None
            and event["window_contact"] == 0
            and event["true_crossing"] == 0
            and event["contact_id_checksum"] == 0
        ),
        "no_growth_side_effect": (
            event is not None and event["rejected_growth"] == 0
        ),
        "production_divider_faces_masked": (
            any(row["level"] == 0 and row["masked_faces"] > 0 for row in masks)
            and all(row["nonzero_faces"] == 0 for row in masks)
        ),
        "no_p11_abort": "P11 particle geometry rejected" not in output
        and "P11 geometry configuration rejected" not in output,
    }
    return {
        "exit_code": completed.returncode,
        "events": rows,
        "divider_masks": masks,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "log": str(run_dir / "stdout.log"),
    }


def invalid_case_row(
    completed: subprocess.CompletedProcess[str], run_dir: Path, expected: str
) -> dict:
    output = completed.stdout + completed.stderr
    checks = {
        "exit_nonzero": completed.returncode != 0,
        "clear_reason": expected in output,
        "no_geometry_event_committed": not event_rows(completed),
    }
    return {
        "exit_code": completed.returncode,
        "expected_token": expected,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "log": str(run_dir / "stdout.log"),
    }


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
    crossing_particle = particle_fixture(particle_base)
    launcher_2 = [str(mpiexec), "-n", "2"]

    valid_rows = {}
    valid_specs = [
        ("central_rank1", -1.0, 1.0, 40, 0, None),
        ("central_rank2", -1.0, 1.0, 40, 0, launcher_2),
        ("central_amr_rank2", -1.0, 1.0, 40, 1, launcher_2),
        ("small_rank1", -0.5, 0.5, 20, 0, None),
        ("large_rank1", -2.0, 2.0, 80, 0, None),
    ]
    for case_id, xlo, xhi, nx, max_level, launcher in valid_specs:
        run_dir = run_root / case_id
        completed = run_case(
            exe,
            run_dir,
            geometry_input(base, xlo=xlo, xhi=xhi, nx=nx, max_level=max_level),
            crossing_particle,
            args.timeout,
            launcher=launcher,
        )
        valid_rows[case_id] = valid_case_row(
            completed, run_dir, expected_level_one=max_level == 1
        )

    rank1_events = valid_rows["central_rank1"]["events"]
    rank2_events = valid_rows["central_rank2"]["events"]
    amr_events = valid_rows["central_amr_rank2"]["events"]
    decomposition_checks = {
        "rank1_rank2_exact_event_identity": rank1_events == rank2_events,
        "level0_level1_exact_event_identity": rank2_events == amr_events,
    }

    enabled = geometry_input(base)
    # These are deterministic engineering branch-forcing values, not physical
    # or biological settings.  They make the inherited z-force propose a hard
    # boundary violation in one update so the production projection path—not
    # only the pure predicate—must execute and report its outcome.
    motion_specs = [
        (
            "internal_frame_tangential_slide",
            set_value(enabled, "cell_force.gravity", "20000.0"),
            particle_fixture(
                particle_base, x=0.07, z=0.811, length=0.02, radius=0.01
            ),
            1,
            1,
        ),
        (
            "outer_z_projection",
            set_value(enabled, "cell_force.gravity", "1000000.0"),
            particle_fixture(
                particle_base, x=0.2, z=0.001, length=0.1, radius=0.001
            ),
            0,
            0,
        ),
    ]
    motion_rows = {}
    for (
        case_id,
        input_text,
        particle_text,
        expected_solid_contact,
        expected_tangential_motion,
    ) in motion_specs:
        run_dir = run_root / case_id
        completed = run_case(
            exe, run_dir, input_text, particle_text, args.timeout
        )
        motion_rows[case_id] = motion_case_row(
            completed,
            run_dir,
            expected_solid_contact=expected_solid_contact,
            expected_tangential_motion=expected_tangential_motion,
        )

    invalid_specs: list[tuple[str, str, str, str]] = []
    invalid_specs.append((
        "wrong_contract",
        set_value(enabled, "p11_geometry.contract_id", "wrong-contract"),
        crossing_particle,
        "contract_id mismatch",
    ))
    invalid_specs.append((
        "wrong_stage",
        set_value(enabled, "p11_geometry.stage", "full_plate"),
        crossing_particle,
        "stage must be local_quasi_2d_interface",
    ))
    invalid_specs.append((
        "wrong_periodicity",
        set_value(enabled, "geometry.is_periodic", "0 0 0"),
        crossing_particle,
        "periodicity must be nonperiodic x/z and periodic y",
    ))
    invalid_specs.append((
        "unapproved_domain",
        geometry_input(base, xlo=-0.75, xhi=0.75, nx=30),
        crossing_particle,
        "x domain is not an approved central/sensitivity extent",
    ))
    invalid_specs.append((
        "misaligned_grid",
        geometry_input(base, nx=42),
        crossing_particle,
        "is not grid-face aligned",
    ))
    wrong_mesh = set_value(enabled, "fluid.chem_species", "A B C D F P")
    wrong_mesh = set_value(
        wrong_mesh,
        "fluid.chem_species_diff",
        "6.0e-10 0.0 6.0e-10 6.0e-10 0.0 0.0",
    )
    wrong_mesh = set_value(
        wrong_mesh,
        "fluid.init_conc_species",
        "2.0e-5 0.0 2.0e-6 2.0e-5 0.0 0.0",
    )
    invalid_specs.append((
        "wrong_mesh_layout",
        wrong_mesh,
        crossing_particle,
        "requires the exact three-state mesh layout",
    ))
    invalid_specs.append((
        "fungus_embedded_in_solid_frame",
        enabled,
        particle_fixture(particle_base, x=0.0, z=0.4, length=0.02),
        "P11 particle geometry rejected",
    ))
    invalid_specs.append((
        "nonfungus_in_aperture",
        enabled,
        particle_fixture(
            particle_base, x=0.0, z=0.9, length=0.0, cell_type=0
        ),
        "P11 particle geometry rejected",
    ))

    invalid_rows = {}
    for case_id, input_text, particle_text, expected in invalid_specs:
        run_dir = run_root / case_id
        completed = run_case(
            exe, run_dir, input_text, particle_text, args.timeout
        )
        invalid_rows[case_id] = invalid_case_row(completed, run_dir, expected)

    passed = (
        all(row["status"] == "PASS" for row in valid_rows.values())
        and all(decomposition_checks.values())
        and all(row["status"] == "PASS" for row in motion_rows.values())
        and all(row["status"] == "PASS" for row in invalid_rows.values())
    )
    report = {
        "artifact_type": "C09_GEOMETRY_RUNTIME_TEST",
        "stage": "C09/P11",
        "status": "PASS" if passed else "FAIL",
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "mpi": {"mpiexec": str(mpiexec), "decomposition_ranks": [1, 2]},
        "valid_cases": valid_rows,
        "decomposition_checks": decomposition_checks,
        "motion_cases": motion_rows,
        "engineering_runtime_overrides": {
            "internal_frame_tangential_slide_gravity": 20000.0,
            "outer_z_projection_gravity": 1000000.0,
            "p_d_diffusion_cm2_per_s": 6e-10,
            "p_f_diffusion_cm2_per_s": 0.0,
            "interpretation": (
                "deterministic branch-forcing values only; not biological or "
                "physical research settings"
            ),
        },
        "invalid_cases": invalid_rows,
        "method": (
            "Run the exact enabled C09 contract on all three approved x extents, "
            "one and two MPI ranks, and level-zero/level-one meshes; count one final "
            "finite-radius fungal aperture contact/crossing per update; mask a "
            "nonzero P_D face coefficient while P_F remains inactive; force the "
            "production internal-frame tangential-slide and outer-wall projection "
            "paths; then exercise contract, stage, periodicity, domain, grid-alignment, "
            "mesh-layout, and embedded-particle fail-closed paths."
        ),
        "claim_boundary": (
            "Windows CPU engineering qualification; not a calibrated biological "
            "claim, release-host evidence, or independent numerical review."
        ),
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "valid": {key: row["status"] for key, row in valid_rows.items()},
        "decomposition_checks": decomposition_checks,
        "motion": {key: row["status"] for key, row in motion_rows.items()},
        "invalid": {key: row["status"] for key, row in invalid_rows.items()},
        "json_out": str(json_out),
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
