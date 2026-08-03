# C02 — first-four-hour build and environment spike

- **Stage ID:** `C02`
- **Status:** `PASS`
- **Date:** 2026-07-30
- **Role:** primary writer (Claude), product lane
- **Input commit / tree:** `893dbaba15143f87cf680a24b2103db9d3723e69` (C01 output) on `rgsw/product`; source tree still `1c73deed…` plus C01's non-source additions
- **Output commit:** see `COMMIT.txt`
- **AMReX:** `cbdc6580ee3d78cccdd37172e4ba077ee181f483`
- **Companion evidence:** `DEFECTS.md`, `ENVIRONMENT.md`, `STAGE_REPORT.json`

---

## 1. Outcome

**A real, reproducible build and execution route exists on native Windows.**
`bmx.exe` builds clean from the unmodified canonical source, reports its build
identity, initialises, advances a timestep, and runs under two MPI ranks.

**No product source was modified.** All five defects found were worked around in
build configuration only, and are recorded in `DEFECTS.md` for a later owner.

## 2. Correction to C01 — native Windows *is* viable

C01 §5 and blocker **B-S00-01** stated that native Windows had no C++ compiler
and that WSL1 was the only complete toolchain. **That was wrong**, and this
report supersedes it. C01's committed report is left intact as the historical
record rather than rewritten.

The error: C01 inventoried tools by probing `PATH`. MSVC is not on `PATH` until
the developer environment is loaded, so a present toolchain looked absent.

Actual state — **Visual Studio Build Tools 2022 17.14.37**, installed at the
literal path `C:\Program`. That is the genuine installation root reported by
`vswhere`, which is why the package's reference recipe reads
`C:/Program/VC/Tools/MSVC/...` — those paths were never sanitised placeholders,
they were accurate, and I misread them as redactions.

| Component | Resolved |
|---|---|
| MSVC toolset | 14.44.35207 (compiler 19.44.35228.0) |
| Ninja | 1.12.1 |
| rc.exe | Windows SDK 10.0.26100.0 |
| CMake | 4.4.0 |
| MS-MPI | SDK include + `msmpi.lib` + `mpiexec` |

**B-S00-01 is closed.** WSL1 was not needed and was not used; it remains an
untested fallback, not a qualified platform.

## 3. Reference platform declared

| Field | Value |
|---|---|
| OS | Windows 11 Home 10.0.26200, AMD64, 8 logical processors |
| Compiler | MSVC 19.44.35228.0 (toolset 14.44.35207) |
| Generator | Ninja 1.12.1 |
| CMake | 4.4.0 |
| MPI | Microsoft MPI (MS-MPI), thread support level 0 |
| Build type | Release, `/O2 /DNDEBUG` |
| Precision | double (`AMReX_PRECISION=DOUBLE`, `AMReX_PARTICLES_PRECISION=DOUBLE`, hard-set by `BMXSetupAMReX.cmake`) |
| GPU | none (`BMX_GPU_BACKEND=NONE`) |
| OpenMP | off |

Verified `CMakeCache.txt` entries: `BMX_MPI=ON`, `BMX_MPI_THREAD_MULTIPLE=OFF`,
`BMX_OMP=OFF`, `BMX_GPU_BACKEND=NONE`, `BMX_HYPRE=OFF`, `BMX_CSG=OFF`,
`AMReX_SPACEDIM=3`, `CMAKE_BUILD_TYPE=Release`.

## 4. Build identity

| Field | Value |
|---|---|
| Executable | `build/c02-native-release/bmx.exe` |
| SHA-256 | `e3c8ee0869a2a04a142bdd672ecc431dce946be2e6f98a7e1c9815c19488a9bc` |
| Size | 2,369,536 bytes |
| Objects | 200 |
| Build time | 213 s at `--parallel 8` |
| Build dir size | 250 MB |
| `CMAKE_CXX_FLAGS` | `/DWIN32 /D_WINDOWS /EHsc /w /D_USE_MATH_DEFINES /std:c++17 /Zc:lambda` |
| `CMAKE_CXX_FLAGS_RELEASE` | `/O2 /DNDEBUG` |

