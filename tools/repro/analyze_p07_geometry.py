#!/usr/bin/env python3
"""BMX RG-SW -- C04 / P07 particle-geometry branch observer.

Resolves blocker B-C04-01. The first C04 fixture matrix inferred branch
execution from *structural* statistics of the stdout log (count of differing
lines, max relative difference). Those statistics cannot distinguish which
growth branch ran: a 20-step run yields the same number of differing MLMG lines
regardless. This module replaces inference with direct observation.

It reads AMReX particle ASCII dumps (`amr.par_ascii_int`), which are pure
output: enabling them does not perturb the trajectory (verified, and re-verified
by fixture G0 in run_p07_geometry_fixtures.ps1). The kernel is therefore
observed at the exact reviewed candidate bytes -- no instrumentation, so the
candidate hash 9519fc24...ffba02 is preserved.

Two independent determinations are made for every particle at every dump and
then required to agree:

  PREDICTED  evaluate the source's own branch predicates
             (bmx_chem_K.H:2038-2105) against the observed radius / c_length
  OBSERVED   classify what actually changed between consecutive dumps

Agreement between a prediction derived from the source text and an observation
derived from the output bytes is what makes this evidence rather than assertion.

Usage:
  python analyze_p07_geometry.py --run-dir DIR --radius-max R --length-max L
  python analyze_p07_geometry.py --compare BASE_DIR REPAIRED_DIR ...
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

# --- Column map -------------------------------------------------------------
# AMReX ParticleContainer::WriteAsciiFile (AMReX_ParticleIO.H:1024) writes, per
# particle: AMREX_SPACEDIM positions, NStructReal rdata, id, cpu, NStructInt
# idata, then SoA components. Offsets below are read off bmx_chem.H and are
# asserted against the file header at load time.
NDIM = 3
RD = NDIM                       # rdata base

# realIdx (bmx_chem.H:41). NOTE: the trailing numbers in that enum's comments
# are 1-based position markers, not indices -- `area // 5` is index 4. An
# earlier version of this file mis-read them and had R_DADT/R_DVDT one slot
# too high, silently reading dvdt as dadt and tau_split as dvdt.
R_RADIUS, R_CLENGTH, R_THETA, R_PHI, R_AREA, R_VOL = 0, 1, 2, 3, 4, 5
R_GZ, R_DADT, R_DVDT, R_TAU_SPLIT, R_BOND_SCALE = 20, 21, 22, 23, 24
R_FIRST_DATA = 28

# intIdx (bmx_chem.H:83)
I_NUM_REALS, I_NUM_INTS, I_REAL_TOT, I_INT_TOT = 0, 1, 2, 3
I_FIRST_REAL_INC, I_CELL_TYPE, I_NBNDS = 4, 5, 6
I_POSITION, I_ID, I_CPU = 19, 33, 34

# cellType / siteLocation (bmx_chem.H:126,134)
CELLTYPE_FUNGI = 1
SITE_TIP = 0

EXPECT_NSTRUCT_INT = 35         # MAX_CHEM_INT_VAR

# P09 widens only the particle storage ABI: 28 + 3*6 -> 28 + 3*8.  The
# feature-off semantic surface remains the first six legacy components.  Keep
# the accepted layouts explicit so a future ABI change still fails closed.
SUPPORTED_LAYOUTS = {
    46: 6,                       # pre-P09: MAX_CHEM_REAL_VAR = 28 + 3*6
    52: 8,                       # P09:     MAX_CHEM_REAL_VAR = 28 + 3*8
}
NUM_SEMANTIC_CHEM = 6

SPECIES = ["A", "B", "C", "D", "E", "P"]

# Branch labels. The two marked DEFECT are the ones B-C04-01 says are
# undemonstrated at runtime.
TIP_PROPORTIONAL = "TIP_PROPORTIONAL"        # bmx_chem_K.H:2044 writes area
TIP_RADIUS_ONLY = "TIP_RADIUS_ONLY"          # :2064 CDEF-04 -- area NOT written
TIP_LENGTH_ONLY = "TIP_LENGTH_ONLY"          # :2072 CDEF-04 -- area NOT written
NONTIP_RADIAL = "NONTIP_RADIAL"              # :2084 writes area
NONTIP_REJECTED = "NONTIP_REJECTED"          # :2098 CDEF-05 -- rollback
NO_GROWTH = "NO_GROWTH"                      # rV == 0, nothing moved


class Particle:
    __slots__ = ("key", "pos", "r", "L", "area", "vol", "dadt", "dvdt",
                 "committed", "working", "increment", "reserved",
                 "storage_components", "cell_type", "n_bnds", "position")

    def __init__(self, cols, nsr, nsi):
        f = [float(c) for c in cols]
        self.r = f[RD + R_RADIUS]
        self.L = f[RD + R_CLENGTH]
        self.area = f[RD + R_AREA]
        self.vol = f[RD + R_VOL]
        self.dadt = f[RD + R_DADT]
        self.dvdt = f[RD + R_DVDT]
        self.pos = (f[0], f[1], f[2])

        ib = NDIM + nsr + 2                          # idata base (after id,cpu)
        self.cell_type = int(f[ib + I_CELL_TYPE])
        self.n_bnds = int(f[ib + I_NBNDS])
        self.position = int(f[ib + I_POSITION])
        self.key = (int(f[ib + I_ID]), int(f[ib + I_CPU]))

        # Self-describing layout check. intIdx::num_reals, real_tot and
        # first_real_inc are written by the model itself and pin the p_vals
        # block, so a wrong R_FIRST_DATA or a changed NUM_CHEM_COMPONENTS is
        # caught here instead of silently shifting every concentration.
        nr, rt, fri = (int(f[ib + I_NUM_REALS]), int(f[ib + I_REAL_TOT]),
                       int(f[ib + I_FIRST_REAL_INC]))
        expected_nr = SUPPORTED_LAYOUTS[nsr]
        if (nr, rt, fri) != (expected_nr, 3 * expected_nr, 2 * expected_nr):
            raise SystemExit(
                f"particle reports num_reals={nr} real_tot={rt} "
                f"first_real_inc={fri}, expected {expected_nr}/{3*expected_nr}/"
                f"{2*expected_nr}. The column map is stale -- do not trust results.")

        pv = RD + R_FIRST_DATA                       # p_vals base
        self.storage_components = nr
        self.committed = f[pv:pv + NUM_SEMANTIC_CHEM]
        self.working = f[pv + nr:pv + nr + NUM_SEMANTIC_CHEM]
        self.increment = f[pv + 2 * nr:pv + 2 * nr + NUM_SEMANTIC_CHEM]
        self.reserved = {
            "committed": f[pv + NUM_SEMANTIC_CHEM:pv + nr],
            "working": f[pv + nr + NUM_SEMANTIC_CHEM:pv + 2 * nr],
            "increment": f[pv + 2 * nr + NUM_SEMANTIC_CHEM:pv + 3 * nr],
        }
        # Physical fields must be positive for a live segment. This is the
        # cheap tripwire for an off-by-one in the rdata offsets.
        if not (self.r > 0.0 and self.area > 0.0 and self.vol > 0.0):
            raise SystemExit(
                f"particle {self.key} has radius={self.r} area={self.area} "
                f"vol={self.vol}; a non-positive geometry field means the "
                f"rdata column map is wrong.")

    @property
    def is_tip(self):
        return self.position == SITE_TIP


def load_dump(path):
    """Parse one AMReX particle ASCII dump. Returns {key: Particle}."""
    with open(path, "r") as fh:
        lines = fh.read().split("\n")
    npart = int(lines[0])
    nsr, nsi = int(lines[1]), int(lines[2])
    nrc, nic = int(lines[3]), int(lines[4])

    # Fail loudly rather than silently mis-slicing if the ABI ever moves.
    if nsr not in SUPPORTED_LAYOUTS or nsi != EXPECT_NSTRUCT_INT:
        raise SystemExit(
            f"{path}: particle ABI is {nsr} reals / {nsi} ints, expected "
            f"one of {sorted(SUPPORTED_LAYOUTS)}/{EXPECT_NSTRUCT_INT}. The column map in "
            f"analyze_p07_geometry.py is stale -- update it before trusting "
            f"any result.")

    expect_cols = NDIM + nsr + 2 + nsi + nrc + nic
    out = {}
    for ln in lines[5:]:
        if not ln.strip():
            continue
        cols = ln.split()
        if len(cols) != expect_cols:
            raise SystemExit(f"{path}: expected {expect_cols} columns, got {len(cols)}")
        p = Particle(cols, nsr, nsi)
        out[p.key] = p
    if len(out) != npart:
        raise SystemExit(f"{path}: header says {npart} particles, parsed {len(out)}"
                         " (duplicate id/cpu key?)")
    return out


def dumps_in(run_dir, prefix="par"):
    pat = os.path.join(run_dir, prefix + "[0-9]" * 5)
    return sorted(glob.glob(pat))


def predict_branch(p, radius_max, length_max):
    """Which branch the geometry predicates select. Mirrors bmx_chem_K.H:2038-2105.

    This answers "which branch would run *if* growth occurred". It deliberately
    does not model whether rV is zero, because rV depends on cB and kv, which
    are not in the dump. So under a kv=0 control the prediction still names a
    geometry branch while the observation correctly reports NO_GROWTH. That
    disagreement is expected and is not evidence of a mismatch; every other
    fixture has nonzero growth, where the two must agree.
    """
    if p.cell_type != CELLTYPE_FUNGI:
        return "YEAST"
    if p.is_tip:
        if p.r < radius_max and p.L < length_max:
            return TIP_PROPORTIONAL
        if p.r < radius_max:
            return TIP_RADIUS_ONLY
        return TIP_LENGTH_ONLY
    if p.r < radius_max:
        return NONTIP_RADIAL
    return NONTIP_REJECTED


def observe_branch(prev, cur):
    """Classify what actually changed. Returns (branch, area_changed).

    Exact comparisons only. Exactness is the point: the radius-only and
    length-only branches are distinguished from the proportional branch
    precisely by one field being left *bit-identical*, and CDEF-05's rollback
    restores vol to orig_cell_vol exactly. A tolerance here would erase the
    signal.
    """
    dr = cur.r != prev.r
    dl = cur.L != prev.L
    dv = cur.vol != prev.vol
    area_changed = cur.area != prev.area

    if not dv and cur.dvdt == 0.0 and cur.dadt == 0.0 and not cur.is_tip:
        return NONTIP_REJECTED, area_changed
    if not dr and not dl and not dv:
        return NO_GROWTH, area_changed
    if not cur.is_tip:
        return NONTIP_RADIAL, area_changed
    if dr and dl:
        return TIP_PROPORTIONAL, area_changed
    if dr and not dl:
        return TIP_RADIUS_ONLY, area_changed
    if dl and not dr:
        return TIP_LENGTH_ONLY, area_changed
    return "UNCLASSIFIED", area_changed


def analyze(run_dir, radius_max, length_max, prefix="par"):
    files = dumps_in(run_dir, prefix)
    if len(files) < 2:
        raise SystemExit(f"{run_dir}: need >= 2 particle dumps, found {len(files)}")

    steps = [(f, load_dump(f)) for f in files]
    predicted, observed, area_stale = {}, {}, {}
    transitions, split_events = 0, 0

    reserved_observations = 0
    reserved_nonzero = 0
    reserved_max_abs = 0.0
    layouts_seen = set()
    for _, dump in steps:
        for p in dump.values():
            layouts_seen.add(p.storage_components)
            for vals in p.reserved.values():
                for value in vals:
                    reserved_observations += 1
                    if value != 0.0:
                        reserved_nonzero += 1
                        reserved_max_abs = max(reserved_max_abs, abs(value))

    for (_, prev), (fcur, cur) in zip(steps, steps[1:]):
        for key, pc in cur.items():
            pp = prev.get(key)
            if pp is None:
                split_events += 1          # particle created this step
                continue
            # A split reassigns c_length discontinuously (seg_split_length).
            # Those transitions are not growth-branch transitions; count them
            # separately rather than misclassifying them.
            if pc.L < pp.L and pc.vol < pp.vol:
                split_events += 1
                continue
            transitions += 1
            b = predict_branch(pc, radius_max, length_max)
            o, area_changed = observe_branch(pp, pc)
            predicted[b] = predicted.get(b, 0) + 1
            observed[o] = observed.get(o, 0) + 1
            # CDEF-04 signature: geometry moved but the stored area field was
            # left bit-identical, i.e. the branch never refreshed it.
            if o in (TIP_RADIUS_ONLY, TIP_LENGTH_ONLY):
                area_stale.setdefault(o, {"stale": 0, "refreshed": 0})
                area_stale[o]["refreshed" if area_changed else "stale"] += 1

    final = steps[-1][1]
    return {
        "run_dir": run_dir,
        "dumps": len(files),
        "radius_max": radius_max,
        "length_max": length_max,
        "transitions_classified": transitions,
        "split_or_new_particle_events": split_events,
        "particle_storage_components_seen": sorted(layouts_seen),
        "reserved_slot_audit": {
            "observations": reserved_observations,
            "nonzero": reserved_nonzero,
            "max_abs": reserved_max_abs,
        },
        "predicted_branch_counts": predicted,
        "observed_branch_counts": observed,
        "area_left_stale_counts": area_stale,
        "final_particle_count": len(final),
        "final_state": {
            f"{k[0]}.{k[1]}": {
                "radius": p.r, "c_length": p.L, "area": p.area, "vol": p.vol,
                "is_tip": p.is_tip, "n_bnds": p.n_bnds,
                "committed": dict(zip(SPECIES, p.committed)),
                "working": dict(zip(SPECIES, p.working)),
                "transferred_amount": dict(zip(SPECIES, p.increment)),
            } for k, p in sorted(final.items())
        },
    }


def compare(base, rep):
    """Baseline-vs-repaired difference on the states the repair should move."""
    bf = base["final_state"]
    rf = rep["final_state"]
    keys = sorted(set(bf) | set(rf))
    rows = []
    for k in keys:
        b, r = bf.get(k), rf.get(k)
        if b is None or r is None:
            rows.append({"particle": k, "present_in_both": False})
            continue
        row = {"particle": k, "present_in_both": True, "fields": {}}
        for grp in ("committed", "working", "transferred_amount"):
            for sp in SPECIES:
                bv, rv = b[grp][sp], r[grp][sp]
                if bv != rv:
                    denom = max(abs(bv), abs(rv))
                    row["fields"][f"{grp}.{sp}"] = {
                        "baseline": bv, "repaired": rv,
                        "rel": (abs(rv - bv) / denom) if denom else 0.0,
                    }
        for gf in ("radius", "c_length", "area", "vol"):
            if b[gf] != r[gf]:
                denom = max(abs(b[gf]), abs(r[gf]))
                row["fields"][gf] = {
                    "baseline": b[gf], "repaired": r[gf],
                    "rel": (abs(r[gf] - b[gf]) / denom) if denom else 0.0,
                }
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir")
    ap.add_argument("--compare", nargs=2, metavar=("BASELINE", "REPAIRED"))
    ap.add_argument("--radius-max", type=float, required=True)
    ap.add_argument("--length-max", type=float, required=True)
    ap.add_argument("--prefix", default="par")
    ap.add_argument("--json-out")
    a = ap.parse_args()

    if a.compare:
        b = analyze(a.compare[0], a.radius_max, a.length_max, a.prefix)
        r = analyze(a.compare[1], a.radius_max, a.length_max, a.prefix)
        diffs = compare(b, r)
        # Emit the verdict-bearing scalars here rather than making the caller
        # introspect the tree. PowerShell's StrictMode cannot safely count
        # properties on a converted-from-JSON object with no members.
        differing = [d for d in diffs
                     if d.get("present_in_both") and d.get("fields")]
        fields_seen = sorted({f for d in differing for f in d["fields"]})
        result = {
            "baseline": b,
            "repaired": r,
            "differences": diffs,
            "summary": {
                "particles_compared": len(diffs),
                "particles_differing": len(differing),
                "trees_identical": len(differing) == 0,
                "fields_differing": fields_seen,
                "max_rel": max((v["rel"] for d in differing
                                for v in d["fields"].values()), default=0.0),
            },
        }
    elif a.run_dir:
        result = analyze(a.run_dir, a.radius_max, a.length_max, a.prefix)
    else:
        ap.error("one of --run-dir or --compare is required")

    text = json.dumps(result, indent=2, sort_keys=True)
    if a.json_out:
        with open(a.json_out, "w") as fh:
            fh.write(text + "\n")
        print(f"wrote {a.json_out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
