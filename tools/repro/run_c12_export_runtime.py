#!/usr/bin/env python3
"""C12/P14 native geometry, export, MPI, and restart qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from run_c09_geometry_runtime import (
    geometry_input,
    particle_fixture,
    run_case,
    set_value,
)


CONTRACT_ID = "bmx-p14-export-reward-v1"
CONTRACT_SHA = "01a9d6eb7291cc8bc0c98f52afbf3c5ea1c86da4fd3f992a02665e283f81ff4e"
FIT_ID = "bmx-p14-o09-fit-v1"
FIT_SHA = "72193a1034d4148d167f059c347053d2206fa580cce9a156ec705304e7f378e7"
KERNEL_SHA = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
ORDER_SHA = "bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6"
MULTIPLIER = 7.736
RATES = [0.0, 1.0e-6, 5.26977773579e-6, 1.0e-5, 1.0e-4]
LEDGER_RE = re.compile(
    r"^P10_LEDGER boundary=(\S+) reference_bound=\d+ reference_total=(\S+) "
    r"mesh_D=(\S+) mesh_F=(\S+) internal_D=(\S+) "
    r"internal_E=(\S+) internal_F=(\S+) accounted=(\S+) "
    r"residual=(\S+) tolerance=(\S+)$",
    re.MULTILINE,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def p14_input(base: str, *, rate: float, dt: float = 100.0,
              max_grid_x: int = 20) -> str:
    result = geometry_input(base, nx=40)
    values = {
        "bmx.fixed_dt": f"{dt:.17g}",
        "bmx.substeps": "1",
        "amr.max_grid_size_x": str(max_grid_x),
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
        "chem_species.max_seg_length": "1",
        "chem_species.seg_split_length": "1",
        "cell_force.fungi_stiffness": "0",
        "cell_force.fungi_wall_stiffness": "0",
        "cell_force.cell_stiffness": "0",
        "cell_force.cell_wall_stiffness": "0",
        "cell_force.viscous_drag": "0",
        "fluid.init_conc_species": "1e-3 0 0 0 0 0 0",
        "chem_species.initial_particle_P": "1e-3 0 0",
        "p12.enabled": "0",
        "p13.enabled": "0",
        "p14.enabled": "1",
        "p14.contract": CONTRACT_ID,
        "p14.contract_sha256": CONTRACT_SHA,
        "p14.operator_fit": FIT_ID,
        "p14.operator_fit_sha256": FIT_SHA,
        "p14.stage": "C12",
        "p14.interface_fraction": "continuous-finite-radius-axial-contact-v1",
        "p14.reward_molar_multiplier": "7.736",
        "p14.k_export": f"{rate:.17g}",
    }
    for key, value in values.items():
        result = set_value(result, key, value)
    return result


def fixture(base: str, kind: str) -> str:
    pi = math.pi
    definitions = {
        "no_contact": dict(x=0.2, z=0.9, radius=0.001, length=0.04,
                           theta=pi/2, phi=0.0),
        "tangency": dict(x=0.051, z=0.9, radius=0.001, length=0.04,
                         theta=0.0, phi=0.0),
        "partial_contact": dict(x=0.0575, z=0.9, radius=0.01, length=0.015,
                                theta=pi/2, phi=0.0),
        "full_contact": dict(x=0.0, z=0.9, radius=0.001, length=0.08,
                             theta=pi/2, phi=0.0),
        "oblique_contact": dict(
            x=0.0, z=0.9, radius=0.001,
            length=math.sqrt(0.4**2 + 0.08**2),
            theta=math.acos(0.08/math.sqrt(0.4**2 + 0.08**2)), phi=0.0),
        "solid_edge": dict(x=0.0, z=0.801, radius=0.001, length=0.08,
                           theta=pi/2, phi=0.0),
        "window_contact_only": dict(x=0.05525, z=0.9, radius=0.001,
                                    length=0.0095, theta=pi/2, phi=0.0),
        "true_crossing": dict(x=0.0, z=0.9, radius=0.001, length=0.4,
                              theta=pi/2, phi=0.0),
    }
    return particle_fixture(base, **definitions[kind])


def rows(completed: subprocess.CompletedProcess[str]) -> list[dict[str, float | int]]:
    parsed: list[dict[str, float | int]] = []
    output = completed.stdout + completed.stderr
    integer_keys = {
        "update_id", "particles", "eligible", "true_crossings",
        "solid_contacts", "accepted_events", "donor_capped_events",
    }
    for line in output.splitlines():
        if not line.startswith("P14_STEP "):
            continue
        row: dict[str, float | int] = {}
        for token in line.split()[1:]:
            key, value = token.split("=", 1)
            row[key] = int(value) if key in integer_keys else float(value)
        parsed.append(row)
    return parsed


def ledgers(completed: subprocess.CompletedProcess[str]) -> list[dict[str, float | str]]:
    output = completed.stdout + completed.stderr
    result = []
    for match in LEDGER_RE.finditer(output):
        result.append({
            "boundary": match.group(1),
            "reference_total": float(match.group(2)),
            "accounted": float(match.group(8)),
            "residual": float(match.group(9)),
            "tolerance": float(match.group(10)),
        })
    return result


def near(left: float, right: float, factor: float = 256.0) -> bool:
    scale = max(abs(left), abs(right), 1.0e-300)
    return abs(left-right) <= factor*math.ulp(1.0)*scale


def successful(completed: subprocess.CompletedProcess[str], expected_steps: int,
               *, fraction: str = "positive") -> dict:
    output = completed.stdout + completed.stderr
    parsed = rows(completed)
    ledger = ledgers(completed)
    fractions = [float(row["interface_fraction_sum"]) for row in parsed]
    fraction_ok = {
        "zero": all(value == 0.0 for value in fractions),
        "unit": all(value == 1.0 for value in fractions),
        "positive": all(0.0 < value <= 1.0 for value in fractions),
    }[fraction]
    checks = {
        "exit_zero": completed.returncode == 0,
        "contract_bound": f"P14_CONTRACT classification=USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE contract={CONTRACT_ID}" in output,
        "step_count": len(parsed) == expected_steps,
        "fraction_class": len(parsed) == expected_steps and fraction_ok,
        "request_identity": all(near(
            float(row["requested_p"]),
            float(row["accepted_p"])+float(row["rejected_p"]),
        ) for row in parsed),
        "receipt_identity": all(float(row["accepted_p"]) ==
                                float(row["exported_p"]) for row in parsed),
        "reward_exact": all(float(row["exchange_derived_a"]) ==
                            MULTIPLIER*float(row["accepted_p"])
                            for row in parsed),
        "bootstrap_separate_zero_credit": all(
            float(row["bootstrap_a_credit"]) == 0.0 for row in parsed),
        "no_negative_or_cap": all(
            float(row["accepted_p"]) >= 0.0 and
            int(row["donor_capped_events"]) == 0 for row in parsed),
        "global_p_conservation": bool(ledger) and all(
            abs(float(row["residual"])) <= float(row["tolerance"])
            for row in ledger),
        "f_inactive": "F_active=0" in output,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "steps": parsed,
        "ledgers": ledger,
        "returncode": completed.returncode,
    }


def rejected(completed: subprocess.CompletedProcess[str], token: str) -> dict:
    output = completed.stdout + completed.stderr
    checks = {
        "exit_nonzero": completed.returncode != 0,
        "expected_reason": token in output,
        "no_completed_export_step": not rows(completed),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "returncode": completed.returncode,
        "expected_token": token,
    }


def final_equivalent(first: dict, second: dict) -> bool:
    if not first.get("steps") or not second.get("steps"):
        return False
    left = first["steps"][-1]
    right = second["steps"][-1]
    real_keys = (
        "cumulative_exported_p", "cumulative_exchange_derived_a",
        "requested_p", "accepted_p", "rejected_p",
    )
    int_keys = ("update_id",)
    return all(near(float(left[key]), float(right[key])) for key in real_keys) and all(
        left[key] == right[key] for key in int_keys
    )


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
    cases: dict[str, dict] = {}

    geometry_expectations = {
        "no_contact": "zero", "tangency": "zero",
        "partial_contact": "positive", "full_contact": "unit",
        "oblique_contact": "positive", "solid_edge": "zero",
        "window_contact_only": "positive", "true_crossing": "positive",
    }
    # Geometry qualification uses the already-qualified P11 small mechanical
    # timestep so wall forces cannot turn a classification fixture into a
    # different physical pose before the final-topology O09 evaluation.
    center_input = p14_input(
        base_input, rate=5.26977773579e-6, dt=1.0e-5
    )
    for name, fraction in geometry_expectations.items():
        completed = run_case(
            exe, root / name, center_input, fixture(base_particle, name),
            timeout=300, max_step=1,
        )
        cases[name] = successful(completed, 1, fraction=fraction)
    cases["solid_edge"]["checks"]["solid_precedence_observed"] = (
        bool(cases["solid_edge"]["steps"]) and
        cases["solid_edge"]["steps"][0]["solid_contacts"] == 1 and
        cases["solid_edge"]["steps"][0]["eligible"] == 0
    )
    cases["window_contact_only"]["checks"]["crossing_not_required"] = (
        bool(cases["window_contact_only"]["steps"]) and
        cases["window_contact_only"]["steps"][0]["eligible"] == 1 and
        cases["window_contact_only"]["steps"][0]["true_crossings"] == 0
    )
    cases["true_crossing"]["checks"]["crossing_diagnostic_only"] = (
        bool(cases["true_crossing"]["steps"]) and
        cases["true_crossing"]["steps"][0]["eligible"] == 1 and
        cases["true_crossing"]["steps"][0]["true_crossings"] == 1
    )
    for name in ("solid_edge", "window_contact_only", "true_crossing"):
        cases[name]["status"] = (
            "PASS" if all(cases[name]["checks"].values()) else "FAIL"
        )

    full_particle = fixture(base_particle, "full_contact")
    for index, rate in enumerate(RATES):
        name = f"rate_{index}"
        completed = run_case(
            exe, root / name, p14_input(base_input, rate=rate),
            full_particle, timeout=300, max_step=1,
        )
        cases[name] = successful(completed, 1, fraction="unit")
        step = cases[name]["steps"][0] if cases[name]["steps"] else {}
        cases[name]["checks"]["rate_response"] = (
            bool(step) and ((rate == 0.0 and step["accepted_p"] == 0.0 and
                            step["exchange_derived_a"] == 0.0) or
                           (rate > 0.0 and step["accepted_p"] > 0.0))
        )
        cases[name]["status"] = (
            "PASS" if all(cases[name]["checks"].values()) else "FAIL"
        )

    analytic_input = p14_input(base_input, rate=5.26977773579e-6)
    continuous = run_case(
        exe, root / "continuous_rank1", analytic_input, full_particle,
        timeout=300, max_step=4, check_int=2,
    )
    cases["continuous_rank1"] = successful(continuous, 4, fraction="unit")
    analytic_rows = cases["continuous_rank1"]["steps"]
    if len(analytic_rows) == 4:
        initial = float(analytic_rows[0]["active_d_basis"])
        expected = initial*(1.0-math.exp(-5.26977773579e-6*100.0*4))
        observed = float(analytic_rows[-1]["cumulative_exported_p"])
        analytic_ok = near(observed, expected, factor=2048.0)
    else:
        analytic_ok = False
    cases["continuous_rank1"]["checks"]["analytical_exponential"] = analytic_ok
    cases["continuous_rank1"]["status"] = (
        "PASS" if all(cases["continuous_rank1"]["checks"].values()) else "FAIL"
    )

    launcher2 = [str(args.mpiexec.resolve()), "-n", "2"]
    rank2 = run_case(
        exe, root / "continuous_rank2", analytic_input, full_particle,
        timeout=300, max_step=4, check_int=2, launcher=launcher2,
    )
    cases["continuous_rank2"] = successful(rank2, 4, fraction="unit")
    decomposition = run_case(
        exe, root / "decomposition_rank2",
        p14_input(base_input, rate=5.26977773579e-6, max_grid_x=10),
        full_particle, timeout=300, max_step=4, launcher=launcher2,
    )
    cases["decomposition_rank2"] = successful(
        decomposition, 4, fraction="unit"
    )

    checkpoint = root / "continuous_rank1" / "chk00002"
    restart11 = run_case(
        exe, root / "restart_1_to_1", analytic_input, full_particle,
        timeout=300, max_step=4, restart=str(checkpoint),
    )
    cases["restart_1_to_1"] = successful(restart11, 2, fraction="unit")
    checkpoint2 = root / "continuous_rank2" / "chk00002"
    restart21 = run_case(
        exe, root / "restart_2_to_1", analytic_input, full_particle,
        timeout=300, max_step=4, restart=str(checkpoint2),
    )
    cases["restart_2_to_1"] = successful(restart21, 2, fraction="unit")

    mutated = root / "mutated_contract_checkpoint"
    shutil.copytree(checkpoint, mutated)
    header = mutated / "Header"
    header.write_text(
        header.read_text(encoding="utf-8").replace(CONTRACT_SHA, "0"*64, 1),
        encoding="utf-8",
    )
    mutation = run_case(
        exe, root / "checkpoint_contract_mutation", analytic_input,
        full_particle, timeout=300, max_step=4, restart=str(mutated),
    )
    cases["checkpoint_contract_mutation"] = rejected(
        mutation,
        "P14 contract, O09 fit, interface, reward, or parameter identity mismatch",
    )

    algebra = root / "mutated_algebra_checkpoint"
    shutil.copytree(checkpoint, algebra)
    algebra_header = algebra / "Header"
    algebra_text = re.sub(
        r"^p14_cumulative_exchange_derived_a \S+$",
        "p14_cumulative_exchange_derived_a 0",
        algebra_header.read_text(encoding="utf-8"), count=1,
        flags=re.MULTILINE,
    )
    algebra_header.write_text(algebra_text, encoding="utf-8")
    algebra_run = run_case(
        exe, root / "checkpoint_algebra_mutation", analytic_input,
        full_particle, timeout=300, max_step=4, restart=str(algebra),
    )
    cases["checkpoint_algebra_mutation"] = rejected(
        algebra_run, "P14 checkpoint violates export, reward, or provenance algebra"
    )

    global_mismatch = root / "mutated_global_checkpoint"
    shutil.copytree(checkpoint, global_mismatch)
    global_header = global_mismatch / "Header"
    global_text = re.sub(
        r"^ledger_exported_p \S+$", "ledger_exported_p 0",
        global_header.read_text(encoding="utf-8"), count=1,
        flags=re.MULTILINE,
    )
    global_header.write_text(global_text, encoding="utf-8")
    global_run = run_case(
        exe, root / "checkpoint_global_mutation", analytic_input,
        full_particle, timeout=300, max_step=4, restart=str(global_mismatch),
    )
    cases["checkpoint_global_mutation"] = rejected(
        global_run, "P14 export ledger differs from global exported P"
    )

    bad_rate = run_case(
        exe, root / "invalid_rate",
        set_value(analytic_input, "p14.k_export", "2e-5"), full_particle,
        timeout=300, max_step=1,
    )
    cases["invalid_rate"] = rejected(
        bad_rate, "P14 k_export is outside the five adopted levels"
    )
    bad_multiplier = run_case(
        exe, root / "invalid_multiplier",
        set_value(analytic_input, "p14.reward_molar_multiplier", "7.735"),
        full_particle, timeout=300, max_step=1,
    )
    cases["invalid_multiplier"] = rejected(
        bad_multiplier,
        "P14 contract, O09 fit, interface, reward, or stage identity mismatch",
    )

    mpi_equivalent = final_equivalent(
        cases["continuous_rank1"], cases["continuous_rank2"]
    )
    decomposition_equivalent = final_equivalent(
        cases["continuous_rank2"], cases["decomposition_rank2"]
    )
    restart_11_equivalent = final_equivalent(
        cases["continuous_rank1"], cases["restart_1_to_1"]
    )
    restart_21_equivalent = final_equivalent(
        cases["continuous_rank1"], cases["restart_2_to_1"]
    )
    overall = (
        all(case["status"] == "PASS" for case in cases.values()) and
        mpi_equivalent and decomposition_equivalent and
        restart_11_equivalent and restart_21_equivalent
    )
    record = {
        "artifact_type": "C12_P14_NATIVE_RUNTIME",
        "stage": "C12/P14",
        "status": "PASS" if overall else "FAIL",
        "cases": cases,
        "mpi_rank1_rank2_equivalent": mpi_equivalent,
        "decomposition_equivalent": decomposition_equivalent,
        "restart_1_to_1_equivalent": restart_11_equivalent,
        "restart_2_to_1_equivalent": restart_21_equivalent,
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "contract": {"id": CONTRACT_ID, "sha256": CONTRACT_SHA},
        "operator_fit": {"id": FIT_ID, "sha256": FIT_SHA},
        "frozen_kernel_sha256": sha256(source / "src/chemistry/bmx_chem_K.H"),
        "global_order_sha256": sha256(source / "contracts/p10/OPERATOR_ORDER_V1.json"),
        "expected_hashes": {"kernel": KERNEL_SHA, "global_order": ORDER_SHA},
        "external_resources": "none",
        "external_spend_usd": 0,
        "claim_boundary": "Windows CPU software/numerical qualification under USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE; not mentor approval, calibration, predictive validation, or C13 science.",
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({
        "status": record["status"],
        "cases": {key: value["status"] for key, value in cases.items()},
        "mpi_equivalent": mpi_equivalent,
        "decomposition_equivalent": decomposition_equivalent,
        "restart_1_to_1_equivalent": restart_11_equivalent,
        "restart_2_to_1_equivalent": restart_21_equivalent,
    }, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
