# C12 blocker report

Status: `BLOCKED` at the P14 specification-completeness gate.

P14 fits the existing `O09_INTERFACE_EXPORT_TRANSACTION` slot. No new global
operator order is required. The adopted source also fixes the donor, recipient,
exponential export law, five `k_export` levels, donor cap, reward destination,
same-update atomicity, and matched zero-export controls.

Two values needed for an executable transaction remain unstated:

1. `D-C12-01-INTERFACE-FRACTION-DEFINITION`: the contract introduces
   `f_I in [0,1]`, but does not define how the P11 finite-radius geometry becomes
   that fraction. P11 supplies binary `window_contact` and `true_crossing`
   predicates; it does not choose binary eligibility, centerline fraction,
   capsule-volume fraction, exposed-surface fraction, or another measure.
2. `D-C12-02-REWARD-CONVERSION-CONSTANT`: the contract specifies
   `delta_N_A = (3*M_P/M_C)*delta_N_P ~= 7.736*delta_N_P`, but freezes neither
   exact `M_P` and `M_C` values nor the rounded literal `7.736` as the exact
   executable multiplier.

Both choices change export/reward ledger values. Filling either gap would
choose an unstated rule or constant, which the C11-to-C13 execution instruction
explicitly prohibits.

To resume C12, bind:

- an exact executable `f_I` definition, including its geometry measure and
  segment-refinement behavior; and
- either literal `7.736` exactly in mol A-equivalent per mol P, or exact `M_P`
  and `M_C` constants for `3*M_P/M_C`.

No P14 source edit, build, or outcome run was started. C13 was not started.
No external resource was launched and spend is `$0`.
