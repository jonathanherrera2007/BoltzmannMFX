# Primary-writer handoff — Claude → Codex

- **Date:** 2026-08-01
- **Branch:** `rgsw/product`
- **HEAD at handoff:** `64e5e04db1ab3bb62f5bf733db1e24aa1f2ea970`
- **Type:** **writer** handoff, not a review handoff.

---

## 0. Read this first — the one-writer rule

`AGENTS.md` says one agent writes the product branch at a time. From this
document forward **Codex is the primary writer** and Claude writes nothing to
`rgsw/product`. Do not run both.

This is a role Codex has *not* held so far. The prompt pack's default assignment
is Claude-as-writer and Codex-as-independent-reviewer (`prompts/codex/X01`–`X09`).
If Codex later performs an independent review of its own writing, that review is
**not independent** and must not be recorded as such. Say so in the report rather
than letting the pack's labels imply otherwise.

Codex reads `AGENTS.md` at the repo root. That file is authoritative for
boundaries; this document only adds state and hard-won context.

## 1. Where the project actually is

| Stage | Status | Notes |
|---|---|---|
| C01 package/source/worktree audit | `PASS` | |
| C02 build spike | `PASS` | six Windows defects worked around, `B-C02-01` |
| C03 lean P06 baseline | `PASS` | |
| C04 P07 carbon repair | **`PASS`, reference-qualified** | all five defect mappings demonstrated at runtime; `release_evidence: true` on GCE |
| C05 P08 comparison | **`PASS`** | 8/8 dimensions, no contradiction, nothing undecided |
| C06A decision reconciliation | `PASS` | mentor packet produced, **unsent** |
| C06B freeze after mentor response | **BLOCKED** | needs the mentor answer (`B-S00-03`) |
| **C07 / P09 three-state infrastructure** | **NEXT** | sanctioned by C06A as *implementable now* |

**Authoritative blocker list is C05's**, the most recent report:

| ID | Owner | Detail |
|---|---|---|
| `B-S00-03` | user / mentor | biology decisions unresolved; mentor packet unsent. Gates P12/P15/P16 experiment contracts and C06B. |
| `B-C02-01` | writer + review | six defects worked around in the Windows build config; expected to be Windows-portability rather than product defects |
| `B-C03-02` | writer | C02 image hash not reproducible after an install-path rename |
| `D-C04-07` | integrator (P10) | volume closure drifts during evolution; reported, not enforced |

**Closed:** `B-S00-01` (at C02), `B-C04-01`, `B-C04-02`, `B-PLATFORM-01` (all at C04).

⚠️ **C06A's blocker list is stale.** It still lists `B-C04-01` and
`B-PLATFORM-01` as open because it was written before C04 closed them. Do not
act on it.

## 2. Frozen identity — verify before touching anything

| Item | Value |
|---|---|
| Canonical baseline commit | `389e9e35a1c7291a4af795b2e39f2db1f0012b61` |
| Canonical baseline tree | `1c73deedf0eb2feea833a7fddbc431ae9754d977` |
| **Chemistry candidate commit** | `adb427331e180cd0b4faa74a4ab2098381b2eabb` |
| **Reviewed kernel** `src/chemistry/bmx_chem_K.H` | `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02` |
| Baseline kernel | `711ae2caa6e7aabb5c084fe841d2d90edb85ee53e7abc7a859d7de00e6614678` |
| `D-C04-05` diagnostic repair | `5481856f46ba4bd2432dd21800fe9dbec8d10a15` |
| `D-C04-08` provenance repair | `8428a5d354025f2a222deae287679bf2e89a4a9b` |
| AMReX commit / tree | `cbdc6580ee3d78cccdd37172e4ba077ee181f483` / `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6` |

The whole `src/chemistry` **tree object** is `423d11cb32c9773bb89c028900b4fcd48d6e4d02`
at both the candidate commit and HEAD — no chemistry byte changed after the
candidate. Re-verify with:

```bash
git rev-parse adb427331e180cd0b4faa74a4ab2098381b2eabb:src/chemistry HEAD:src/chemistry
```

## 3. The next stage: C07 / P09

**Authority to implement exists**, but read the chain carefully because two
documents appear to conflict and do not:

- `prompts/claude/C07_P09_THREE_STATE_INFRASTRUCTURE.md` is an **execution**
  prompt.
- C06A lists **P09 as `stages_implementable_now`**.
- `P09_P_THREE_STATE_INFRASTRUCTURE_PREP_SANITIZED.md` ends with *"Stop pending
  separate source-write/build/test authorization"* — that is the **preparation**
  document deferring to exactly the authorization the C07 prompt supplies. It is
  not a live blocker.

