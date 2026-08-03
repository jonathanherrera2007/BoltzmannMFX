#!/usr/bin/env bash
# BMX RG-SW — configure a Release / double-precision / CPU / MPI build on Linux.
#
# Deliberately MINIMAL. None of the six Windows workarounds recorded in
# evidence/stages/C02/DEFECTS.md are applied here:
#
#   D-C02-01 /D_USE_MATH_DEFINES   -- g++ defines _GNU_SOURCE, so M_PI is exposed
#   D-C02-02 grep on PATH          -- grep is a base utility on Linux
#   D-C02-03 /EHsc restoration     -- MSVC-specific flag semantics
#   D-C02-04 MPI_*_HEADER_DIR      -- FindMPI resolves normally via mpicxx
#   D-C02-05 /std:c++17 /Zc:lambda -- GCC accepts the constexpr-in-lambda usage
#   D-C02-06 compile_commands copy -- still occurs; it is a source-tree issue
#
# That is the point: whether this configure succeeds unmodified is direct
# evidence about which of those defects are product defects and which are
# Windows-portability defects. Do NOT add a workaround here to make it pass --
# a failure is a finding.
#
# Usage:
#   bash configure_linux.sh [-s <source>] [-b <build>] [-f]     (-f = fresh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR=""
FRESH=0

while getopts "s:b:f" opt; do
  case "$opt" in
    s) SOURCE_DIR="$(cd "$OPTARG" && pwd)" ;;
    b) BUILD_DIR="$OPTARG" ;;
    f) FRESH=1 ;;
    *) echo "usage: $0 [-s source] [-b build] [-f] [-- <extra cmake args>]" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
# Anything after `--` is passed through to CMake verbatim. A reference-host
# qualification run needs -DBMX_REQUIRE_PROVENANCE=ON, and hard-coding that here
# would force it on ordinary development builds too. The option set below is the
# reviewed recipe and is NOT overridable by this mechanism -- extra args are
# appended, so a caller cannot silently change the build type or precision
# without it being visible on the recorded command line.
EXTRA_CMAKE_ARGS=("$@")

[[ -n "$BUILD_DIR" ]] || BUILD_DIR="$(dirname "$(dirname "$SOURCE_DIR")")/build/linux-release"

# shellcheck source=linux_env.sh
source "$SCRIPT_DIR/linux_env.sh"

[[ -f "$SOURCE_DIR/CMakeLists.txt" ]] || { echo "not a BMX source tree: $SOURCE_DIR" >&2; exit 1; }
[[ -f "$SOURCE_DIR/subprojects/amrex/CMakeLists.txt" ]] || {
  echo "AMReX submodule not bound at: $SOURCE_DIR/subprojects/amrex" >&2; exit 1; }

if (( FRESH )) && [[ -d "$BUILD_DIR" ]]; then
  echo "removing existing build directory: $BUILD_DIR"
  rm -rf "$BUILD_DIR"
fi
mkdir -p "$BUILD_DIR"

echo
echo "source : $SOURCE_DIR"
echo "build  : $BUILD_DIR"
echo

# Option set mirrors the reviewed Windows recipe: Release, CPU, MPI on, OMP off,
# no GPU, SPACEDIM 3. Double precision is not an option -- BMXSetupAMReX.cmake
# hard-sets AMReX_PRECISION=DOUBLE and AMReX_PARTICLES_PRECISION=DOUBLE.
"$BMX_CMAKE" \
  -S "$SOURCE_DIR" \
  -B "$BUILD_DIR" \
  -G "$BMX_GENERATOR" \
  -DCMAKE_C_COMPILER="$BMX_CC" \
  -DCMAKE_CXX_COMPILER="$BMX_CXX" \
  -DCMAKE_BUILD_TYPE:STRING=Release \
  -DCMAKE_C_FLAGS_RELEASE:STRING="-O2 -DNDEBUG" \
  -DCMAKE_CXX_FLAGS_RELEASE:STRING="-O2 -DNDEBUG" \
  -DCMAKE_EXPORT_COMPILE_COMMANDS:BOOL=ON \
  -DBMX_MPI:BOOL=ON \
  -DBMX_MPI_THREAD_MULTIPLE:BOOL=OFF \
  -DBMX_OMP:BOOL=OFF \
  -DBMX_GPU_BACKEND:STRING=NONE \
  -DBMX_HYPRE:BOOL=OFF \
  -DBMX_CSG:BOOL=OFF \
  -DAMReX_SPACEDIM:STRING=3 \
  "${EXTRA_CMAKE_ARGS[@]}"

echo
if (( ${#EXTRA_CMAKE_ARGS[@]} )); then
  echo "extra cmake args: ${EXTRA_CMAKE_ARGS[*]}"
fi
echo "configure OK -> $BUILD_DIR"
echo "platform class: $BMX_PLATFORM_CLASS"
