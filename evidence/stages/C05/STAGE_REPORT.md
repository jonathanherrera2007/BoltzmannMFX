# C05 — P08 baseline-versus-repair comparison

- **Stage ID:** `C05`
- **Status:** `PASS`
- **Date:** 2026-08-01
- **Role:** primary writer (the independent reviewer), product lane
- **Input HEAD:** `6f981670` (the predeclaration commit)
- **Contract:** `CON-P08-001`, `contracts/p08/`
- **Companion evidence:** `STAGE_REPORT.json`, `COMPARISON_RECORD.json`,
 `SELFTEST.json`, `BUNDLE.json`

> **All eight comparison dimensions resolve. No contradiction, nothing
> undecided.** The four P07 defect mappings covered by D1–D4 are **reproduced in
> the baseline tree and corrected in the repaired tree, observed directly**.
> Carbon-only scope and identity continuity hold, and cross-platform variance is
> zero across 19 tree/fixture/observable groups, so **no observed difference is
> platform-attributable**.
>
> **No model source was changed by this stage.** C05 owns the comparison
> harness, schemas, fixtures, analysis and evidence only.

---

## 1. What P08 needed, and what was missing

`P08_COMPARISON_HARNESS_SPEC_DRAFT.md` is a template in status
`PRELIMINARY_TEMPLATE_DEPENDENCY_BLOCKED`. Five of its seven comparison
dimensions were literally `[UNSPECIFIED]`, and its completion condition is that
criteria be accepted *"without inspecting real P08 results."*

C06A froze technical policies for P09–P15 but **nothing for P08**, so these
dimensions were genuinely unfrozen. C05 froze them.

## 2. Predeclaration, and an honest limit on it

`CON-P08-001` was committed at **`6f981670`**, *before* the comparator
(`4dc5e...` onward) and before any comparison was run. The ordering is
verifiable from git history rather than asserted.

**The limit, stated plainly:** the raw observations already existed and the
writer had already seen them — they were produced by C04. This is not a blind
predeclaration and it would be false to present it as one.

What protects it instead:

1. Every rule derives from the **five reviewed defect mappings** (CDEF-01…05)
 and from tolerances already in `AGENTS.md`. Both predate the observations.
2. No rule cites a numeric value taken from an observed outcome. Thresholds are
 exact equality, an `AGENTS.md` tolerance, or a *shape* criterion (saturation,
 sign, staleness, count).
3. Every outcome class — including the four the real data never produces — is
 exercised by synthetic fixtures containing none of the real measurements. A
 rule tuned to the actual results would fail those.

A reviewer can check (1) against the defect mappings and (3) by running
`run_p08_selftest.py`.

## 3. The eight dimensions

| | Dimension | Comparator | Result |
|---|---|---|---|
| **D1** | CDEF-01/02 second-half donor cap | `INVARIANT` + `EXACT` | **REPAIR_VERIFIED** |
| **D2** | CDEF-03 first-half stale exchange area | `EXACT` | **REPAIR_VERIFIED** |
| **D3** | CDEF-04 tip stored-area staleness | `INVARIANT` + `EXACT` | **REPAIR_VERIFIED** |
| **D4** | CDEF-05 non-tip rejected-growth rollback | `INVARIANT` + `EXACT` | **REPAIR_VERIFIED** |
| **D5** | carbon-only scope preserved | `EXACT` | UNCHANGED_INVARIANT |
| **D6** | phosphorus excluded from claims | `INVARIANT` | UNCHANGED_INVARIANT |
| **D7** | source/build/executable identity continuity | `EXACT` | UNCHANGED_INVARIANT |
| **D8** | platform-only differences not attributed to P07 | `EXACT` across platforms | UNCHANGED_INVARIANT |

Detail as recorded:

- **D1** — baseline uncapped across 6 `k1` rows; repaired saturates
 (spread `1.82e-15` ≤ `1e-06`) and final content equals `fA0·V_cell` exactly on
 4 rows.
- **D2** — trees differ on 5 fixtures with a directly observed tip growth branch.
- **D3** — both tip branches execute as predicted with stored area unchanged on
 4 fixtures, and the trees differ there.