**But its other stop conditions still bind and are not superseded.** Stop if
completion would require *"assigning semantics, units, values, defaults,
tolerances, or expected results"*. P09 is storage and I/O plumbing only. No
biological value, no reaction, uptake, export, reward, limitation, or geometry
behaviour. Anything unresolved stays **default-off** and becomes a recorded
release blocker.

A draft plan exists at `evidence/stages/C07/IMPLEMENTATION_PLAN.md` (committed
with this handoff). Its §0 dependency discussion is **now stale** — it was
written when C04 was blocked and no Linux reference host existed. Both are
resolved. The rest of the plan (layout, files, tests) is still current, but it
is a *draft*: re-derive it against the actual source before trusting it.

### `D-C07-01` — a live trap in this stage

`input_fungi` declares `fluid.chem_species = A B C D F P`, making slot 4 **F**.
The kernel names slot 4 **E** (`fE = mesh_vals[4]`, `cE = p_vals[4]`) and uses it
actively — reaction 5 at `bmx_chem_K.H:1856-1860` and bacterial growth at
`:1988-1989`. Configuration and kernel disagree about what slot 4 *is*.

It is dormant today only because the fungi case zeroes slot 4's diffusion
coefficient and initial concentration. **P09 introduces `P_E`, at which point two
different E-like quantities coexist and one is mislabelled in plot and checkpoint
output.** Implement `AGENTS.md`'s frozen order exactly (slot 4 = `F`), change no
legacy behaviour, and carry `D-C07-01` forward as an open naming defect requiring
resolution before release.

## 4. Ownership boundaries currently in force

| Area | Owner |
|---|---|
| `src/chemistry/bmx_chem_K.H` | **frozen** — the reviewed candidate. Do not touch without explicit authorization. |
| `src/chemistry/bmx_chem.H`, `.cpp`, `bmx_fluid_parms.cpp`, `bmx_init_fluid.cpp`, `bmx_pc_init.cpp`, `bmx_plt.cpp` | C07 writer |
| `bmx_calc_txfr.cpp`, `bmx_pc.H`, `bmx_evolve.cpp`, central CMake | **integrator (C13)** — not C07 |
| `src/bmx.cpp`, `src/bmx.H`, `src/setup/bmx_init.cpp`, `tools/CMake/BMX_Provenance.cmake` | integrator (instrumentation, already repaired) |

## 5. Tooling that exists and works

All cross-platform Python unless noted. Every one has been run on both Windows
and the Linux reference host.

| Tool | Purpose |
|---|---|
| `tools/repro/run_c04_qualification.py` | full qualification sequence; emits `release_evidence` and **cannot be overridden** |
| `tools/repro/run_p07_geometry_fixtures.py` | 7-fixture geometry matrix + `G0` neutrality (`.ps1` is the Windows twin; both verified to agree) |
| `tools/repro/analyze_p07_geometry.py` | branch predicted-vs-observed classifier from particle dumps |
| `tools/repro/run_p07_donor_cap_fixture.py` | donor-cap `k1` sweep, saturation, exact-equality assertion |
| `tools/repro/check_sums_diagnostic.py` | conservation-diagnostic guard, 5 checks |
| `tools/repro/check_build_provenance.py` | provenance regression fixture, 7 checks incl. fail-closed |
| `tools/repro/p08_comparator.py` + `run_p08_selftest.py` + `p08_extract_observations.py` | P08 comparison, 23-case synthetic suite |
| `tools/repro/make_handoff.py` | cuts a verified, self-contained reference-host handoff |
| `handoff/qualify.sh` | one-command reference-host entrypoint |

### Reference-platform qualification (how to repeat it)

`DEC-PLATFORM-001` makes **Linux** the reference platform. WSL1 on this machine
is `smoke-only` and **cannot** carry release evidence; WSL2 is impossible here
(the host is a Blade/Shadow cloud VM with no nested virtualization — proven by
`Hypervisor launch failed; Either SVM not present or not enabled in BIOS`).

The route that worked, and its cost:

```bash
python tools/repro/make_handoff.py --out <dir>
# provision GCE n2-standard-8, us-west1-b, --min-cpu-platform "Intel Cascade Lake"
# scp the archive, then:
bash qualify.sh ~/bmx-c04-qual
# DELETE the instance afterwards
```

`gcloud` is authenticated **inside WSL** as `redacted@example.invalid`,
project `project-a4ddb38c-cbe3-43a7-8d0`, billing enabled. Owner has authorized
≤ USD 100/account (§105) and confirmed the accounts are legitimate paid accounts
(§104). **A single-node qualification costs about USD 1–2, not 100.** §91 requires
pinning `--min-cpu-platform` and recording machine type, CPU platform, compiler
and MPI. §98–99: the instance is a read-only consumer of a frozen commit and must
never write the product branch.

