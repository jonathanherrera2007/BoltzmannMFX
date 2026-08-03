# C06A — decision reconciliation

Reconciles all **59** generic unknowns in
`SCIENTIFIC_DECISION_LEDGER_SANITIZED.json` against the **13** confirmed
exploratory-v1 decisions in `CONFIRMED_SCIENCE_DECISIONS_REDACTED.json`, plus
the user's explicit 2026-08-01 adoption of the P10-U01 topology contract,
the C09 activation of section 9 of that same preserved user contract, and
the exact V2 user-adopted provisional decision freeze, and
the hash-bound independent P10-U02 operator-order review.

Machine-readable: `contracts/decision_reconciliation.json`,
`contracts/release_blockers.json`.
Every field is accounted for exactly once — enforced programmatically; the
generator aborts on any unmapped or extra ID.

---

## Result

| Status | Count | Meaning |
|---|---:|---|
| `CLOSED_SCIENTIFIC` | **1** | the remaining confirmed scientific entry not superseded by a user-only adoption |
| `CLOSED_TECHNICAL` | **8** | no biological content; frozen by the writer under source-safety justification, with P10-U02 independently reviewed |
| `CLOSED_USER_ADOPTED` | **42** | binding provisional user decisions; every covered entry is explicitly pending mentor override and retains any residual gap |
| `CLOSED_MEASURED` | **3** | operational values measured from real runs |
| `OPEN` | **5** | P17 post-results fields only |

**54 of 59 fields are closed by status.** `CLOSED_USER_ADOPTED` is not a
scientific closure: its non-null residual gaps remain release gates. The five
open fields are P17 and belong to the post-results review.

## The reconciliation rule applied

`DECISION_RECONCILIATION_REQUIRED.md` warns against assuming either "all
science is settled" or "all generic unknowns remain unresolved". Both failure
modes were avoided explicitly:

- A confirmed decision closes a field **only within its stated scope**. The
  clearest case is `P13-U03-RATE-VALUES-BOUNDS`: rate values 1e-6/1e-5/1e-4 s⁻¹
  are confirmed, but *as sensitivities only*, and the decision says to select no
  biological baseline. It is recorded `CLOSED_SCIENTIFIC` for the sensitivity
  axis and explicitly **not** as a calibrated value.
- A field is `CLOSED_TECHNICAL` only where no biology is involved — checkpoint
  compatibility, numerical tolerances, non-finite policy, test-case enumeration,
  ledger schema. These are frozen now so implementation is not blocked on the
  mentor for engineering matters.

## What the reconciliation removed from the mentor's list

The pre-existing urgent packet asks 8 items. Reconciliation closed two of them
against decisions already made, which is the main practical value of this stage:

1. **The export law form was already decided.** `MD-88955e1dff7ca225-02` states
   export occurs "at `k_export` multiplied by local D" — that fixes the
   functional form as first-order in local internal D. Only the operand
   (amount vs concentration), units, and magnitude remain. Asking "first-order,
   area-based, or another form?" would have re-litigated a settled decision.
2. **The reward conversion was already fully specified.**
   `MD-5b43f4b235dec87e-03` gives `r = 3` as mass C per mass P actually
   exported and derives ≈7.736 mol A-equivalent per mol P, plus "no version-1
   capacity or delay" — which also answers whether an extra interface cap
   exists. It does not.

The refined packet is `mentor/MENTOR_PACKET_C06A.md`.

## Residual gaps NOT present as ledger fields

Two items materially block implementation but have no ledger ID, so they would
be missed by a field-by-field pass alone:

| ID | Gap | Why it matters |
|---|---|---|
| `G-EXT-01` | D membrane uptake coefficient value/range, and confirmation that D uses the same reversible area-based form as carbon | P12 cannot run its final contract without it |
| `G-EXT-02` | `k_export` operand (amount vs concentration), units, and value/range | P14 export cannot be enabled |

Both are in the packet.

## Cross-cutting review triggers carried forward

