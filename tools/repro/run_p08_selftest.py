#!/usr/bin/env python3
"""BMX RG-SW -- P08 comparator synthetic suite.

Exercises every branch the contract names, using MANUFACTURED bundles that
contain none of the real measurements. This is what makes the predeclaration
checkable: a rule tuned to the actual C04 results would fail the classes the
real data never produces (CONTRADICTORY, INCONCLUSIVE, and the membership
rejections).

Covers the spec's synthetic branch list:
  historical expected failure + repaired expected success
  both fail, both pass, contradictory dimensions
  missing historical or repaired member
  wrong P06/P07 manifest or source chain
  platform-only difference incorrectly classified as repair effect
  boundary equality and just-inside/just-outside approved tolerance
  incomplete controls or derived output
plus duplicate and extra members, and input-order independence.

Usage:
  python run_p08_selftest.py [--json-out <path>]
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p08_comparator as C  # noqa: E402

GEN = dict(C.FROZEN)
GEN["candidate_commit"] = "adb427331e180cd0b4faa74a4ab2098381b2eabb"


def ob(dim, tree, fixture, observable, value, platform="synthetic", **extra):
    o = {"dimension": dim, "platform": platform, "tree": tree, "fixture": fixture,
         "observable": observable, "value": value, "source": f"synthetic://{dim}/{fixture}"}
    o.update(extra)
    return o


def healthy():
    """A bundle in which every dimension resolves the way a genuine repair would."""
    obs = []
    # D1: baseline rises with k1; repaired pinned and exactly equal.
    for k1, bv in ((1.0, 1.0e-13), (2.0, 2.0e-13), (5.0, 4.0e-13), (20.0, 9.0e-13)):
        obs.append(ob("D1", "baseline", f"k1_{k1}", "delta_A_particles", bv, k1=k1,
                      alpha_prime=k1 * 0.65))
        obs.append(ob("D1", "candidate", f"k1_{k1}", "delta_A_particles", 4.871e-12, k1=k1,
                      alpha_prime=k1 * 0.65, over_available=False))
        if k1 * 0.65 > 1.0:
            obs.append(ob("D1", "candidate", f"k1_{k1}", "final_equals_available", True, k1=k1))
    obs.append(ob("D2", "both", "G1", "trees_differ", True, branch_execution_observed=True))
    obs.append(ob("D3", "both", "G1", "predicted_equals_observed", True))
    obs.append(ob("D3", "both", "G1", "area_left_stale", True))
    obs.append(ob("D3", "both", "G1", "trees_differ", True))
    obs.append(ob("D4", "both", "G4", "rejections_observed", 188))
    obs.append(ob("D4", "both", "G4", "cB_differs", True))
    obs.append(ob("D5", "both", "patch", "p_lines_identical", True))
    obs.append(ob("D5", "both", "patch", "files_changed", 1))
    obs.append(ob("D6", "both", "report", "no_phosphorus_correctness_claim", True))
    obs.append(ob("D6", "both", "report", "asymmetry_restated", True))
    obs.append(ob("D7", "both", "identity", "kernel_hash_matches", True))
    obs.append(ob("D7", "both", "identity", "amrex_matches", True))
    # A SWEEP, not a single fixture. The real bundle is a k1 sweep, and a
    # grouping key that omits the fixture collapses its rows into one group and
    # reports variance that is really just the sweep varying. That defect
    # survived the first synthetic suite because it used one fixture.
    for p in ("plat_a", "plat_b"):
        for i, v in enumerate((1.5, 2.5, 3.5)):
            obs.append(ob("D8", "baseline", f"sweep_{i}", "value_x", v, platform=p))
            obs.append(ob("D8", "candidate", f"sweep_{i}", "value_x", v * 2, platform=p))
    return {"generation": dict(GEN), "observations": obs, "required_members": []}


CASES = []


def case(name, expect_status=None, expect=None, reject_contains=None):
    def deco(fn):
        CASES.append((name, fn, expect_status, expect or {}, reject_contains))
        return fn
    return deco


# ---- the healthy path ------------------------------------------------------
@case("historical_failure_and_repaired_success",
      expect={"D1": C.REPAIR_VERIFIED, "D2": C.REPAIR_VERIFIED, "D3": C.REPAIR_VERIFIED,
              "D4": C.REPAIR_VERIFIED, "D5": C.UNCHANGED_INVARIANT, "D6": C.UNCHANGED_INVARIANT,
              "D7": C.UNCHANGED_INVARIANT, "D8": C.UNCHANGED_INVARIANT})
def _healthy():
    return healthy()


# ---- both pass -------------------------------------------------------------
@case("both_pass_no_difference_is_not_a_repair", expect={"D2": C.CONTRADICTORY})
def _both_pass():
    b = healthy()
    for o in b["observations"]:
        if o["dimension"] == "D2" and o["observable"] == "trees_differ":
            o["value"] = False        # branch ran, yet nothing changed
    return b


# ---- both fail -------------------------------------------------------------
@case("both_fail_repaired_does_not_saturate", expect={"D1": C.REPRODUCED})
def _both_fail():
    b = healthy()
    for o in b["observations"]:
        if o["dimension"] == "D1" and o["tree"] == "candidate" \
           and o["observable"] == "delta_A_particles":
            o["value"] = 1e-13 * o["k1"]    # repaired also tracks k1
    return b


# ---- contradictory ---------------------------------------------------------
@case("contradictory_repaired_exceeds_available", expect={"D1": C.CONTRADICTORY})
def _over():
    b = healthy()
    for o in b["observations"]:
        if o["dimension"] == "D1" and o["tree"] == "candidate" \
           and o["observable"] == "delta_A_particles":
            o["over_available"] = True
    return b


@case("contradictory_branch_prediction_disagrees", expect={"D3": C.CONTRADICTORY})
def _branch():
    b = healthy()
    for o in b["observations"]:
        if o["dimension"] == "D3" and o["observable"] == "predicted_equals_observed":
            o["value"] = False
    return b


@case("contradictory_phosphorus_line_changed", expect={"D5": C.CONTRADICTORY})
def _pline():
    b = healthy()
    for o in b["observations"]:
        if o["observable"] == "p_lines_identical":
            o["value"] = False
    return b


@case("contradictory_phosphorus_claim_present", expect={"D6": C.CONTRADICTORY})
def _claim():
    b = healthy()
    for o in b["observations"]:
        if o["observable"] == "no_phosphorus_correctness_claim":
            o["value"] = False
    return b


@case("contradictory_identity_mismatch", expect={"D7": C.CONTRADICTORY})
def _ident():
    b = healthy()
    for o in b["observations"]:
        if o["dimension"] == "D7" and o["observable"] == "kernel_hash_matches":
            o["value"] = False
    return b


# ---- the platform trap -----------------------------------------------------
@case("platform_only_difference_must_not_be_a_repair_effect",
      expect={"D8": C.CONTRADICTORY})
def _platform():
    b = healthy()
    # Same tree, same observable, different value on a second platform.
    for o in b["observations"]:
        if o["dimension"] == "D8" and o["tree"] == "baseline" and o["platform"] == "plat_b":
            o["value"] = 99.0
    return b


@case("sweep_rows_are_not_platform_variance", expect={"D8": C.UNCHANGED_INVARIANT})
def _sweep():
    """Regression guard: a multi-fixture sweep whose rows differ from each other
    but agree across platforms must NOT be reported as platform variance."""
    return healthy()


@case("single_platform_cannot_decide_attribution", expect={"D8": C.INCONCLUSIVE})
def _oneplat():
    b = healthy()
    b["observations"] = [o for o in b["observations"]
                         if not (o["dimension"] == "D8" and o["platform"] == "plat_b")]
    return b


# ---- attribution without observed execution --------------------------------
@case("difference_without_observed_branch_is_inconclusive", expect={"D2": C.INCONCLUSIVE})
def _noexec():
    b = healthy()
    for o in b["observations"]:
        if o["dimension"] == "D2":
            o["branch_execution_observed"] = False
    return b


@case("no_rejection_observed_is_inconclusive", expect={"D4": C.INCONCLUSIVE})
def _norej():
    b = healthy()
    for o in b["observations"]:
        if o["observable"] == "rejections_observed":
            o["value"] = 0
    return b


# ---- tolerance boundary ----------------------------------------------------
@case("saturation_just_inside_tolerance", expect={"D1": C.REPAIR_VERIFIED})
def _inside():
    b = healthy()
    v = [o for o in b["observations"]
         if o["dimension"] == "D1" and o["tree"] == "candidate"
         and o["observable"] == "delta_A_particles" and o["alpha_prime"] > 1.0]
    v[0]["value"] = 4.871e-12 * (1 + C.SATURATION_REL * 0.5)
    return b


@case("saturation_just_outside_tolerance", expect={"D1": C.REPRODUCED})
def _outside():
    b = healthy()
    v = [o for o in b["observations"]
         if o["dimension"] == "D1" and o["tree"] == "candidate"
         and o["observable"] == "delta_A_particles" and o["alpha_prime"] > 1.0]
    v[0]["value"] = 4.871e-12 * (1 + C.SATURATION_REL * 10)
    return b


# ---- membership rejections -------------------------------------------------
@case("missing_historical_member", expect_status="REJECTED", reject_contains="missing required")
def _missing_hist():
    b = healthy()
    b["required_members"] = [["D1", "synthetic", "baseline", "k1_1.0", "delta_A_particles"]]
    b["observations"] = [o for o in b["observations"]
                         if not (o["dimension"] == "D1" and o["tree"] == "baseline"
                                 and o["fixture"] == "k1_1.0")]
    return b


@case("missing_repaired_member", expect_status="REJECTED", reject_contains="missing required")
def _missing_rep():
    b = healthy()
    b["required_members"] = [["D4", "synthetic", "both", "G4", "cB_differs"]]
    b["observations"] = [o for o in b["observations"] if o["observable"] != "cB_differs"]
    return b


@case("duplicate_member", expect_status="REJECTED", reject_contains="duplicate member")
def _dup():
    b = healthy()
    b["observations"].append(copy.deepcopy(b["observations"][0]))
    return b


@case("extra_member_unknown_dimension", expect_status="REJECTED", reject_contains="extra member")
def _extra():
    b = healthy()
    b["observations"].append(ob("D99", "both", "x", "y", True))
    return b


@case("wrong_generation_source_chain", expect_status="REJECTED", reject_contains="wrong generation")
def _wrongen():
    b = healthy()
    b["generation"]["candidate_kernel_sha256"] = "0" * 64
    return b


@case("untraceable_derived_record", expect_status="REJECTED", reject_contains="untraceable")
def _untraceable():
    b = healthy()
    b["observations"][0]["source"] = ""
    return b


@case("incomplete_derived_output", expect_status="REJECTED", reject_contains="missing required field")
def _incomplete():
    b = healthy()
    del b["observations"][0]["value"]
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out")
    ap.add_argument("--seed", type=int, default=20260801)
    a = ap.parse_args()

    results, failures = [], []
    for name, fn, expect_status, expect, reject_contains in CASES:
        bundle = fn()
        rec = C.compare(bundle)
        ok, why = True, []

        if expect_status:
            if rec["status"] != expect_status:
                ok = False
                why.append(f"status {rec['status']} != {expect_status}")
            if reject_contains and not any(reject_contains in e for e in rec["membership_errors"]):
                ok = False
                why.append(f"no membership error containing {reject_contains!r}")
        else:
            got = {r["dimension"]: r["result"] for r in rec["dimensions"]}
            for d, want in expect.items():
                if got.get(d) != want:
                    ok = False
                    why.append(f"{d}: {got.get(d)} != {want}")

        results.append({"case": name, "status": "PASS" if ok else "FAIL",
                        "detail": "; ".join(why) if why else "as predeclared"})
        if not ok:
            failures.append(name)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}"
              + (f"  -- {'; '.join(why)}" if why else ""))

    # ---- input-order independence ------------------------------------------
    rng = random.Random(a.seed)
    base = healthy()
    canon = json.dumps(C.compare(base), indent=2, sort_keys=True)
    order_ok = True
    for _ in range(12):
        sh = copy.deepcopy(base)
        rng.shuffle(sh["observations"])
        if json.dumps(C.compare(sh), indent=2, sort_keys=True) != canon:
            order_ok = False
            break
    results.append({"case": "input_order_independence",
                    "status": "PASS" if order_ok else "FAIL",
                    "detail": "12 shuffles produce byte-identical records"
                              if order_ok else "record changed under reordering"})
    if not order_ok:
        failures.append("input_order_independence")
    print(f"  [{'PASS' if order_ok else 'FAIL'}] input_order_independence")

    out = {"suite": "p08_selftest", "contract_id": C.CONTRACT_ID,
           "cases": results, "failures": failures,
           "status": "PASS" if not failures else "FAIL"}
    if a.json_out:
        os.makedirs(os.path.dirname(a.json_out) or ".", exist_ok=True)
        with open(a.json_out, "w", newline="\n") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"\nwrote {a.json_out}")
    print(f"\nstatus: {out['status']}  ({len(results) - len(failures)}/{len(results)})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
