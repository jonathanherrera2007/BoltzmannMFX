# C10 / P12 V2 stage report

## Verdict

**C10/P12 V2 is `PASS`.** The qualification passed on Windows and the pinned
native-Linux reference host, and final independent acceptance passed all ten
requested confirmations. The frozen selector chose **L0 (`8 x 8 x 4`) with
`dt = 1800 s`** on both hosts, with exact agreement on all checked claim-bearing
values.

`D-C10-02-NUMERICAL-CONVERGENCE` is closed. C11 has not started and is not
authorized by this closure.

## Exact identities

- Implementation commit: `0f38760b4daba3acbfd4b658c9ac522523b5c69b`
- Implementation tree: `511e3d1ec6ec5148aa0548b6256c85b52a3b68a2`
- V2 numerical contract: `43d64a8f4ec6c8c00379fc3d9605441cb900479fcdd8db9e78e6fc1edd28f81f`
- Prerun review: `bda12aef209793b4537915e374e09caf100397c0fdf8678ed00118ff987a3ea2`
- Final independent acceptance: `de1fb8ba26696a84ff0f0233e9fe269e091a384eb5034e86fc74250cbb72de58`
- Evidence commit reviewed: `3c4a0806c9d345b3ce8809076447c22784d5cbff`
- Exact Windows outcome: `e25ff8256a1ab151cea3b007228b261bd1c4d8b83fa34234d71371d62b2d0ab0`
- Linux reference outcome: `b3d72145bfd9310d4d0f2ea171bbcb0e814debe36bbac56ac6e52103e7b89d43`
- Linux timing evidence: `2473d2f8675077d6e9ede062f128b1a8307035bd23f21f8bf03ce5f75ed0d2e5`
- Linux executable: `30d9e79289d1c9fe4324aaefe0d3bfb998f650578431fcc4b2e32a4f0dafbe4b`
- Runner: `882fb997a71ccc91d6f660af33855b3631ba4e4fd39b6f6665464c7853622d5d`
- Full-volume extractor source: `5733e5d5b0b3ef65ad8a2282111c735c476ec6872331546e5e443fa250e63d1b`
- Frozen kernel: `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`
- Frozen global order: `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`

The prerun review is attributed to the independent reviewer (Opus 5) but is not
cryptographically signed. It is recorded as attributed-but-unsigned, matching
the P10 review precedent.

## Qualification outcome

All 10 unique case groups and 50 simulation summaries passed on each host. The
Linux result exactly reproduced the Windows coupled comparisons, temporal
comparisons, saturation prediction, production selection, and every checked
canonical cumulative/state value.

Across every qualified trajectory:

- maximum run-wide eta: `0.10654141714024555 <= 0.25`;
- minimum donor scale: exactly `1.0 >= 0.9999999999999858`;
- maximum cumulative rejected amount: exactly `0 mol`.

The largest coupled uptake difference was `2.2035613306748612e-4` (0.02204%),
versus the frozen 2% limit. The largest coupled profile difference was
`3.31410499321656e-5` (0.003314%), versus the frozen 5% limit.

At selected L0, temporal confirmation used `dt`, `dt/2`, and `dt/4`. The largest
temporal uptake difference was `6.535350337340911e-6` (0.0006535%); the largest
temporal profile difference was `6.4680593257785305e-6` (0.0006468%).

No scientific uptake parameter, environmental arm, diffusion coefficient,
operator order, donor rule, arbitration rule, or acceptance threshold changed
from the independently prereviewed V2 contract.

## Low/high contrast against saturation

The concentration ratio is `2.8074534161490687`, but transporter saturation
predicts an initial flux ratio of only `1.039154791108985`.

| Level | Measured 48 h high/low | Relative excess over prediction |
|---|---:|---:|
| L0 | `1.0402603688571577` | 0.1064% |
| L1 | `1.0403670905798583` | 0.1167% |
| L2 | `1.0405657805592736` | 0.1358% |

The measured contrast is near-null as saturation predicts. It is recorded as a
result; no arm, parameter, resolution, or gate was tuned to manufacture
separation, and no biological amplification claim is made.

## Reference host and timing

The authorized host was one GCE `n2-standard-8` in `us-west1-b`, with both the
required and observed CPU platform equal to `Intel Cascade Lake`. It ran native
Ubuntu 24.04.4 with GCC/G++ 13.3.0 and Open MPI 4.1.6.

At selected L0, a complete 48-hour uptake-only run with 96 updates, a plot on
every update, and a midpoint checkpoint had five-repeat arm medians of
`0.9068460409998806 s` (low) and `0.9089595030000055 s` (high). The representative
average of those medians is `0.9079027719999431 s`.

For 151 configurations and nine simultaneous instances, idealized wave
projections are:

| Replicates | Runs | Waves | Projected elapsed |
|---:|---:|---:|---:|
| n=5 | 755 | 84 | 1.27 min |
| n=10 | 1510 | 168 | 2.54 min |
| n=20 | 3020 | 336 | 5.08 min |

These projections exclude provisioning, queueing, transfer, retry, and later
P13/P14/P15 model cost. They describe only the frozen 48-hour uptake-only C10
fixture. They are **not P15 estimates**: P15 is a 216-hour all-mechanism study
with growth, reactions, topology and export, and its runtime may differ by
orders of magnitude.

## Packaging findings

The first reference attempt stopped before outcomes because the frozen V1 hash
names the original Windows CRLF result while Git stores the review copy as LF.
A second pre-outcome attempt correctly stopped on the dirty worktree produced
by an unreconciled exact-byte overlay. The final handoff overlays the frozen
CRLF bytes, passes them through Git's clean filter, requires no staged diff, and
requires a clean worktree. This is a representation repair only.

After the qualification and timing had passed, the original driver verified a
relative-path manifest from the wrong working directory. A packaging-only
finalizer verified the existing output, asserted its identities, and repacked
the compact evidence without rerunning any outcome. The reusable driver now
verifies from the work root.

## Cloud cleanup and spend boundary

The VM and its auto-delete boot disk were deleted immediately after retrieved
archives passed local SHA-256 verification. Subsequent instance and disk lists
were empty. The resource existed for approximately 84 minutes. Exact billing
has not settled or been queried, so no exact USD claim is made. The user
authorized the run with a USD 1–2 estimate.

## Independent acceptance and closure

The byte-identical final artifact
`FINAL_INDEPENDENT_ACCEPTANCE.json` passed with acceptance ID
`IA-20260802-C10-V2-FINAL`. The independent reviewer confirmed the exact source,
frozen gates, L0 selection rule, 240 canonical cross-platform comparisons,
claim boundaries, packaging corrections and cloud cleanup. This closes
`D-C10-02` from an engineering standpoint.

Two new findings are nonblocking:

- **F-16 (LOW):** the requested 151-configuration arithmetic must never be
 treated as a P15 estimate. The stronger disclaimer above is now binding.
- **F-17 (INFO):** exact cloud billing is unsettled. Query and record it before
 any P15 budget decision; it is not required for C10 closure.

The near-null contrast is also a prospective P15 design warning, not an adopted
change: before P15 costing or science, either adopt arms that straddle `K_m` or
explicitly predeclare the current environmental-D factor as expected-null and
demote it to a control. Do not choose after observing P15 outcomes.

## Claim and next-stage boundary

This PASS establishes C10/P12 numerical and software correctness only. Every
scientific parameter remains
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`. It is not mentor approval,
calibration, predictive validation, RG-SCI progress, or authorization for C11
or any later stage. No later stage has started.
