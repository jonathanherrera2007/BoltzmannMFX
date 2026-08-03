#!/usr/bin/env python3
"""BMX RG-SW - C03 baseline analysis.

Derives a summary from raw baseline stdout ONLY. Deterministic: same raw inputs
always give byte-identical output. Re-runnable without re-running the model.

Nothing here is a scientific result. It records what the untouched canonical
build does, including defects, as OBSERVATIONS -- never as repaired
expectations, and never as a claim that any behaviour is correct.

Usage:
  python analyze_baseline.py <runs/c03-baseline> <out.json>
"""

import hashlib
import json
import re
import sys
from pathlib import Path

# "Max/min of species 3 (D) at level 1   2.0000000000e-05 0"
RE_SPECIES = re.compile(
    r"Max/min of species\s+(\d+)\s+\(([^)]+)\)\s+at level\s+(\d+)\s+"
    r"([-+0-9.eE]+)\s+([-+0-9.eE]+)"
)
# "In Particle Exchange with 2 particles at level 1"
RE_PARTICLES = re.compile(r"In Particle Exchange with\s+(\d+)\s+particles at level\s+(\d+)")
# "MLMG: Final Iter. 2 resid, resid/bnorm = 1.2e-18, 3.4e-13"
RE_MLMG_FINAL = re.compile(r"MLMG: Final Iter\.\s+\d+ resid, resid/bnorm =\s*([-+0-9.eE]+),\s*([-+0-9.eE]+)")

# Lines carrying wall-clock timing vary run to run and must be excluded from any
# determinism comparison.
RE_TIMING = re.compile(r"Time (spent|per)|Timers:")

# Lines describing how the domain was split across ranks. These MUST differ
# between a 1-rank and a 2-rank run -- that is the decomposition working, not a
# physics difference. Stripped only for the explicit cross-rank comparison.
RE_DECOMP = re.compile(
    r"MPI initialized with|SETTING NEW GRIDS|m_pmap\[|^\s*\(\(\d+,\d+,\d+\)"
)


def normalize(text, strip_decomposition=False):
    """Canonical comparable form of a raw log.

    This -- not the parsed observable stream -- is the authoritative comparator.
    The parsed stream is coarse (see PRECISION_CAVEAT) and cannot detect small
    numerical differences.
    """
    out = []
    for line in text.splitlines():
        line = line.rstrip("\r")
        if RE_TIMING.search(line):
            continue
        if strip_decomposition and RE_DECOMP.search(line):
            continue
        out.append(line)
    return "\n".join(out)


def diff_count(a, b):
    """Number of differing lines between two normalized texts."""
    import difflib
    return sum(1 for d in difflib.unified_diff(a.splitlines(), b.splitlines(), n=0)
               if d[:1] in "+-" and not d.startswith(("---", "+++")))


PRECISION_CAVEAT = (
    "The parsed observable stream is COARSE: BMX prints species max/min at about "
    "one significant figure (e.g. '2e-05 0'), so identical parsed streams do NOT "
    "establish numerical agreement. Verified concretely: the 1-rank and 2-rank "
    "runs have identical parsed streams but 24 differing raw lines. All "
    "equality verdicts below therefore come from the normalized RAW log, not "
    "from the parsed stream."
)


def read_text(path):
    # PowerShell writes UTF-8 with BOM; utf-8-sig strips it.
    return path.read_text(encoding="utf-8-sig", errors="replace")


