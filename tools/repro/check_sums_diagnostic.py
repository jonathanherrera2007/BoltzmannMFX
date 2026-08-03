#!/usr/bin/env python3
"""BMX RG-SW -- regression guard for the ComputeAndPrintSums conservation diagnostic.

The diagnostic in src/bmx.cpp was dead for long enough to acquire two silent
defects (hard-coded particle components 22/23/24 that stopped meaning A/B/C when
realIdx::first_data moved to 28, and hard-coded mesh components that ignore the
order in `fluid.chem_species`). Anything that can rot while unused needs a test
that fails when it rots again.

Five checks, each of which fails loudly:

  1. FIELD MAP     the reported particle component for each species equals
                   realIdx::first_data + slot, and the mesh component is the one
                   the species actually occupies in fluid.chem_species
  2. PARTICLE SUM  the diagnostic's particle totals match a reference computed
                   independently from the particle ASCII dump (different code
                   path, different output channel)
  3. FLUID SUM     the diagnostic's fluid totals match the analytic content of
                   the initial condition
  4. BAD MAP ABORTS  a reordered fluid.chem_species is rejected rather than
                   silently pairing different species together
  5. NEUTRALITY    enabling the diagnostic does not change the trajectory

Cross-platform on purpose: DEC-PLATFORM-001 makes Linux the reference platform,
so this must run there unchanged.

Usage:
  python check_sums_diagnostic.py --exe <bmx> [--case-dir <exec/fungi>]
                                  [--work-dir <scratch>] [--json-out <path>]
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
sys.path.insert(0, HERE)
import analyze_p07_geometry as G  # noqa: E402  (same directory, intentional)

SPECIES = ["A", "B", "C"]
RE_MAP = re.compile(r"^SUMS component_map (\w+) mesh=(-?\d+) particle=(-?\d+)", re.M)
RE_FIRST = re.compile(r"^SUMS first_data (\d+)", re.M)
RE_KV = re.compile(r"^SUMS ([A-Za-z_]+) ([-+0-9.eE]+)$", re.M)
RE_TIMING = re.compile(r"Time|time|seconds|memory|Memory")


def run(exe, workdir, case_dir, args, init_cfg=None):
    os.makedirs(workdir, exist_ok=True)
    shutil.copy(os.path.join(case_dir, "input_fungi"), workdir)
    shutil.copy(init_cfg or os.path.join(case_dir, "fungi_init_cfg.dat"),
                os.path.join(workdir, "fungi_init_cfg.dat"))
    cmd = [exe, "input_fungi", "amr.plot_int=-1", "amr.check_int=-1"] + args
    p = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=900)
    log = p.stdout + p.stderr
    with open(os.path.join(workdir, "stdout.log"), "w") as fh:
        fh.write(log)
    return p.returncode, log


def parse_sums(log):
    """Last SUMS block in the log."""
    kv = {}
    for m in RE_KV.finditer(log):
        kv[m.group(1)] = float(m.group(2))
    cmap = {m.group(1): (int(m.group(2)), int(m.group(3))) for m in RE_MAP.finditer(log)}
    first = RE_FIRST.search(log)
    return kv, cmap, (int(first.group(1)) if first else None)


def read_input_scalars(case_dir):
    """Pull the few input values the analytic fluid reference needs."""
    txt = open(os.path.join(case_dir, "input_fungi")).read()

    def find(key):
        m = re.search(rf"^\s*{re.escape(key)}\s*=\s*(.+?)(?:#.*)?$", txt, re.M)
        return m.group(1).strip() if m else None

    lo = [float(x) for x in find("geometry.prob_lo").split()]
    hi = [float(x) for x in find("geometry.prob_hi").split()]
    ncell = [int(x) for x in find("amr.n_cell").split()]
    names = find("fluid.chem_species").split()
    conc = [float(x) for x in find("fluid.init_conc_species").split()]
    surf = float(find("fluid.surface_location"))
    return dict(lo=lo, hi=hi, ncell=ncell, names=names, conc=conc, surface=surf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--case-dir", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--json-out")
    a = ap.parse_args()

    results, failures = [], []

    def record(name, ok, detail):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        if not ok:
            failures.append(name)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    cfg = read_input_scalars(a.case_dir)

    # ---- baseline run: initialization only, diagnostic on, dump on ---------
    w0 = os.path.join(a.work_dir, "init")
    rc, log = run(a.exe, w0, a.case_dir,
                  ["bmx.max_step=0", "bmx.print_sums=1",
                   "amr.par_ascii_int=1", "amr.par_ascii_file=par"])
    if rc != 0:
        record("run_succeeds", False, f"exit={rc}")
        print(log[-2000:])
        return 1
    kv, cmap, first_data = parse_sums(log)

    # ---- 1. FIELD MAP -----------------------------------------------------
    ok, detail = True, []
    if first_data is None or not cmap:
        ok, detail = False, ["diagnostic emitted no component map"]
    else:
        for slot, sp in enumerate(SPECIES):
            if sp not in cmap:
                ok = False; detail.append(f"{sp} missing"); continue
            mesh, part = cmap[sp]
            want_mesh = cfg["names"].index(sp) if sp in cfg["names"] else None
            want_part = first_data + slot
            if part != want_part:
                ok = False
                detail.append(f"{sp} particle={part} expected first_data+{slot}={want_part}")
            if mesh != want_mesh:
                ok = False
                detail.append(f"{sp} mesh={mesh} expected {want_mesh}")
        # The stale indices this guard exists to catch.
        if first_data + 0 == 22:
            ok = False; detail.append("first_data is 22 -- the stale layout is back")
    record("field_map_matches_first_data_and_species_order", ok,
           "; ".join(detail) if detail else
           f"first_data={first_data}, " +
           ", ".join(f"{s}=mesh{cmap[s][0]}/part{cmap[s][1]}" for s in SPECIES))

    # ---- 2. PARTICLE SUM vs independent reference -------------------------
    # Reference comes from the particle ASCII dump, a different output path
    # entirely: sum(vol * committed concentration) over live particles.
    dump = os.path.join(w0, "par00000")
    ok, detail = True, []
    if not os.path.exists(dump):
        ok, detail = False, ["par00000 not written"]
    else:
        parts = G.load_dump(dump)
        for slot, sp in enumerate(SPECIES):
            ref = sum(p.vol * p.committed[slot] for p in parts.values())
            got = kv.get(f"{sp}_particles")
            if got is None:
                ok = False; detail.append(f"{sp}_particles not reported"); continue
            den = max(abs(ref), abs(got))
            rel = abs(got - ref) / den if den else 0.0
            if rel > 1e-12:
                ok = False
                detail.append(f"{sp}: diagnostic={got!r} reference={ref!r} rel={rel:.3e}")
            else:
                detail.append(f"{sp}={got:.10e} (rel {rel:.1e})")
    record("particle_totals_match_independent_dump_reference", ok, "; ".join(detail))

    # ---- 3. FLUID SUM vs analytic initial condition -----------------------
    # The initial fluid field is init_conc below fluid.surface_location and zero
    # above it, so the analytic content is conc * domain_area * surface height.
    lo, hi = cfg["lo"], cfg["hi"]
    area = (hi[0] - lo[0]) * (hi[1] - lo[1])
    height = cfg["surface"] - lo[2]
    ok, detail = True, []
    for sp in SPECIES:
        idx = cfg["names"].index(sp)
        ref = cfg["conc"][idx] * area * height
        got = kv.get(f"{sp}_fluid")
        if got is None:
            ok = False; detail.append(f"{sp}_fluid not reported"); continue
        den = max(abs(ref), abs(got))
        rel = abs(got - ref) / den if den else 0.0
        if rel > 1e-9:
            ok = False
            detail.append(f"{sp}: diagnostic={got!r} analytic={ref!r} rel={rel:.3e}")
        else:
            detail.append(f"{sp}={got:.10e} (rel {rel:.1e})")
    record("fluid_totals_match_analytic_initial_condition", ok, "; ".join(detail))

    # ---- 4. BAD MAP ABORTS ------------------------------------------------
    # Reorder the species list so A is no longer component 0. The diagnostic
    # must refuse rather than pair mesh B with particle A.
    w1 = os.path.join(a.work_dir, "badmap")
    rc2, log2 = run(a.exe, w1, a.case_dir,
                    ["bmx.max_step=0", "bmx.print_sums=1",
                     'fluid.chem_species="B A C D F P"'])
    aborted = rc2 != 0
    ours = "ComputeAndPrintSums" in log2
    record("reordered_species_is_rejected", aborted,
           f"exit={rc2}, diagnostic-owned abort={ours}" +
           ("" if aborted else " -- a wrong map was accepted silently"))

    # ---- 5. NEUTRALITY ----------------------------------------------------
    def strip(text):
        # Every line the diagnostic emits is prefixed "SUMS", so removing that
        # prefix plus wall-clock timing leaves exactly the trajectory.
        return [ln for ln in text.splitlines()
                if not ln.startswith("SUMS") and not RE_TIMING.search(ln)]

    wa = os.path.join(a.work_dir, "neutral_on")
    wb = os.path.join(a.work_dir, "neutral_off")
    _, la = run(a.exe, wa, a.case_dir, ["bmx.max_step=20", "bmx.print_sums=1"])
    _, lb = run(a.exe, wb, a.case_dir, ["bmx.max_step=20", "bmx.print_sums=0"])
    sa, sb = strip(la), strip(lb)
    ok = sa == sb
    record("enabling_diagnostic_is_trajectory_neutral", ok,
           f"{len(sa)} non-diagnostic lines compared, "
           + ("identical" if ok else f"{sum(1 for x, y in zip(sa, sb) if x != y)} differ"))

    out = {
        "exe": a.exe,
        "case_dir": a.case_dir,
        "first_data": first_data,
        "component_map": {k: {"mesh": v[0], "particle": v[1]} for k, v in cmap.items()},
        "checks": results,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
        print(f"\nwrote {a.json_out}")
    print(f"\nstatus: {out['status']}" + (f"  failures: {failures}" if failures else ""))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
