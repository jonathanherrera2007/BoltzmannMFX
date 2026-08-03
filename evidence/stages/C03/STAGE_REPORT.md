# C03 — lean P06-equivalent baseline evidence

- **Stage ID:** `C03`
- **Status:** `PASS`
- **Date:** 2026-07-30
- **Role:** primary writer (Claude), product lane
- **Baseline worktree:** `389e9e3` / tree `1c73deed`, AMReX `cbdc658`
- **Output commit:** see `COMMIT.txt`
- **Companion evidence:** `STAGE_REPORT.json`, `runs/c03-baseline/RUN_INDEX.json`, `BASELINE_MANIFEST.json`, `BASELINE_ANALYSIS.json`

> This is a **lean, product-oriented** baseline. It deliberately does not
> reproduce the Control Tower P06 package structure (authorisation receipts,
> nonces, protected-path proofs, Pro-review records). **No claim of official P06
> acceptance is made.** The P06 spec in the planning package is itself marked
> `PRELIMINARY_TEMPLATE_DEPENDENCY_BLOCKED`.

---

## 1. Outcome

An untouched-canonical baseline evidence package exists: 8 executed cases, 65
hashed artefacts, a machine-readable run index, a manifest, and a derived
analysis regenerable from raw output alone.

## 2. Platform interruption during this stage — resolved

Mid-stage, the configure step failed with
`no Visual Studio installation with the MSVC x64 toolset was found`. The
Build Tools installation had been **renamed from `C:\Program` to `C:\Program1`**.

`vswhere` handled this badly and misled the initial diagnosis: it continued to
report the **old** path while flipping the instance to `isComplete: false`, so
`-latest` returned nothing and `-all` returned a directory that no longer
existed. I first recorded this as a possible loss of the toolchain; the user
corrected it, and the toolchain was found intact at `C:\Program1` with the same
toolset `14.44.35207`.

**Fix applied — discovery hardened rather than re-pointed at a new hard-coded
path.** `tools/repro/native_windows_env.ps1` now resolves the toolchain by:

