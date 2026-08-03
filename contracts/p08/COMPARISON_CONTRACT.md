# P08 comparison contract — v1

- **Contract ID:** `CON-P08-001`
- **Version:** 1
- **Status:** `FROZEN_FOR_IMPLEMENTATION`
- **Date:** 2026-08-01
- **Class:** technical policy. Contains **no** biological or scientific value and
  touches no decision blocked by `B-S00-03`.
- **Caveat, carried from C06A:** frozen for implementation, **not** mentor
  approval; subject to independent numerical review before final runs.

This replaces the `[UNSPECIFIED]` rules in
`planning-package/02_REQUIREMENTS/P08_COMPARISON_HARNESS_SPEC_DRAFT.md`, whose
completion condition is that comparison criteria be accepted *"without
inspecting real P08 results."*

---

## 0. Honest statement about predeclaration

The raw baseline-versus-repaired observations this contract will be applied to
**already exist**: they were produced by the C04 reference-host run and have been
seen by the writer. Pretending otherwise would be false.

What protects the predeclaration is therefore not ignorance of the data but the
*derivation* of the rules:

1. Every dimension rule below is derived from the **five reviewed defect
   mappings** in the P07 candidate (CDEF-01…CDEF-05) and from tolerances already
   frozen in `AGENTS.md`. Those predate the observations.
2. No rule references a numeric value taken from an observed outcome. Where a
   threshold is needed, it is either exact equality, an `AGENTS.md` tolerance, or
   a *shape* criterion (saturation, sign, staleness) that was stated in the C04
   report before this contract existed.
3. Every outcome class is exercised by **synthetic fixtures** that are
   independent of the real data, including the classes the real data does not
   produce. A rule that only works on the actual results would fail those.

A reviewer should check point 1 by comparing each rule to the defect mapping it
cites, and point 3 by running the synthetic suite.

## 1. Comparison classes

Every dimension resolves to exactly one:

| Class | Meaning |
|---|---|
| `REPRODUCED` | the historical defect is observed in the **baseline** tree |
| `REPAIR_VERIFIED` | the defect is observed in baseline **and** the corrected behaviour is observed in repaired, on the same fixture |
| `UNCHANGED_INVARIANT` | baseline and repaired agree, and agreement is what the dimension requires |
| `CONTRADICTORY` | the observations conflict with the dimension's own rule, in either direction |
| `INCONCLUSIVE` | the evidence needed to decide is absent, incomplete, or not attributable |

`INCONCLUSIVE` is **not** a soft pass. A dimension that cannot be decided is
reported as undecided and blocks any conclusion that depends on it.

## 2. Comparator kinds

| Kind | Rule |
|---|---|
| `EXACT` | bitwise equality of the parsed double, or of the text line for log comparisons. No tolerance. |
| `TOLERANCE` | relative difference against a threshold **stated in this contract or in `AGENTS.md`**. A tolerance may never be introduced or widened after an outcome is seen. |
| `INVARIANT` | a property that must hold regardless of value — a sign, a bound, a monotonicity, a saturation shape, or a count |

Selection is fixed per dimension below and is not negotiable per-run.

## 3. Dimensions

Ordered. Each cites the defect mapping or requirement it derives from.

### D1 — CDEF-01/02 second-half donor cap

- **Derives from:** P07 mapping CDEF-01/CDEF-02 (`bmx_chem_K.H:2188`, `:2220`).
- **Observable:** fluid-side `A_particles` and `A_fluid` from `bmx.print_sums`,
  over the `k1` sweep.
- **Comparator:** `INVARIANT` (saturation shape) **and** `EXACT`
  (`A_particles_final == fA0 * V_cell`).
- **`REPRODUCED` when:** the baseline transfer grows monotonically with `k1`
  across the sweep — i.e. it is *not* capped.
- **`REPAIR_VERIFIED` when:** additionally the repaired transfer saturates
  (constant to within 1e-6 relative across all rows with `alpha' > 1`) **and**
  `A_particles_final` equals `fA0 * V_cell` exactly.
- **`CONTRADICTORY` when:** the repaired transfer exceeds the available amount,
  or the baseline saturates while the repaired does not.

### D2 — CDEF-03 first-half stale exchange area

- **Derives from:** P07 mapping CDEF-03 (`bmx_chem_K.H:1623`).
- **Observable:** particle `cA`, `cC` after a tip growth step.
- **Comparator:** `EXACT` inequality (the two trees must differ).
- **`REPAIR_VERIFIED` when:** baseline and repaired differ on a fixture in which
  a tip growth branch is directly observed to execute.