- **D4** — 188 non-tip rejections observed; `cB` differs between trees.
- **D8** — cross-platform variance is zero across 2 platforms
 (`gce-reference-linux`, `windows-development`) on 19
 tree/fixture/observable groups.

## 4. Exact / tolerance / invariant, kept distinct

The contract fixes which comparator applies per dimension; it is not chosen
per-run.

- **`EXACT`** carries the weight wherever the claim is an equality or a
 non-difference: the donor-cap equality, stored-area staleness, the 91
 phosphorus lines, identity continuity, and every cross-platform comparison.
- **`TOLERANCE`** is used **once**, for the D1 saturation spread, at `1e-6`
 relative. Observed spread is `1.82e-15` — nine orders inside it. The threshold
 was declared in the contract before the comparison ran and was not widened.
- **`INVARIANT`** covers shape claims that no tolerance could express:
 monotonicity of the baseline transfer, predicted-equals-observed branch
 classification, rejection counts.

## 5. Platform-only differences (D8)

The spec listed *"platform-only difference incorrectly classified as repair
effect"* as a synthetic branch but left the platform comparison class
`[UNSPECIFIED]`. The contract states it:

> A difference may be attributed to P07 **only** when it appears between
> baseline and repaired **within a single platform**. A difference for the
> **same tree across platforms** is platform-only and may never be attributed to
> the repair.

Measured: for every one of 19 same-tree/same-fixture/same-observable groups, the
value agrees across the GCE reference host and the Windows development host.
Cross-platform variance is **zero**, so no baseline-versus-repaired difference
reported here can be platform-induced.

## 6. Synthetic suite — 23/23

`run_p08_selftest.py` manufactures bundles containing none of the real
measurements and covers every branch the spec names:

| Group | Cases |
|---|---|
| healthy path | historical failure + repaired success |
| both fail / both pass | repaired also tracks `k1`; branch ran yet nothing changed |
| contradictory | repaired exceeds available; branch prediction disagrees; P-line changed; phosphorus claim present; identity mismatch |
| platform trap | platform-only difference must not read as a repair effect; single platform cannot decide |
| attribution | difference without observed branch execution; no rejection observed |
| tolerance boundary | just inside and just outside the saturation threshold |
| membership | missing historical, missing repaired, duplicate, extra, wrong generation, untraceable, incomplete |
| determinism | input-order independence |

## 7. Determinism and traceability

| Check | Result |
|---|---|
| synthetic bundle, 12 shuffles | byte-identical |
| **real bundle, 25 shuffles** | **byte-identical**, sha256 `3bfd9434…` |
| dimensions with no traceable evidence | **none** — D1:1, D2:5, D3:4, D4:1, D5:1, D6:1, D7:1, D8:16 sources |

## 8. A comparator defect the real data exposed

The first run of the comparator against real evidence returned
**D8 CONTRADICTORY**, claiming cross-platform variance. That was wrong, and the
cause was mine.

`d8_platform` grouped observations by `(tree, observable)` — **omitting
`fixture`**. All six `k1` rows of the baseline sweep therefore collapsed into one
group and, of course, disagreed with each other. The comparator was reporting
the sweep varying and calling it platform variance.

Direct check of the underlying numbers showed the platforms agree to ten
significant figures:

```
 k1 baseline GCE baseline WIN repaired GCE repaired WIN
 0.5 1.261737482e-13 1.261737482e-13 4.569057503e-12 4.569057503e-12
 5.0 1.139173166e-12 1.139173166e-12 4.871032500e-12 4.871032500e-12
 100.0 4.870055587e-12 4.870055587e-12 4.871032500e-12 4.871032500e-12
```

The grouping key now includes `fixture`, and a group present on only one
platform is treated as *not comparable* rather than as evidence of agreement.

**Why the synthetic suite missed it:** the D8 case used a single fixture, so a
key missing `fixture` behaved correctly there. The suite now uses a
three-fixture sweep whose rows differ from each other but agree across
platforms, as a regression guard — `sweep_rows_are_not_platform_variance`.

