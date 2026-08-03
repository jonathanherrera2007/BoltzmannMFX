#!/usr/bin/env bash
# BMX RG-SW — Linux toolchain resolution and platform classification.
#
# Source this file. It resolves every required tool, fails loudly on any
# absence, and — importantly — classifies the host as REFERENCE-CAPABLE or not.
#
# Platform policy
# ---------------
# WSL 1 is a syscall translation layer, not a Linux kernel. AMReX and MPI
# behaviour there is not equivalent to a real kernel, and /mnt/c (DrvFs) has
# different I/O and file-locking semantics. WSL1 is therefore usable as a
# PORTABILITY SMOKE platform only, and must never carry release evidence.
# This script refuses to silently pretend otherwise: it sets
# BMX_PLATFORM_CLASS to 'reference-capable' or 'smoke-only' and every script
# that consumes it is expected to stamp that into its output.
#
# Exports: BMX_CC BMX_CXX BMX_CMAKE BMX_NPROC BMX_PLATFORM_CLASS
#          BMX_PLATFORM_DESC BMX_MPI_LAUNCHER

set -euo pipefail

_require() {
  local tool="$1" what="$2"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "required build prerequisite is absent: $what ($tool)" >&2
    return 1
  fi
  command -v "$tool"
}

BMX_CC=$(_require gcc      "C compiler")
BMX_CXX=$(_require g++     "C++ compiler")
BMX_CMAKE=$(_require cmake "CMake")
_require make  "make"        >/dev/null || true
_require mpicxx "MPI C++ wrapper" >/dev/null
BMX_MPI_LAUNCHER=$(_require mpirun "MPI launcher")

# Ninja is preferred but not mandatory; fall back to Unix Makefiles.
if command -v ninja >/dev/null 2>&1; then
  BMX_GENERATOR="Ninja"
else
  BMX_GENERATOR="Unix Makefiles"
fi

BMX_NPROC=$(nproc)

# --- platform classification -------------------------------------------------
_kernel=$(uname -r)
_distro=$( . /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown}" )

if grep -qi microsoft /proc/version 2>/dev/null; then
  # WSL2 reports a real kernel version (5.x/6.x with 'microsoft-standard');
  # WSL1 reports the 4.4.0-*-Microsoft shim.
  if [[ "$_kernel" == *microsoft-standard* ]] || [[ "$_kernel" =~ ^[5-9]\. ]] || [[ "$_kernel" =~ ^[1-9][0-9]\. ]]; then
    BMX_PLATFORM_CLASS="reference-capable"
    BMX_PLATFORM_DESC="WSL2 / $_distro / kernel $_kernel"
  else
    BMX_PLATFORM_CLASS="smoke-only"
    BMX_PLATFORM_DESC="WSL1 (syscall translation layer, NOT a kernel) / $_distro / kernel $_kernel"
  fi
else
  BMX_PLATFORM_CLASS="reference-capable"
  BMX_PLATFORM_DESC="native Linux / $_distro / kernel $_kernel"
fi

# Building on a DrvFs mount is slow and has different locking semantics; warn
# even on a reference-capable host.
_srcfs=$(df -PT . 2>/dev/null | awk 'NR==2{print $2}')
if [[ "${_srcfs:-}" == "9p" || "${_srcfs:-}" == "drvfs" ]]; then
  BMX_PLATFORM_DESC="$BMX_PLATFORM_DESC / WARNING: working tree is on $_srcfs (Windows drive mount)"
fi

export BMX_CC BMX_CXX BMX_CMAKE BMX_NPROC BMX_GENERATOR
export BMX_PLATFORM_CLASS BMX_PLATFORM_DESC BMX_MPI_LAUNCHER

cat <<EOF
platform      : $BMX_PLATFORM_DESC
class         : $BMX_PLATFORM_CLASS
compiler      : $($BMX_CXX --version | head -1)
cmake         : $($BMX_CMAKE --version | head -1)
mpi           : $(mpicxx -show 2>/dev/null | head -1 || echo "(mpicxx present)")
generator     : $BMX_GENERATOR
nproc         : $BMX_NPROC
EOF

if [[ "$BMX_PLATFORM_CLASS" == "smoke-only" ]]; then
  cat <<'EOF'

*** SMOKE-ONLY PLATFORM ***
This host may be used to shake out portability problems. Its output must NOT
be used as release evidence, must not be labelled a reference build, and must
not satisfy any C16 acceptance row.
EOF
fi
