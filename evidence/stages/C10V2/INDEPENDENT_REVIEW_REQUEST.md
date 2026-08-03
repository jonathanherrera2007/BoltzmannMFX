# C10/P12 V2 independent numerical review request

Status: `FULFILLED` by `INDEPENDENT_NUMERICAL_REVIEW_V2.json`, SHA-256
`bda12aef209793b4537915e374e09caf100397c0fdf8678ed00118ff987a3ea2`.
This file remains as the preserved prerun request; it is not the final
acceptance request.

Review the clean commit containing this file from a separate read-only worktree
or detached checkout. The exact numerical preregistration is:

- ID: `USER-DIRECTED-20260801-P12-NUMERICAL-V2`
- SHA-256: `43d64a8f4ec6c8c00379fc3d9605441cb900479fcdd8db9e78e6fc1edd28f81f`
- File: `contracts/p12/NUMERICAL_PREREGISTRATION_V2.json`

The unavailable `sandbox:/mnt/data` proposal files and their stated hashes are
recorded as source provenance, but this repository artifact does **not** claim
byte identity with files that were not locally supplied.

## Required review

Confirm all of the following against the exact candidate commit:

1. Halving all three cell dimensions divides the represented one-cell donor
   volume by eight, so the V2 `dt/8` refinement is derived prospectively rather
   than tuned to the failed L2 scale.
2. V1 and the failed C10 evidence retain the SHA-256 identities in
   `V1_PRESERVATION.json`.
3. The scientific uptake law, parameters, arms, area, diffusivity, donor
   ownership/arbitration, O02 semantics, operator order, duration, observations,
   and 2%/5% gates are unchanged.
4. Run-wide `eta_max`, minimum donor scale, zero-inventory/positive-request
   events, and cumulative rejected amount are computed over the whole
   trajectory and survive checkpoint/restart.
5. The primary-arm gates are exactly `eta_max <= 0.25`,
   `s_min >= 1-64*epsilon_double`, and the frozen roundoff rejection bound; only
   the deliberate shared-donor cap fixture is exempt from no-clipping.
6. The V2 runner verifies clean source, exact contract/evidence hashes,
   independent approval, deterministic reruns, MPI/decomposition, restart,
   coupled grid/time convergence, fixed-grid time convergence, and the frozen
   production-selection rule.
7. No C11 or later behavior is present.

Use `contracts/p12/INDEPENDENT_NUMERICAL_REVIEW_V2.template.json` as the schema
for the signed review evidence. The review artifact must identify the exact
candidate commit, set `reviewer_is_implementation_writer` to `false`, mark every
confirmation, and explicitly authorize outcome execution. The runner refuses
to start otherwise.

## Current boundary

The prereview subsequently authorized outcomes. Windows and pinned-Linux V2
qualifications passed and selected L0 with `dt = 1800 s`. Final independent
acceptance was fulfilled by `FINAL_INDEPENDENT_ACCEPTANCE.json`, SHA-256
`de1fb8ba26696a84ff0f0233e9fe269e091a384eb5034e86fc74250cbb72de58`.
C10 is PASS; C11 remains unstarted and unauthorized.
