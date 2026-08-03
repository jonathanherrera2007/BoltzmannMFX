#!/usr/bin/env python3
"""C13/P15 Stage 0 native graph, terminal, MPI, and restart qualification.

This driver is deliberately limited to short engineering fixtures.  It sets
``p15.qualification_outcomes_enabled=0`` in every successful case and includes
a negative test proving that the 216-hour gate rejects a pending review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from run_c08_checkpoint_tests import (
    compare_particle_ascii,
    parse_particle_ascii,
)
from run_c09_geometry_runtime import set_value


P11_CONTRACT = "bmx-p11-split-plate-geometry-v1"
P12_CONTRACT = "UDC-20260801-P12-UPTAKE-ONLY-V1"
P12_SHA = "2094aed3c8ef21a257d2c597352793384d01a1efc3d72936d5c5108d308f8804"
P13_CONTRACT = "bmx-p13-reaction-liebig-v1"
P13_SHA = "06f575a09b56178d74f809003fec532d6d3d509b972e62c29da21754cab0d26d"
P13_FIT = "bmx-p13-o02-fit-v1"
P13_FIT_SHA = "ea6e8dc2ca3f69fe2f366801c9df8ec9832b58f399d605c88d91527ff2098407"
P14_CONTRACT = "bmx-p14-export-reward-v1"
P14_SHA = "01a9d6eb7291cc8bc0c98f52afbf3c5ea1c86da4fd3f992a02665e283f81ff4e"
P14_FIT = "bmx-p14-o09-fit-v1"
P14_FIT_SHA = "72193a1034d4148d167f059c347053d2206fa580cce9a156ec705304e7f378e7"
P15_BINDING = "UDC-20260802-C13-STAGE0-BINDINGS-V1"
P15_BINDING_SHA = "c726cc575684e078d3c3359ececef28fde91daf5050aec273161b734710875d7"
P15_BONDED = "UDC-20260802-C13-BONDED-D-V1"
P15_BONDED_SHA = "e6022bffb56defa13cb31e7c0ac2097dfd197c9513e2f3e2e3a5ade37feeda44"
P15_NUMERICAL = "UDC-20260802-C13-216H-NUMERICAL-V1"
P15_NUMERICAL_SHA = "c4d8dd50bb9c4b2b945e80410d71c4b822a32b29a325d7bb9ca5a8ec53531182"
P15_TERMINAL = "UDC-20260802-C13-TERMINAL-ZONE-V1"
P15_TERMINAL_SHA = "272106fabb9af9221d13c9f3b82fa9a963bea831c0a983747986789452b1bfe6"
P15_FIT = "bmx-p15-c13-operator-fit-v1"
P15_FIT_SHA = "4e391b63796f61cade7381a0a4168c6aa2d607272cd0c009cedef5aec4ad7168"
KERNEL_SHA = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
ORDER_SHA = "bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6"
SEED = 2461941894568478670
PI = math.pi


@dataclass(frozen=True)
class Segment:
    x: float
    y: float
    z: float
    radius: float
    length: float
    theta: float
    phi: float
    free_caps: int


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def network_text(base: str, segments: list[Segment], *, area_scale: float = 1.0) -> str:
    source = base.splitlines()[1].split()[:27]
    if len(source) != 27:
        raise ValueError("base particle row is not the 27-field ASCII schema")
    rows: list[str] = []
    for segment in segments:
        fields = source.copy()
        area = (
            2.0 * PI * segment.radius * segment.length
            + PI * segment.radius**2 * segment.free_caps
        ) * area_scale
        volume = PI * segment.radius**2 * segment.length
        values = {
            0: segment.x,
            1: segment.y,
            2: segment.z,
            3: segment.radius,
            4: segment.length,
            5: segment.theta,
            6: segment.phi,
            7: area,
            8: volume,
            26: 1,
        }
        for index, value in values.items():
            fields[index] = str(value) if isinstance(value, int) else repr(value)
        for index in range(9, 26):
            fields[index] = "0"
        rows.append(" ".join(fields))
    return f"{len(rows)}\n" + "\n".join(rows) + "\n"


def chain_segments(count: int, *, length: float = 0.07,
                   radius: float = 5.0e-4) -> list[Segment]:
    start = -0.03
    child_length = length / count
    result = []
    for index in range(count):
        result.append(Segment(
            x=start + (index + 0.5) * child_length,
            y=0.05,
            z=0.9,
            radius=radius,
            length=child_length,
            theta=PI / 2.0,
            phi=0.0,
            free_caps=(1 if index == 0 else 0)
                      + (1 if index == count - 1 else 0),
        ))
    return result


def unequal_chain() -> list[Segment]:
    return [
        Segment(-0.015, 0.05, 0.9, 2.0e-4, 0.03, PI / 2.0, 0.0, 1),
        Segment(0.02, 0.05, 0.9, 4.0e-4, 0.04, PI / 2.0, 0.0, 1),
    ]


def branch_segments(degree: int) -> list[Segment]:
    if degree not in (3, 4):
        raise ValueError("branch fixture degree must be three or four")
    origin = (0.0, 0.05, 0.9)
    length = 0.012
    directions = [
        (1.0, 0.0, 0.0, PI / 2.0, 0.0),
        (-1.0, 0.0, 0.0, PI / 2.0, PI),
        (0.0, 0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, -1.0, PI, 0.0),
    ]
    result = []
    for index, (nx, ny, nz, theta, phi) in enumerate(directions[:degree]):
        result.append(Segment(
            origin[0] + 0.5 * length * nx,
            origin[1] + 0.5 * length * ny,
            origin[2] + 0.5 * length * nz,
            2.0e-4 * (index + 1),
            length,
            theta,
            phi,
            1,
        ))
    return result


def physical_areas(segments: list[Segment]) -> tuple[float, float]:
    full = 0.0
    for segment in segments:
        full += (
            2.0 * PI * segment.radius * segment.length
            + PI * segment.radius**2 * segment.free_caps
        )
    # This routine is used only for the straight equal-radius chain fixtures,
    # whose two outer free endpoints are the terminal origins.
    radius = segments[0].radius
    total_length = sum(segment.length for segment in segments)
    tip_length = min(total_length, 0.02)
    tip = 2.0 * PI * radius * tip_length
    if total_length > 0.02:
        tip += 2.0 * PI * radius**2
    else:
        tip += 2.0 * PI * radius**2
    return full, tip


def integrated_input(
    base: str,
    *,
    network_sha: str,
    generator_sha: str,
    diffusivity: float,
    dt: float = 0.125,
    j_max: float = 2.95949412514e-12,
    area_mode: str = "FULL_EXPOSED_EXTRARADICAL_SURFACE",
    area_match: tuple[float, float, float] = (0.0, 0.0, 0.0),
    cap_fault: bool = False,
    outcomes: bool = False,
    max_grid_x: int = 40,
) -> str:
    multiplier, full_area, tip_area = area_match
    values = {
        "bmx.seed": str(SEED),
        "bmx.fixed_dt": repr(dt),
        "bmx.substeps": "1",
        "amr.max_level": "0",
        "geometry.coord_sys": "0",
        "geometry.is_periodic": "0 1 0",
        "geometry.prob_lo": "-1.0 0.0 0.0",
        "geometry.prob_hi": "1.0 0.1 1.2",
        "amr.n_cell": "40 2 24",
        "amr.blocking_factor": "2",
        "amr.max_grid_size_x": str(max_grid_x),
        "amr.max_grid_size_y": "2",
        "amr.max_grid_size_z": "24",
        "amr.regrid_int": "-1",
        "bmx.tag_region": "false",
        "fluid.surface_location": "1.2",
        "fluid.chem_species": "A B C D F P_D P_F",
        "fluid.chem_species_diff": "0 0 0 0 0 5e-6 0",
        "fluid.init_conc_species": "0 0 0 0 0 1e-7 0",
        "chem_species.initial_particle_P": "0 0 0",
        "chem_species.k1": "0", "chem_species.kr1": "0",
        "chem_species.k2": "0", "chem_species.kr2": "0",
        "chem_species.k3": "0", "chem_species.kr3": "0",
        "chem_species.k4": "0", "chem_species.kr4": "0",
        "chem_species.k5": "0", "chem_species.kr5": "0",
        "chem_species.k6": "0", "chem_species.kr6": "0",
        "chem_species.k7": "0", "chem_species.kr7": "0",
        "chem_species.kP": "0", "chem_species.krP": "0",
        "chem_species.kg": "0", "chem_species.kv": "0",
        "chem_species.kb": "0", "chem_species.kbv": "0",
        "chem_species.mass_transfer_A": "0",
        "chem_species.mass_transfer_B": "0",
        "chem_species.mass_transfer_C": "0",
        "chem_species.mass_transfer_P": "0",
        "chem_species.p_growth_limit": "0",
        "chem_species.qP": "0",
        "chem_species.branching_probability": "0",
        "chem_species.splitting_probability": "0",
        "chem_species.fusion_probability": "0",
        "chem_species.max_vol": "1",
        "chem_species.max_seg_radius": "0.1",
        "chem_species.max_seg_length": "0.1",
        "chem_species.seg_split_length": "0.1",
        "chem_species.rg_frequency": "1000000",
        "cell_force.gravity": "0",
        "cell_force.fluctuation_scale": "0",
        "cell_force.fungi_stiffness": "0",
        "cell_force.fungi_wall_stiffness": "0",
        "cell_force.cell_stiffness": "0",
        "cell_force.cell_wall_stiffness": "0",
        "cell_force.viscous_drag": "1",
        "cell_force.neighbor_width": "0.01",
        "bmx.cnc_deposition_scheme": "one_to_one",
        "bmx.vf_deposition_scheme": "one_to_one",
        "diffusion.rtol": "1e-13",
        "diffusion.atol": "0",
        "diffusion.maxiter": "200",
        "p11_geometry.enabled": "1",
        "p11_geometry.schema_version": "1",
        "p11_geometry.contract_id": P11_CONTRACT,
        "p11_geometry.stage": "local_quasi_2d_interface",
        "p12.enabled": "1",
        "p12.contract": P12_CONTRACT,
        "p12.contract_sha256": P12_SHA,
        "p12.numerical_contract": P15_NUMERICAL,
        "p12.numerical_contract_sha256": P15_NUMERICAL_SHA,
        "p12.stage": "C13",
        "p12.network_sha256": network_sha,
        "p12.j_max": repr(j_max),
        "p12.k_m": "1.00084710414e-9",
        "p12.area_mode": area_mode,
        "p12.area_multiplier": repr(multiplier if area_mode == "TIP_010_AREA_MATCHED" else 1.0),
        "p13.enabled": "1",
        "p13.contract": P13_CONTRACT,
        "p13.contract_sha256": P13_SHA,
        "p13.operator_fit": P13_FIT,
        "p13.operator_fit_sha256": P13_FIT_SHA,
        "p13.stage": "C13",
        "p13.reactions_enabled": "0",
        "p13.growth_enabled": "0",
        "p13.k_de": "0",
        "p13.k_ed": "0",
        "p13.q_p": "0",
        "p13.k_gP_over_k_gB": "0",
        "p14.enabled": "1",
        "p14.contract": P14_CONTRACT,
        "p14.contract_sha256": P14_SHA,
        "p14.operator_fit": P14_FIT,
        "p14.operator_fit_sha256": P14_FIT_SHA,
        "p14.stage": "C13",
        "p14.interface_fraction": "continuous-finite-radius-axial-contact-v1",
        "p14.reward_molar_multiplier": "7.736",
        "p14.k_export": "0",
        "p15.enabled": "1",
        "p15.binding_contract": P15_BINDING,
        "p15.binding_contract_sha256": P15_BINDING_SHA,
        "p15.bonded_contract": P15_BONDED,
        "p15.bonded_contract_sha256": P15_BONDED_SHA,
        "p15.numerical_contract": P15_NUMERICAL,
        "p15.numerical_contract_sha256": P15_NUMERICAL_SHA,
        "p15.terminal_contract": P15_TERMINAL,
        "p15.terminal_contract_sha256": P15_TERMINAL_SHA,
        "p15.operator_fit": P15_FIT,
        "p15.operator_fit_sha256": P15_FIT_SHA,
        "p15.stage": "C13",
        "p15.bonded_d_diffusivity": repr(diffusivity),
        "p15.cap_fault_injection": "1" if cap_fault else "0",
        "p15.qualification_outcomes_enabled": "1" if outcomes else "0",
        "p15.initial_network_sha256": network_sha,
        "p15.generated_configuration_sha256": generator_sha,
        "p15.expected_area_match_multiplier": repr(multiplier),
        "p15.expected_initial_full_area": repr(full_area),
        "p15.expected_initial_tip010_area": repr(tip_area),
        "p15.independent_review_status": "PENDING",
        "p15.independent_review_sha256": "PENDING",
        "p15.reviewed_source_commit": "PENDING",
    }
    result = base
    for key, value in values.items():
        result = set_value(result, key, value)
    return result


def run_case(
    exe: Path,
    run_dir: Path,
    input_text: str,
    particle_text: str,
    *,
    steps: int,
    ranks: int,
    mpiexec: Path,
    check_int: int = -1,
    restart: Path | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input_fungi").write_text(input_text, encoding="utf-8")
    (run_dir / "fungi_init_cfg.dat").write_text(particle_text, encoding="utf-8")
    command = [] if ranks == 1 else [str(mpiexec), "-n", str(ranks)]
    command += [
        str(exe), "input_fungi", f"bmx.max_step={steps}",
        "amr.plot_int=-1", f"amr.check_int={check_int}",
        "amr.check_file=chk", "amr.par_ascii_int=1",
        "amr.par_ascii_file=par",
    ]
    if restart is not None:
        command.append(f"amr.restart={restart}")
    completed = subprocess.run(
        command, cwd=run_dir, capture_output=True, text=True, timeout=timeout
    )
    output = completed.stdout + completed.stderr
    (run_dir / "stdout.log").write_text(output, encoding="utf-8")
    (run_dir / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8"
    )
    return completed


def kv_rows(completed: subprocess.CompletedProcess[str], prefix: str) -> list[dict]:
    integer_fields = {
        "update", "segments", "live_terminal_origins", "internal_substeps",
        "virtual_pairs", "material_cap_activations", "particles",
        "eligible", "accepted_events", "donor_capped_events",
    }
    rows = []
    for line in (completed.stdout + completed.stderr).splitlines():
        if not line.startswith(prefix + " "):
            continue
        row: dict[str, float | int | str] = {}
        for token in line.split()[1:]:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            if key in integer_fields:
                row[key] = int(value)
            else:
                try:
                    row[key] = float(value)
                except ValueError:
                    row[key] = value
        rows.append(row)
    return rows


LEDGER_RE = re.compile(
    r"^P10_LEDGER boundary=(\S+).*?residual=(\S+) tolerance=(\S+)$",
    re.MULTILINE,
)


def p10_rows(completed: subprocess.CompletedProcess[str]) -> list[dict]:
    output = completed.stdout + completed.stderr
    return [
        {"boundary": match.group(1), "residual": float(match.group(2)),
         "tolerance": float(match.group(3))}
        for match in LEDGER_RE.finditer(output)
    ]


def successful(completed: subprocess.CompletedProcess[str], *, steps: int,
               expect_bonded: bool, expect_caps: bool = False,
               expect_initial_network: bool = True) -> dict:
    output = completed.stdout + completed.stderr
    terminal = kv_rows(completed, "P15_TERMINAL")
    bonded = kv_rows(completed, "P15_BONDED_D")
    uptake = kv_rows(completed, "P12_UPTAKE")
    reactions = kv_rows(completed, "P13_STEP")
    exports = kv_rows(completed, "P14_STEP")
    ledgers = p10_rows(completed)
    o10 = [row for row in ledgers if row["boundary"] == "O10_POST_UPDATE_LEDGER"]
    bonded_algebra = all(
        math.isclose(
            float(row["requested"]),
            float(row["accepted"]) + float(row["rejected"]),
            rel_tol=1e-12, abs_tol=1e-28,
        ) and math.isclose(
            float(row["accepted"]), float(row["gross_absolute_accepted"]),
            rel_tol=1e-12, abs_tol=1e-28,
        )
        for row in bonded
    )
    checks = {
        "exit_zero": completed.returncode == 0,
        "stage0_contract_bound": (
            f"binding_contract={P15_BINDING}" in output
            and "qualification_outcomes_enabled=0" in output
        ),
        "canonical_initial_network_count": output.count("P15_INITIAL_NETWORK ") == (
            1 if expect_initial_network else 0
        ),
        "terminal_once_per_o02": len(terminal) == steps,
        "terminal_areas_nested": len(terminal) == steps and all(
            0.0 <= float(row["physical_tip005_area"])
            <= float(row["physical_tip010_area"])
            <= float(row["physical_tip020_area"])
            <= float(row["physical_full_area"])
            for row in terminal
        ),
        "bonded_step_identity": (
            len(bonded) == steps if expect_bonded else len(bonded) == 0
        ),
        "bonded_ledger_algebra": bonded_algebra,
        "cap_expectation": (
            bool(bonded)
            and any(int(row["material_cap_activations"]) > 0 for row in bonded)
            and any(float(row["rejected"]) > 0.0 for row in bonded)
        ) if expect_caps else all(
            int(row["material_cap_activations"]) == 0
            and float(row["rejected"]) <= 1e-28 for row in bonded
        ),
        "integrated_operator_records": (
            len(uptake) == steps and len(reactions) == steps
            and len(exports) == steps
        ),
        "p10_o10_once_per_step": len(o10) == steps,
        "global_p_conservation": len(o10) == steps and all(
            abs(float(row["residual"])) <= float(row["tolerance"])
            for row in o10
        ),
        "frozen_order_reported_unchanged": (
            f"global_order_sha256={ORDER_SHA}" in output
            and "global_order_changed=0" in output
            and "frozen_kernel_changed=0" in output
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "terminal": terminal,
        "bonded": bonded,
        "uptake": uptake,
        "reactions": reactions,
        "exports": exports,
        "p10": ledgers,
        "returncode": completed.returncode,
    }


def rejected(completed: subprocess.CompletedProcess[str], token: str,
             *, no_uptake: bool = True) -> dict:
    output = completed.stdout + completed.stderr
    checks = {
        "exit_nonzero": completed.returncode != 0,
        "expected_reason": token in output,
        "pre_amount_mutation": not no_uptake or "P12_UPTAKE " not in output,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "expected_token": token,
        "returncode": completed.returncode,
    }


def final_bonded(case: dict) -> dict | None:
    return case["bonded"][-1] if case.get("bonded") else None


def equivalent_ledgers(first: dict, second: dict) -> bool:
    left = final_bonded(first)
    right = final_bonded(second)
    if left is None or right is None:
        return False
    keys = (
        "cumulative_requested", "cumulative_accepted",
        "cumulative_rejected", "cumulative_gross_absolute_accepted",
        "maximum_diagonal_rate", "minimum_donor_scale",
    )
    return all(
        math.isclose(float(left[key]), float(right[key]),
                     rel_tol=1e-12, abs_tol=1e-28)
        for key in keys
    )


def copy_mutate_checkpoint(source: Path, target: Path) -> None:
    shutil.copytree(source, target)
    header = target / "Header"
    text = header.read_text(encoding="utf-8")
    if P15_BONDED_SHA not in text:
        raise RuntimeError("checkpoint does not contain the P15 bonded hash")
    header.write_text(text.replace(P15_BONDED_SHA, "0" * 64, 1), encoding="utf-8")


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
    root = args.run_root.resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    base_input = (source / "exec/fungi/input_fungi").read_text(encoding="utf-8")
    base_particle = (source / "exec/fungi/fungi_init_cfg.dat").read_text(
        encoding="utf-8"
    )
    generator_sha = sha256(Path(__file__).resolve())
    cases: dict[str, dict] = {}

    unequal = network_text(base_particle, unequal_chain())
    unequal_sha = hashlib.sha256(unequal.encode()).hexdigest()
    main_input = integrated_input(
        base_input, network_sha=unequal_sha, generator_sha=generator_sha,
        diffusivity=1.25e-6,
    )
    continuous = run_case(
        exe, root / "continuous_rank1", main_input, unequal,
        steps=4, ranks=1, mpiexec=args.mpiexec.resolve(), check_int=2,
    )
    cases["continuous_rank1"] = successful(
        continuous, steps=4, expect_bonded=True
    )
    rank2 = run_case(
        exe, root / "continuous_rank2", main_input, unequal,
        steps=4, ranks=2, mpiexec=args.mpiexec.resolve(), check_int=2,
    )
    cases["continuous_rank2"] = successful(rank2, steps=4, expect_bonded=True)
    decomposition_input = integrated_input(
        base_input, network_sha=unequal_sha, generator_sha=generator_sha,
        diffusivity=1.25e-6, max_grid_x=20,
    )
    decomposition = run_case(
        exe, root / "decomposition_rank2", decomposition_input, unequal,
        steps=4, ranks=2, mpiexec=args.mpiexec.resolve(),
    )
    cases["decomposition_rank2"] = successful(
        decomposition, steps=4, expect_bonded=True
    )

    checkpoint1 = root / "continuous_rank1" / "chk00002"
    restart11 = run_case(
        exe, root / "restart_1_to_1", main_input, unequal,
        steps=4, ranks=1, mpiexec=args.mpiexec.resolve(), restart=checkpoint1,
    )
    cases["restart_1_to_1"] = successful(
        restart11, steps=2, expect_bonded=True, expect_initial_network=False
    )
    checkpoint2 = root / "continuous_rank2" / "chk00002"
    restart21 = run_case(
        exe, root / "restart_2_to_1", main_input, unequal,
        steps=4, ranks=1, mpiexec=args.mpiexec.resolve(), restart=checkpoint2,
    )
    cases["restart_2_to_1"] = successful(
        restart21, steps=2, expect_bonded=True, expect_initial_network=False
    )

    mutation_checkpoint = root / "mutated_p15_checkpoint"
    if checkpoint1.exists():
        copy_mutate_checkpoint(checkpoint1, mutation_checkpoint)
        mutation = run_case(
            exe, root / "checkpoint_contract_mutation", main_input, unequal,
            steps=4, ranks=1, mpiexec=args.mpiexec.resolve(),
            restart=mutation_checkpoint,
        )
        cases["checkpoint_contract_mutation"] = rejected(
            mutation,
            "P15 contract, review, configuration, or parameter identity mismatch",
        )
    else:
        cases["checkpoint_contract_mutation"] = {
            "status": "FAIL", "checks": {"checkpoint_exists": False}
        }

    for degree in (3, 4):
        particle = network_text(base_particle, branch_segments(degree))
        network_sha = hashlib.sha256(particle.encode()).hexdigest()
        branch_input = integrated_input(
            base_input, network_sha=network_sha, generator_sha=generator_sha,
            diffusivity=1.25e-6,
        )
        completed = run_case(
            exe, root / f"degree_{degree}_junction", branch_input, particle,
            steps=1, ranks=1, mpiexec=args.mpiexec.resolve(),
        )
        case = successful(completed, steps=1, expect_bonded=True)
        expected_pairs = degree * (degree - 1) // 2
        case["checks"]["junction_elimination_pair_count"] = bool(case["bonded"]) and (
            int(case["bonded"][0]["virtual_pairs"]) == expected_pairs
        )
        case["checks"]["same_basal_site_tips_preserved"] = bool(case["terminal"]) and (
            int(case["terminal"][0]["live_terminal_origins"]) == degree
        )
        case["status"] = "PASS" if all(case["checks"].values()) else "FAIL"
        cases[f"degree_{degree}_junction"] = case

    refinement_values = []
    for count in (1, 2, 4, 8):
        segments = chain_segments(count)
        particle = network_text(base_particle, segments)
        network_sha = hashlib.sha256(particle.encode()).hexdigest()
        full, tip = physical_areas(segments)
        multiplier = full / tip
        fixture_input = integrated_input(
            base_input, network_sha=network_sha, generator_sha=generator_sha,
            diffusivity=0.0, j_max=0.0,
            area_mode="TIP_010_AREA_MATCHED",
            area_match=(multiplier, full, tip),
        )
        completed = run_case(
            exe, root / f"refinement_{count}", fixture_input, particle,
            steps=1, ranks=1, mpiexec=args.mpiexec.resolve(),
        )
        case = successful(completed, steps=1, expect_bonded=False)
        cases[f"refinement_{count}"] = case
        if case["terminal"]:
            refinement_values.append({
                "count": count,
                "full": float(case["terminal"][0]["physical_full_area"]),
                "tip010": float(case["terminal"][0]["physical_tip010_area"]),
                "effective": float(case["terminal"][0]["effective_uptake_area"]),
                "multiplier": multiplier,
            })
    refinement_invariant = len(refinement_values) == 4 and all(
        math.isclose(row[key], refinement_values[0][key],
                     rel_tol=1e-12, abs_tol=1e-28)
        for row in refinement_values[1:]
        for key in ("full", "tip010", "effective", "multiplier")
    )

    zero_particle = network_text(base_particle, unequal_chain())
    zero_sha = hashlib.sha256(zero_particle.encode()).hexdigest()
    zero_input = integrated_input(
        base_input, network_sha=zero_sha, generator_sha=generator_sha,
        diffusivity=0.0, j_max=0.0,
    )
    zero_run = run_case(
        exe, root / "zero_diffusivity_identity", zero_input, zero_particle,
        steps=2, ranks=1, mpiexec=args.mpiexec.resolve(), check_int=1,
    )
    zero_case = successful(zero_run, steps=2, expect_bonded=False)
    zero_dump = root / "zero_diffusivity_identity" / "par00002"
    if zero_dump.exists():
        parsed = parse_particle_ascii(zero_dump)
        d_concentrations = [record["floats"][3 + 28 + 5]
                            for record in parsed["records"].values()]
    else:
        d_concentrations = []
    zero_header = root / "zero_diffusivity_identity" / "chk00001" / "Header"
    zero_header_text = zero_header.read_text(encoding="utf-8") if zero_header.exists() else ""
    zero_case["checks"]["D_amounts_exact_zero"] = bool(d_concentrations) and all(
        value == 0.0 for value in d_concentrations
    )
    zero_case["checks"]["transport_ledger_exactly_untouched"] = (
        "p15_bonded_updates 0" in zero_header_text
        and "p15_bonded_cumulative_requested 0" in zero_header_text
        and "p15_bonded_cumulative_accepted 0" in zero_header_text
    )
    zero_case["status"] = "PASS" if all(zero_case["checks"].values()) else "FAIL"
    cases["zero_diffusivity_identity"] = zero_case

    cap_input = integrated_input(
        base_input, network_sha=unequal_sha, generator_sha=generator_sha,
        diffusivity=1.25e-5, dt=100.0, cap_fault=True,
    )
    cap_run = run_case(
        exe, root / "proportional_cap_fault", cap_input, unequal,
        steps=1, ranks=1, mpiexec=args.mpiexec.resolve(),
    )
    cases["proportional_cap_fault"] = successful(
        cap_run, steps=1, expect_bonded=True, expect_caps=True
    )

    bad_area = network_text(base_particle, unequal_chain(), area_scale=1.1)
    bad_area_sha = hashlib.sha256(bad_area.encode()).hexdigest()
    bad_area_input = integrated_input(
        base_input, network_sha=bad_area_sha, generator_sha=generator_sha,
        diffusivity=1.25e-6,
    )
    bad_area_run = run_case(
        exe, root / "invalid_stored_area", bad_area_input, bad_area,
        steps=1, ranks=1, mpiexec=args.mpiexec.resolve(),
    )
    cases["invalid_stored_area"] = rejected(
        bad_area_run, "stored/computed full-area mismatch"
    )

    invalid_segments = unequal_chain()
    invalid_segments[0] = Segment(
        invalid_segments[0].x, invalid_segments[0].y, invalid_segments[0].z,
        0.0, invalid_segments[0].length, invalid_segments[0].theta,
        invalid_segments[0].phi, invalid_segments[0].free_caps,
    )
    invalid_particle = network_text(base_particle, invalid_segments)
    invalid_sha = hashlib.sha256(invalid_particle.encode()).hexdigest()
    invalid_input = integrated_input(
        base_input, network_sha=invalid_sha, generator_sha=generator_sha,
        diffusivity=1.25e-6,
    )
    invalid_run = run_case(
        exe, root / "invalid_geometry", invalid_input, invalid_particle,
        steps=1, ranks=1, mpiexec=args.mpiexec.resolve(),
    )
    cases["invalid_geometry"] = rejected(
        invalid_run, "initial fungal geometry is nonfinite or nonpositive"
    )

    pending_input = integrated_input(
        base_input, network_sha=unequal_sha, generator_sha=generator_sha,
        diffusivity=1.25e-6, outcomes=True,
    )
    pending_run = run_case(
        exe, root / "independent_review_gate", pending_input, unequal,
        steps=1, ranks=1, mpiexec=args.mpiexec.resolve(),
    )
    cases["independent_review_gate"] = rejected(
        pending_run,
        "216-hour qualification outcomes remain prohibited pending a hash-bound independent PASS review",
    )

    particle_mpi = (
        compare_particle_ascii(
            root / "continuous_rank1" / "par00004",
            root / "continuous_rank2" / "par00004",
        ) if (root / "continuous_rank1" / "par00004").exists()
        and (root / "continuous_rank2" / "par00004").exists()
        else {"status": "FAIL", "reason": "missing MPI dump"}
    )
    particle_decomposition = (
        compare_particle_ascii(
            root / "continuous_rank2" / "par00004",
            root / "decomposition_rank2" / "par00004",
        ) if (root / "continuous_rank2" / "par00004").exists()
        and (root / "decomposition_rank2" / "par00004").exists()
        else {"status": "FAIL", "reason": "missing decomposition dump"}
    )
    particle_restart11 = (
        compare_particle_ascii(
            root / "continuous_rank1" / "par00004",
            root / "restart_1_to_1" / "par00004",
        ) if (root / "restart_1_to_1" / "par00004").exists()
        else {"status": "FAIL", "reason": "missing 1-to-1 restart dump"}
    )
    particle_restart21 = (
        compare_particle_ascii(
            root / "continuous_rank1" / "par00004",
            root / "restart_2_to_1" / "par00004",
        ) if (root / "restart_2_to_1" / "par00004").exists()
        else {"status": "FAIL", "reason": "missing 2-to-1 restart dump"}
    )
    equivalence = {
        "mpi_rank1_rank2": {
            "particle": particle_mpi,
            "bonded_ledger": equivalent_ledgers(
                cases["continuous_rank1"], cases["continuous_rank2"]),
        },
        "decomposition": {
            "particle": particle_decomposition,
            "bonded_ledger": equivalent_ledgers(
                cases["continuous_rank2"], cases["decomposition_rank2"]),
        },
        "restart_1_to_1": {
            "particle": particle_restart11,
            "bonded_ledger": equivalent_ledgers(
                cases["continuous_rank1"], cases["restart_1_to_1"]),
        },
        "restart_2_to_1": {
            "particle": particle_restart21,
            "bonded_ledger": equivalent_ledgers(
                cases["continuous_rank1"], cases["restart_2_to_1"]),
        },
    }
    equivalence_pass = all(
        item["particle"]["status"] == "PASS" and item["bonded_ledger"]
        for item in equivalence.values()
    )
    overall = (
        all(case["status"] == "PASS" for case in cases.values())
        and refinement_invariant and equivalence_pass
    )
    record = {
        "artifact_type": "C13_P15_STAGE0_NATIVE_ENGINEERING_RUNTIME",
        "stage": "C13/P15 Stage 0",
        "status": "PASS" if overall else "FAIL",
        "classification": "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE",
        "cases": cases,
        "refinement": {
            "status": "PASS" if refinement_invariant else "FAIL",
            "values": refinement_values,
            "scope": "geometry-preserving 1-to-2, 1-to-4, and 1-to-8 only",
            "transient_particle_identity_claimed": False,
        },
        "equivalence": equivalence,
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "generator_sha256": generator_sha,
        "fixture_network_sha256": unequal_sha,
        "contracts": {
            "binding": P15_BINDING_SHA,
            "bonded": P15_BONDED_SHA,
            "numerical": P15_NUMERICAL_SHA,
            "terminal": P15_TERMINAL_SHA,
            "operator_fit": P15_FIT_SHA,
        },
        "frozen_kernel_sha256": sha256(source / "src/chemistry/bmx_chem_K.H"),
        "global_order_sha256": sha256(source / "contracts/p10/OPERATOR_ORDER_V1.json"),
        "expected_frozen_hashes": {"kernel": KERNEL_SHA, "order": ORDER_SHA},
        "outcome_hours": 0,
        "qualification_outcomes_executed": False,
        "independent_review_gate_crossed": False,
        "external_resources": "none",
        "external_spend_usd": 0,
        "claim_boundary": "Short C13 Stage 0 RG-SW engineering qualification only; not a 216-hour outcome, mentor approval, calibration, predictive validation, or P15 science.",
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": record["status"],
        "cases": {name: case["status"] for name, case in cases.items()},
        "refinement": record["refinement"]["status"],
        "equivalence": equivalence_pass,
    }, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
