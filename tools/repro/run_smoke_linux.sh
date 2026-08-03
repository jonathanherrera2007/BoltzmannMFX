#!/usr/bin/env bash
# BMX RG-SW — minimal execution smoke test for a Linux build.
#
# Mirrors run_smoke_native_windows.ps1: --describe, init-only, one step, and a
# two-rank launch check. Two-rank is a LAUNCH check only; it is not the
# rank/decomposition invariance study, which is predeclared and owned by C16.
#
# Usage:
#   bash run_smoke_linux.sh [-b <build>] [-o <run root>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR=""
OUT_ROOT=""

while getopts "b:o:" opt; do
  case "$opt" in
    b) BUILD_DIR="$OPTARG" ;;
    o) OUT_ROOT="$OPTARG" ;;
    *) echo "usage: $0 [-b build] [-o out]" >&2; exit 2 ;;
  esac
done

RGSW_ROOT="$(dirname "$(dirname "$SOURCE_DIR")")"
[[ -n "$BUILD_DIR" ]] || BUILD_DIR="$RGSW_ROOT/build/linux-release"
[[ -n "$OUT_ROOT"  ]] || OUT_ROOT="$RGSW_ROOT/runs/linux-smoke"

# shellcheck source=linux_env.sh
source "$SCRIPT_DIR/linux_env.sh"

exe="$BUILD_DIR/bmx"
[[ -x "$exe" ]] || { echo "executable not found: $exe" >&2; exit 1; }
case_dir="$SOURCE_DIR/exec/fungi"
for f in input_fungi fungi_init_cfg.dat; do
  [[ -f "$case_dir/$f" ]] || { echo "missing case input: $case_dir/$f" >&2; exit 1; }
done

echo
echo "executable : $exe"
echo "sha256     : $(sha256sum "$exe" | cut -d' ' -f1)"
echo "run root   : $OUT_ROOT"
echo

rm -rf "$OUT_ROOT"; mkdir -p "$OUT_ROOT"

rc_init=0; rc_step=0; rc_mpi=0

run_stage() {
  local name="$1"; shift
  local needs_case="$1"; shift
  local dir="$OUT_ROOT/$name"
  mkdir -p "$dir"
  if [[ "$needs_case" == "yes" ]]; then
    cp "$case_dir/input_fungi" "$case_dir/fungi_init_cfg.dat" "$dir/"
  fi
  echo "--- $name : $*"
  local start; start=$(date +%s%N)
  local code=0
  ( cd "$dir" && "$@" ) >"$dir/stdout.log" 2>&1 || code=$?
  local ms=$(( ( $(date +%s%N) - start ) / 1000000 ))
  echo "    exit=$code  elapsed=${ms}ms  log=$dir/stdout.log"
  return "$code"
}

run_stage describe   no  "$exe" --describe || true
run_stage max_step_0 yes "$exe" input_fungi bmx.max_step=0 amr.plot_int=-1 amr.check_int=-1 || rc_init=$?
run_stage max_step_1 yes "$exe" input_fungi bmx.max_step=1 amr.plot_int=-1 amr.check_int=-1 || rc_step=$?
run_stage mpi_2rank  yes "$BMX_MPI_LAUNCHER" -n 2 "$exe" input_fungi bmx.max_step=1 amr.plot_int=-1 amr.check_int=-1 || rc_mpi=$?

echo
echo "platform      : $BMX_PLATFORM_DESC"
echo "platform_class: $BMX_PLATFORM_CLASS"

if (( rc_init != 0 || rc_step != 0 || rc_mpi != 0 )); then
  echo "smoke run FAILED (init=$rc_init step=$rc_step mpi=$rc_mpi)" >&2
  exit 1
fi
echo "smoke run OK"
if [[ "$BMX_PLATFORM_CLASS" == "smoke-only" ]]; then
  echo "NOTE: smoke-only platform. Not release evidence."
fi
