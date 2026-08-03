#!/usr/bin/env python3
"""BMX RG-SW -- C04 / P07 geometry-observable fixtures, cross-platform driver.

Port of run_p07_geometry_fixtures.ps1. The PowerShell driver cannot run on the
Linux reference platform, which made the qualification sequence unable to
execute end-to-end there (RT-1). Fixture definitions, engineering test values
and verdict rules are identical to the PowerShell version; only the driver
changed.

See run_p07_geometry_fixtures.ps1 for the full rationale. In brief: the first
C04 matrix inferred branch execution from structural statistics of the stdout
log, which cannot attribute a difference to a branch. This enables
`amr.par_ascii_int`, which is pure output, so the kernel is observed at the
exact reviewed candidate bytes.

Every override is an ENGINEERING TEST VALUE chosen to force a code branch.
None is biological, none is calibrated, none may be promoted to scientific
evidence.

Usage:
  python run_p07_geometry_fixtures.py --baseline-exe <bmx> --repaired-exe <bmx>
        --case-dir exec/fungi --out-dir <runs/...> [--json-out <path>]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

STOCK_RMAX = 2.5e-4
STOCK_LMAX = 35.0e-4
RE_STEP = re.compile(r"^\s*Step (\d+):", re.M)
RE_TIMING = re.compile(r"Time|time|seconds|memory|Memory")

FIXTURES = [
    dict(id="G1_tip_length_only", branch="TIP_LENGTH_ONLY", defect="CDEF-04",
         desc=("stock parameters. radius(2.5e-4) >= max_seg_radius(2.5e-4) at t=0, so :2044 "
               "and :2064 are both false and the tip takes the length-only path :2072"),
         args=["bmx.max_step=40"], rmax=STOCK_RMAX, lmax=STOCK_LMAX),
    dict(id="G2_tip_radius_only", branch="TIP_RADIUS_ONLY", defect="CDEF-04",
         desc=("raise max radius above r and drop max length below L: :2044 false, :2064 true "
               "-> radius-only path"),
         args=["bmx.max_step=40", "chem_species.max_seg_radius=1.0e-3",
               "chem_species.max_seg_length=1.0e-3"], rmax=1.0e-3, lmax=1.0e-3),
    dict(id="G3_tip_proportional", branch="TIP_PROPORTIONAL", defect="none (contrast)",
         desc=("raise both maxima so :2044 is true -> proportional path, which DOES write "
               "realIdx::area. Distinguishes 'area is stale' from 'area never changes'."),
         args=["bmx.max_step=40", "chem_species.max_seg_radius=1.0e-3",
               "chem_species.max_seg_length=1.0e-2"], rmax=1.0e-3, lmax=1.0e-2),
    dict(id="G4_nontip_rejected", branch="NONTIP_REJECTED", defect="CDEF-05",
         desc=("cascade splits into a multi-segment chain; non-tip segments have radius >= "
               "max_seg_radius so :2084 is false and growth is rejected at :2098"),
         args=["bmx.max_step=30", "chem_species.max_seg_length=6.0e-4",
               "chem_species.seg_split_length=3.0e-4"], rmax=STOCK_RMAX, lmax=6.0e-4),
    dict(id="G5_nontip_radial", branch="NONTIP_RADIAL",
         defect="none (contrast, expected unreachable)",
         desc=("raises max radius so :2084 could fire, but that same predicate gates "
               "checkSplit, so no chain forms and no non-tip segment exists"),
         args=["bmx.max_step=30", "chem_species.max_seg_length=6.0e-4",
               "chem_species.seg_split_length=3.0e-4", "chem_species.max_seg_radius=1.0e-3"],
         rmax=1.0e-3, lmax=6.0e-4, expect_unreachable=True),
    dict(id="G6_no_growth_stock_init", branch="NO_GROWTH", defect="none (control)",
         desc=("kv=0 with the STOCK init file. Geometry is inert, but the repair still differs "
               "by ~1.7e-5 because the stored area is rounded to 4 s.f."),
         args=["bmx.max_step=20", "chem_species.kv=0.0"], rmax=STOCK_RMAX, lmax=STOCK_LMAX,
         expect_identical=False),
    dict(id="G7_no_growth_exact_init", branch="NO_GROWTH", defect="none (control)",
         desc=("kv=0 with a self-consistent init file (area at full precision). The repair must "
               "now be exactly inert."),
         args=["bmx.max_step=20", "chem_species.kv=0.0"], rmax=STOCK_RMAX, lmax=STOCK_LMAX,
         initcfg="fixtures/fungi_init_cfg_selfconsistent.dat", expect_identical=True),
]


def run_tree(exe, wd, case_dir, model_args, init_cfg=None, ascii_on=True, timeout=900):
    os.makedirs(wd, exist_ok=True)
    shutil.copy(os.path.join(case_dir, "input_fungi"), wd)
    src = os.path.join(HERE, init_cfg) if init_cfg else os.path.join(case_dir, "fungi_init_cfg.dat")
    if not os.path.exists(src):
        raise SystemExit(f"init config not found: {src}")
    shutil.copy(src, os.path.join(wd, "fungi_init_cfg.dat"))

    io_args = (["amr.par_ascii_int=1", "amr.par_ascii_file=par"] if ascii_on
               else ["amr.par_ascii_int=-1"])
    cmd = [exe, "input_fungi"] + list(model_args) + ["amr.plot_int=-1", "amr.check_int=-1"] + io_args
    p = subprocess.run(cmd, cwd=wd, capture_output=True, text=True, timeout=timeout)
    log = p.stdout + p.stderr
    with open(os.path.join(wd, "stdout.log"), "w") as fh:
        fh.write(log)
    with open(os.path.join(wd, "command.txt"), "w") as fh:
        fh.write(" ".join(cmd) + "\n")

    # Do not trust that the overrides arrived -- prove it from the output.
    req = next((int(a.split("=")[1]) for a in model_args if a.startswith("bmx.max_step=")), None)
    if req is not None:
        steps = [int(m.group(1)) for m in RE_STEP.finditer(log)]
        if steps and max(steps) > req:
            raise SystemExit(
                f"override was dropped: requested bmx.max_step={req} but the run reached step "
                f"{max(steps)}. Fix the harness before trusting any fixture result.")
    if ascii_on:
        dumps = [f for f in os.listdir(wd) if re.fullmatch(r"par\d{5}", f)]
        if len(dumps) < 2:
            raise SystemExit(f"no particle dumps in {wd} -- amr.par_ascii_int did not take effect")
    return p.returncode, log


def strip_timing(text):
    return [ln for ln in text.splitlines() if not RE_TIMING.search(ln)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-exe", required=True)
    ap.add_argument("--repaired-exe", required=True)
    ap.add_argument("--case-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--json-out")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    analyzer = os.path.join(HERE, "analyze_p07_geometry.py")
    if os.path.isdir(a.out_dir):
        shutil.rmtree(a.out_dir)
    os.makedirs(a.out_dir, exist_ok=True)

    def sha(p):
        import hashlib
        return hashlib.sha256(open(p, "rb").read()).hexdigest()

    print(f"baseline exe : {a.baseline_exe}\n  sha256     : {sha(a.baseline_exe)}")
    print(f"repaired exe : {a.repaired_exe}\n  sha256     : {sha(a.repaired_exe)}\n")

    # ---- G0: observation neutrality ---------------------------------------
    # Everything below depends on the dump not perturbing the run. Prove it
    # first, on the repaired image, before any fixture is believed.
    print("--- G0_ascii_neutrality  [does observing change the result?]")
    g0 = os.path.join(a.out_dir, "G0_ascii_neutrality")
    _, on = run_tree(a.repaired_exe, os.path.join(g0, "ascii_on"), a.case_dir,
                     ["bmx.max_step=40"], timeout=a.timeout)
    _, off = run_tree(a.repaired_exe, os.path.join(g0, "ascii_off"), a.case_dir,
                      ["bmx.max_step=40"], ascii_on=False, timeout=a.timeout)
    sa, sb = strip_timing(on), strip_timing(off)
    neutral = sa == sb
    print(f"    non-timing lines compared : {len(sa)}")
    print(f"    NEUTRALITY                : {'PASS (identical)' if neutral else 'FAIL (differs)'}\n")
    if not neutral:
        raise SystemExit("particle ASCII output changed the trajectory. Every geometry fixture "
                         "below would be measuring the observer, not the model. Stopping.")

    rows = []
    for f in FIXTURES:
        fdir = os.path.join(a.out_dir, f["id"])
        print(f"--- {f['id']}  [target branch {f['branch']}]  defect {f['defect']}")
        print(f"    {f['desc']}")
        bd = os.path.join(fdir, "baseline")
        rd = os.path.join(fdir, "repaired")
        bx, _ = run_tree(a.baseline_exe, bd, a.case_dir, f["args"], f.get("initcfg"), timeout=a.timeout)
        rx, _ = run_tree(a.repaired_exe, rd, a.case_dir, f["args"], f.get("initcfg"), timeout=a.timeout)
        print(f"    baseline exit={bx}  repaired exit={rx}")

        js = os.path.join(fdir, "GEOMETRY.json")
        p = subprocess.run([sys.executable, analyzer, "--compare", bd, rd,
                            "--radius-max", repr(f["rmax"]), "--length-max", repr(f["lmax"]),
                            "--json-out", js], capture_output=True, text=True, timeout=900)
        if p.returncode != 0:
            raise SystemExit(f"analyzer failed for {f['id']}:\n{p.stdout}{p.stderr}")
        g = json.load(open(js))

        obs = g["repaired"]["observed_branch_counts"]
        pre = g["repaired"]["predicted_branch_counts"]
        hit = f["branch"] in obs
        identical = g["summary"]["trees_identical"]
        ndiff = g["summary"]["particles_differing"]
        print(f"    predicted : {pre}")
        print(f"    observed  : {obs}")
        print(f"    target branch reached : {'YES' if hit else 'NO'}")
        print(f"    baseline vs repaired  : "
              + ("IDENTICAL" if identical
                 else f"{ndiff} particle(s) differ, max_rel={g['summary']['max_rel']:.3e}"))

        if "expect_identical" in f:
            verdict = "PASS" if identical == f["expect_identical"] else "FAIL"
            print(f"    control expectation   : expect_identical={f['expect_identical']} -> {verdict}")
        elif f.get("expect_unreachable"):
            # Predeclared. If the branch DOES fire the argument is wrong and
            # that must surface as a failure, not be quietly absorbed.
            verdict = "FAIL_UNEXPECTEDLY_REACHED" if hit else "PASS_UNREACHABLE_AS_PREDICTED"
            print(f"    unreachability        : {verdict}")
        else:
            verdict = "PASS" if hit else "NOT_REACHED"

        rows.append(dict(id=f["id"], target_branch=f["branch"], defect=f["defect"],
                         description=f["desc"], arguments=f["args"],
                         init_cfg=f.get("initcfg", "exec/fungi/fungi_init_cfg.dat"),
                         radius_max=f["rmax"], length_max=f["lmax"],
                         baseline_exit=bx, repaired_exit=rx,
                         baseline_dir=bd, repaired_dir=rd, geometry_json=js,
                         branch_reached=hit, trees_identical=identical,
                         particles_differing=ndiff, max_rel=g["summary"]["max_rel"],
                         verdict=verdict))
        print()

    print("=" * 70)
    for r in rows:
        print(f"{r['id']:<28} {r['target_branch']:<30} {r['verdict']}")
    print("=" * 70)
    bad = [r for r in rows if r["verdict"].startswith("FAIL") or r["verdict"] == "NOT_REACHED"]
    print(f"fixtures run   : {len(rows)}")
    print(f"failing        : {len(bad)}")

    out = dict(baseline_exe=a.baseline_exe, baseline_exe_sha256=sha(a.baseline_exe),
               repaired_exe=a.repaired_exe, repaired_exe_sha256=sha(a.repaired_exe),
               case_dir=a.case_dir, ascii_neutrality="PASS" if neutral else "FAIL",
               neutrality_lines_compared=len(sa), fixtures=rows,
               failing=len(bad), status="PASS" if not bad else "FAIL")
    if a.json_out:
        os.makedirs(os.path.dirname(a.json_out), exist_ok=True)
        with open(a.json_out, "w") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
        print(f"index          : {a.json_out}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
