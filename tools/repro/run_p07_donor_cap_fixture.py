#!/usr/bin/env python3
"""BMX RG-SW -- C04 / P07 second-half donor-cap fixture (CDEF-01 / CDEF-02).

WHAT IS BEING PROVEN
--------------------
bmx_chem_K.H:2188 (A) and :2220 (C) cap the second-half fluid->particle
exchange at the amount the fluid actually holds. The P07 patch changes

    baseline:  dA2 = -fA_tmp*fluid_vol ;  dfA = -fA_tmp
    repaired:  dA2 =  fA_tmp*fluid_vol ;  dfA = dA2/fluid_vol

The baseline sign both zeroes the fluid AND debits the particle, destroying A.
The repaired form credits the particle exactly what the fluid held.

The mandatory C04 row is "capped transfer equals available amount", so the
evidence has to be fluid-side. A particle-transfer sign flip cannot establish
it: a sign flip only occurs when the BASELINE cap fires, and this construction
deliberately keeps the baseline under the cap, so only the repaired side
activates. That is why this fixture reads bmx.print_sums instead.

HOW THE WINDOW IS OPENED
------------------------
Both trees use the STORED area in the first half; only the repaired tree
recomputes the true geometric area for the second half. Storing an area 100x
smaller than 2*pi*r*(r+L) therefore puts the first half far under the cap while
the repaired second half can exceed it:

    alpha  = 0.5*dtp*A_stored*k1/fluid_vol   (both trees, first half)
    alpha' = 0.5*dtp*A_true  *k1/fluid_vol   (repaired only, second half)

with fluid_vol = grid_vol/npart (:1438), dtp = fixed_dt/substeps = 0.0625.

TWO CONFOUNDS THAT HAD TO BE REMOVED FIRST
------------------------------------------
1. The particle sits at z = 0.0752, just ABOVE fluid.surface_location = 0.075,
   where the initial fluid A is zero. No uptake is possible there at all, so the
   surface is raised above the domain to make the field uniform.
2. rA = -k2*cA + kr2*cB*cC (:1849) drains A far faster than the exchange moves
   it, which masks the effect entirely. k2/kr2 are zeroed, along with growth
   (kv, kg), so the ONLY process touching A is the membrane exchange.

Every override is an ENGINEERING TEST VALUE chosen to force a code branch.
None is biological, none is calibrated, none may be promoted to scientific
evidence.

THE SIGNATURE
-------------
Sweeping k1: an UNCAPPED transfer grows linearly with k1 forever. A CAPPED
transfer saturates at the cell's content and stops. Saturation at exactly
fA0*V_cell is the proof, and it is a shape, not a single number.

Usage:
  python run_p07_donor_cap_fixture.py --baseline-exe <bmx> --repaired-exe <bmx>
        --case-dir exec/fungi --out-dir <runs/...> [--json-out <path>]
Both executables must be built WITH the bmx.print_sums diagnostic.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys

RE_KV = re.compile(r"^SUMS (\w+) ([-+0-9.eE]+)$")

# Engineering test values. See module docstring for the derivation of each.
K1_SWEEP = [0.5, 1.0, 2.0, 5.0, 20.0, 100.0]
STORED_AREA_RATIO = 100.0
BASE_ARGS = [
    "amr.plot_int=-1", "amr.check_int=-1", "bmx.print_sums=1",
    "bmx.max_step=1",
    "fluid.surface_location=0.2",   # confound 1: put fluid A at the particle
    "chem_species.kr1=0.0",         # pure uptake, no back-reaction
    "chem_species.k2=0.0",          # confound 2: stop rA from draining A
    "chem_species.kr2=0.0",
    "chem_species.kv=0.0",          # no growth
    "chem_species.kg=0.0",
]


def sums_blocks(path):
    out, cur = [], {}
    for ln in open(path):
        m = RE_KV.match(ln.rstrip())
        if m:
            cur[m.group(1)] = float(m.group(2))
        elif cur and "A_total" in cur:
            out.append(cur); cur = {}
    if cur and "A_total" in cur:
        out.append(cur)
    return out


def write_small_area_init(case_dir, dst, ratio):
    lines = open(os.path.join(case_dir, "fungi_init_cfg.dat")).read().split("\n")
    cols = lines[1].split()
    r, L = float(cols[3]), float(cols[4])
    true_area = 2.0 * math.pi * r * (r + L)     # n_bnds == 0 branch, :2110
    cols[7] = repr(true_area / ratio)
    with open(dst, "w") as fh:
        fh.write(lines[0] + "\n" + " ".join(cols) + "\n")
    return r, L, true_area


def run(exe, workdir, case_dir, init_cfg, extra):
    os.makedirs(workdir, exist_ok=True)
    shutil.copy(os.path.join(case_dir, "input_fungi"), workdir)
    shutil.copy(init_cfg, os.path.join(workdir, "fungi_init_cfg.dat"))
    cmd = [exe, "input_fungi"] + BASE_ARGS + extra
    p = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=900)
    log = p.stdout + p.stderr
    with open(os.path.join(workdir, "stdout.log"), "w") as fh:
        fh.write(log)
    with open(os.path.join(workdir, "command.txt"), "w") as fh:
        fh.write(" ".join(cmd) + "\n")
    return p.returncode, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-exe", required=True)
    ap.add_argument("--repaired-exe", required=True)
    ap.add_argument("--case-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--json-out")
    a = ap.parse_args()

    if os.path.isdir(a.out_dir):
        shutil.rmtree(a.out_dir)
    os.makedirs(a.out_dir, exist_ok=True)

    init_cfg = os.path.join(a.out_dir, "fungi_init_cfg_small_stored_area.dat")
    r, L, true_area = write_small_area_init(a.case_dir, init_cfg, STORED_AREA_RATIO)
    stored_area = true_area / STORED_AREA_RATIO

    # Geometry / discretisation constants, read from the case rather than assumed.
    txt = open(os.path.join(a.case_dir, "input_fungi")).read()

    def find(k):
        m = re.search(rf"^\s*{re.escape(k)}\s*=\s*(.+?)(?:#.*)?$", txt, re.M)
        return m.group(1).strip()

    lo = [float(x) for x in find("geometry.prob_lo").split()]
    hi = [float(x) for x in find("geometry.prob_hi").split()]
    nc = [int(x) for x in find("amr.n_cell").split()]
    max_level = int(find("amr.max_level"))
    fixed_dt = float(find("bmx.fixed_dt"))
    fA0 = float(find("fluid.init_conc_species").split()[0])

    cell0 = ((hi[0]-lo[0])*(hi[1]-lo[1])*(hi[2]-lo[2])) / (nc[0]*nc[1]*nc[2])
    cell_fine = cell0 / (8 ** max_level)         # 2x refinement per level, 3D
    dtp = fixed_dt / 4.0                          # 4 chemistry substeps per step
    available = fA0 * cell_fine

    print(f"radius={r!r} c_length={L!r}")
    print(f"true area   = {true_area:.8e}")
    print(f"stored area = {stored_area:.8e}  (ratio {STORED_AREA_RATIO:g})")
    print(f"fine cell volume = {cell_fine:.8e}")
    print(f"AVAILABLE A in one cell = fA0*V = {available:.8e}")
    print()
    print(f"{'k1':>7} {'alpha':>9} {'alphaprime':>11} "
          f"{'baseline dA':>14} {'repaired dA':>14} {'rep/available':>14} {'capped':>7}")

    rows = []
    for k1 in K1_SWEEP:
        alpha = 0.5 * dtp * stored_area * k1 / cell_fine
        alphap = 0.5 * dtp * true_area * k1 / cell_fine
        rec = {"k1": k1, "alpha_first_half": alpha, "alpha_second_half_repaired": alphap,
               "uncapped_request_true_area": 0.5*dtp*true_area*k1*fA0}
        for tag, exe in (("baseline", a.baseline_exe), ("repaired", a.repaired_exe)):
            wd = os.path.join(a.out_dir, f"k1_{k1:g}", tag)
            rc, _ = run(exe, wd, a.case_dir, init_cfg, [f"chem_species.k1={k1}"])
            b = sums_blocks(os.path.join(wd, "stdout.log"))
            if rc != 0 or len(b) < 2:
                rec[tag] = {"exit": rc, "error": "no usable SUMS blocks"}
                continue
            dP = b[-1]["A_particles"] - b[0]["A_particles"]
            dF = b[-1]["A_fluid"] - b[0]["A_fluid"]
            rec[tag] = {
                "exit": rc,
                "A_particles_initial": b[0]["A_particles"],
                "A_particles_final": b[-1]["A_particles"],
                "A_fluid_initial": b[0]["A_fluid"],
                "A_fluid_final": b[-1]["A_fluid"],
                "delta_A_particles": dP,
                "delta_A_fluid": dF,
                "conservation_residual": dP + dF,
                "transfer_over_available": dP / available if available else None,
                "run_dir": wd,
            }
        bd = rec["baseline"].get("delta_A_particles")
        rd = rec["repaired"].get("delta_A_particles")
        ratio = (rd / available) if (rd is not None and available) else float("nan")
        # A capped transfer cannot exceed the cell content. Allow a little
        # headroom for diffusive refill across the four substeps.
        capped = (alphap > 1.0) and (ratio <= 1.02)
        rec["repaired_capped"] = bool(capped)
        rows.append(rec)
        print(f"{k1:7g} {alpha:9.4f} {alphap:11.3f} {bd:14.6e} {rd:14.6e} "
              f"{ratio:14.6f} {str(capped):>7}")

    # Verdict.
    #
    # Two things must both hold, because either alone is weak:
    #   SATURATION  once alpha' > 1 the transfer stops tracking k1 and pins to
    #               the cell content. An uncapped transfer would keep growing.
    #   CONSERVED   the fluid loses exactly what the particle gains, which is
    #               what distinguishes the repaired assignment from the baseline
    #               one that destroys A.
    active = [r for r in rows if r["alpha_second_half_repaired"] > 1.0
              and "delta_A_particles" in r.get("repaired", {})]
    ratios = [r["repaired"]["delta_A_particles"] / available for r in active]
    saturated = bool(active) and (max(ratios) - min(ratios) < 1e-3) and all(x <= 1.02 for x in ratios)
    max_resid = max((abs(r[t]["conservation_residual"]) / available
                     for r in rows for t in ("baseline", "repaired")
                     if "conservation_residual" in r.get(t, {})), default=None)
    conserved = (max_resid is not None) and (max_resid < 1e-9)

    # The mandatory C04 row, stated exactly. After the cap fires, everything the
    # cell held is in the particle: what it already carried plus the capped
    # transfer must equal fA0*V_cell. This is the claim itself, not a proxy for
    # it, so it is checked to near machine precision rather than to a tolerance
    # chosen for convenience.
    eq_rows = []
    for r in active:
        rep = r["repaired"]
        got = rep["A_particles_final"]
        rel = abs(got - available) / available
        eq_rows.append({"k1": r["k1"], "A_particles_final": got,
                        "available": available, "relative_difference": rel,
                        "equal": rel <= 1e-14})
        rep["transfer_equals_available"] = bool(rel <= 1e-14)
    equality = bool(eq_rows) and all(e["equal"] for e in eq_rows)

    verdict = ("CAP_FIRES_AND_TRANSFER_EQUALS_AVAILABLE"
               if (saturated and conserved and equality) else
               "CAP_NOT_DEMONSTRATED" if not saturated else
               "CAP_FIRES_BUT_NOT_CONSERVATIVE" if not conserved else
               "CAP_FIRES_BUT_TRANSFER_NOT_EQUAL_TO_AVAILABLE")

    out = {
        "purpose": "runtime evidence for CDEF-01/CDEF-02, the second-half fluid donor cap",
        "baseline_exe": a.baseline_exe, "repaired_exe": a.repaired_exe,
        "observable": "bmx.print_sums fluid-side totals (A_fluid, A_particles) at full precision",
        "why_not_sign_flip": ("a sign flip only occurs when the BASELINE cap fires; this "
                              "construction keeps the baseline under the cap by design, so only "
                              "the repaired side activates and the sign test is blind to it"),
        "confounds_removed": [
            "particle sits above fluid.surface_location where fluid A is zero -> surface raised to 0.2",
            "rA = -k2*cA + kr2*cB*cC drains A faster than the exchange -> k2/kr2 zeroed",
            "growth would change the area mid-step -> kv/kg zeroed",
        ],
        "geometry": {"radius": r, "c_length": L, "true_area": true_area,
                     "stored_area": stored_area, "stored_area_ratio": STORED_AREA_RATIO,
                     "fine_cell_volume": cell_fine, "fA0": fA0,
                     "available_A_in_cell": available, "dtp": dtp},
        "rows": rows,
        "saturation_observed": saturated,
        "conservation_max_relative_residual": max_resid,
        "transfer_equals_available": equality,
        "transfer_equals_available_rows": eq_rows,
        "verdict": verdict,
    }
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
        print(f"\nwrote {a.json_out}")
    print()
    for e in eq_rows:
        print(f"  k1={e['k1']:<6} A_particles_final={e['A_particles_final']!r} "
              f"available={e['available']!r} rel={e['relative_difference']:.2e} "
              f"{'EQUAL' if e['equal'] else 'NOT EQUAL'}")
    print(f"\nsaturation observed        : {saturated}")
    print(f"transfer equals available  : {equality}")
    print(f"max conservation residual  : {max_resid:.3e} (relative to the cell content)")
    print(f"VERDICT                    : {verdict}")
    return 0 if verdict == "CAP_FIRES_AND_TRANSFER_EQUALS_AVAILABLE" else 1


if __name__ == "__main__":
    sys.exit(main())
