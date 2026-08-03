# C01 environment record

Captured 2026-07-30. This supersedes `05_BUILD_PLATFORM/ENVIRONMENT_SUMMARY.md`
in the planning package, which was captured before the WSL distribution became
enumerable. **No build was attempted in C01**; this is a presence inventory only.
C02 owns the actual build spike.

## Host

- OS: Windows 11 Home, `10.0.26200`, AMD64
- Logical processors: 8
- System drive free space: 188 GB of 511 GB

## Native Windows PATH

| Tool | State | Path / version |
|---|---|---|
| git | FOUND | `C:\Program Files\Git\cmd\git.exe` — 2.55.0.windows.3 |
| cmake | FOUND | `C:\Program Files\CMake\bin\cmake.exe` — 4.4.0 |
| mpiexec | FOUND | `C:\Program Files\Microsoft MPI\Bin\mpiexec.exe` |
| python | FOUND | `...\Programs\Python\Python313\python.exe` |
| wsl | FOUND | `C:\WINDOWS\system32\wsl.exe` |
| ninja | MISSING | |
| make | MISSING | |
| g++ | MISSING | |
| clang++ | MISSING | |
| cl | MISSING | |
| msbuild | MISSING | |
| mpirun | MISSING | |
| pwsh | MISSING | |

**No C++ compiler is present on native Windows.** A native build cannot be
configured today without first installing a toolchain.

## WSL

| Field | Value |
|---|---|
| Distribution | Ubuntu 24.04.1 LTS |
| State | Running |
| WSL version | **1** |
| Kernel | `4.4.0-26100-Microsoft` |
| nproc | 8 |

| Tool | State | Path |
|---|---|---|
| gcc | FOUND | `/usr/bin/gcc` |
| g++ | FOUND | `/usr/bin/g++` |
| make | FOUND | `/usr/bin/make` |
| cmake | FOUND | `/usr/bin/cmake` |
| ninja | FOUND | `/usr/bin/ninja` |
| mpicc | FOUND | `/usr/bin/mpicc` |
| mpicxx | FOUND | `/usr/bin/mpicxx` |
| mpirun | FOUND | `/usr/bin/mpirun` |
| python3 | FOUND | `/usr/bin/python3` |
| git | FOUND | `/usr/bin/git` |

## Consequence for C02

The WSL1 Ubuntu route is the only route with a complete toolchain today and is
therefore the leading reference-platform candidate. It is **not qualified**.
Open risks C02 must settle by actually building and running:

1. WSL **1** is a syscall translation layer, not a Linux kernel. AMReX/MPI
   behaviour under WSL1 is not equivalent to WSL2 or native Linux and must be
   demonstrated, not assumed.
2. The product tree lives on `/mnt/c` (DrvFs). Build I/O there is slow and file
   locking/permission semantics differ. C02 should evaluate building from the
   WSL native filesystem instead.
3. Compiler and MPI versions have not been recorded; C02 must capture exact
   versions and flags as part of the build identity.
4. MS-MPI (Windows) and OpenMPI/MPICH (WSL) are different stacks. Only one may
   be declared the reference; they must not be mixed in one build identity.
