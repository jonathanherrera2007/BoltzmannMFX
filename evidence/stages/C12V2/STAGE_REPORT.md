# C12 / P14 stage report

## Verdict

**C12/P14 is `PASS` for Windows software and numerical engineering.** The
implementation fills the frozen O09 export slot, preserves the frozen
chemistry kernel and global operator order, and passes analytical, native,
feature-off, MPI, decomposition, restart, corruption, topology, P12, and P13
qualification.

The authority remains
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`. This result is not mentor
approval, calibration, `CLOSED_SCIENTIFIC`, predictive validation, RG-SCI
progress, release-host reproduction, or a C13 scientific outcome.

## Frozen decision and operator fit

The decision-only commit `ba8e1e8` froze the continuous finite-radius
interface fraction and exact reward multiplier before product implementation.
The P14 contract SHA-256 is
`01a9d6eb7291cc8bc0c98f52afbf3c5ea1c86da4fd3f992a02665e283f81ff4e`.

P14 fits `O09_INTERFACE_EXPORT_TRANSACTION` unchanged. O09 already reserves a
single final-topology segment transaction in which eligibility, request, and
caps are computed before the accepted local-D debit, local-A credit, and
external exported-P receipt are committed together. No global operator was
added, removed, or reordered.

- Global-order SHA-256:
 `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`
- P14 O09-fit SHA-256:
 `72193a1034d4148d167f059c347053d2206fa580cce9a156ec705304e7f378e7`
- Global order changed: **no**

the implementation writer is the implementation writer and makes no independent-review claim.

## Implemented transaction

For each final-topology fungal segment, C12 computes the normalized axial
measure whose finite-radius centerline lies strictly inside the P11 aperture
support after P11 snapping and tolerance handling. Tangency contributes zero,
solid-frame contact takes precedence, and `true_crossing` remains diagnostic
only. The calculation does not depend on cell occupancy, AMR level, rank,
tile, or decomposition.

The export request is
`f_I * N_D * (1 - exp(-k_export * dt))`. The donor cap is evaluated before the
same-update commit that debits local D, credits the external exported-P
receipt, and credits local exchange-derived A. The A reward uses the exact
executable rational `967/125 = 7.736` per accepted elemental-P amount. No
atomic-mass constant or table derivation was introduced, and bootstrap A stays
separate from exchange-derived A. F remains inactive and unchanged.

Every geometry-preserving collinear child recomputes its own fraction from
final geometry. Horizontal and oblique 1-to-2, 1-to-4, and 1-to-8 subdivisions
preserve both active volume and the C08-partitioned active D amount within the
frozen P10 local tolerance.

## Qualification

- Clean Release build from commit
 `9432628e47ed9defc9007cdbcda0f8956e813d63`: **PASS**
- Analytical export, geometry, cap, reward, refinement, and invalid-input
 suite, 137 checks: **PASS**
- Enabled native suite, 23 cases: **PASS**
- No-contact, tangency, partial, full, oblique, solid-edge, window-only, and
 true-crossing cases: **PASS**
- All five adopted export rates and exact zero controls: **PASS**
- Local/global P conservation, exact reward, atomic commit, provenance, and
 nonnegative donor checks: **PASS**
- One-rank versus two-rank and alternate decomposition equivalence: **PASS**
- Continuous versus 1-to-1 restart and 2-to-1 rank-change restart: **PASS**
- Contract, algebra, global-ledger, bad-rate, and bad-multiplier failures:
 **rejected before a valid P14 commit**
- C11-vs-C12 G1/G4 feature-off semantic trajectory, 420 particle records:
 **0 differing values**
- P10 topology and actual redistribution regressions: **PASS**
- P12 and P13 runtime regressions: **PASS**
- Static scope/freeze/order audit, 27 checks: **PASS**

The clean executable SHA-256 is
`910425149ee025d4701d8a42525e3c3ffdc03489284e3b537afadf0945633540`.
Checkpoint schema v7 binds the P14 contract, selected rate, exact multiplier,
and complete cumulative ledgers, including their equality to global exported
P.

The frozen chemistry kernel remains byte-identical at
`9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.

## Blockers and next boundary

`D-C12-01-INTERFACE-FRACTION-DEFINITION` and
`D-C12-02-REWARD-CONVERSION-CONSTANT` are closed as `CLOSED_USER_ADOPTED` for
RG-SW implementation only. Their adoption does not imply mentor approval or
scientific closure. P14 recipient-pool and operator-position residuals remain
documented under the same provisional classification.

C13/P15 Stage 0 may now begin under the existing authorization. It must stop
before every C13 scientific-outcome run. No external resources were used and
spend was `$0`.
