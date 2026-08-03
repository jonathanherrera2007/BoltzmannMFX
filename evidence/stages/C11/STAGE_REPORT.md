# C11 / P13 stage report

## Verdict

**C11/P13 is `PASS` for Windows software and numerical engineering.** It
implements the provisional user-adopted D/E reaction and Liebig growth
contract, preserves the frozen kernel and global operator order, and passes
enabled, feature-off, MPI, restart, corruption, topology, and redistribution
qualification.

This is not mentor approval, a biological baseline, calibration, predictive
validation, RG-SCI progress, release-host evidence, or C12+ behavior.

## Operator order

P13 fits the existing `O02_LOCAL_MESH_PARTICLE_UPDATE` slot of
`bmx-p10-global-order-v1`. O02 already says membrane transfer precedes an
enabled local D/E reaction, which precedes growth eligibility from the
post-reaction state; it also requires admissible geometry before B/E debit and
structural-P credit only for accepted realized growth. C11 fills those clauses
without adding or reordering a global operator.

- Global-order SHA-256: `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`
- P13 O02-fit SHA-256: `ea6e8dc2ca3f69fe2f366801c9df8ec9832b58f399d605c88d91527ff2098407`
- Global order changed: **no**

the implementation writer is the implementation writer and does not claim to be an independent
reviewer. P13-U05 is recorded as a writer-owned technical fit freeze while its
decision status remains `CLOSED_USER_ADOPTED` and its authority residual is
preserved.

## Implemented transaction

Forward and reverse D/E requests use one common pre-reaction state. Each is
independently capped by its donor amount, and the two accepted transfers commit
simultaneously. Growth then computes the carbon-supported and E-supported
volume increments, takes their minimum, and caps it by available B, available
E, and native geometry.

Only accepted growth commits geometry and debits B/E. The exact E debit is
credited to persistent structural P. Rejected or geometry-ineligible growth
consumes neither donor. F remains inactive and conserved.

When P13 is off, the frozen chemistry kernel receives the original parameter
pointer. When P13 is on for a fungal particle, C11 supplies a copied parameter
vector with only the superseded legacy growth/limiter slots zeroed, executes
the frozen earlier chemistry, and then applies P13 once. The frozen kernel
remains byte-identical at
`9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.

## Qualification

- Clean Release build from commit
 `ff059edbc5bf10d61936a43b2b5bdfb05d69c133`: **PASS**
- Analytical reaction/growth/negative/nonfinite suite, 43 checks: **PASS**
- Enabled native suite, 18 cases: **PASS**
- One-rank vs two-rank equivalence at one and four steps: **PASS**
- Continuous vs 1->1 restart and 2->1 rank-change restart: **PASS**
- Five checkpoint identity/algebra/structural mutations rejected: **PASS**
- C10-vs-C11 G1/G4 semantic feature-off trajectory: **0 differences**
- P10 topology regression, four runs: **PASS**
- P10 redistribution guards, four cases including 2->1 restart: **PASS**
- Static scope/freeze/fail-closed audit, 24 checks: **PASS**

The clean executable SHA-256 is
`a7a2700556b553f7cfae298bbe681474fff9086cdab5a8c83d53b4869fd38825`.
Checkpoint schema v6 binds the P13 contract, O02 fit, exact parameters, every
cumulative diagnostic, and the equality between P13 structuralization and the
global structural-P ledger.

## Authority and next boundary

Every P13 scientific entry remains
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`. The adopted rate and quota
values are sensitivities only; C11 selects no biological baseline and makes no
scientific claim.

P12 uptake-only and P13 reaction/growth remain deliberately fail-closed when
requested together because C11 did not preregister a combined experiment. A
combined all-mechanism path belongs to the separately authorized C13 Stage 0
work, before which no C13 science run may occur.

C12/P14 is separately user-authorized, but C12 was not started by this report.
No external resources were used and spend was `$0`.
