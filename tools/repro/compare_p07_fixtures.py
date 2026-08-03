#!/usr/bin/env python3
"""BMX RG-SW - C04: compare P07 fixture runs (baseline tree vs repaired tree).

Reads FIXTURE_INDEX.json produced by run_p07_fixtures.ps1 and decides, per
fixture, whether the repaired tree behaved differently from the untouched
baseline.

Reachability is established by DIFFERENCE. If a fixture that targets a patched
branch shows no difference, the branch was NOT REACHED and the corresponding
P07 validation hook is reported UNMET -- never silently counted as a pass.

Reuses the normalization rules from analyze_baseline.py so the comparator is the
same one C03 established and C05 will reuse.

Usage:
  python compare_p07_fixtures.py <runs/c04-p07-fixtures> <out.json>
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_baseline import normalize, diff_count, read_text  # noqa: E402

# The two trees necessarily report different build provenance: they are
# different commits, and the product worktree is 'dirty' while the patch is
# uncommitted. That line says nothing about behaviour, so it is stripped -- and
# reported as stripped, rather than silently dropped.
RE_BUILD_ID = re.compile(r"BMX git hash:")

RE_NUM = re.compile(r"[-+]?\d+\.?\d*[eE][-+]?\d+|[-+]?\d+\.\d+")


def load(path):
    text = read_text(Path(path))
    kept = [ln for ln in normalize(text).splitlines() if not RE_BUILD_ID.search(ln)]
    return "\n".join(kept)


def magnitude(a_text, b_text):
    """Largest relative difference between paired numbers on differing lines.

    Line counts alone cannot distinguish "the repair perturbed the 9th
    significant digit" from "the repair changed the answer". Quantify it.
    """
    a_lines, b_lines = a_text.splitlines(), b_text.splitlines()
    worst = 0.0
    worst_pair = None
    compared = 0
    for la, lb in zip(a_lines, b_lines):
        if la == lb:
            continue
        na, nb = RE_NUM.findall(la), RE_NUM.findall(lb)
        if len(na) != len(nb):
            continue
        for xa, xb in zip(na, nb):
            try:
                fa, fb = float(xa), float(xb)
            except ValueError:
                continue
            compared += 1
            denom = max(abs(fa), abs(fb))
            if denom == 0:
                continue
            rel = abs(fa - fb) / denom
            if rel > worst:
                worst, worst_pair = rel, (la.strip()[:110], lb.strip()[:110])
    return {"max_relative_difference": worst,
            "numbers_compared": compared,
            "worst_pair": worst_pair}


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    root, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    index = json.loads((root / "FIXTURE_INDEX.json").read_text(encoding="utf-8-sig"))
    if isinstance(index, dict):
        index = [index]

    # Floor signatures: what stock parameters already change, purely from the
    # area-refresh repair. A targeted fixture whose signature is identical to
    # the matching floor has NOT demonstrated that it reached its own branch --
    # its difference is fully explained by the effect stock settings produce.
    floors = {}
    for f in index:
        if f["hook"] == "blast-radius reference":
            b, r = load(f["baseline_log"]), load(f["repaired_log"])
            steps = next((a.split("=")[1] for a in f["arguments"] if a.startswith("bmx.max_step=")), "?")
            floors[steps] = {"id": f["id"], "lines": diff_count(b, r),
                             "max_rel": magnitude(b, r)["max_relative_difference"]}

    results, unmet, contradictions = [], [], []
    for f in index:
        b, r = load(f["baseline_log"]), load(f["repaired_log"])
        differs = b != r
        n = diff_count(b, r)
        mag = magnitude(b, r)

        expect_differ = f["expectation"] == "DIFFER"
        if expect_differ:
            # Branch reached iff behaviour changed.
            reached = differs
            verdict = "REACHED_AND_CHANGED" if differs else "NOT_REACHED"
            if not differs:
                unmet.append({"fixture": f["id"], "hook": f["hook"],
                              "why": "baseline and repaired outputs are identical, so the patched branch was not executed by this fixture"})
            elif f["hook"] != "blast-radius reference":
                steps = next((a.split("=")[1] for a in f["arguments"] if a.startswith("bmx.max_step=")), "?")
                fl = floors.get(steps)
                if fl and n == fl["lines"] and abs(mag["max_relative_difference"] - fl["max_rel"]) < 1e-18:
                    reached = None
                    verdict = "INDISTINGUISHABLE_FROM_STOCK_AREA_REFRESH"
                    unmet.append({"fixture": f["id"], "hook": f["hook"],
                                  "why": (f"difference signature ({n} lines, max_rel "
                                          f"{mag['max_relative_difference']:.3e}) is identical to the stock "
                                          f"reference {fl['id']}, so it is fully explained by the area-refresh "
                                          f"repair that stock parameters already trigger; this fixture does NOT "
                                          f"demonstrate that its own targeted branch was reached")})
                else:
                    verdict = "REACHED_AND_CHANGED_ABOVE_FLOOR"
        else:
            reached = None
            verdict = "CONTROL_UNCHANGED" if not differs else "CONTROL_CHANGED"
            if differs:
                contradictions.append({"fixture": f["id"], "hook": f["hook"],
                                       "why": "a no-trigger control changed behaviour; the repair is not confined to the reviewed predicates",
                                       "differing_lines": n})

        clean = f["baseline_exit"] == 0 and f["repaired_exit"] == 0
        if not clean:
            contradictions.append({"fixture": f["id"], "hook": f["hook"],
                                   "why": f"non-zero exit (baseline={f['baseline_exit']}, repaired={f['repaired_exit']})"})

        results.append({
            "id": f["id"], "hook": f["hook"], "description": f["description"],
            "expectation": f["expectation"], "ranks": f["ranks"],
            "arguments": f["arguments"],
            "baseline_exit": f["baseline_exit"], "repaired_exit": f["repaired_exit"],
            "outputs_differ": differs, "differing_lines": n,
            "magnitude": mag,
            "branch_reached": reached, "verdict": verdict,
        })

    report = {
        "stage": "C04",
        "build_identity_line_stripped": "the 'BMX git hash:' line is removed before comparison; the two trees are different commits and the product worktree is dirty while the patch is uncommitted, so that line always differs and carries no behavioural information",
        "method": "differential: identical inputs run against the untouched baseline image and the P07-repaired image; normalization shared with analyze_baseline.py",
        "why_differential": "the default fungi case never reaches the donor-exhaustion branches (established in C03), and instrumenting the source would change the candidate hash away from the reviewed bytes",
        "parameter_note": "every override is an ENGINEERING TEST VALUE chosen to force a branch; none is biological, calibrated, or promotable to scientific evidence",
        "fixtures": results,
        "unmet_hooks": unmet,
        "contradictions": contradictions,
        "summary": {
            "fixtures": len(results),
            "targeted_branches_reached": sum(1 for r in results if r["verdict"] == "REACHED_AND_CHANGED_ABOVE_FLOOR"),
            "targeted_indistinguishable_from_floor": sum(1 for r in results if r["verdict"] == "INDISTINGUISHABLE_FROM_STOCK_AREA_REFRESH"),
            "targeted_branches_not_reached": sum(1 for r in results if r["branch_reached"] is False),
            "controls_unchanged": sum(1 for r in results if r["verdict"] == "CONTROL_UNCHANGED"),
            "controls_changed": sum(1 for r in results if r["verdict"] == "CONTROL_CHANGED"),
        },
    }
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for r in results:
        m = r["magnitude"]["max_relative_difference"]
        print(f"{r['id']:26s} expect={r['expectation']:6s} differ={str(r['outputs_differ']):5s} "
              f"lines={r['differing_lines']:5d} max_rel={m:.3e}  {r['verdict']}")
    print()
    print(f"unmet hooks    : {len(unmet)}")
    for u in unmet:
        print(f"  UNMET {u['fixture']} -> {u['hook']}")
    print(f"contradictions : {len(contradictions)}")
    for c in contradictions:
        print(f"  CONTRADICTION {c['fixture']}: {c['why']}")
    print(f"written        : {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
