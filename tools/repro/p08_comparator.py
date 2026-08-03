#!/usr/bin/env python3
"""BMX RG-SW -- P08 historical-versus-repaired comparator.

Applies the frozen contract CON-P08-001 (contracts/p08/) to a bundle of raw
baseline and repaired observations and emits an ordered, contradiction-aware
comparison record.

The contract was committed BEFORE this file, so the predeclaration is verifiable
from git history rather than asserted here.

DESIGN NOTES

* The comparator never re-runs the model. It consumes observations that a
  separate extractor pulled from raw evidence, and every dimension result
  carries the evidence paths it was decided from. A conclusion that cannot be
  traced back to a raw record is a hard error, not a soft warning.

* Membership is checked BEFORE any dimension is evaluated. Missing, extra,
  duplicated, or wrong-generation members are rejected rather than interpreted --
  a comparator that quietly tolerates a missing baseline member will happily
  report "no difference".

* INCONCLUSIVE is a real outcome, not a soft pass. A dimension that cannot be
  decided blocks any conclusion depending on it.

* Output is canonicalised (sorted keys, sorted dimension order) so the record is
  byte-identical under any input ordering. run_p08_selftest.py verifies that by
  shuffling.

Usage:
  python p08_comparator.py --bundle <bundle.json> [--json-out <record.json>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

CONTRACT_ID = "CON-P08-001"

REPRODUCED = "REPRODUCED"
REPAIR_VERIFIED = "REPAIR_VERIFIED"
UNCHANGED_INVARIANT = "UNCHANGED_INVARIANT"
CONTRADICTORY = "CONTRADICTORY"
INCONCLUSIVE = "INCONCLUSIVE"

DIMENSION_ORDER = ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

# Frozen identity chain. A bundle whose generation block disagrees with this is
# a different generation and is rejected outright (contract §4).
FROZEN = {
    "baseline_commit": "389e9e35a1c7291a4af795b2e39f2db1f0012b61",
    "baseline_kernel_sha256": "711ae2caa6e7aabb5c084fe841d2d90edb85ee53e7abc7a859d7de00e6614678",
    "candidate_kernel_sha256": "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02",
    "amrex_commit": "cbdc6580ee3d78cccdd37172e4ba077ee181f483",
    "amrex_tree": "fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6",
}

SATURATION_REL = 1e-6          # contract D1; a shape threshold, not a fitted one


class HardError(Exception):
    """A condition the contract says to reject rather than interpret."""


# --------------------------------------------------------------------------
# observation access
# --------------------------------------------------------------------------
def obs_key(o):
    return (o.get("dimension"), o.get("platform"), o.get("tree"),
            o.get("fixture"), o.get("observable"))


def check_membership(bundle):
    """Contract §4. Runs before any dimension is evaluated."""
    errors = []
    obs = bundle.get("observations", [])

    seen = {}
    for o in obs:
        for f in ("dimension", "platform", "tree", "fixture", "observable", "value", "source"):
            if f not in o:
                errors.append(f"observation missing required field '{f}': {o}")
        k = obs_key(o)
        if k in seen:
            errors.append(f"duplicate member: {k}")
        seen[k] = o
        if o.get("dimension") not in DIMENSION_ORDER:
            errors.append(f"extra member for unknown dimension {o.get('dimension')!r}: {k}")
        # Every derived record must trace to a raw record.
        if not o.get("source"):
            errors.append(f"untraceable record (empty source): {k}")

    gen = bundle.get("generation", {})
    for k, v in FROZEN.items():
        if k not in gen:
            errors.append(f"generation block missing '{k}'")
        elif gen[k] != v:
            errors.append(f"wrong generation: {k}={gen[k]!r}, frozen value is {v!r}")

    required = bundle.get("required_members", [])
    for r in required:
        if tuple(r) not in seen:
            errors.append(f"missing required member: {tuple(r)}")

    return errors, seen


def pick(seen, dimension, platform=None, tree=None, fixture=None, observable=None):
    out = []
    for k, o in seen.items():
        d, p, t, f, ob = k
        if d != dimension:
            continue
        if platform is not None and p != platform:
            continue
        if tree is not None and t != tree:
            continue
        if fixture is not None and f != fixture:
            continue
        if observable is not None and ob != observable:
            continue
        out.append(o)
    return out


def one(seen, *a, **kw):
    r = pick(seen, *a, **kw)
    if len(r) != 1:
        raise HardError(f"expected exactly one observation for {a} {kw}, got {len(r)}")
    return r[0]


def srcs(*records):
    return sorted({r["source"] for r in records})


# --------------------------------------------------------------------------
# dimensions
# --------------------------------------------------------------------------
def d1_donor_cap(seen):
    """CDEF-01/02. Baseline must NOT be capped; repaired must saturate at exactly
    the available amount."""
    base = sorted(pick(seen, "D1", tree="baseline", observable="delta_A_particles"),
                  key=lambda o: o["k1"])
    rep = sorted(pick(seen, "D1", tree="candidate", observable="delta_A_particles"),
                 key=lambda o: o["k1"])
    if len(base) < 2 or len(rep) < 2:
        return INCONCLUSIVE, "fewer than two k1 rows per tree", srcs(*base, *rep)

    # Baseline: uncapped means the transfer keeps tracking k1.
    bvals = [o["value"] for o in base]
    baseline_monotone = all(bvals[i] < bvals[i + 1] for i in range(len(bvals) - 1))

    # Repaired: saturated means constant across the rows where the second-half
    # request exceeds the available amount.
    active = [o for o in rep if o.get("alpha_prime", 0) > 1.0]
    if not active:
        return INCONCLUSIVE, "no repaired row has alpha_prime > 1", srcs(*base, *rep)
    avals = [o["value"] for o in active]
    spread = (max(avals) - min(avals)) / max(abs(v) for v in avals)
    saturated = spread <= SATURATION_REL

    eq = pick(seen, "D1", tree="candidate", observable="final_equals_available")
    if not eq:
        return INCONCLUSIVE, "no equality observation present", srcs(*base, *rep)
    all_equal = all(o["value"] is True for o in eq)

    ev = srcs(*base, *rep, *eq)

    # Contradiction checks come first: a repaired transfer above the available
    # amount, or a baseline that saturates while the repaired does not, would
    # invert the whole claim.
    over = [o for o in rep if o.get("over_available") is True]
    if over:
        return CONTRADICTORY, "repaired transfer exceeds the available amount", ev
    if not baseline_monotone and saturated is False:
        return CONTRADICTORY, "baseline appears capped while repaired does not saturate", ev

    if baseline_monotone and saturated and all_equal:
        return (REPAIR_VERIFIED,
                f"baseline uncapped across {len(bvals)} k1 rows; repaired saturates "
                f"(spread {spread:.2e} <= {SATURATION_REL:g}) and final content equals "
                f"fA0*V_cell exactly on {len(eq)} rows", ev)
    if baseline_monotone:
        return REPRODUCED, "baseline uncapped, but repaired did not both saturate and equal", ev
    return INCONCLUSIVE, "baseline transfer is not monotone in k1", ev


def d2_stale_first_half(seen):
    """CDEF-03. Trees must differ on a fixture where a tip branch was OBSERVED to
    execute; a bare difference does not attribute."""
    diffs = pick(seen, "D2", observable="trees_differ")
    if not diffs:
        return INCONCLUSIVE, "no difference observation present", []
    attributed = [o for o in diffs if o.get("branch_execution_observed") is True]
    ev = srcs(*diffs)
    if not attributed:
        return (INCONCLUSIVE,
                "trees differ but no branch execution was observed on those fixtures", ev)
    if all(o["value"] is True for o in attributed):
        return (REPAIR_VERIFIED,
                f"trees differ on {len(attributed)} fixture(s) with a directly observed tip "
                f"growth branch", ev)
    return CONTRADICTORY, "a fixture with an observed branch shows no difference", ev


def d3_tip_area_stale(seen):
    """CDEF-04. Predicted branch must equal observed branch, stored area must be
    left unchanged, and the trees must differ."""
    pv = pick(seen, "D3", observable="predicted_equals_observed")
    st = pick(seen, "D3", observable="area_left_stale")
    df = pick(seen, "D3", observable="trees_differ")
    if not (pv and st and df):
        return INCONCLUSIVE, "branch, staleness or difference observation missing", srcs(*pv, *st, *df)
    ev = srcs(*pv, *st, *df)
    if not all(o["value"] is True for o in pv):
        return CONTRADICTORY, "predicted and observed branch disagree on some transition", ev
    if not all(o["value"] is True for o in st):
        return CONTRADICTORY, "stored area was refreshed on a branch that must leave it stale", ev
    if all(o["value"] is True for o in df):
        return (REPAIR_VERIFIED,
                f"both tip branches execute as predicted with stored area unchanged on "
                f"{len(st)} fixture(s), and the trees differ there", ev)
    return REPRODUCED, "staleness reproduced in baseline but trees do not differ", ev


def d4_rejected_growth(seen):
    """CDEF-05. Rejections observed, and cB restored in repaired but not baseline."""
    rj = pick(seen, "D4", observable="rejections_observed")
    cb = pick(seen, "D4", observable="cB_differs")
    if not (rj and cb):
        return INCONCLUSIVE, "rejection or cB observation missing", srcs(*rj, *cb)
    ev = srcs(*rj, *cb)
    counts = [o["value"] for o in rj]
    if not all(isinstance(c, (int, float)) and c > 0 for c in counts):
        return INCONCLUSIVE, "no non-tip rejection was observed", ev
    if all(o["value"] is True for o in cb):
        return (REPAIR_VERIFIED,
                f"{int(sum(counts))} non-tip rejection(s) observed; cB differs between trees", ev)
    return REPRODUCED, "rejections observed but cB does not differ", ev


def d5_carbon_only(seen):
    """Phosphorus exclusion boundary."""
    pl = pick(seen, "D5", observable="p_lines_identical")
    fc = pick(seen, "D5", observable="files_changed")
    if not (pl and fc):
        return INCONCLUSIVE, "P-line or file-scope observation missing", srcs(*pl, *fc)
    ev = srcs(*pl, *fc)
    if not all(o["value"] is True for o in pl):
        return CONTRADICTORY, "a phosphorus-bearing line changed", ev
    if any(o["value"] != 1 for o in fc):
        return CONTRADICTORY, "the patch touches more than one file", ev
    return UNCHANGED_INVARIANT, "all phosphorus lines byte-identical; patch scope is one file", ev


def d6_no_phosphorus_claim(seen):
    a = pick(seen, "D6", observable="no_phosphorus_correctness_claim")
    b = pick(seen, "D6", observable="asymmetry_restated")
    if not (a and b):
        return INCONCLUSIVE, "claim-audit observation missing", srcs(*a, *b)
    ev = srcs(*a, *b)
    if all(o["value"] is True for o in a) and all(o["value"] is True for o in b):
        return (UNCHANGED_INVARIANT,
                "no conclusion asserts phosphorus correctness; the dP1/dP2 asymmetry is restated", ev)
    return CONTRADICTORY, "a phosphorus claim is present or the asymmetry is not restated", ev


def d7_identity(seen):
    ids = pick(seen, "D7")
    if not ids:
        return INCONCLUSIVE, "no identity observation present", []
    ev = srcs(*ids)
    bad = [o for o in ids if o["value"] is not True]
    if bad:
        return (CONTRADICTORY,
                "identity mismatch: " + ", ".join(sorted(o["observable"] for o in bad)), ev)
    return UNCHANGED_INVARIANT, f"all {len(ids)} identity checks match the frozen chain", ev


def d8_platform(seen):
    """A difference for the SAME tree ACROSS platforms is platform-only and may
    never be attributed to the repair."""
    recs = pick(seen, "D8")
    if not recs:
        return INCONCLUSIVE, "no cross-platform observation present", []
    ev = srcs(*recs)
    platforms = {o["platform"] for o in recs}
    if len(platforms) < 2:
        return INCONCLUSIVE, f"only {len(platforms)} platform available for the same tree", ev
    # Group the SAME THING across platforms: same tree, same fixture, same
    # observable. The fixture must be part of the key -- without it, a sweep's
    # rows collapse into one group and disagree with each other by design,
    # which reports platform variance where none exists.
    groups = {}
    for o in recs:
        groups.setdefault((o["tree"], o["fixture"], o["observable"]), []).append(o)
    # A group seen on only one platform says nothing about cross-platform
    # agreement; it is not evidence of variance.
    comparable = {k: g for k, g in groups.items()
                  if len({x["platform"] for x in g}) > 1}
    if not comparable:
        return (INCONCLUSIVE,
                "no observable is present for the same tree and fixture on more than one platform",
                ev)
    varying = [k for k, g in comparable.items()
               if len({json.dumps(x["value"], sort_keys=True) for x in g}) > 1]
    if varying:
        return (CONTRADICTORY,
                f"cross-platform variance for the same tree on {varying}; a baseline-vs-repaired "
                f"difference on these observables could be platform-induced", ev)
    return (UNCHANGED_INVARIANT,
            f"cross-platform variance is zero across {len(platforms)} platforms "
            f"({', '.join(sorted(platforms))}) on {len(comparable)} tree/fixture/observable "
            f"groups; no observed difference is platform-attributable", ev)


EVALUATORS = {"D1": d1_donor_cap, "D2": d2_stale_first_half, "D3": d3_tip_area_stale,
              "D4": d4_rejected_growth, "D5": d5_carbon_only, "D6": d6_no_phosphorus_claim,
              "D7": d7_identity, "D8": d8_platform}

NAMES = {"D1": "CDEF-01/02 second-half donor cap",
         "D2": "CDEF-03 first-half stale exchange area",
         "D3": "CDEF-04 tip stored-area staleness",
         "D4": "CDEF-05 non-tip rejected-growth rollback",
         "D5": "carbon-only scope preserved",
         "D6": "phosphorus excluded from claims",
         "D7": "source/build/executable identity continuity",
         "D8": "platform-only differences not attributed to P07"}


def compare(bundle):
    errors, seen = check_membership(bundle)
    if errors:
        return {"contract_id": CONTRACT_ID, "status": "REJECTED",
                "membership_errors": sorted(errors), "dimensions": [],
                "contradictions": [], "conclusion": None,
                "conclusion_withheld_because": sorted(errors)}

    results = []
    for d in DIMENSION_ORDER:
        try:
            cls, detail, ev = EVALUATORS[d](seen)
        except HardError as e:
            cls, detail, ev = INCONCLUSIVE, f"hard error: {e}", []
        results.append({"dimension": d, "name": NAMES[d], "result": cls,
                        "detail": detail, "evidence": ev})

    contradictions = [r["dimension"] for r in results if r["result"] == CONTRADICTORY]
    undecided = [r["dimension"] for r in results if r["result"] == INCONCLUSIVE]

    supported = [r["dimension"] for r in results
                 if r["result"] in (REPAIR_VERIFIED, UNCHANGED_INVARIANT)]

    if contradictions or undecided:
        conclusion = None
        withheld = ([f"{d} CONTRADICTORY" for d in contradictions] +
                    [f"{d} INCONCLUSIVE" for d in undecided])
    else:
        verified = [r["dimension"] for r in results if r["result"] == REPAIR_VERIFIED]
        conclusion = (
            "Within the carbon-only scope of P07 and on the identities recorded in this record, "
            f"the defect mappings covered by {', '.join(verified)} are reproduced in the baseline "
            "tree and corrected in the repaired tree, observed directly rather than inferred. "
            "Carbon-only scope and identity continuity hold, and cross-platform variance is zero, "
            "so no observed difference is platform-attributable. "
            "This record makes NO claim about phosphorus behaviour, about any conservation "
            "property of the model as a whole, about any scientific or biological result, about "
            "P07 phase success, about formal P05-P18 acceptance, or about RG-SW:GO or RG-SCI:GO.")
        withheld = []

    return {"contract_id": CONTRACT_ID, "status": "EVALUATED",
            "membership_errors": [], "dimensions": results,
            "supported_dimensions": supported,
            "contradictions": contradictions, "undecided": undecided,
            "conclusion": conclusion, "conclusion_withheld_because": withheld}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--json-out")
    a = ap.parse_args()

    with open(a.bundle) as fh:
        bundle = json.load(fh)
    rec = compare(bundle)
    rec["generation"] = bundle.get("generation", {})

    text = json.dumps(rec, indent=2, sort_keys=True) + "\n"
    if a.json_out:
        os.makedirs(os.path.dirname(a.json_out) or ".", exist_ok=True)
        with open(a.json_out, "w", newline="\n") as fh:
            fh.write(text)

    print(f"contract : {rec['contract_id']}")
    print(f"status   : {rec['status']}")
    if rec["membership_errors"]:
        for e in rec["membership_errors"]:
            print(f"  REJECT  {e}")
        return 2
    for r in rec["dimensions"]:
        print(f"  {r['dimension']}  {r['result']:<20} {r['name']}")
        print(f"        {r['detail']}")
    print()
    if rec["conclusion"]:
        print("CONCLUSION:")
        print("  " + rec["conclusion"])
    else:
        print("CONCLUSION WITHHELD:")
        for w in rec["conclusion_withheld_because"]:
            print(f"  - {w}")
    if a.json_out:
        print(f"\nwrote {a.json_out}")
    return 0 if rec["status"] == "EVALUATED" and not rec["contradictions"] else 1


if __name__ == "__main__":
    sys.exit(main())
