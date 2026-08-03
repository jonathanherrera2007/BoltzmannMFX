# C02 — source defects found during the build spike

These are defects in the **canonical source at `389e9e3`**, found by actually
configuring and compiling it. None of them were patched in C02: C02 owns build
configuration only, not product source. Each was worked around in the build
environment, and each is recorded here for a later owner to fix properly.

Every workaround is confined to `tools/repro/configure_native_windows.ps1` and
`tools/repro/native_windows_env.ps1`. **No file under `src/` was modified.**

---

## D-C02-01 — `M_PI` is not portable to MSVC

- **Severity:** HIGH (hard build failure on the reference platform)
- **File:** `src/chemistry/bmx_cell_interaction_K.H`
- **Lines:** 542, 547, 556, 558, 561, 562, 1210, 1217, 1226, 1228, 1231, 1232,
  1293, 1298, 1307, 1309, 1312, 1313, 1590, 1597 (20 occurrences)

**Observed:** `error C2065: 'M_PI': undeclared identifier`, 20 times, aborting
the build at `[163/200]`.

**Cause:** `M_PI` is a POSIX/X-Open constant, not standard C++. libstdc++ and
libc++ expose it from `<cmath>` by default as an extension, so the code compiles
on Linux and macOS. MSVC's `<cmath>` defines it only when `_USE_MATH_DEFINES` is
defined *before* the header is included. The source relies on the extension.

**Workaround applied (build config):** `/D_USE_MATH_DEFINES` added to
`CMAKE_C_FLAGS` and `CMAKE_CXX_FLAGS`. A compiler-level `/D` is established
before any include in every translation unit, so the ordering requirement is
met. This changes no value — `M_PI` is the same double either way.

**Recommended real fix:** replace `M_PI` with a constant owned by the project,
e.g. `amrex::Math::pi<amrex::Real>()`, or a file-local
`constexpr amrex::Real pi = 3.14159265358979323846;`. Do not rely on a
platform extension in a research-grade numerical kernel.

**Retest scope:** full rebuild plus any numerical test touching cell geometry.

---

## D-C02-02 — build system requires POSIX `grep` on `PATH`

- **Severity:** MEDIUM (hard configure failure on a bare Windows host)
- **File:** `tools/CMake/BMX_Utils.cmake`
- **Lines:** 7–24 (`get_git_info` macro)

**Observed, before the workaround:**

```
CMake Error at tools/CMake/BMX_Utils.cmake:18 (string):
  string sub-command REPLACE requires at least four arguments.
CMake Error at tools/CMake/BMX_Utils.cmake:19 (string):
  string sub-command STRIP requires two arguments.
```

**Cause:** the macro shells out to `git branch | grep \*`. `grep` is not a
Windows command. The pipeline produces empty output, `out` is unset, and
`string(REPLACE "*" "" out ${out})` is then called with three arguments instead
of four. The guard on line 15 (`if(err)`) does not catch this, because the
failure leaves `err` empty as well — so the macro's own error handling does not
fire on the failure mode it was presumably written for.

**Workaround applied (build env):** Git for Windows' `usr/bin` (which ships a
real `grep.exe`) is **appended** to `PATH`. Appending is deliberate — that
directory also contains `link.exe`, `sort.exe` and `find.exe`, which would
shadow the MSVC linker and the Windows `sort`/`find` if prepended.

**Residual defect, not fixed:** even with `grep` present, configure now emits

```
CMake Warning at tools/CMake/BMX_Utils.cmake:16 (message):
  Failing to retrieve BMX Git branch
```

so the branch name compiled into the executable is **empty**. The commit hash is
stamped correctly. This is a provenance weakness: build identity should not
depend on a text-processing pipeline that can silently yield nothing.

**Recommended real fix:** replace the whole macro body with
`git rev-parse --abbrev-ref HEAD` (no pipe, no external `grep`), check
`RESULT_VARIABLE` rather than `ERROR_VARIABLE`, and quote the argument
(`string(STRIP "${out}" out)`) so an empty result degrades to an empty string
instead of a CMake error. Treat an unresolvable branch as a hard configure
error if branch provenance is release-significant.

**Retest scope:** configure on a host without POSIX tools; verify the stamped
branch and commit in `bmx --describe` output.

---

## D-C02-03 — reviewed reference recipe disables C++ exception unwinding

- **Severity:** MEDIUM (silent correctness risk, not a build failure)
- **File:** `05_BUILD_PLATFORM/REFERENCE_WINDOWS_BUILD_RECIPE_SANITIZED.cmake`
  lines 52–55 (planning package, not product source)

**Observed:** every translation unit warned
`C4530: C++ exception handler used, but unwind semantics are not enabled.
Specify /EHsc`.

**Cause:** the recipe sets `CMAKE_C_FLAGS` / `CMAKE_CXX_FLAGS` to exactly `/w`.
Assigning those variables **replaces** CMake's MSVC defaults, which include
`/DWIN32 /D_WINDOWS /EHsc`. The result is a build where `throw` does not unwind
correctly. AMReX does throw.

The recipe can tolerate this because it states it "never launches either
produced BMX image" — it exists to prove compilation only. C02 does launch the
image, so the defaults must be restored.

**Workaround applied (build config):** flags set to
`/DWIN32 /D_WINDOWS /EHsc /w /D_USE_MATH_DEFINES`, i.e. CMake's MSVC defaults
plus the recipe's `/w` plus D-C02-01's define. No optimisation level, precision
setting, or scientific parameter is affected.

**Consequence for later stages:** any evidence produced by an executable built
with the unmodified recipe flags should be treated as suspect for error-path
behaviour. All C02 evidence uses the corrected flags.

---