Self-reported by the executable (`--describe`), independently confirming the
identity chain:

- `BMX git describe: v0.1-108-g893dbaba1514` — matches the C01 output commit
- `AMReX git describe: 22.07-4-gcbdc6580ee3d` — matches the pinned AMReX commit

## 5. Deviations from the reviewed reference recipe

Five deviations, each with cause. None alters an optimisation level, a precision
setting, or any scientific parameter. Full detail in `DEFECTS.md`.

| ID | Deviation | Why |
|---|---|---|
| D-C02-01 | `+ /D_USE_MATH_DEFINES` | `M_PI` in `bmx_cell_interaction_K.H` (20 sites) is a POSIX extension MSVC does not expose by default |
| D-C02-02 | Git `usr/bin` appended to `PATH` | `BMX_Utils.cmake` shells out to `grep`, absent on Windows |
| D-C02-03 | `+ /DWIN32 /D_WINDOWS /EHsc` | recipe's `/w` **replaced** CMake's MSVC defaults, disabling exception unwinding |
| D-C02-04 | `+ MPI_{C,CXX}_HEADER_DIR` | CMake 4.4 `FindMPI` requires these; recipe supplies only the derived `*_INCLUDE_DIRS` |
| D-C02-05 | `+ /std:c++17 /Zc:lambda` | `constexpr` in a lambda without capture; **both** flags required |

D-C02-03 deserves emphasis. The recipe builds with `/w` assigned to
`CMAKE_CXX_FLAGS`, which wipes out CMake's default `/EHsc`, so every translation
unit warned C4530 and the resulting image would not unwind exceptions correctly.
The recipe tolerates this because it explicitly states it never launches the
image it produces. C02 does launch it, and AMReX throws, so the defaults were
restored. **Any evidence produced by an executable built with the unmodified
recipe flags should be treated as suspect for error-path behaviour.**

D-C02-05 is the largest deviation: it changes the language standard for the
whole product as a workaround for a one-line source issue. Flagged for
independent numerical review before any final run.

## 6. Execution smoke test

Run root `runs/c02-smoke/`, outside the Git worktree.

| Stage | Command | Exit | Elapsed |
|---|---|---|---|
| describe | `bmx.exe --describe` | 0 | 0.035 s |
| init only | `bmx.exe input_fungi bmx.max_step=0 …` | 0 | 0.065 s |
| one step | `bmx.exe input_fungi bmx.max_step=1 …` | 0 | 0.149 s |
| two ranks | `mpiexec -n 2 bmx.exe … bmx.max_step=1 …` | 0 | 0.226 s |

**Exit codes alone were not treated as proof.** Sub-second timings were checked
against log content before accepting the result; the case is genuinely tiny
(16×16×8 cells, 1 particle), and `Time spent in main` is 0.11 s.

Positive evidence from the logs:

- `MPI initialized with 1 MPI processes` / `with 2 MPI processes`
- `AMReX (22.07-4-gcbdc6580ee3d) initialized` … `finalized`
- `Reading in 6 chem_species` → `A B C D F P`, matching the **disabled
  compatibility mesh order** in `AGENTS.md`. Phosphorus infrastructure is not
  enabled, as expected at this stage.
- `Evolving particles on level: 1 ... with fluid dt 0.25`, `In Particle Exchange
  with 1 particles at level 1`, `Time per step 0.0494016` under 2 ranks
- Scan for `nan|inf|assert|abort|error` across all smoke logs: **no matches**

The two-rank run is a **launch check only**. It shows the MPI build actually
communicates rather than merely linking. It is **not** the rank/decomposition
invariance study, which is predeclared and owned by C16.

## 7. Reproducible scripts

Committed under `tools/repro/`:

