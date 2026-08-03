#!/usr/bin/env python3
"""Run a small P growth-limitation calibration sweep for the fungi example.

The script keeps all run products outside the repository by default. It copies
the input deck and particle initialization file into per-case directories under
/private/tmp, runs the local BMX binary, parses the existing network diagnostics,
and writes a compact CSV summary.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


FLOAT_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
STEP_RE = re.compile(rf"Step\s+(\d+): from old time {FLOAT_RE} to new time ({FLOAT_RE})")
TOTAL_PARTICLES_RE = re.compile(r"TOTAL PARTICLES\s+(\d+)")
EXCHANGE_PARTICLES_RE = re.compile(r"In Particle Exchange with\s+(\d+) particles at level\s+1")
VOLUME_RE = re.compile(rf"Network total volume V.*:\s+({FLOAT_RE})")
SURFACE_RE = re.compile(rf"Network total surface area S.*:\s+({FLOAT_RE})")
PARTICLE_P_RE = re.compile(rf"Network total particle P content:\s+({FLOAT_RE})")


@dataclass(frozen=True)
class Case:
    name: str
    p_growth_limit: int
    qp: float
    initial_p: float


@dataclass
class CaseResult:
    case: Case
    returncode: int
    finalized: bool
    final_step: int | None
    final_particles: int | None
    first_split_step: int | None
    first_split_time: float | None
    final_volume: float | None
    final_surface: float | None
    final_particle_p: float | None
    first_particle_p: float | None
    min_particle_p: float | None
    run_dir: Path


def parse_float_list(value: str) -> list[float]:
    return [float(item) for item in value.replace(",", " ").split()]


def fmt(value: float) -> str:
    return f"{value:.6g}"


def write_case_input(source_input: Path, case_input: Path, initial_p: float) -> None:
    lines = source_input.read_text().splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.strip().startswith("fluid.init_conc_species"):
            lhs, rhs = line.split("=", 1)
            values = rhs.split()
            if len(values) < 6:
                raise ValueError("fluid.init_conc_species must contain at least 6 values")
            values[5] = fmt(initial_p)
            out.append(f"{lhs.strip()} = {' '.join(values)}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        raise ValueError("Could not find fluid.init_conc_species in input deck")
    case_input.write_text("\n".join(out) + "\n")


def parse_run(case: Case, run_dir: Path, text: str, returncode: int) -> CaseResult:
    current_step: int | None = None
    current_time: float | None = None
    final_step: int | None = None
    total_particles: list[int] = []
    exchange_particles: list[int] = []
    volumes: list[float] = []
    surfaces: list[float] = []
    particle_ps: list[float] = []
    first_split_step: int | None = None
    first_split_time: float | None = None

    for line in text.splitlines():
        if step_match := STEP_RE.search(line):
            current_step = int(step_match.group(1))
            current_time = float(step_match.group(2))
            final_step = current_step
        if total_match := TOTAL_PARTICLES_RE.search(line):
            total_particles.append(int(total_match.group(1)))
        if exchange_match := EXCHANGE_PARTICLES_RE.search(line):
            exchange_particles.append(int(exchange_match.group(1)))
        if volume_match := VOLUME_RE.search(line):
            volumes.append(float(volume_match.group(1)))
        if surface_match := SURFACE_RE.search(line):
            surfaces.append(float(surface_match.group(1)))
        if p_match := PARTICLE_P_RE.search(line):
            particle_ps.append(float(p_match.group(1)))
        if "Generating new growth tip" in line and first_split_step is None:
            first_split_step = current_step
            first_split_time = current_time

    final_particles = None
    if exchange_particles:
        final_particles = exchange_particles[-1]
    elif total_particles:
        final_particles = total_particles[-1]

    return CaseResult(
        case=case,
        returncode=returncode,
        finalized="finalized" in text,
        final_step=final_step,
        final_particles=final_particles,
        first_split_step=first_split_step,
        first_split_time=first_split_time,
        final_volume=volumes[-1] if volumes else None,
        final_surface=surfaces[-1] if surfaces else None,
        final_particle_p=particle_ps[-1] if particle_ps else None,
        first_particle_p=particle_ps[0] if particle_ps else None,
        min_particle_p=min(particle_ps) if particle_ps else None,
        run_dir=run_dir,
    )


def run_case(
    case: Case,
    binary: Path,
    source_input: Path,
    init_file: Path,
    work_root: Path,
    max_step: int,
    timeout: int,
) -> CaseResult:
    run_dir = work_root / case.name
    run_dir.mkdir(parents=True, exist_ok=False)
    write_case_input(source_input, run_dir / "input_fungi", case.initial_p)
    shutil.copy2(init_file, run_dir / init_file.name)

    cmd = [
        str(binary),
        "input_fungi",
        f"bmx.max_step={max_step}",
        "amr.plot_int=-1",
        "amr.check_int=-1",
        "amr.par_ascii_int=-1",
        "chem_species.rg_frequency=1",
        f"chem_species.p_growth_limit={case.p_growth_limit}",
        f"chem_species.qP={fmt(case.qp)}",
    ]
    proc = subprocess.run(
        cmd,
        cwd=run_dir,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    combined = proc.stdout + proc.stderr
    (run_dir / "run.log").write_text(combined)
    return parse_run(case, run_dir, combined, proc.returncode)


def choose_provisional_qp(control: CaseResult, qp_results: list[CaseResult]) -> float:
    if control.final_volume is None or control.final_volume <= 0.0:
        return qp_results[-1].case.qp

    candidates: list[tuple[float, CaseResult]] = []
    for result in qp_results:
        if result.final_volume is None or not result.finalized:
            continue
        reduction = 1.0 - result.final_volume / control.final_volume
        first_p = result.first_particle_p if result.first_particle_p is not None else -math.inf
        if 0.05 <= reduction <= 0.50 and first_p > 1.0e-18:
            candidates.append((reduction, result))

    if candidates:
        candidates.sort(key=lambda item: abs(item[0] - 0.20))
        return candidates[0][1].case.qp

    usable = [r for r in qp_results if r.final_volume is not None and r.finalized]
    if not usable:
        return qp_results[-1].case.qp
    usable.sort(key=lambda r: abs((1.0 - r.final_volume / control.final_volume) - 0.20))
    return usable[0].case.qp


def reduction(control: CaseResult, result: CaseResult) -> float | None:
    if control.final_volume is None or result.final_volume is None or control.final_volume == 0.0:
        return None
    return 1.0 - result.final_volume / control.final_volume


def write_csv(path: Path, control: CaseResult, results: list[CaseResult]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "case",
                "p_growth_limit",
                "qP",
                "initial_P",
                "returncode",
                "finalized",
                "final_step",
                "final_particles",
                "first_split_step",
                "first_split_time",
                "final_volume",
                "final_surface",
                "final_particle_P",
                "first_particle_P",
                "min_particle_P",
                "volume_reduction_vs_control",
                "run_dir",
            ]
        )
        for result in results:
            rel_reduction = reduction(control, result)
            writer.writerow(
                [
                    result.case.name,
                    result.case.p_growth_limit,
                    fmt(result.case.qp),
                    fmt(result.case.initial_p),
                    result.returncode,
                    int(result.finalized),
                    result.final_step,
                    result.final_particles,
                    result.first_split_step,
                    result.first_split_time,
                    result.final_volume,
                    result.final_surface,
                    result.final_particle_p,
                    result.first_particle_p,
                    result.min_particle_p,
                    rel_reduction,
                    result.run_dir,
                ]
            )


def print_table(control: CaseResult, results: list[CaseResult], provisional_qp: float, csv_path: Path) -> None:
    print(f"Work root: {csv_path.parent}")
    print(f"CSV: {csv_path}")
    print(f"Provisional qP: {fmt(provisional_qp)}")
    print()
    print(
        "case,p_growth_limit,qP,initial_P,final_volume,volume_reduction,"
        "final_particle_P,final_particles,first_split_step,finalized"
    )
    for result in results:
        rel_reduction = reduction(control, result)
        red_text = "" if rel_reduction is None else f"{rel_reduction:.6g}"
        print(
            ",".join(
                [
                    result.case.name,
                    str(result.case.p_growth_limit),
                    fmt(result.case.qp),
                    fmt(result.case.initial_p),
                    "" if result.final_volume is None else f"{result.final_volume:.12g}",
                    red_text,
                    "" if result.final_particle_p is None else f"{result.final_particle_p:.12g}",
                    "" if result.final_particles is None else str(result.final_particles),
                    "" if result.first_split_step is None else str(result.first_split_step),
                    str(int(result.finalized)),
                ]
            )
        )


def main() -> int:
    repo_default = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_default)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--init-file", type=Path)
    parser.add_argument("--max-step", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--qps", default="1e-6,1e-5,1e-4,2e-4,3e-4,5e-4,1e-3")
    parser.add_argument("--initial-p", type=float, default=2.0e-5)
    parser.add_argument("--p-supply", default="2e-6,2e-5,2e-4")
    parser.add_argument("--work-root", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    binary = (args.binary or repo_root / "build" / "bmx").resolve()
    source_input = (args.input or repo_root / "exec" / "fungi" / "input_fungi").resolve()
    init_file = (args.init_file or repo_root / "exec" / "fungi" / "fungi_init_cfg.dat").resolve()
    if args.work_root is None:
        base_tmp = Path("/private/tmp") if Path("/private/tmp").exists() else Path(tempfile.gettempdir())
        work_root = Path(tempfile.mkdtemp(prefix=f"bmx_p_growth_sweep_{int(time.time())}_", dir=base_tmp))
    else:
        work_root = args.work_root.resolve()
        work_root.mkdir(parents=True, exist_ok=False)

    qps = parse_float_list(args.qps)
    p_supply = parse_float_list(args.p_supply)

    control = run_case(
        Case("control_default_p", 0, qps[0], args.initial_p),
        binary,
        source_input,
        init_file,
        work_root,
        args.max_step,
        args.timeout,
    )
    qp_results = [
        run_case(
            Case(f"qp_{fmt(qp)}_p_{fmt(args.initial_p)}", 1, qp, args.initial_p),
            binary,
            source_input,
            init_file,
            work_root,
            args.max_step,
            args.timeout,
        )
        for qp in qps
    ]
    provisional_qp = choose_provisional_qp(control, qp_results)

    supply_results = []
    for initial_p in p_supply:
        if math.isclose(initial_p, args.initial_p, rel_tol=0.0, abs_tol=0.0):
            continue
        supply_results.append(
            run_case(
                Case(f"p_supply_{fmt(initial_p)}_qp_{fmt(provisional_qp)}", 1, provisional_qp, initial_p),
                binary,
                source_input,
                init_file,
                work_root,
                args.max_step,
                args.timeout,
            )
        )

    results = [control] + qp_results + supply_results
    csv_path = work_root / "p_growth_sweep_summary.csv"
    write_csv(csv_path, control, results)
    print_table(control, results, provisional_qp, csv_path)

    failed = [result for result in results if result.returncode != 0 or not result.finalized]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
