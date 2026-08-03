# S00 — Session bootstrap (BMX RG-SW)

- **Stage:** `S00_SESSION_BOOTSTRAP`
- **Status:** `PASS`
- **Captured:** 2026-07-30
- **Role:** primary writer (the independent reviewer), product lane
- **Production-source edits in this stage:** none

---

## 1. Planning package identity — VERIFIED

| Field | Value |
|---|---|
| Located at | `C:\Users\Shadow\Documents\the implementation writer\2026-07-28\how\outputs\BMX_RESEARCH_GRADE_PLANNING_PLANNING_PACKAGE_20260730.zip` |
| Size | 321,212 bytes |
| Expected SHA-256 | `014607d34400638a5a915674e500b1b8afbacfebf0159801f8b7e5f32cac74a1` |
| Actual SHA-256 | `014607d34400638a5a915674e500b1b8afbacfebf0159801f8b7e5f32cac74a1` |
| Verdict | **MATCH** |

Extracted read-only to `BMX-RG-SW/planning-package/`.

Internal manifest: `MANIFEST.sha256`, 153 members.
`sha256sum -c MANIFEST.sha256` → **153/153 OK, 0 failures**.

Commands:

```
Get-FileHash <zip> -Algorithm SHA256
Expand-Archive -Path <zip> -DestinationPath BMX-RG-SW\planning-package -Force
sha256sum -c MANIFEST.sha256
```

## 2. Package reading (required order)

Read in this session:

- `00_START_HERE/README_FIRST.md`
- `05_BUILD_PLATFORM/SOURCE_IDENTITY.json`
- `05_BUILD_PLATFORM/ENVIRONMENT_SUMMARY.md`

Not yet read (required before the stages that consume them, per `AGENTS.md`
reading order): `00_START_HERE/PLANNING_PLANNING_PROMPT.md`,
`01_CURRENT_STATE/PRODUCT_STATE_SUMMARY.md`,
`01_CURRENT_STATE/RESEARCH_GRADE_DEFINITION_OF_DONE.md`,
`01_CURRENT_STATE/TARGET_AND_CLAIM_BOUNDARY.md`,
`02_REQUIREMENTS/CONFIRMED_SCIENCE_DECISIONS_REDACTED.json`,
`02_REQUIREMENTS/DECISION_RECONCILIATION_REQUIRED.md`.

`SOURCE_IDENTITY.json` confirms the pinned identities used throughout the prompt
pack and records `amrex_included: false` — AMReX must be bound, not extracted.

## 3. Canonical source availability — VERIFIED, but not yet isolated

The canonical BMX objects exist locally in an **existing lane repository**:

`C:\Users\Shadow\Documents\the implementation writer\2026-07-25\github-plugin-curated-remote-3\work\BoltzmannMFX`

| Check | Result |
|---|---|
| `git cat-file -t 389e9e35a1c7291a4af795b2e39f2db1f0012b61` | `commit` (present) |
| `git rev-parse 389e9e3^{tree}` | `1c73deedf0eb2feea833a7fddbc431ae9754d977` — **matches required tree** |
| Commit subject | "Add phosphorus transport and growth sensitivity review", Jonathan Herrera, Thu Jul 9 2026 |
| `git ls-tree 389e9e3 subprojects/amrex` | gitlink `cbdc6580ee3d78cccdd37172e4ba077ee181f483` — **matches pinned AMReX commit** |
| Current submodule state | `cbdc6580e` (`22.07-4-gcbdc6580e`) — already at pin |
| Remote | `origin https://github.com/jonathanherrera2007/BoltzmannMFX.git` |

**Classification of this repository: NOT the product worktree.** It is a live
multi-lane scratch workspace:

- HEAD is `dfe1eefe26a5ed0bda336e2800a8808562891571` on branch
 `workspace/bmx-connected-poster-pilot`, not the canonical commit.
- Four registered worktrees point at **WSL-style `/mnt/c/...` paths** and are all
 marked `prunable`; a fifth (`BoltzmannMFX-convergence-repair`) reports 2 dirty
 entries.
- Several sibling `BoltzmannMFX-*` directories are detached copies with no `.git`.

Its object database is nevertheless a legitimate source for C01, because commit
and tree SHA-1s are self-verifying and both match the required identities. C01
must create a **separate, clean, isolated** clone/worktree at `389e9e3` rather
than working in this tree. Do not prune or repair the lane worktrees — that is
another lane's evidence.

## 4. Product workspace isolation

- **New product root (created this stage):** `C:\Users\Shadow\Documents\the implementation writer\BMX-RG-SW\`
 — currently contains only `planning-package/` and `evidence/session/`.
- **P05 workspace (must not be touched):**
 `C:\Users\Shadow\Documents\the implementation writer\2026-07-25\perform-a-strict-read-only-import\work\p05-production-readiness\`
- **Path overlap:** none.
- **Writers on the product root:** exactly one (this session).
- No prior RG-SW `evidence/stages/*` directory exists anywhere under
 `Documents\the implementation writer`. **This is a cold start; no stage C01+ has been executed.**

## 5. Environment recapture (supersedes package `ENVIRONMENT_SUMMARY.md`)

Native Windows (host PATH):

| Tool | State |
|---|---|
| git | **FOUND** 2.55.0.windows.3 |
| cmake | **FOUND** 4.4.0 |
| mpiexec (MS-MPI) | **FOUND** |
| python | **FOUND** 3.13 |
| ninja, make, g++, clang++, cl, msbuild, mpirun, pwsh | **MISSING** |

**There is no C++ compiler on native Windows.** A native build is not currently
possible without installing a toolchain.

WSL — this is a **change from the package observation**, which reported distro
enumeration failing with access denied:

| Field | Value |
|---|---|
| Distro | Ubuntu 24.04.1 LTS, State `Running` |
| WSL version | **1** (kernel `4.4.0-26100-Microsoft`) |
| nproc | 8 |
| Toolchain | gcc, g++, make, cmake, ninja, mpicc, mpicxx, mpirun, python3, git — **all present** |

**Consequence for C02:** the four-hour native-Windows spike has effectively
already failed its prerequisite check (no compiler), and a complete Linux
toolchain is available today. The WSL1 Ubuntu route is the leading reference
platform candidate. It is **not yet qualified** — WSL1 is not a real Linux
kernel, and its filesystem and MPI behavior on `/mnt/c` must be proven by an
actual configure/build/run before it can be declared the reference platform.
Working inside the WSL native filesystem rather than `/mnt/c` should be
evaluated during C02.

## 6. Blockers

| ID | Blocker | Owner | Blocks |
|---|---|---|---|
| B-S00-01 | No qualified build platform yet; native Windows has no C++ compiler, WSL1 route unproven | writer | C02 and everything downstream |
| B-S00-02 | No isolated product/baseline/review worktrees exist | writer | C01 |
| B-S00-03 | All biology-dependent decisions remain unresolved (mentor packet not yet sent) | user/mentor | C06B, C10, C11, C12, C14, C15 |

None of these block the next stage.

## 7. Claims that remain prohibited

No claim of: formal P05–P18 acceptance; empirical calibration; predictive
validity; production qualification; publication readiness; `RG-SW:GO`;
`RG-SCI:GO`; or any statement that a build, test, or scientific result has been
produced. **Nothing has been built, run, or tested in this stage.**

## 8. Next valid prompt

`prompts/writer/C01_PACKAGE_SOURCE_AND_WORKTREE_AUDIT.md`

Its preconditions are met: package hash and manifest verified, canonical
commit/tree and pinned AMReX gitlink located and confirmed, isolation from P05
established, single writer confirmed.