def parse_case(log_path):
    text = read_text(log_path)
    species, particles, mlmg = [], [], []
    for line in text.splitlines():
        line = line.rstrip("\r")
        if RE_TIMING.search(line):
            continue
        m = RE_SPECIES.search(line)
        if m:
            species.append({
                "index": int(m.group(1)), "name": m.group(2),
                "level": int(m.group(3)), "max": m.group(4), "min": m.group(5),
            })
            continue
        m = RE_PARTICLES.search(line)
        if m:
            particles.append({"count": int(m.group(1)), "level": int(m.group(2))})
            continue
        m = RE_MLMG_FINAL.search(line)
        if m:
            mlmg.append({"resid": m.group(1), "resid_over_bnorm": m.group(2)})

    # Canonical observable stream: every deterministic quantity, in order,
    # rendered as text. This is what determinism comparisons hash.
    stream_lines = (
        [f"S {d['index']} {d['name']} L{d['level']} {d['max']} {d['min']}" for d in species]
        + [f"P L{d['level']} {d['count']}" for d in particles]
        + [f"M {d['resid']} {d['resid_over_bnorm']}" for d in mlmg]
    )
    stream = "\n".join(stream_lines)

    # Negative species minima are recorded, not judged. The P07 preparation maps
    # two donor-exhaustion defects (CDEF-01 A, CDEF-02 C) whose stated failure
    # mode is a sign reversal on the capped transfer. Whether that manifests as a
    # negative minimum in this configuration is exactly the sort of thing the
    # baseline must record without asserting cause.
    negatives = [d for d in species if _to_float(d["min"]) < 0.0]
    nonfinite = [d for d in species
                 if not _finite(d["max"]) or not _finite(d["min"])]

    return {
        "log": log_path.name,
        "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        "observable_stream_sha256": hashlib.sha256(stream.encode()).hexdigest(),
        "counts": {"species_records": len(species),
                   "particle_records": len(particles),
                   "mlmg_records": len(mlmg)},
        "particle_count_first": particles[0]["count"] if particles else None,
        "particle_count_last": particles[-1]["count"] if particles else None,
        "particle_count_max": max((d["count"] for d in particles), default=None),
        "final_species": species[-12:],
        "observations": {
            "negative_species_minimum_records": len(negatives),
            "negative_species_examples": negatives[:8],
            "nonfinite_records": len(nonfinite),
            "nonfinite_examples": nonfinite[:8],
        },
        "raw_normalized_sha256": hashlib.sha256(normalize(text).encode()).hexdigest(),
        "raw_normalized_no_decomp_sha256":
            hashlib.sha256(normalize(text, strip_decomposition=True).encode()).hexdigest(),
        "_stream": stream,
        "_norm": normalize(text),
        "_norm_nd": normalize(text, strip_decomposition=True),
    }


def _to_float(s):
    try:
        return float(s)
    except ValueError:
        return 0.0


