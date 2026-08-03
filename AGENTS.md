# BMX phosphorus RG-SW agent rules


## Fixed project identity

- Planning package: `/mnt/data/BMX_RESEARCH_GRADE_GPT_PRO_PLANNING_PACKAGE_20260730.zip`
- Expected planning-package SHA-256: `014607d34400638a5a915674e500b1b8afbacfebf0159801f8b7e5f32cac74a1`
- Canonical BMX commit: `389e9e35a1c7291a4af795b2e39f2db1f0012b61`
- Canonical BMX Git tree: `1c73deedf0eb2feea833a7fddbc431ae9754d977`
- Pinned AMReX commit: `cbdc6580ee3d78cccdd37172e4ba077ee181f483`
- Pinned AMReX Git tree: `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6`
- Immediate release target: `RG-SW`, a research-grade software implementation of the approved, bounded, exploratory, uncalibrated v1 model.
- Separate scientific target: `RG-SCI`; it is not satisfied without independent quantitative data, calibration, and held-out validation.
- Formal P05-P18 acceptance is not part of the product lane and must not be claimed.

### Local binding (recorded by C01, does not supersede the identities above)

- Product root: `C:\Users\Shadow\Documents\Codex\BMX-RG-SW\`
- Planning package located at `C:\Users\Shadow\Documents\Codex\2026-07-28\how\outputs\BMX_RESEARCH_GRADE_GPT_PRO_PLANNING_PACKAGE_20260730.zip` (hash verified) and extracted to `planning-package/`. The `/mnt/data/...` path above is the package's origin path and is not present on this host.


## Authoritative reading order

Before source changes, read completely:

1. `00_START_HERE/README_FIRST.md`
2. `00_START_HERE/GPT_PRO_PLANNING_PROMPT.md`
3. `01_CURRENT_STATE/PRODUCT_STATE_SUMMARY.md`
4. `01_CURRENT_STATE/RESEARCH_GRADE_DEFINITION_OF_DONE.md`
5. `01_CURRENT_STATE/TARGET_AND_CLAIM_BOUNDARY.md`
6. `02_REQUIREMENTS/CONFIRMED_SCIENCE_DECISIONS_REDACTED.json`
7. `02_REQUIREMENTS/DECISION_RECONCILIATION_REQUIRED.md`
8. The requirement file for the stage being implemented.
9. The actual current source bytes and all prior stage reports.

The transferred source snapshot is a planning reference, not a substitute for an exact clean Git checkout.

## Non-negotiable boundaries

- Do not invent biological parameters, experiment designs, strategy definitions, or claim thresholds.
- Unresolved scientific behavior remains default-off and is recorded as a release blocker.
- Active F biology is prohibited. F storage/transport infrastructure may exist, but every F reaction, exchange, and transport coefficient must remain exactly zero for v1.
- E is internal-only. It has no mesh representation, diffusion, membrane exchange, bonded transport, or export.
- D is the sole active mobile and exportable phosphorus currency.
- Use elemental-P-equivalent amounts and concentrations in native BMX units. Conservation operates on moles.
- Bootstrap A and exchange-derived A must have separate provenance ledgers.
- Rejected or clipped growth consumes neither B nor E.
- Do not claim calibrated biology, predictive validity, full-plate validity, production qualification, publication readiness, or formal P05-P18 acceptance.
- Do not modify the P05 workspace or share branches, builds, outputs, hashes, or writers with it.
- Do not push, open a pull request, contact anyone, delete remote data, or run paid/cloud actions without explicit user authorization.
- Do not use destructive Git commands to hide changes. Preserve evidence.

## Canonical technical architecture unless a frozen contract supersedes it

- Enabled mesh order: `A, B, C, D, F, P_D, P_F`.
- Enabled particle order: `A, B, C, D, F, P_D, P_E, P_F`.
- Disabled compatibility mesh order: `A, B, C, D, F, P`.
- Particle storage reserves eight chemistry slots in both modes; slots 6 and 7 remain zero in disabled mode.
- Reject simultaneous `P` and `P_D`, mesh `P_E`, missing enabled `P_F`, reordered legacy components, and any nonzero F-active coefficient.
- Mesh and particle component counts are distinct and connected through explicit reviewed maps.
- Structural P and cumulative ledgers are extensive amounts.
- Legacy checkpoints are rejected before particle deserialization unless an approved migration contract is later supplied.
- Use checkpoint schema v2 or later with component names/counts, layout hash, operator-order ID, units contract, decision-contract hash, and global ledgers.
- Use one versioned global operator order frozen before final runs. Do not change it after outcome inspection.

## Numerical defaults to freeze before final outcomes

These are technical starting contracts, subject to independent numerical review before final runs:

- Local algebraic conservation: `abs(residual) <= 64 * eps_double * S_L1`.
- Integrated conservation: `abs(residual) <= max(1e-28 mol, 1e-10 * S_L1)`.
- Restart field comparison: exact identifiers and schema; floating fields `<= 1e-12` relative unless a stricter exact comparator applies.
- Any NaN or infinity is a hard failure.
- Negative amount above the conservation tolerance is a hard failure.
- Roundoff-scale clamps must be centralized, counted, and reported; unexplained clamps block release.
- Final timestep/grid/rank/thread/decomposition criteria must be predeclared in the frozen numerical contract and may not be widened after final outcomes are seen.

## One-writer and checkpoint discipline

- One agent writes the product branch at a time.
- Independent reviewers use separate read-only worktrees or detached commits.
- Before every stage: record `git status`, HEAD, submodule state, build identity, and prior stage result.
- After every stage: run required tests, record exact commands and outputs, commit only stage-scoped changes, and write `evidence/stages/<stage-id>/STAGE_REPORT.md` plus machine-readable JSON.
- Do not proceed from a failed or blocked stage.

## Required stage-report content

- Stage ID and status: `PASS`, `FAIL`, or `BLOCKED`.
- Input commit/tree, dependency identities, environment, and configuration hashes.
- Files changed and why.
- Exact commands and exit codes.
- Tests run, results, tolerances, and raw evidence paths.
- Conservation/restart/claim effects.
- Unresolved blockers and their owners.
- Commit hash produced by the stage.
- Explicit statement of claims that remain prohibited.

## Completion rule

Do not stop after planning. For an execution prompt, continue through implementation, build, tests, evidence capture, and stage report unless blocked by missing external information or an actual environment failure. Never mask a blocker by choosing an unstated scientific value.