- **`INCONCLUSIVE` when:** they differ but no branch execution was observed —
  a difference alone does not attribute to this mapping.

### D3 — CDEF-04 tip stored-area staleness

- **Derives from:** P07 mapping CDEF-04 (`:2064` radius-only, `:2072`
  length-only).
- **Observable:** per-transition branch classification plus the stored
  `realIdx::area` field.
- **Comparator:** `INVARIANT` (branch predicted == branch observed) **and**
  `EXACT` (stored area unchanged across the transition).
- **`REPRODUCED` when:** in the baseline, both branches execute with the stored
  area left bit-unchanged on every such transition.
- **`REPAIR_VERIFIED` when:** additionally the repaired tree's `cA`/`cC` differ
  from baseline on those same fixtures.
- **`CONTRADICTORY` when:** predicted and observed branches disagree on any
  transition.

### D4 — CDEF-05 non-tip rejected-growth rollback

- **Derives from:** P07 mapping CDEF-05 (`:2098`).
- **Observable:** particle `cB`, `vol`, `dvdt`, `dadt` on non-tip segments.
- **Comparator:** `INVARIANT` (rejection observed: `vol` unchanged, `dvdt == 0`,
  `dadt == 0`) **and** `EXACT` (`cB` differs between trees).
- **`REPAIR_VERIFIED` when:** rejections are observed **and** repaired `cB` is
  restored while baseline `cB` remains debited.

### D5 — carbon-only scope preserved

- **Derives from:** the P07 phosphorus exclusion boundary.
- **Observable:** the 91 phosphorus-bearing source lines, and the diff scope.
- **Comparator:** `EXACT`.
- **`UNCHANGED_INVARIANT` when:** all 91 P-lines are byte-identical between
  baseline and candidate, and the patch touches exactly one file.
- **`CONTRADICTORY` when:** any P-line changed.

### D6 — phosphorus excluded from claims

- **Required by the spec, not optional.**
- **Observable:** the claim text of this stage's own report.
- **Comparator:** `INVARIANT`.
- **`UNCHANGED_INVARIANT` when:** no conclusion asserts phosphorus correctness,
  and the deliberate `dP1`/`dP2` staleness asymmetry is restated.

### D7 — source/build/executable identity continuity

- **Required.**
- **Observable:** baseline commit and kernel hash, candidate commit and kernel
  hash, AMReX commit and tree, the four image SHA-256s, and each image's
  self-reported provenance.
- **Comparator:** `EXACT`.
- **`UNCHANGED_INVARIANT` when:** every identity matches the frozen value and
  every image reports `RESOLVED` provenance on a clean tree.
- **`CONTRADICTORY` when:** any identity mismatches — this is a hard stop, not a
  finding.

### D8 — platform-only differences not attributed to P07

- **Derives from:** the spec's synthetic branch *"platform-only difference
  incorrectly classified as repair effect."*
- **Rule (the platform comparison class):** a difference may be attributed to
  P07 **only** when it appears between baseline and repaired **within a single
  platform**. A difference that appears for the **same tree across platforms** is
  platform-only and may never be attributed to the repair.
- **Comparator:** `EXACT` across platforms.
- **`UNCHANGED_INVARIANT` when:** for each tree, the observables agree across all
  platforms exercised, so cross-platform variance is zero and no observed
  baseline-vs-repaired difference can be platform-induced.
- **`INCONCLUSIVE` when:** fewer than two platforms are available for the same
  tree.

## 4. Membership and generation rules

The comparator rejects, rather than interprets:

| Condition | Outcome |
|---|---|
| a required member is missing | hard error, dimension `INCONCLUSIVE` |
| an unexpected extra member is present | hard error |
| a member appears more than once | hard error |
| baseline and repaired members come from different generations (different source or image identity than the frozen chain) | hard error |
| a derived record cannot be traced to a raw record | hard error |

## 5. Determinism

The comparison record must be **byte-identical under any input ordering**.
The comparator sorts by a canonical key before emitting, and the synthetic suite
verifies this by shuffling.

## 6. Conclusion rule

A bounded conclusion may state only:

- which of the five defect mappings are `REPRODUCED` and `REPAIR_VERIFIED`,
- that the carbon-only scope held,
- that identity continuity held,
- that no observed difference is platform-attributable.

It may **not** state: any phosphorus behaviour is correct; any conservation
property of the model as a whole; any scientific or biological result; P07 phase
success; formal P05–P18 acceptance; `RG-SW:GO`; `RG-SCI:GO`.

If any dimension is `CONTRADICTORY` or `INCONCLUSIVE`, the conclusion must name
it and must not claim overall support for P07.
