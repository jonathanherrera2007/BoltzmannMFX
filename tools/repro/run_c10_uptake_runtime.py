#!/usr/bin/env python3
"""C10/P12 native uptake transaction, MPI, control, and restart tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path


CONTRACT_ID = "UDC-20260801-P12-UPTAKE-ONLY-V1"
CONTRACT_SHA = "2094aed3c8ef21a257d2c597352793384d01a1efc3d72936d5c5108d308f8804"
NUMERICAL_CONTRACT_ID = "USER-DIRECTED-20260801-P12-NUMERICAL-V2"
NUMERICAL_CONTRACT_SHA = "43d64a8f4ec6c8c00379fc3d9605441cb900479fcdd8db9e78e6fc1edd28f81f"
UPTAKE_RE = re.compile(
    r"^P12_UPTAKE update=(\d+) requested=(\S+) accepted=(\S+) "
    r"rejected=(\S+) eligible_area=(\S+) min_donor_scale=(\S+) "
    r"max_donor_eta=(\S+) zero_inventory_positive_request=(\d+) "
    r"cumulative_requested=(\S+) cumulative_accepted=(\S+) "
    r"cumulative_rejected=(\S+) cumulative_area_time=(\S+) "
    r"run_min_donor_scale=(\S+) run_max_donor_eta=(\S+) "
    r"run_positive_request_updates=(\d+) "
    r"run_zero_inventory_positive_request_updates=(\d+) "
    r"E=0 F=0 structural=0 export=0 reward=0 growth=0$",
    re.MULTILINE,
)
LEDGER_RE = re.compile(
    r"^P10_LEDGER boundary=(\S+).*?mesh_D=(\S+).*?internal_D=(\S+) "
    r"internal_E=(\S+) internal_F=(\S+).*?residual=(\S+) tolerance=(\S+)$",
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


def uptake_input(base: str, *, mesh_d: float, j_max: float, d_diff: float,
                 area_mode: str = "FULL_EXPOSED_EXTRARADICAL_SURFACE",
                 dt: float = 1800.0, ncell: int = 8) -> str:
    values = {
        "bmx.fixed_dt": f"{dt:.17g}",
        "bmx.substeps": "1",
        "amr.max_level": "0",
        "geometry.is_periodic": "0 1 0",
        "geometry.prob_lo": "0.0 0.0 0.0",
        "geometry.prob_hi": "0.2 0.2 0.1",
        "amr.n_cell": f"{ncell} {ncell} {max(2, ncell // 2)}",
        "amr.blocking_factor": "2",
        "amr.max_grid_size_x": str(ncell),
        "amr.max_grid_size_y": str(ncell),
        "amr.max_grid_size_z": str(max(2, ncell // 2)),
        "bmx.tag_region": "false",
        "amr.regrid_int": "-1",
        "fluid.surface_location": "0.1",
        "fluid.chem_species": "A B C D F P_D P_F",
        "fluid.chem_species_diff": f"0 0 0 0 0 {d_diff:.17g} 0",
        "fluid.init_conc_species": f"0 0 0 0 0 {mesh_d:.17g} 0",
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
        "chem_species.branching_probability": "0",
        "chem_species.splitting_probability": "0",
        "chem_species.fusion_probability": "0",
        "chem_species.max_seg_length": "1",
        "chem_species.seg_split_length": "1",
        "chem_species.rg_frequency": "1000000",
        "cell_force.gravity": "0",
        "cell_force.fluctuation_scale": "0",
        "p11_geometry.enabled": "0",
        "p12.enabled": "1",
        "p12.contract": CONTRACT_ID,
        "p12.contract_sha256": CONTRACT_SHA,
        "p12.numerical_contract": NUMERICAL_CONTRACT_ID,
        "p12.numerical_contract_sha256": NUMERICAL_CONTRACT_SHA,
        "p12.stage": "C10",
        "p12.network_sha256": "1f2294613b8a608b068d60269ff8eb29990210d3a1bc6d8142d4f840aa292702",
        "p12.j_max": f"{j_max:.17g}",
        "p12.k_m": "1.00084710414e-9",
        "p12.area_mode": area_mode,
        "p12.area_multiplier": "1",
        "bmx.cnc_deposition_scheme": "one_to_one",
        "bmx.vf_deposition_scheme": "one_to_one",
        "diffusion.rtol": "1e-13",
        "diffusion.atol": "0",
        "diffusion.maxiter": "200",
    }
    result = base
    for key, value in values.items():
        result = set_value(result, key, value)
    return result


def particle_fixture(base: str, count: int, *, reverse: bool = False) -> str:
    if count == 0:
        return "0\n"
    lines = base.splitlines()
    # The legacy example carries three ignored trailing values because it has
    # one row. Native initialization consumes exactly 27 values per particle;
    # retaining the extras would shift every row after the first.
    fields0 = lines[1].split()[:27]
    rows = []
    radius = 2.5e-4
    length = 3.0e-3
    area = 2.0 * math.pi * radius * length + 2.0 * math.pi * radius**2
    volume = math.pi * radius**2 * length
    for index in range(count):
        fields = fields0.copy()
        values = {0: 0.1 + index * 1.0e-5, 1: 0.1, 2: 0.05,
                  3: radius, 4: length, 5: math.pi/2, 6: 0.0,
                  7: area, 8: volume, 26: 1}
        for slot, value in values.items():
            fields[slot] = str(value) if isinstance(value, int) else f"{value:.17g}"
        for slot in range(9, 26):
            fields[slot] = "0"
        rows.append(" ".join(fields))
    if reverse:
        rows.reverse()
    return str(count) + "\n" + "\n".join(rows) + "\n"


def run_case(exe: Path, run_dir: Path, input_text: str, particle_text: str,
             *, steps: int, ranks: int, mpiexec: Path,
             check_int: int = -1, restart: Path | None = None,
             timeout: int = 240) -> subprocess.CompletedProcess[str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input_fungi").write_text(input_text, encoding="utf-8")
    (run_dir / "fungi_init_cfg.dat").write_text(particle_text, encoding="utf-8")
    command = [] if ranks == 1 else [str(mpiexec), "-n", str(ranks)]
    command += [str(exe), "input_fungi", f"bmx.max_step={steps}",
                "amr.plot_int=-1", f"amr.check_int={check_int}",
                "amr.check_file=chk", "amr.par_ascii_int=1",
                "amr.par_ascii_file=par"]
    if restart is not None:
        command.append(f"amr.restart={restart}")
    completed = subprocess.run(command, cwd=run_dir, capture_output=True,
                               text=True, timeout=timeout)
    output = completed.stdout + completed.stderr
    (run_dir / "stdout.log").write_text(output, encoding="utf-8")
    (run_dir / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8")
    return completed


def uptake_rows(completed: subprocess.CompletedProcess[str]) -> list[dict]:
    output = completed.stdout + completed.stderr
    result = []
    for match in UPTAKE_RE.finditer(output):
        result.append({
            "update": int(match.group(1)),
            "requested": float(match.group(2)),
            "accepted": float(match.group(3)),
            "rejected": float(match.group(4)),
            "area": float(match.group(5)),
            "min_scale": float(match.group(6)),
            "max_eta": float(match.group(7)),
            "zero_inventory_positive_request": int(match.group(8)),
            "cum_requested": float(match.group(9)),
            "cum_accepted": float(match.group(10)),
            "cum_rejected": float(match.group(11)),
            "cum_area_time": float(match.group(12)),
            "run_min_scale": float(match.group(13)),
            "run_max_eta": float(match.group(14)),
            "run_positive_request_updates": int(match.group(15)),
            "run_zero_inventory_positive_request_updates":
                int(match.group(16)),
        })
    return result


def ledger_rows(completed: subprocess.CompletedProcess[str]) -> list[dict]:
    output = completed.stdout + completed.stderr
    return [{"boundary": m.group(1), "mesh_d": float(m.group(2)),
             "internal_d": float(m.group(3)), "internal_e": float(m.group(4)),
             "internal_f": float(m.group(5)), "residual": float(m.group(6)),
             "tolerance": float(m.group(7))} for m in LEDGER_RE.finditer(output)]


def summary(completed: subprocess.CompletedProcess[str], *, steps: int,
            expect_activity: bool, expect_cap: bool = False) -> dict:
    output = completed.stdout + completed.stderr
    uptake = uptake_rows(completed)
    ledgers = ledger_rows(completed)
    last = uptake[-1] if uptake else None
    o10 = [row for row in ledgers if row["boundary"] == "O10_POST_UPDATE_LEDGER"]
    rejection_tolerance = (max(1e-28, 64.0 * math.ulp(1.0) *
                               last["cum_requested"])
                           if last else math.nan)
    primary_no_clipping = (not expect_activity or expect_cap or bool(
        last and last["run_max_eta"] <= 0.25 and
        last["run_min_scale"] >= 1.0 - 64.0 * math.ulp(1.0) and
        last["cum_rejected"] <= rejection_tolerance and
        last["run_zero_inventory_positive_request_updates"] == 0))
    checks = {
        "exit_zero": completed.returncode == 0,
        "contract_bound": f"contract={CONTRACT_ID}" in output,
        "numerical_contract_bound":
            f"numerical_contract={NUMERICAL_CONTRACT_ID}" in output,
        "one_uptake_record_per_step": len(uptake) == steps,
        "o10_record_per_step": len(o10) == steps,
        "activity_expectation": bool(last and last["cum_accepted"] > 0.0) == expect_activity,
        "cap_expectation": (not expect_cap) or bool(
            last and last["cum_rejected"] > 0.0 and
            last["run_min_scale"] < 1.0 and last["run_max_eta"] > 1.0),
        "diagnostics_finite": bool(last) and all(math.isfinite(last[key]) for key in (
            "min_scale", "max_eta", "run_min_scale", "run_max_eta")),
        "primary_no_clipping": primary_no_clipping,
        "explicit_later_state_zeros": "E=0 F=0 structural=0 export=0 reward=0 growth=0" in output,
        "ledger_within_tolerance": bool(o10) and all(abs(row["residual"]) <= row["tolerance"] for row in o10),
        "internal_e_f_zero": bool(o10) and all(row["internal_e"] == 0.0 and row["internal_f"] == 0.0 for row in o10),
    }
    return {"exit_code": completed.returncode, "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks, "last_uptake": last, "last_o10": o10[-1] if o10 else None}


def near(a: float, b: float) -> bool:
    return abs(a-b) <= max(1e-28, 1e-10 * (abs(a) + abs(b)))


def main() -> int:
    parser = argparse.ArgumentParser()
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
    base_particle = (source / "contracts/p12/network/P12_FIXED_NETWORK_V1.dat").read_text(encoding="utf-8")
    jmax = 2.95949412514e-12

    cases: dict[str, dict] = {}
    definitions = [
        ("active_low_rank1", 1.61e-8, jmax, 5e-6, "FULL_EXPOSED_EXTRARADICAL_SURFACE", 1, 1, True, False),
        ("active_low_rank2", 1.61e-8, jmax, 5e-6, "FULL_EXPOSED_EXTRARADICAL_SURFACE", 1, 2, True, False),
        ("active_high_rank1", 4.52e-8, jmax, 5e-6, "FULL_EXPOSED_EXTRARADICAL_SURFACE", 1, 1, True, False),
        ("jmax_zero", 1.61e-8, 0.0, 5e-6, "FULL_EXPOSED_EXTRARADICAL_SURFACE", 1, 1, False, False),
        ("zero_mesh_d", 0.0, jmax, 5e-6, "FULL_EXPOSED_EXTRARADICAL_SURFACE", 1, 1, False, False),
        ("zero_diffusion", 1.61e-8, jmax, 0.0, "FULL_EXPOSED_EXTRARADICAL_SURFACE", 1, 1, True, False),
        ("zero_area", 1.61e-8, jmax, 5e-6, "ZERO", 1, 1, False, False),
        ("shared_donor_cap", 1.61e-8, 3*jmax, 5e-6, "FULL_EXPOSED_EXTRARADICAL_SURFACE", 8, 1, True, True),
        ("shared_donor_cap_rank2", 1.61e-8, 3*jmax, 5e-6, "FULL_EXPOSED_EXTRARADICAL_SURFACE", 8, 2, True, True),
        ("empty_network", 1.61e-8, jmax, 5e-6, "FULL_EXPOSED_EXTRARADICAL_SURFACE", 0, 1, False, False),
    ]
    for name, mesh_d, rate, diff, mode, particles, ranks, activity, cap in definitions:
        inp = uptake_input(base_input, mesh_d=mesh_d, j_max=rate,
                           d_diff=diff, area_mode=mode)
        completed = run_case(exe, root/name, inp,
                             particle_fixture(base_particle, particles),
                             steps=1, ranks=ranks, mpiexec=args.mpiexec)
        cases[name] = summary(completed, steps=1,
                              expect_activity=activity, expect_cap=cap)
        cases[name]["log"] = str(root/name/"stdout.log")

    order_input = uptake_input(base_input, mesh_d=1.61e-8, j_max=3*jmax,
                               d_diff=5e-6)
    order = run_case(exe, root/"donor_order_permuted", order_input,
                     particle_fixture(base_particle, 8, reverse=True),
                     steps=1, ranks=1, mpiexec=args.mpiexec)
    cases["donor_order_permuted"] = summary(order, steps=1,
                                             expect_activity=True, expect_cap=True)
    baseline_last = cases["shared_donor_cap"]["last_uptake"]
    order_last = cases["donor_order_permuted"]["last_uptake"]
    cases["donor_order_permuted"]["checks"]["aggregate_order_invariant"] = bool(
        baseline_last and order_last and
        near(baseline_last["cum_requested"], order_last["cum_requested"]) and
        near(baseline_last["cum_accepted"], order_last["cum_accepted"]))
    if not all(cases["donor_order_permuted"]["checks"].values()):
        cases["donor_order_permuted"]["status"] = "FAIL"

    restart_input = uptake_input(base_input, mesh_d=1.61e-8, j_max=jmax,
                                 d_diff=5e-6, dt=1800.0)
    continuous = run_case(exe, root/"continuous", restart_input,
                          particle_fixture(base_particle, 1), steps=4, ranks=1,
                          mpiexec=args.mpiexec, check_int=2)
    cases["continuous"] = summary(continuous, steps=4, expect_activity=True)
    checkpoint = root/"continuous"/"chk00002"
    restarted = run_case(exe, root/"restarted", restart_input,
                         particle_fixture(base_particle, 1), steps=4, ranks=1,
                         mpiexec=args.mpiexec, restart=checkpoint)
    # A restart emits only the remaining two uptake steps but restores update ids.
    restart_summary = summary(restarted, steps=2, expect_activity=True)
    cont_last = cases["continuous"]["last_uptake"]
    restart_last = restart_summary["last_uptake"]
    restart_summary["checks"]["cumulative_restart_equivalence"] = bool(
        cont_last and restart_last and
        near(cont_last["cum_requested"], restart_last["cum_requested"]) and
        near(cont_last["cum_accepted"], restart_last["cum_accepted"]) and
        near(cont_last["cum_rejected"], restart_last["cum_rejected"]) and
        near(cont_last["run_min_scale"], restart_last["run_min_scale"]) and
        near(cont_last["run_max_eta"], restart_last["run_max_eta"]) and
        cont_last["run_positive_request_updates"] ==
            restart_last["run_positive_request_updates"] and
        cont_last["run_zero_inventory_positive_request_updates"] ==
            restart_last["run_zero_inventory_positive_request_updates"])
    if not all(restart_summary["checks"].values()):
        restart_summary["status"] = "FAIL"
    cases["restarted"] = restart_summary

    mutation_dir = root/"mutated_checkpoint"
    shutil.copytree(checkpoint, mutation_dir)
    header = mutation_dir/"Header"
    header.write_text(header.read_text(encoding="utf-8").replace(
        CONTRACT_SHA, "0"*64, 1), encoding="utf-8")
    mutation = run_case(exe, root/"mutation_run", restart_input,
                        particle_fixture(base_particle, 1), steps=4, ranks=1,
                        mpiexec=args.mpiexec, restart=mutation_dir)
    mutation_output = mutation.stdout + mutation.stderr
    cases["checkpoint_contract_mutation"] = {
        "exit_code": mutation.returncode,
        "checks": {
            "exit_nonzero": mutation.returncode != 0,
            "specific_rejection": "P12 uptake contract or parameter identity mismatch" in mutation_output,
            "before_particle_deserialization": "Finished reading particle data" not in mutation_output,
        },
    }
    cases["checkpoint_contract_mutation"]["status"] = (
        "PASS" if all(cases["checkpoint_contract_mutation"]["checks"].values()) else "FAIL")

    numerical_mutation_dir = root/"mutated_numerical_checkpoint"
    shutil.copytree(checkpoint, numerical_mutation_dir)
    numerical_header = numerical_mutation_dir/"Header"
    numerical_header.write_text(numerical_header.read_text(encoding="utf-8").replace(
        NUMERICAL_CONTRACT_SHA, "0"*64, 1), encoding="utf-8")
    numerical_mutation = run_case(
        exe, root/"numerical_mutation_run", restart_input,
        particle_fixture(base_particle, 1), steps=4, ranks=1,
        mpiexec=args.mpiexec, restart=numerical_mutation_dir)
    numerical_mutation_output = (
        numerical_mutation.stdout + numerical_mutation.stderr)
    cases["checkpoint_numerical_contract_mutation"] = {
        "exit_code": numerical_mutation.returncode,
        "checks": {
            "exit_nonzero": numerical_mutation.returncode != 0,
            "specific_rejection":
                "P12 uptake contract or parameter identity mismatch"
                in numerical_mutation_output,
            "before_particle_deserialization":
                "Finished reading particle data" not in numerical_mutation_output,
        },
    }
    cases["checkpoint_numerical_contract_mutation"]["status"] = (
        "PASS" if all(cases["checkpoint_numerical_contract_mutation"]["checks"].values())
        else "FAIL")

    rank1 = cases["active_low_rank1"]["last_uptake"]
    rank2 = cases["active_low_rank2"]["last_uptake"]
    mpi_equivalent = bool(rank1 and rank2 and
                          near(rank1["cum_requested"], rank2["cum_requested"]) and
                          near(rank1["cum_accepted"], rank2["cum_accepted"]))
    cap_rank1 = cases["shared_donor_cap"]["last_uptake"]
    cap_rank2 = cases["shared_donor_cap_rank2"]["last_uptake"]
    shared_donor_mpi_equivalent = bool(
        cap_rank1 and cap_rank2 and
        near(cap_rank1["cum_requested"], cap_rank2["cum_requested"]) and
        near(cap_rank1["cum_accepted"], cap_rank2["cum_accepted"]) and
        near(cap_rank1["cum_rejected"], cap_rank2["cum_rejected"]))
    overall = (all(case["status"] == "PASS" for case in cases.values())
               and mpi_equivalent and shared_donor_mpi_equivalent)
    record = {
        "artifact_type": "C10_UPTAKE_RUNTIME",
        "stage": "C10/P12",
        "status": "PASS" if overall else "FAIL",
        "cases": cases,
        "mpi_decomposition_equivalent": mpi_equivalent,
        "shared_donor_cap_mpi_equivalent": shared_donor_mpi_equivalent,
        "executable": {"path": str(exe), "sha256": sha256(exe)},
        "contract": {"id": CONTRACT_ID, "sha256": CONTRACT_SHA},
        "numerical_contract": {
            "id": NUMERICAL_CONTRACT_ID, "sha256": NUMERICAL_CONTRACT_SHA},
        "frozen_kernel_sha256": sha256(source/"src/chemistry/bmx_chem_K.H"),
        "external_resources": "none", "external_spend_usd": 0,
        "claim_boundary": "Windows CPU native engineering transaction/control/restart evidence; not release-host, calibrated, predictive, complete-biology, or mentor-approved evidence.",
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "mpi": mpi_equivalent,
                      "cases": {k: v["status"] for k,v in cases.items()}}, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