## D-C02-04 — reference recipe's MPI variables are stale for CMake 4.4

- **Severity:** MEDIUM (hard configure failure)
- **File:** `05_BUILD_PLATFORM/REFERENCE_WINDOWS_BUILD_RECIPE_SANITIZED.cmake`
  lines 63–67 (planning package, not product source)

**Observed:**

```
-- Could NOT find MPI_C (missing: MPI_C_HEADER_DIR) (found version "2.0")
CMake Error ... Could NOT find MPI (missing: MPI_C_FOUND MPI_CXX_FOUND C CXX)
```

**Cause:** the recipe supplies `MPI_C_INCLUDE_DIRS` / `MPI_CXX_INCLUDE_DIRS`.
Under CMake 4.4 those are *outputs* assembled by `FindMPI`
(`Modules/FindMPI.cmake` ~line 1305); the cache entry listed in
`MPI_<lang>_REQUIRED_VARS` is `MPI_<lang>_HEADER_DIR` (~line 1966). The recipe
predates this contract.

**Workaround applied (build config):** `MPI_C_HEADER_DIR` and
`MPI_CXX_HEADER_DIR` are passed in addition to the recipe's original variables,
which are retained for fidelity.

**Note:** the recipe pins CMake ≥ 3.24 but was evidently exercised against an
older FindMPI. The reference platform must record its exact CMake version
(4.4.0 here) as part of build identity, because this contract has changed.

---

## D-C02-05 — `constexpr` used in a lambda without capture

- **Severity:** HIGH (hard build failure on the reference platform)
- **File:** `src/des/bmx_pc_interaction.cpp`
- **Lines:** declaration at 174 and 610, use at **246** and **656**

**Observed:** `error C3493: 'small_number' cannot be implicitly captured because
no default capture mode has been specified`, aborting the build at `[166/200]`.

**Code:** `constexpr Real small_number = 1.0e-15;` declared outside a lambda and
used inside it as `(r_lm - small_number)*(r_lm - small_number)`.

**Cause — two independent contributing factors, both required:**

1. **Language standard.** `src/CMakeLists.txt` declares
   `target_compile_features(bmxcore PUBLIC cxx_std_14)`. Under C++14 a
   `constexpr` variable of non-integral type used in a lambda *is* odr-used and
   must be captured. Under C++17 it is not odr-used here, because
   lvalue-to-rvalue conversion is applied immediately. GCC/Clang never reported
   this because their recent defaults are `gnu++17`.
2. **MSVC's legacy lambda parser.** Setting `/std:c++17` alone was **not
   sufficient** — the identical error recurred. MSVC's pre-16.10 lambda
   processor mishandles this case regardless of `/std:`. `/Zc:lambda` selects
   the conformant parser and resolves it.

**Workaround applied (build config):** `/std:c++17 /Zc:lambda` added to
`CMAKE_CXX_FLAGS`. Both are required; neither alone builds.

Two implementation traps worth recording for whoever maintains the build:

- `-DCMAKE_CXX_STANDARD=17` is **silently ineffective** here. The target's own
  `target_compile_features(cxx_std_14)` takes precedence over the global
  variable, and since MSVC's default is already C++14, CMake emits no `/std:`
  flag at all. Verified by inspecting `compile_commands.json`, which showed no
  `/std:` entry. The flag must go in `CMAKE_CXX_FLAGS`.
- `/permissive-` was deliberately *not* used. It is a much broader conformance
  switch and risks disturbing AMReX code that depends on permissive behaviour.
  `/Zc:lambda` is the narrowest switch that fixes this defect.

**Why this is the most significant deviation in C02:** it changes the language
standard the entire product compiles under, as a build-configuration workaround
for what should be a one-line source change. It must be confirmed by
independent numerical review before any final run.

**Recommended real fix:** capture the constant explicitly, or make it
`static constexpr`, or use the literal — then reassess whether C++17 is still
required. If the project genuinely intends C++14, `cxx_std_14` should be
enforced in CI on a conforming compiler; if it intends C++17, the declared
feature level should say so rather than relying on compiler defaults.

**Retest scope:** full rebuild; any test touching particle interaction
geometry; and a rebuild at the *declared* C++14 level once the source is fixed,
to confirm the standard bump is no longer needed.

---

## D-C02-06 — configure writes a generated artefact into the source tree

- **Severity:** LOW (process hygiene, but it collides with a release gate)
- **File:** `CMakeLists.txt`
- **Lines:** 158–162

**Observed:** after every successful configure, an untracked
`compile_commands.json` (~440 KB) appears in the **source root**.

**Cause:** not a CMake side effect — the project does it deliberately:

```cmake
# Copy compile_commands.json from the build directory to the project root directory
if ( EXISTS "${CMAKE_CURRENT_BINARY_DIR}/compile_commands.json" )
  ... ${CMAKE_CURRENT_SOURCE_DIR}/compile_commands.json
```

The stated motivation is editor tooling (YouCompleteMe).

**Why it matters here:** `AGENTS.md` requires a clean `git status` before and
after every stage, and C19/C21 require clean-worktree freezes and reproductions.
A rule that "configuring the project dirties the worktree" silently breaks that
gate, and the file contains absolute machine-specific paths, so committing it
would poison reproducibility comparisons.

**Workaround applied:** `/compile_commands.json` added to `.gitignore` with an
explanatory comment. The artefact is never committed.

**Recommended real fix:** guard the copy behind an opt-in option
(e.g. `BMX_EXPORT_COMPILE_COMMANDS_TO_SOURCE_DIR`, default `OFF`), so a
research-grade build does not write into its own source tree by default.

**Retest scope:** configure, then confirm `git status` is clean.
