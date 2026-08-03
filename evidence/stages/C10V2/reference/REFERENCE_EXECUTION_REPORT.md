# C10/P12 V2 reference execution

## Verdict

The pinned native-Linux reference qualification is **PASS**. The frozen V2
selector independently reproduced L0 (`8 x 8 x 4`) with `dt = 1800 s`, and the
reference result matches the Windows result exactly on every claim-bearing
comparison, selection field, and canonical state value checked.

C10 remains **BLOCKED** only because the exact implementation and accumulated
evidence still require final independent acceptance. C11 has not started.

## Host and provenance

- GCE instance: `bmx-c10v2-qual-20260802`
- Zone and shape: `us-west1-b`, `n2-standard-8`
- Required and observed CPU: `Intel Cascade Lake`
- OS: Ubuntu 24.04.4 LTS, kernel `6.17.0-1021-gcp`, ext4
- Toolchain: GCC/G++ 13.3.0, CMake 3.28.3, Open MPI 4.1.6, Ninja 1.11.1
- Implementation: `0f38760b4daba3acbfd4b658c9ac522523b5c69b`
- Native executable: `30d9e79289d1c9fe4324aaefe0d3bfb998f650578431fcc4b2e32a4f0dafbe4b`
- Qualification result: `b3d72145bfd9310d4d0f2ea171bbcb0e814debe36bbac56ac6e52103e7b89d43`
- Timing result: `2473d2f8675077d6e9ede062f128b1a8307035bd23f21f8bf03ce5f75ed0d2e5`

The VM was built from the exact detached implementation commit and pinned
AMReX commit. Provenance was resolved and the source worktree was clean before
the build and every claim-bearing outcome.

GCC emitted six nonblocking instances of one diagnostic: it cannot prove that
two `[[noreturn]]` rejection helpers cannot return through pinned AMReX's
`Abort` interface. The build completed, the helpers are fail-closed guards, and
their negative-path suites pass. No post-qualification source change was made.

The platform-agnostic runner retains generic `not yet reference-host` and
`external_resources: none` fields in its generated JSON. Those fields describe
runner-internal orchestration, not the host on which it was invoked. This
wrapper report and the captured environment provide the authoritative reference
host and GCE resource classification.

## Numerical result

All 10 unique case groups and 50 simulation summaries passed. Across the full
qualification matrix, maximum eta was `0.10654141714024555`, minimum donor scale
was exactly `1.0`, and cumulative rejection was exactly `0 mol`.

The largest grid-pair uptake difference was 0.02204% against the frozen 2%
limit. The largest grid-pair profile difference was 0.003314% against the 5%
limit. Fixed-grid temporal differences were smaller still.

The predicted saturation ratio is `1.039154791108985`; measured 48-hour ratios
were `1.0402603688571577`, `1.0403670905798583`, and `1.0405657805592736` at
L0, L1, and L2. The near-null contrast agrees with the saturation prediction;
no parameter or arm was tuned and no biological amplification claim is made.

## Timing

At selected L0, a complete 48-hour uptake-only run (96 updates, plot every
update, checkpoint at update 48, one MPI rank) had arm medians of:

- low D: `0.9068460409998806 s`;
- high D: `0.9089595030000055 s`;
- representative average of the two medians: `0.9079027719999431 s`.

For 151 configurations and nine simultaneous `n2-standard-8` instances, the
idealized projections are 1.27 minutes at n=5, 2.54 minutes at n=10, and 5.08
minutes at n=20. They exclude provisioning, queueing, transfer, retries, and
all P13/P14/P15 model cost, so they are not full-campaign runtime guarantees.

## Fail-closed packaging corrections

Two pre-outcome attempts stopped on the frozen V1 file's CRLF-versus-Git-LF
representation. The final handoff overlays the exact frozen bytes, validates
that Git's clean filter maps them to the unchanged blob, requires no staged
diff, and then requires a clean worktree. No scientific or numerical byte,
operator order, parameter, or gate changed.

After qualification and timing passed, the original driver invoked manifest
verification from the wrong directory. A packaging-only finalizer verified and
repacked the already completed evidence without rerunning outcomes; the reusable
script now verifies from the work root.

## Cleanup and stop boundary

The instance and its auto-delete boot disk were deleted after the downloaded
archives passed local hash verification. Subsequent instance and disk listings
were both empty. Exact billing has not settled or been queried, so no exact cost
claim is made. The single VM existed for about 84 minutes; the user authorized
the run with a USD 1–2 estimate.

No C11 or later-stage behavior was started.
