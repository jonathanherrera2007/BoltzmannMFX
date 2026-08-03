# C10 integrator handoff

C10 stops at `D-C10-02-NUMERICAL-CONVERGENCE`. The implementation and all
non-outcome engineering checks pass, but no production resolution qualifies.
Do not begin C11 until a new numerical contract is frozen and independently
reviewed, then the complete L0/L1/L2 matrix is rerun without changing the
scientific arms or rates.

The root cause is donor-cell amount resolution, not Michaelis–Menten kinetics:
the low arm is uncapped at L0/L1 and capped at L2. Preserve the failed result.
Do not cite the L2 1.723 contrast as biology.

The tree contains no C11/P13, C12/P14, or C13/P15 implementation. The frozen
kernel remains byte-identical. No external resource was launched and nothing
was pushed.
