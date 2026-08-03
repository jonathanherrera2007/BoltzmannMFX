# BMX RG-SW — configure an untouched Release / double-precision / CPU / MPI build
# on native Windows with MSVC + Ninja + MS-MPI.
#
# Option set is taken verbatim from the reviewed reference recipe in
# 05_BUILD_PLATFORM/REFERENCE_WINDOWS_BUILD_RECIPE_SANITIZED.cmake.
# Double precision is not an option here: BMXSetupAMReX.cmake hard-sets
# AMReX_PRECISION=DOUBLE and AMReX_PARTICLES_PRECISION=DOUBLE.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File configure_native_windows.ps1 `
#              [-SourceDir <path>] [-BuildDir <path>] [-Fresh]

[CmdletBinding()]
param(
    [string]$SourceDir,
    [string]$BuildDir,
    [switch]$Fresh
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'native_windows_env.ps1')

if (-not $SourceDir) { $SourceDir = (Resolve-Path (Join-Path $scriptDir '..\..')).Path }
if (-not $BuildDir)  { $BuildDir  = Join-Path (Split-Path -Parent (Split-Path -Parent $SourceDir)) 'build\c02-native-release' }

if (-not (Test-Path -LiteralPath (Join-Path $SourceDir 'CMakeLists.txt'))) {
    throw "not a BMX source tree (no CMakeLists.txt): $SourceDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $SourceDir 'subprojects\amrex\CMakeLists.txt'))) {
    throw "AMReX submodule is not bound at: $SourceDir\subprojects\amrex"
}

