# C12 / P14 stage report

Status: **BLOCKED before source implementation**.

## Completed

- Verified the attached user-adopted decision freeze is byte-identical to the
  preserved V2 source at SHA-256
  `34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066`.
- Confirmed P14 fits the existing `O09_INTERFACE_EXPORT_TRANSACTION` slot.
  The global-order bytes remain
  `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`;
  no operator-order v2 is required.
- Reconciled the adopted P14 source, P11 geometry contract, decision ledger,
  and verified pre-mentor P14 inventory.
- Confirmed the C11 source tree and frozen kernel remain unchanged.

## Blocking root cause

The contract defines the export equation, but not the executable value of two
of its operands:

1. `f_I` is bounded and named, but no binding artifact maps P11's binary
   finite-radius predicates to an interface-active fraction. Choosing binary
   eligibility, a centerline fraction, a capsule-volume fraction, a surface
   fraction, or another measure would change P14 outcomes.
2. The reward relation is written as `3*M_P/M_C ~= 7.736`, but neither exact
   atomic masses nor the rounded literal as an exact multiplier are frozen.

These are not operator-placement questions and are not safe technical defaults.
They directly set export and reward amounts. The controlling instruction says
to record `BLOCKED` rather than choose an unstated value, so no P14 source edit,
build, or runtime qualification was started.

## Required bindings

- Define `f_I` exactly, including its geometry measure and
  segment-refinement behavior.
- Bind either literal `7.736` exactly as mol A-equivalent per mol P, or exact
  `M_P` and `M_C` constants for `3*M_P/M_C`.

P14 entries remain `CLOSED_USER_ADOPTED` under
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`; this report neither changes
their preserved residual-gap fields nor claims `CLOSED_SCIENTIFIC`.

C11 remains `PASS`. C13 was not started because C12 did not clear its binding
gate. No external resource was launched and spend is `$0`.
