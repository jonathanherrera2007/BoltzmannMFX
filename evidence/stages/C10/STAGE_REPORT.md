# C10 / P12 stage report

Status: **BLOCKED — engineering implementation complete; numerical
qualification failed.**

## Frozen identities

- Implementation commit: `ce1764e`.
- Evidence/build commit: `8f19296`; clean definitive executable SHA-256
  `8efdf36d3e8cbd022b5a3dbc4e3d5b54889cee8a2fcf90410387bf5f3ae6c4df`.
- Frozen kernel SHA-256:
  `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.
- V2 user decision source SHA-256:
  `34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066`.
- P12 contract SHA-256:
  `2094aed3c8ef21a257d2c597352793384d01a1efc3d72936d5c5108d308f8804`.
- Operator order remains `bmx-p10-global-order-v1` at
  `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`.

## Operator-order determination

The two-pass gather/scale/apply algorithm fits O02 unchanged. All requests
are gathered from one immutable pre-O02 state, one donor scale is computed,
and accepted particle transfers are applied inside the same membrane-transfer
operator. O03 still commits signed extensive mesh increments and O04 still
performs diffusion. The frozen bytes do not require particle-iteration-order
single-pass execution, so no operator-order-v2 was created or self-approved.

## Decision and checkpoint consequences

Covered decisions are labelled `CLOSED_USER_ADOPTED` with
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`; residual gaps are retained
and no new entry is `CLOSED_SCIENTIFIC`. The linear uptake law is only
`ENGINEERING_REGRESSION_COMPARATOR` and carries no C10/C13 claim.

The new decision hash is bound into schema v4. The reissued C08 suite passes
one-rank, two-rank, 2→2, and 2→1 restart equivalence. A mutated decision hash
is rejected before particle deserialization. F-8 now uses the true pre-C08 tip
`40a28b3`.

## P12 implementation and engineering checks

- Inward-only Michaelis–Menten surface uptake with shared-donor arbitration.
- Accepted-only mesh-D debit and internal-D credit; E/F/export/reward/growth
  remain exact zero.
- Fixed-network terminal sensitivities are valid because the sole 0.003 cm
  live-tip segment lies wholly inside the smallest 0.005 cm window. Any future
  topology requiring graph distance or partial area aborts.
- Fixed-network mechanics/topology are bypassed while P12 is enabled.
- Analytical unit: `PASS` (28 assertions).
- Native transaction/MPI/control/restart matrix: `PASS`.
- Static/ownership/frozen-kernel suite: `PASS`.
- Checkpoint/restart reissue: `PASS`, including 2→1.

## Saturation prediction and measured contrast

The low/high arms are at saturation fractions 0.9415 and 0.9783. Although
their concentration ratio is 2.8075, the predicted initial flux ratio is only
`1.039154791108985`.

| Level | low accepted (mol) | high accepted (mol) | high/low | wall/run on local Windows host |
|---|---:|---:|---:|---:|
| L0 | 2.45492869952405e-12 | 2.55376503448491e-12 | 1.04026036885716 | 2.36–2.70 s |
| L1 | 2.45465105258539e-12 | 2.55372641185809e-12 | 1.04036229881569 | 7.46–7.62 s |
| L2 | 1.48209197049112e-12 | 2.55365091018489e-12 | 1.72300434860240 | 69.44–70.40 s |

L0/L1 return the predicted near-null contrast. L2's larger contrast is not a
scientific result: it is caused by the low-arm donor cap and fails the frozen
convergence gate.

## Stop and timing boundary

`D-C10-02-NUMERICAL-CONVERGENCE` is open. No production resolution was
selected. Consequently, reference-host wall time and projections for 151
configurations at n=5/10/20 are `NOT_AVAILABLE`, not guessed from a
nonqualifying local level. C11, C12, and C13 Stage 0 were not begun. No C13,
C14/P16, or P17 science ran. No remote operation or external spend occurred.