## 6. Traps that cost real time — read before writing code

These are not hypothetical. Each was a defect that shipped into a run and had to
be caught.

1. **A structural log statistic cannot attribute a difference to a branch.** The
   first C04 matrix compared "lines differing" and "max relative difference", and
   produced three false conclusions. Use observables the model already emits at
   full precision: `amr.par_ascii_int` (particle fields, trajectory-neutral) and
   `bmx.print_sums` (fluid side). Predict the branch from the source's own
   predicates *and* observe what changed, then require agreement.

2. **The `realIdx` enum comments are 1-based position markers, not indices.**
   Reading them as indices silently shifts fields — it put `dadt`/`dvdt` one slot
   off and read `tau_split` as `dvdt`. Verify any hand-derived column map against
   physics before trusting it.

3. **A fixture can be a no-op against its own reference.** Stock
   `max_seg_radius` equals the initial radius, so `radius < radius_max` is already
   false at t=0 — the "forcing" override selected the same branch as the control.

4. **`fungi_init_cfg.dat` stores `area` rounded to 4 significant figures.** The
   true `2πr(r+L)` differs at 1.7e-5, so a repair that recomputes the area is not
   inert even with growth off. There is a self-consistent init file at
   `tools/repro/fixtures/fungi_init_cfg_selfconsistent.dat`.

5. **A detector can be structurally blind.** The donor-cap sign-flip test could
   only ever see a *baseline*-side activation, so a repaired-side-only firing was
   invisible. It produced a confident "NOT REACHED" that was wrong.

6. **Writing files from Python on Windows silently produces CRLF.** That broke
   `configure_linux.sh` on the reference platform with `$'\r': command not found`.
   `.gitattributes` now pins LF for executed/parsed text; use `newline='\n'`.

7. **Synthetic tests verify logic, not the shape of real data.** Twice a harness
   passed its suite and failed on production structure — most recently the P08
   comparator grouped by `(tree, observable)` without `fixture`, collapsing a
   sweep into one group and reporting phantom platform variance. Make synthetic
   fixtures structurally as rich as production.

8. **`--describe` provenance of the source tree ≠ provenance of each image.** A
   reference run reported `release_evidence: true` while two images carried a
   commit that did not describe their own bytes (dirty tree). Interrogate every
   built binary, and require `RESOLVED` + 40-char commit + **clean** worktree.

## 7. Discipline that must not slip

- **Do not push, merge, open a PR, or contact anyone** without explicit
  authorization. Nothing has been pushed; there is no upstream.
- **Predeclare before measuring.** C05's contract was committed *before* the
  comparator so the ordering is verifiable from history. Where predeclaration
  cannot be blind — because data already exists — **say so** and explain what
  protects it instead. `contracts/p08/COMPARISON_CONTRACT.md` §0 is the pattern.
- **`INCONCLUSIVE` is not a soft pass.** Neither is "the tests are green".
- **Never widen a tolerance after seeing an outcome.**
- **A stage does not reach `PASS` with an unresolved blocker in its own
  mandatory scope.**

## 8. Claims that remain prohibited

Regardless of stage outcome:

- any phosphorus behaviour is correct — **`dP1`/`dP2` still use the stale
  `new_cell_area`; phosphorus retains exactly the CDEF-03 staleness that carbon
  had repaired**
- any conservation property of the model as a whole (`D-C04-07` open)
- calibrated biology, predictive validity, full-plate validity, production
  qualification, publication readiness
- P07 phase success; formal P05–P18 acceptance
- `RG-SW:GO`; `RG-SCI:GO`

## 9. Suggested first actions for Codex

1. Read `AGENTS.md`, then `prompts/shared/S01_RESUME_FROM_CHECKPOINT.md`.
2. Verify identity (§2) from actual bytes — do not trust this document.
3. Confirm `git status --porcelain=v1` is clean apart from anything you add.
4. Re-derive the C07 plan against real source; treat the committed draft as
   input, not instruction.
5. Record `D-C07-01` before implementing.
6. Implement P09 as storage/I-O plumbing only, default-off, and prove the
   feature-off path is unchanged against the C04 reference.
7. Qualify on the Linux reference host before claiming release evidence.

## 10. What Claude did not do

- Did not send the mentor packet (user action, `B-S00-03`).
- Did not start C06B, C07, or anything in Phase B.
- Did not push anything.
- Did not resolve `B-C02-01`, `B-C03-02`, or `D-C04-07`.
- Did not perform any independent review of its own work — `prompts/codex/X01`–`X07`
  remain unexecuted, and they were written on the assumption that a *different*
  agent from the writer performs them.
