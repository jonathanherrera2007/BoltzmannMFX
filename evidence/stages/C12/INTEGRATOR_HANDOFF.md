# C12 integrator handoff

C11/P13 remains complete and qualified. C12/P14 is blocked before source edit
on two missing executable bindings:

1. `D-C12-01-INTERFACE-FRACTION-DEFINITION`: bind the exact mapping from the
   P11 finite-radius geometry to `f_I`. State whether it is binary or
   continuous; for a continuous rule, define the measured primitive,
   numerator, denominator, boundary/tolerance handling, and
   segment-refinement behavior.
2. `D-C12-02-REWARD-CONVERSION-CONSTANT`: bind either literal `7.736` exactly
   in mol A-equivalent per mol P, or exact `M_P` and `M_C` values used in
   `3*M_P/M_C`.

P14's global placement is not blocked. The writer-frozen artifact
`contracts/p14/OPERATOR_FIT_V1.json` proves it fills the existing O09 slot at
SHA-256 `72193a1034d4148d167f059c347053d2206fa580cce9a156ec705304e7f378e7`.
Do not create a global-order v2 unless a later implementation cannot honor
that artifact; if so, freeze exact new bytes and stop for independent review.

No P14 source, schema, build, or runtime output exists. The C11 source tree is
still `ef72f6930912a57e95a942dd7742a8584d7bc684`, and the frozen kernel remains
`9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.

C13/P15 Stage 0 was not started because the sequence requires C12 completion
first. After the two bindings are supplied, resume C12 on `rgsw/c12-p14`,
implement and qualify it fully, then enter C13 Stage 0 only. Do not run C13
science outcomes.
