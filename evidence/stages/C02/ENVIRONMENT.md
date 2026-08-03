# C02 environment record

Captured 2026-07-30. Supersedes `05_BUILD_PLATFORM/ENVIRONMENT_SUMMARY.md` in
the planning package **and** the environment section of the C01 stage report.

## Host

- OS: Windows 11 Home, `10.0.26200`, AMD64
- Logical processors: 8
- System drive free space: 188 GB of 511 GB

## Why a `PATH` inventory is not a toolchain inventory

An earlier probe of `PATH` reported no C++ compiler and concluded native Windows
was unusable. That conclusion was wrong. **MSVC is not placed on `PATH` by
installation** — it becomes available only after `vcvars64.bat` (or a developer
prompt) sets `PATH`, `INCLUDE` and `LIB`. Discovery must go through `vswhere`,
not `Get-Command`.

Compounding it: Visual Studio Build Tools is installed at the literal path
`C:\Program` on this host — a directory genuinely named `Program`, not a
truncation of `C:\Program Files`. The planning package's reference recipe reads
`C:/Program/VC/Tools/MSVC/...`, which looks exactly like a sanitised placeholder
and was initially misread as one. It is the real path.

Lesson for later stages: **resolve tools by their installation metadata, never
by `PATH` presence**, and treat an odd-looking path in the reviewed recipe as
possibly literal until checked.

## Native Windows toolchain — resolved via `vswhere`

| Component | Status | Location / version |
|---|---|---|
| Visual Studio Build Tools 2022 | **FOUND** | `C:\Program` — 17.14.37516.0, instance `8ab13726` |
| `cl.exe` | **FOUND** | `C:\Program\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe` — MSVC 19.44.35228.0 |
| `ninja.exe` | **FOUND** | `C:\Program\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe` — 1.12.1 |
| `rc.exe` | **FOUND** | Windows SDK `10.0.26100.0`, x64 |
| `MSBuild.exe` | **FOUND** | `C:\Program\MSBuild\Current\Bin` (unused; Ninja is the generator) |
| `cmake.exe` | **FOUND** | `C:\Program Files\CMake\bin` — 4.4.0 |
| MS-MPI SDK | **FOUND** | `mpi.h` + `Lib\x64\msmpi.lib` |
| `mpiexec.exe` | **FOUND** | `C:\Program Files\Microsoft MPI\Bin` |
| `git.exe` | **FOUND** | 2.55.0.windows.3 |
| `grep.exe` | **FOUND** | `C:\Program Files\Git\usr\bin` — required by the build system, see D-C02-02 |
| `python.exe` | **FOUND** | 3.13 |

This is a complete, sufficient native toolchain. It produced a working
`bmx.exe`; see the stage report.

## PATH ordering constraint

`C:\Program Files\Git\usr\bin` must be **appended** to `PATH`, never prepended:
it contains `link.exe`, `sort.exe` and `find.exe`, which would shadow the MSVC
linker and the Windows `sort`/`find` that `vcvars64.bat` places ahead of them.
Enforced in `tools/repro/native_windows_env.ps1`.

## WSL — available, unused, unqualified

| Field | Value |
|---|---|
| Distribution | Ubuntu 24.04.1 LTS, State `Running` |
| WSL version | **1** (kernel `4.4.0-26100-Microsoft`) |
| nproc | 8 |
| Toolchain | gcc, g++, make, cmake, ninja, mpicc, mpicxx, mpirun, python3, git — all present |

WSL was **not used** and is **not qualified**. It remains an untested fallback.
If it is ever adopted, these risks must be settled first: WSL1 is a syscall
translation layer rather than a Linux kernel, so AMReX/MPI behaviour is not
equivalent to WSL2 or native Linux; the product tree lives on `/mnt/c` (DrvFs)
where I/O is slow and locking semantics differ; and MS-MPI and OpenMPI/MPICH are
different stacks that must never be mixed within one build identity.