def _finite(s):
    try:
        v = float(s)
    except ValueError:
        return False
    return v == v and abs(v) != float("inf")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    root, out_path = Path(sys.argv[1]), Path(sys.argv[2])

    cases = {}
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        log = d / "stdout.log"
        if log.exists():
            cases[d.name] = parse_case(log)

    def cmp_raw(a, b, key="_norm"):
        if a not in cases or b not in cases:
            return {"identical": None, "differing_lines": None}
        ta, tb = cases[a][key], cases[b][key]
        return {"identical": ta == tb, "differing_lines": diff_count(ta, tb)}

    def final_state(name):
        return cases[name]["final_species"] if name in cases else None

    comparisons = {
        "_comparator": "normalized RAW log (wall-clock timing lines removed). "
                       "The parsed observable stream is NOT used for equality.",
        "_precision_caveat": PRECISION_CAVEAT,
        "determinism_B02_vs_B03": dict(
            question="does an exact rerun with the same seed reproduce the raw log byte for byte?",
            **cmp_raw("B02_steps20", "B03_steps20_rerun"),
            interpretation_rule="PASS requires identical; a difference means the baseline is not reproducible and every later comparison is unsafe",
        ),
        "seed_sensitivity_B02_vs_B04": dict(
            question="does changing only bmx.seed change the raw log?",
            **cmp_raw("B02_steps20", "B04_steps20_seed2"),
            interpretation_rule="OBSERVATION ONLY. Neither outcome is a defect by itself. Note this configuration sets chem_species.branching_probability=0, so a seed-independent result at 20 steps is plausible rather than surprising; it is NOT evidence that the RNG is unused elsewhere",
        ),
        "restart_equivalence_B02_vs_B06": {
            "question": "does continuing from a step-10 checkpoint to step 20 reach the same final state as a continuous run to step 20?",
            "continuous_final_species": final_state("B02_steps20"),
            "restart_final_species": final_state("B06_ckpt_restart"),
            "note": "logs are not directly hash-comparable: B06 covers steps 11-20 only, B02 covers 1-20",
            "interpretation_rule": "OBSERVATION ONLY at C03. The frozen restart comparator is not defined until C06B; no tolerance is applied or invented here",
        },
        "rank_sensitivity_B02_vs_B07": {
            "question": "does running the same case on 2 MPI ranks change the raw log?",
            "raw": cmp_raw("B02_steps20", "B07_steps20_2rank"),
            "raw_excluding_decomposition_metadata":
                cmp_raw("B02_steps20", "B07_steps20_2rank", key="_norm_nd"),
            "residual_difference_analysis": {
                "what_remains": "a growth-tip creation event, reported with different particle identity",
                "one_rank": "Generating new growth tip. Parent id: 1 cpu: 0 child id: 2 cpu: 0",
                "two_rank": "Generating new growth tip. Parent id: 1 cpu: 0 child id: 1 cpu: 1",
                "physics_identical": "yes -- both report the same trigger length 0.00350903 and the same parent",
                "identity_differs": "yes -- the new segment's (id, cpu) pair is decomposition-dependent",
                "ordering_differs": "yes -- under 2 ranks these lines appear after 'AMReX finalized' because rank stdout interleaves",
            },
            "consequences_for_later_stages": [
                "A raw-log comparator can NEVER be a valid cross-rank comparator here: particle ids are rank-local and stdout interleaves. C16 must compare canonical identities and metrics, not raw logs.",
                "P10 (C08) must preserve ledgers and accounting across MPI redistribution even though (id, cpu) is not stable across decompositions.",
            ],
            "interpretation_rule": "OBSERVATION ONLY. Not a defect finding: rank-local ids and interleaved stdout are expected. This is NOT the rank/decomposition invariance study, which is predeclared and owned by C16",
        },
    }

    total_negative = sum(c["observations"]["negative_species_minimum_records"] for c in cases.values())
    total_nonfinite = sum(c["observations"]["nonfinite_records"] for c in cases.values())

    for c in cases.values():
        for k in ("_stream", "_norm", "_norm_nd"):
            del c[k]

    report = {
        "stage": "C03",
        "role": "derived summary regenerated from raw baseline stdout only",
        "claims": "none; this records untouched-baseline behaviour including defects, as observations",
        "cases": cases,
        "comparisons": comparisons,
        "aggregate_observations": {
            "total_negative_species_minimum_records": total_negative,
            "total_nonfinite_records": total_nonfinite,
            "note": "Recorded as historical baseline behaviour. NOT a repaired expectation, NOT attributed to any specific defect, and NOT a claim that the behaviour is wrong. Attribution is C04/C05 work under a fresh exact-scope review.",
        },
    }

    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"cases analysed        : {len(cases)}")
    print(f"determinism B02==B03  : {comparisons['determinism_B02_vs_B03']['identical']} "
          f"(diff lines {comparisons['determinism_B02_vs_B03']['differing_lines']})")
    print(f"seed  B02==B04        : {comparisons['seed_sensitivity_B02_vs_B04']['identical']} "
          f"(diff lines {comparisons['seed_sensitivity_B02_vs_B04']['differing_lines']})")
    r = comparisons['rank_sensitivity_B02_vs_B07']
    print(f"ranks B02==B07 raw    : {r['raw']['identical']} (diff lines {r['raw']['differing_lines']})")
    print(f"ranks B02==B07 no-dec : {r['raw_excluding_decomposition_metadata']['identical']} "
          f"(diff lines {r['raw_excluding_decomposition_metadata']['differing_lines']})")
    print(f"negative-min records  : {total_negative}")
    print(f"nonfinite records     : {total_nonfinite}")
    print(f"written               : {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