| Script | Purpose |
|---|---|
| `native_windows_env.ps1` | discovers and validates every tool path, fails loudly on any absence, imports the MSVC environment |
| `configure_native_windows.ps1` | configure with the reviewed option set plus the five documented deviations |
| `build_native_windows.ps1` | build `bmx`, verify the image exists, hash it |
| `run_smoke_native_windows.ps1` | describe / init / one step / two ranks |

All use `Set-StrictMode -Version Latest` and `$ErrorActionPreference = 'Stop'`,
quote every path, and throw on non-zero exit. Per C01's `core.fileMode=false`
constraint, none relies on a working-tree executable bit — each is invoked as
`powershell -NoProfile -ExecutionPolicy Bypass -File <script>`.

Re-running configure + build from a **cleared** build directory succeeded (this
was done repeatedly while resolving the five defects; the final clean run is the
one recorded in §4).

## 8. Process error made and corrected

While iterating on D-C02-05 I launched a reconfigure+rebuild while a previous
background build was **still running against the same build directory and the
same log file**. The second run reported a `/Zc:lambda` failure that was
actually contamination from the first. I discarded that result and re-ran the
configure and build strictly serially with distinct log files; §4 and §6 record
only the clean serial run. No conclusion in this report rests on the
contaminated run.

## 9. Files changed

| Path | Reason |
|---|---|
| `tools/repro/native_windows_env.ps1` | toolchain resolution and MSVC env import |
| `tools/repro/configure_native_windows.ps1` | configure with documented deviations |
| `tools/repro/build_native_windows.ps1` | build + image hash |
| `tools/repro/run_smoke_native_windows.ps1` | execution smoke test |
| `evidence/stages/C02/STAGE_REPORT.md` | this report |
| `evidence/stages/C02/STAGE_REPORT.json` | machine-readable report |
| `evidence/stages/C02/DEFECTS.md` | five defects found by building |
| `evidence/stages/C02/ENVIRONMENT.md` | corrected environment record |
| `evidence/stages/C02/COMMIT.txt` | stage commit hash |

**Zero files under `src/` changed.** Build outputs (`build/`), run outputs
(`runs/`) and logs live outside the worktree and are not committed.

## 10. Mandatory validation

| Check | Result |
|---|---|
| Clean configure and link | **PASS** (200/200 objects, 0 errors) |
| `bmx` executable hash recorded | **PASS** `e3c8ee08…88a9bc` |
| One-rank initialisation and one-step launch succeed | **PASS** |
| Re-running the build script from a cleared build directory succeeds | **PASS** |
| Source remains unchanged | **PASS** (`git status` clean apart from the files in §9) |

## 11. Blockers

| ID | Blocker | Owner | Status |
|---|---|---|---|
| B-S00-01 | No qualified build platform | writer | **CLOSED** by this stage |
| B-S00-03 | Biology decisions unresolved; mentor packet not sent | user / mentor | **OPEN** — blocks C06B and final runs in C10–C15 |
| B-C02-01 | Five source/recipe defects worked around in build config, not fixed at source | writer + independent review | **OPEN** — non-blocking for C03–C05; D-C02-05 must be reviewed before any final run |

## 12. Claims that remain prohibited

The build compiles and runs. That is **all** that is established. Specifically
**not** claimed: platform qualification (that is C16); numerical correctness;
conservation or restart integrity; MPI rank-invariance; any scientific result;
formal P05–P18 acceptance; empirical calibration; predictive validity;
production qualification; publication readiness; `RG-SW:GO`; `RG-SCI:GO`.

Status remains **`RESEARCH-USE-CANDIDATE — RG-SW INCOMPLETE`**, **`RG-SCI:NO-GO`**,
formal acceptance **NO**.

## 13. Next valid prompt

`prompts/claude/C03_P06_LEAN_BASELINE_EVIDENCE.md`

C03 must build in the **baseline** worktree using these same scripts and record
its own executable hash; the C02 image was built from the product worktree and
is not a baseline artefact.