1. `$env:BMX_VS_ROOT` explicit override,
2. `vswhere` (`-latest`, then `-all`),
3. directory scan of `C:\` and both Program Files roots,

with **every** candidate validated by the presence of `VC\Auxiliary\Build\vcvars64.bat`
before acceptance. A path from `vswhere` is never trusted without checking disk.
The script now prints which root it used and how it was found. It resolved
`C:\Program1` via the scan fallback.

**Reproducibility consequence, recorded so no later stage discovers it as an
unexplained mismatch:** the installation root is embedded in the AMReX build-info
banner and in every absolute path in `compile_commands.json`. C02's recorded
image hash `e3c8ee08…88a9bc` is bound to the old `C:\Program` root and **will not
reproduce**. The C02 image itself is untouched, still present, still executes,
and still hashes to its recorded value — C02's `PASS` stands as accurate history.
But a rebuild of identical source with identical flags now yields a different
hash. The baseline image built this stage is `e2effe2c…918a9b9a`, the same
2,369,536 bytes, differing only in embedded paths.

## 3. Frozen baseline identity

| Field | Value |
|---|---|
| BMX commit / tree | `389e9e35…12b61` / `1c73deed…4d977` |
| AMReX commit | `cbdc6580…81f483` |
| `src/chemistry/bmx_chem_K.H` | `711ae2ca…14678`, 2,908 lines |
| Baseline `bmx.exe` | `e2effe2c375890d70cc28c40ab038ef00cc3e86cf384e25f1683f164918a9b9a`, 2,369,536 B, 200 objects, 191 s |
| Toolchain | MSVC 19.44.35228.0 (toolset 14.44.35207) at `C:\Program1`, Ninja 1.12.1, CMake 4.4.0, MS-MPI |
| Phosphorus state | **feature-off reference**: `chem_species.p_growth_limit = 0`; mesh species `A B C D F P` (legacy 6-component order) |

### No drift from the historical P07 evidence kernel

`bmx_chem_K.H` hashes to `711ae2caa6e7aabb5c084fe841d2d90edb85ee53e7abc7a859d7de00e6614678`,
which is **byte-identical to `E-C6-KERNEL`** in
`P07_ISOLATED_CARBON_REPAIR_PREP_SANITIZED.md`. That document names *"drift
between the historical Q05 kernel and the adopted successor source"* as an
explicit stop condition. **There is no drift** — the five-defect map was derived
against exactly the bytes bound here.

Two locators were spot-checked and land precisely on the described code:

| ID | Locator | Actual content |
|---|---|---|
| `CDEF-01` | `:2173-2179` | `if (fA_tmp < 0.0) { cA -= dA2/new_cell_vol; … }` — second-half **A** donor-exhaustion cap |
| `CDEF-02` | `:2205-2211` | `if (fC_tmp < 0.0) { cC -= dC2/new_cell_vol; … }` — **C** analogue |

Locator accuracy only. **Not** an acceptance of the mappings and **not** a claim
that the code is or is not defective — that is C04 under a fresh exact-scope review.

## 4. Run matrix — 8/8 executed, 0 failures

| ID | Purpose | Ranks | Exit | Elapsed |
|---|---|---|---|---|
| `B01_init_only` | initialisation only | 1 | 0 | 0.18 s |
| `B02_steps20` | 20 steps, canonical seed | 1 | 0 | 1.44 s |
| `B03_steps20_rerun` | exact rerun of B02 | 1 | 0 | 1.30 s |
| `B04_steps20_seed2` | alternate seed | 1 | 0 | 1.30 s |
| `B05_ckpt_write` | 10 steps, write `chk00010` | 1 | 0 | 0.74 s |
| `B06_ckpt_restart` | restart from `chk00010` → step 20 | 1 | 0 | 0.79 s |
| `B07_steps20_2rank` | 20 steps, 2 MPI ranks | 2 | 0 | 1.03 s |
| `B08_steps200_growth` | 200 steps | 1 | 0 | 12.31 s |

Checkpoint **write and read both work** on this platform: B05 produced a
29-member `chk00010`, and B06 restarted from it and continued to step 20.

## 5. Derived analysis

`tools/repro/analyze_baseline.py` reads raw stdout only and is **deterministic** —
verified by running it twice and comparing output bytes (identical).

| Comparison | Result |
|---|---|
| Determinism `B02` vs `B03` | **identical**, 0 differing lines |
| Seed `B02` vs `B04` | identical, 0 differing lines |
| Ranks `B02` vs `B07`, raw | differ, 24 lines |
| Ranks `B02` vs `B07`, decomposition metadata removed | differ, 7 lines |
| Negative species minima | **0** records |
| Non-finite values | **0** records |

### A false positive in my own analyzer, caught and fixed

My first analyzer compared a *parsed observable stream* and reported all three
comparisons "identical". That was wrong. BMX prints species max/min at roughly
one significant figure (`2e-05 0`), which is far too coarse to detect
differences — and the 1-rank vs 2-rank pair, which the parsed stream called
identical, has **24 differing raw lines**. The analyzer now uses the
**normalized raw log** as the authoritative comparator; the parsed stream is
retained only as a coarse view and is explicitly labelled as such. The
determinism and seed results above were re-derived with the corrected
comparator.

### What the 7 residual cross-rank differences actually are

Not noise, and worth recording precisely:

```
1 rank : Generating new growth tip. Parent id: 1 cpu: 0 child id: 2 cpu: 0
2 ranks: Generating new growth tip. Parent id: 1 cpu: 0 child id: 1 cpu: 1
```

The **physics event is identical** — same trigger length `0.00350903`, same
parent. What differs is the new segment's `(id, cpu)` pair, which is
decomposition-dependent, plus ordering, because rank stdout interleaves (under
2 ranks these lines appear after `AMReX finalized`).

Two consequences carried forward:

- **A raw-log comparator can never be a valid cross-rank comparator here.**
  Particle ids are rank-local and stdout interleaves. C16 must compare canonical
  identities and metrics, not logs.
- **P10 (C08)** must preserve ledgers and accounting across MPI redistribution
  even though `(id, cpu)` is not stable across decompositions.

This is an observation, **not** a defect finding — rank-local ids and interleaved
stdout are expected behaviour.

## 6. Historical defects recorded as observations

Per the stage requirement, baseline behaviour is recorded **as observed**, never
as a repaired expectation:

- **0 negative species minima** and **0 non-finite values** across all 8 cases.
  The P07 preparation maps two donor-exhaustion defects (`CDEF-01` A,
  `CDEF-02` C) whose stated failure mode is a sign reversal on a capped
  transfer. **This baseline configuration did not exhibit a negative minimum.**
  That is recorded as a fact about this configuration and this run length. It is
  **not** evidence that the defects are absent, and **not** a prediction about
  what P07 will change — the donor-exhaustion branches may simply never be
  reached here. Designing fixtures that actually reach them is C04's work
  (`AT_P07_DONOR_CAP_A`, `AT_P07_DONOR_CAP_C`).
- Particle count grows 1 → 2 within 20 steps and stays at 2 through 200 steps in
  `B08`. Growth and tip generation occur; splitting beyond one event does not.

## 7. Artefacts

| Artefact | Value |
|---|---|
| `runs/c03-baseline/RUN_INDEX.json` | 8 cases, per-case argv, exit code, elapsed, per-file hashes |
| `runs/c03-baseline/BASELINE_MANIFEST.json` | 65 members, 3,908,409 bytes total; manifest sha256 `85020bf14a204d87e57377b378af431492c5a0ac38d0643cabd8c8803a1ab18e` |
| `runs/c03-baseline/BASELINE_ANALYSIS.json` | derived summary, regenerable from raw output |

Raw outputs live outside the Git worktree under `runs/`; scripts and evidence
are committed.

## 8. Mandatory validation

| Check | Result |
|---|---|
| All baseline members manifest and hash correctly | **PASS** (65/65) |
| Commands replay from the baseline worktree | **PASS** (full matrix re-runnable from `RUN_INDEX.json` argv) |
| No product or P07 changes present | **PASS** — baseline `git status` clean, HEAD `389e9e3`, tree `1c73deed` |
| Baseline outputs sufficient for the P08 comparator | **PASS** — per-case raw logs, normalized hashes, and a deterministic analyzer C05 can reuse directly |

The D-C02-06 source-tree pollution did **not** occur in the baseline worktree.
Mechanism: `CMakeLists.txt:159` copies `compile_commands.json` only `if EXISTS`
at configure time, and on a genuinely fresh build directory the file is not
generated until afterwards — so the first configure of a clean directory leaves
the source tree untouched, and only a repeat configure pollutes it.

## 9. Files changed

| Path | Reason |
|---|---|
| `tools/repro/native_windows_env.ps1` | hardened toolchain discovery (override → vswhere → scan, all validated) |
| `tools/repro/run_baseline_matrix.ps1` | baseline run matrix, run index, per-artefact hashing |
| `tools/repro/analyze_baseline.py` | deterministic derived analysis from raw output |
| `evidence/stages/C03/STAGE_REPORT.md` / `.json` | this report |
| `evidence/stages/C03/COMMIT.txt` | stage commit hash |

**Zero files under `src/` changed.**

## 10. Blockers

| ID | Blocker | Owner | Status |
|---|---|---|---|
| B-C03-01 | Reference platform lost | — | **CLOSED** — renamed, not lost; discovery hardened |
| B-C03-02 | C02 image hash `e3c8ee08…` is not reproducible after the install-path rename | writer | **OPEN**, non-blocking — C02's build should be repeated under `C:\Program1` when a fresh C02 hash is needed |
| B-S00-03 | Biology decisions unresolved; mentor packet not sent | user / mentor | **OPEN** — blocks C06B and final runs C10–C15 |
| B-C02-01 | Six defects worked around in build config, not fixed at source | writer + review | **OPEN** — D-C02-05 before any final run |

## 11. Claims

Enabled: an untouched canonical baseline was built and executed on the declared
platform, and its raw outputs are hashed, indexed, and deterministically
summarisable.

Still prohibited and **not** claimed: official P06 acceptance; that any defect
is present or absent; conservation or restart correctness (restart *ran*; no
correctness comparator exists until C06B); rank invariance; platform
qualification; any scientific result; empirical calibration; formal P05–P18
acceptance; `RG-SW:GO`; `RG-SCI:GO`.

Status remains **`RESEARCH-USE-CANDIDATE — RG-SW INCOMPLETE`**, **`RG-SCI:NO-GO`**.

## 12. Next valid prompt

`prompts/claude/C04_P07_CARBON_REPAIR_IMPLEMENT_AND_VALIDATE.md`

C04 starts from a strong position: the P07 candidate patch targets bytes that
are confirmed drift-free against the historical evidence kernel. Its harder task
is building fixtures that actually reach the donor-exhaustion branches, which
this baseline shows are not exercised by the default `fungi` case.