This is the second time in this project that a harness passed synthetic tests
and failed on real structure. It is worth stating as a pattern rather than an
incident: synthetic fixtures verify the *logic*, not the *shape of the real
data*, and a suite whose fixtures are simpler than production will certify a
comparator that cannot read production.

## 9. Bounded conclusion

Reproduced verbatim from `COMPARISON_RECORD.json`:

> Within the carbon-only scope of P07 and on the identities recorded in this
> record, the defect mappings covered by D1, D2, D3, D4 are reproduced in the
> baseline tree and corrected in the repaired tree, observed directly rather
> than inferred. Carbon-only scope and identity continuity hold, and
> cross-platform variance is zero, so no observed difference is
> platform-attributable. This record makes NO claim about phosphorus behaviour,
> about any conservation property of the model as a whole, about any scientific
> or biological result, about P07 phase success, about formal P05–P18
> acceptance, or about RG-SW:GO or RG-SCI:GO.

The conclusion is emitted by the comparator, not written by hand, and is
withheld automatically if any dimension is `CONTRADICTORY` or `INCONCLUSIVE`.

## 10. Deliberate asymmetry — restated, as D6 requires

`dP1`/`dP2` continue to use the stale `new_cell_area` while carbon moves to the
refreshed `carbon_exchange_area`. This is intentional — the P07 phosphorus
exclusion boundary — and the 91/91 P-line check confirms no phosphorus line
changed. **Phosphorus retains exactly the CDEF-03 staleness that carbon just had
repaired.** Nothing in this record may be read as evidence that phosphorus area
handling is correct.

## 11. Mandatory validation

| Row | Status |
|---|---|
| Missing, extra, duplicate, wrong-generation, contradictory fixture tests pass | **PASS** — 23/23 |
| Comparator is input-order independent | **PASS** — synthetic 12 shuffles, real bundle 25 shuffles, byte-identical |
| Every conclusion traces to raw baseline and repaired evidence | **PASS** — all 8 dimensions cite sources; untraceable records are a hard error |
| Comparison dimensions frozen before outcomes | **PASS** — contract committed at `6f981670`, before the comparator, with the honesty limit in §2 recorded |
| Both trees built under one toolchain, same ordered cases | **PASS** — the C04 reference-host run, four independent builds on one host |
| Exact / tolerance / invariant distinguished | **PASS** — §4 |
| Platform-only differences not attributed to P07 | **PASS** — D8, zero variance over 19 groups |
| No model source altered | **PASS** — `src/` untouched; kernel still `9519fc24…ffba02` |

## 12. Claims

**Established:** the four defect mappings covered by D1–D4 are reproduced in
baseline and corrected in repaired, under predeclared rules, on a
reference-qualified platform, with every dimension traceable to raw evidence and
no platform-attributable confound.

**Not claimed:** anything about phosphorus behaviour; any conservation property
of the model as a whole (`D-C04-07` remains open); any scientific or biological
result; P07 phase success; formal P05–P18 acceptance; `RG-SW:GO`; `RG-SCI:GO`.

## 13. Blockers

| ID | Blocker | Owner | Status |
|---|---|---|---|
| B-S00-03 | Biology decisions unresolved; mentor packet unsent. Gates the P12/P15/P16 experiment contracts. | user / mentor | OPEN |
| B-C02-01 | Six defects worked around in the Windows build config; expected to be Windows-portability rather than product defects, which the Linux configure is written to test | writer + review | OPEN |
| B-C03-02 | C02 image hash not reproducible after install-path rename | writer | OPEN |
| D-C04-07 | Volume closure drifts during evolution; reported, not enforced | integrator (P10) | OPEN |

None blocks C05's own scope.

## 14. Next step

`PROMPT_INDEX` order after C05 is **C06A**, which is already complete
(`fd8b0ed`), then the mentor response gate. `C06B` cannot start until the mentor
packet is answered — that is `B-S00-03`, and it is a user action.

C07 (P09 three-state infrastructure) is the next *implementable* stage, and its
own plan is drafted but uncommitted. It does not depend on the mentor response
for the infrastructure work, but it must not proceed past default-off behaviour
into anything requiring a biological value.