if ($Fresh -and (Test-Path -LiteralPath $BuildDir)) {
    Write-Host "removing existing build directory: $BuildDir"
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

Write-Host "source : $SourceDir"
Write-Host "build  : $BuildDir"

$cmakeArgs = @(
    '-S', $SourceDir,
    '-B', $BuildDir,
    '-G', 'Ninja',
    "-DCMAKE_MAKE_PROGRAM:FILEPATH=$($BmxTool.Ninja)",
    "-DCMAKE_C_COMPILER:FILEPATH=$($BmxTool.Cl)",
    "-DCMAKE_CXX_COMPILER:FILEPATH=$($BmxTool.Cl)",
    "-DCMAKE_RC_COMPILER:FILEPATH=$($BmxTool.Rc)",
    "-DCMAKE_MT:FILEPATH=$($BmxTool.Mt)",
    '-DCMAKE_BUILD_TYPE:STRING=Release',
    # Deviation from the reviewed reference recipe, with cause.
    #
    # The recipe sets CMAKE_{C,CXX}_FLAGS to exactly "/w". Assigning that
    # variable *replaces* CMake's MSVC defaults ("/DWIN32 /D_WINDOWS /EHsc"),
    # so the recipe silently builds with exception unwind semantics disabled —
    # every translation unit warns C4530. The recipe can tolerate that because
    # it explicitly never launches the image it produces. C02 does launch it,
    # and AMReX throws, so /EHsc is restored along with the other defaults.
    #
    # _USE_MATH_DEFINES is required because src/chemistry/bmx_cell_interaction_K.H
    # uses M_PI, which is a POSIX/GNU extension rather than standard C++.
    # libstdc++ exposes it by default; MSVC's <cmath> only defines it when
    # _USE_MATH_DEFINES is set before the include, so without this the build
    # fails with ~20x "error C2065: 'M_PI': undeclared identifier".
    #
    # Neither change alters an optimisation level, a precision setting, or any
    # scientific parameter. See DEFECTS.md for the underlying source portability
    # defects, which are recorded for a later owner rather than patched here.
    '-DCMAKE_C_FLAGS:STRING=/DWIN32 /D_WINDOWS /w /D_USE_MATH_DEFINES',
    '-DCMAKE_CXX_FLAGS:STRING=/DWIN32 /D_WINDOWS /EHsc /w /D_USE_MATH_DEFINES /std:c++17 /Zc:lambda',
    '-DCMAKE_C_FLAGS_RELEASE:STRING=/O2 /DNDEBUG',
    '-DCMAKE_CXX_FLAGS_RELEASE:STRING=/O2 /DNDEBUG',
    '-DCMAKE_EXPORT_COMPILE_COMMANDS:BOOL=ON',
    # Deviation: raise the C++ standard from the project's declared minimum.
    #
    # src/CMakeLists.txt declares target_compile_features(bmxcore PUBLIC
    # cxx_std_14) -- a MINIMUM, not a pin. Under C++14, a constexpr variable of
    # non-integral type used inside a lambda is odr-used and must be captured
    # explicitly, so MSVC rejects src/des/bmx_pc_interaction.cpp:246 and :656
    # with "error C3493: 'small_number' cannot be implicitly captured".
    # C++17 removed that requirement, which is why GCC/Clang -- whose recent
    # defaults are gnu++17 -- never reported it. Building at C++17 is therefore
    # closer to the toolchain this source was actually developed against, not
    # further from it. AMReX 22.07 supports C++17.
    #
    # This is the largest deviation in this file: it changes the language
    # standard for the whole product. It is recorded as D-C02-05 and must be
    # confirmed by independent numerical review before any final run.
    # Applied as an explicit flag rather than -DCMAKE_CXX_STANDARD=17: the
    # target's own target_compile_features(cxx_std_14) wins over the global
    # CMAKE_CXX_STANDARD, and because MSVC's default is already C++14 CMake
    # emits no /std: flag at all -- verified via compile_commands.json, which
    # showed no /std: entry when CMAKE_CXX_STANDARD was set. Since nothing else
    # emits a /std: flag, putting it in CMAKE_CXX_FLAGS is unambiguous.
    '-DCMAKE_CXX_STANDARD:STRING=17',
    '-DCMAKE_CXX_STANDARD_REQUIRED:BOOL=ON',
    '-DCMAKE_CXX_EXTENSIONS:BOOL=OFF',
    '-DBMX_MPI:BOOL=ON',
    '-DBMX_MPI_THREAD_MULTIPLE:BOOL=OFF',
    '-DBMX_OMP:BOOL=OFF',
    '-DBMX_GPU_BACKEND:STRING=NONE',
    '-DBMX_HYPRE:BOOL=OFF',
    '-DBMX_CSG:BOOL=OFF',
    '-DAMReX_SPACEDIM:STRING=3',
    "-DMPI_C_INCLUDE_DIRS:PATH=$($BmxTool.MpiInc)",
    "-DMPI_CXX_INCLUDE_DIRS:PATH=$($BmxTool.MpiInc)",
    '-DMPI_C_LIB_NAMES:STRING=msmpi',
    '-DMPI_CXX_LIB_NAMES:STRING=msmpi',
    "-DMPI_msmpi_LIBRARY:FILEPATH=$($BmxTool.MpiLib)",
    # Deviation from the reviewed reference recipe, with cause.
    # The recipe supplies only MPI_<lang>_INCLUDE_DIRS. Under CMake 4.4's
    # FindMPI that variable is an *output* (assembled at Modules/FindMPI.cmake
    # line ~1305) and MPI_<lang>_HEADER_DIR is the cache entry actually listed
    # in MPI_<lang>_REQUIRED_VARS (line ~1966). Supplying only the old name
    # therefore fails with "missing: MPI_C_HEADER_DIR". Both names are passed:
    # the recipe's originals are kept for fidelity, and the header dirs are
    # added so the module's required variable is satisfied.
    # This changes no compiler flag, no build type, and no scientific setting;
    # it only tells FindMPI where the MS-MPI headers already are.
    "-DMPI_C_HEADER_DIR:PATH=$($BmxTool.MpiInc)",
    "-DMPI_CXX_HEADER_DIR:PATH=$($BmxTool.MpiInc)"
)

& $BmxTool.CMake @cmakeArgs
if ($LASTEXITCODE -ne 0) { throw "cmake configure failed with exit code $LASTEXITCODE" }

Write-Host ''
Write-Host "configure OK -> $BuildDir"