- **Renewed review before P16.** `MD-5b43f4b235dec87e-05` approves `q_P` and
  `k_gP/k_gB` as sensitivities only and selects no baseline; using them to
  define or compare explorer/exploiter strategies requires renewed review. The
  packet requests it explicitly rather than assuming.
- **F activation prohibited.** F infrastructure may exist, but every F reaction,
  exchange, and transport coefficient stays exactly zero. Activation needs a
  separate decision.

## Technical policies frozen by this stage

Justified by source safety, containing no biological selection:

| Field | Frozen policy |
|---|---|
| `P09-U01` | canonical vocabulary is D/E/F; legacy `P_uptake`/`P_growth`/`P_delivery` aliases rejected in enabled mode |
| `P09-U03` | reject legacy checkpoints before particle deserialization; require schema v2 with names/counts, layout hash, operator-order ID, units contract, decision hash, global ledgers |
| `P10-U03` | local `abs(residual) <= 64·eps·S_L1`; integrated `abs(residual) <= max(1e-28 mol, 1e-10·S_L1)`; NaN/Inf hard fail; negative amount beyond tolerance hard fail |
| `P10-U04` | exact identifiers and schema; floating fields `<= 1e-12` relative unless a stricter exact comparator applies |
| `P10-U01` | user-approved v1 topology contract: exact successor ownership or pre-mutation abort; zero other exits; unique bond remap/prune; immutable-snapshot disjoint batches and atomic conflict abort |
| `P13-U07` | centralized, counted, reported roundoff clamps; unexplained clamps block release |
| `P13-U08` | limiting-case test enumeration is writer-owned test design |
| `P14-U08`, `P14-U09` | ledger field list/schema and shared numerical tolerances |
| `P12-U05`, `P12-U06`, `P15-U06` | timeouts and output quotas measured from real runs |

**These are proposals frozen for implementation, not mentor approval.** They
remain subject to independent numerical review before final runs.

## Stages that may proceed

Superseded C06A snapshot: Implementable now, within closed contracts: **P09** (state infrastructure) and
**P10** (conservation, topology, restart) — apart from the deletion/orphan/
simultaneous-event semantics named in `P10-U01` and the global operator order in
`P10-U02`, both of which must be frozen and reviewed before final runs.

Current C08 reconciliation: `P10-U01` is closed by the binding user-approved
contract preserved at `contracts/USER_APPROVED_DECISION_CONTRACT_20260801.txt`.
It is labeled `CLOSED_USER_ADOPTED`, not `CLOSED_SCIENTIFIC`: the adoption is
limited to P10-U01 for RG-SW C08, does not constitute mentor approval, and does
did not ingest or close later-stage decisions present in that source. The former
derived-container authority blocker is closed by the user's exact C08-only
grant recorded in `evidence/stages/C08/USER_APPROVAL.md`; the wrappers and the
pre-deserialization Restart payload guard pass their clean engineering suite.
The independent receipt `IR-20260801-P10-U02` approves the unchanged
`OPERATOR_ORDER_V1.json` artifact at SHA-256
`bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`;
its implementation and evidence corrections are tracked in the C08 review
disposition rather than rewriting the reviewed order.

Current C09 reconciliation: the user's explicit C09 authorization activates
only section 9 of the already-adopted contract. `P11-U04` and `P11-U05` are
therefore `CLOSED_USER_ADOPTED`, not `CLOSED_SCIENTIFIC`; C10+ sections remain
unconsumed. **P11** may now be implemented. **P12, P13, P14** may have infrastructure built default-off, but
**no final run may execute**. **P15, P16** are fully blocked. **P17** is
post-results.

