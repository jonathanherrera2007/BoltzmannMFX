# C04 — Linux portability smoke (NOT release evidence)

- **Date:** 2026-07-31
- **Purpose:** `DEC-PLATFORM-001` makes Linux the reference platform. This
 records what could and could not be established toward that on the available
 hardware.

> **This is not platform-qualified evidence and does not close
> `B-PLATFORM-01`.** The host is WSL1, which `tools/repro/linux_env.sh`
> classifies `smoke-only`, with the policy written at C02: *"WSL 1 is a syscall
> translation layer, not a Linux kernel… usable as a PORTABILITY SMOKE platform
> only, and must never carry release evidence."* That classification is honoured
> here rather than argued around.

## 1. Why a reference-capable host was not available

| | |
|---|---|
| WSL2 | **unavailable** — `WSL2 is unable to start since virtualization is not enabled on this machine` (firmware setting, not something an agent may change) |
| WSL1 Ubuntu 24.04.1 LTS | present, kernel `4.4.0-26100-Microsoft`, working tree on drvfs |
| toolchain | g++ 13.3.0, cmake 3.28.3, OpenMPI (`mpicxx`), ninja, make — complete |
| `BMX_PLATFORM_CLASS` | `smoke-only` |

Provisioning a reference-capable Linux host (native, or WSL2 after enabling
virtualization in firmware) is a **user action**.

## 2. What the smoke does establish

### 2a. The Windows workarounds are Windows-specific, not product defects

`tools/repro/configure_linux.sh` deliberately applies **none** of the six
workarounds recorded in `evidence/stages/C02/DEFECTS.md`. It configured and
built cleanly anyway:

| Windows defect | Linux result |
|---|---|
| `D-C02-01` `/D_USE_MATH_DEFINES` for `M_PI` | not needed |
| `D-C02-02` `grep` on PATH | not needed |
| `D-C02-03` `/EHsc` restoration | not needed |
| `D-C02-04` `MPI_*_HEADER_DIR` | `FindMPI` resolved via `mpicxx` |
| `D-C02-05` `/std:c++17 /Zc:lambda` | g++ accepted the constexpr-in-lambda usage |
| `D-C02-06` `compile_commands` copy | still occurs — a source-tree issue, not Windows-specific |

**200/200 objects compiled and linked** with `-O2 -DNDEBUG -Werror=return-type`.

### 2b. All C04 results reproduce numerically identically across platform and compiler

Same fixtures, MSVC/Windows vs g++ 13.3.0/Linux:

| Result | Windows | Linux | |
|---|---|---|---|
| Donor cap `A_particles_final` @ k1=5 | `4.882812500000002e-12` | `4.882812500000002e-12` | **identical** |
| Donor cap available `fA0*V_cell` | `4.882812500000002e-12` | `4.882812500000002e-12` | **identical** |
| Donor cap relative difference | `0.00e+00` | `0.00e+00` | **identical** |
| Saturation plateau (k1 = 2…100) | `4.871033e-12` | `4.871033e-12` | **identical** |
| Conservation max rel residual | `4.822e-11` | `4.822e-11` | **identical** |
| G1 `TIP_LENGTH_ONLY` / area stale | 76 / 76 | 76 / 76 | **identical** |
| G1 `max_rel` | `5.480783e-02` | `5.480783e-02` | **identical** |
| G4 `NONTIP_REJECTED` / `TIP_LENGTH_ONLY` | 188 / 133 | 188 / 133 | **identical** |
| G4 `max_rel` | `9.999936e-01` | `9.999936e-01` | **identical** |
| Diagnostic regression guard | 5/5 PASS | **5/5 PASS** | — |
| Diagnostic field map | `first_data=28`, A=0/28 B=1/29 C=2/30 | same | **identical** |

The only difference found is the abort exit code for the rejected-species
negative test (Windows 22, Linux 6), which is platform convention, not
behaviour.

### 2c. Images

| image | chemistry | diagnostic | SHA-256 |
|---|---|---|---|
| `/tmp/bmx-linux-smoke` | repaired `9519fc24` | yes | `af1964856ce49a3449a1f9e3d6c9e28ddad305cacfe4df960b6ac54fd696e3a9` |
| `/tmp/bmx-linux-baseline-diag` | baseline `711ae2ca` | yes | `9cbbcef72891bc1d83fd111ebd9be10b553670f2226005d6e892d02bc3ef75c7` |

Hashes are recorded for traceability only. Being smoke-only, they are **not**
release artefacts.

## 3. New finding (since REPAIRED)

**`D-C04-08` — git worktree metadata did not resolve cross-platform.** The
`.git` file in each worktree stores an absolute *Windows* path
(`C:/Users/.../repo/.git/worktrees/product`). Under Linux this yielded

```
fatal: not a git repository: /mnt/c/.../worktrees/product/C:/Users/.../worktrees/product
```

so the build stamped **empty provenance** — a genuine defect for release
evidence, where the build must record which commit produced it.

**Repaired** in commit `8428a5d` (`STAGE_REPORT.md` §15). Both platforms now
report `48375fc42b36d238241656796ae4e7938a42ff21`, Linux noting *"translated
across platforms"*, and `BMX_REQUIRE_PROVENANCE=ON` makes configure fail rather
than emit an unattributable artefact. Regression fixture
`tools/repro/check_build_provenance.py` passes 7/7 on Windows **and** Linux.

This is tracked as release-transition requirement **RT-2**: repaired and
verified, but not yet exercised through a full qualification run on a reference
host — because no reference host exists (RT-1).

## 4. Reproduction

```bash
wsl -d Ubuntu
cd /mnt/c/Users/Shadow/Documents/the implementation writer/BMX-RG-SW/worktrees/product

source tools/repro/linux_env.sh # must print class: smoke-only here
bash tools/repro/configure_linux.sh -b /tmp/bmx-linux-smoke -f
bash tools/repro/build_linux.sh -b /tmp/bmx-linux-smoke

python3 tools/repro/check_sums_diagnostic.py \
 --exe /tmp/bmx-linux-smoke/bmx --case-dir exec/fungi \
 --work-dir /tmp/bmx-linux-diagcheck

bash tools/repro/configure_linux.sh -s ../baseline-diag -b /tmp/bmx-linux-baseline-diag -f
bash tools/repro/build_linux.sh -b /tmp/bmx-linux-baseline-diag

python3 tools/repro/run_p07_donor_cap_fixture.py \
 --baseline-exe /tmp/bmx-linux-baseline-diag/bmx \
 --repaired-exe /tmp/bmx-linux-smoke/bmx \
 --case-dir exec/fungi --out-dir /tmp/bmx-linux-donorcap
```

## 5. Status

| Item | Status |
|---|---|
| C04 gate (correctness of the P07 repair) | **met** — all five defect mappings demonstrated |
| Portability to Linux/gcc | **demonstrated** — builds unmodified, results numerically identical at full emitted precision |
| `DEC-PLATFORM-001` reference-platform qualification | **NOT met** — no reference-capable host exists |
| `B-PLATFORM-01` | **OPEN** |
| C05, C07 | **BLOCKED** |

The agreement is a strong portability signal and materially
reduces the risk that re-execution on a reference host will change anything.
It is not a substitute for that re-execution.