Current C10 reconciliation: the user's exact V2 source is bound as
`UDC-20260801-MENTOR-DECISION-FREEZE-V2`, at SHA-256
`34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066`.
Every covered decision is `CLOSED_USER_ADOPTED` under the exact
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE` classification, never
`CLOSED_SCIENTIFIC`; existing residual gaps are preserved. The old linear
uptake law is `ENGINEERING_REGRESSION_COMPARATOR` only. The four supersessions
are Michaelis--Menten uptake, the 5e-6 cm2/s mesh-D diffusivity centre, the
5.26977773579e-6 s-1 export centre, and the P16 surface-area-density objective.
P16 memberships remain `[]` and `BLOCKED_ON_EXTERNAL_STRATEGY_BASELINE`.

Current C11 reconciliation: P13 was implemented only under the provisional
user-adopted contract and remains pending mentor override. The writer-owned
P13-U05 technical freeze is recorded at
`contracts/p13/OPERATOR_FIT_V1.json` (SHA-256
`ea6e8dc2ca3f69fe2f366801c9df8ec9832b58f399d605c88d91527ff2098407`).
It fills the already-frozen `O02_LOCAL_MESH_PARTICLE_UPDATE` slot without
changing the global operator-order bytes. The decision status remains
`CLOSED_USER_ADOPTED`, its residual gap is preserved, and no
`CLOSED_SCIENTIFIC` claim is made for P13.

Current C12 reconciliation: P14 fits the already-frozen
`O09_INTERFACE_EXPORT_TRANSACTION` slot. The writer-owned fit is recorded at
`contracts/p14/OPERATOR_FIT_V1.json` (SHA-256
`72193a1034d4148d167f059c347053d2206fa580cce9a156ec705304e7f378e7`),
so no global-order v2 is required. Source implementation is blocked before
edit by `D-C12-01-INTERFACE-FRACTION-DEFINITION` and
`D-C12-02-REWARD-CONVERSION-CONSTANT`: the adopted source names `f_I` without
an executable geometry-to-fraction rule and gives `3*M_P/M_C ~= 7.736`
without freezing exact masses or the rounded multiplier. P14 decision statuses
and their pre-existing residual gaps remain unchanged; this downstream
completeness gate makes no `CLOSED_SCIENTIFIC` claim. C13 was not started.

Current C12 resumption: explicit user decision
`UDC-20260802-P14-C12-BINDINGS-V1` closes both implementation gaps under
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`. The exact contract is
`contracts/p14/EXPORT_REWARD_CONTRACT_V1.json` at SHA-256
`01a9d6eb7291cc8bc0c98f52afbf3c5ea1c86da4fd3f992a02665e283f81ff4e`.
It binds a continuous finite-radius axial-contact fraction with P11 snapping,
strict non-tangent capsule-interior overlap, solid-frame precedence, and
segment-refinement identities. It also binds the exact executable reward
multiplier `7.736 = 967/125` without atomic-mass constants. This is RG-SW
implementation/preregistration authority only, not mentor approval,
calibration, predictive validation, or `CLOSED_SCIENTIFIC`.

Current C13 resumption: explicit user decision
`UDC-20260802-C13-STAGE0-BINDINGS-V1` closes the three Stage-0 specification
gaps under `USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`. The binding
source SHA-256 is
`cbd1eedddf31b94c8a9d23d7b2d3329f065a007824387c70435d1004fdc6f350`.
It freezes a separate conservative finite-volume bonded-D graph operator for
O07, a prospective 216-hour numerical preregistration, and general
metric-graph terminal-zone areas for O02. The global order and frozen chemistry
kernel remain unchanged. Product implementation and short engineering fixtures
may proceed, but independent frozen-source/numerical review is required before
any 216-hour qualification outcome, and no P15 scientific outcome is
authorized. This is not mentor approval, calibration, predictive validation,
RG-SCI progress, or `CLOSED_SCIENTIFIC`.

The first forced stochastic-topology decomposition fixture subsequently exposed
`D-C13-04-RNG-TOPOLOGY-DECOMPOSITION`. The adopted seed is exact, but neither
the decision contract nor the numerical preregistration binds a stateless RNG
key/draw algorithm, conditional draw schedule, canonical child-ID namespace,
or checkpointed RNG/event ledger. The inherited rank-offset AMReX streams
produce different child identities and geometry when the same parent moves
between MPI owners. C13 therefore remains blocked before exact-source review
and before every 216-hour outcome. Resolving this requires a prospective
user-adopted technical binding; it must remain
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE` and must not be labelled
`CLOSED_SCIENTIFIC`.
