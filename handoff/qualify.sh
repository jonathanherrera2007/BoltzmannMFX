#!/usr/bin/env bash
# BMX RG-SW -- C04 reference-host qualification entrypoint.
#
# ONE COMMAND. Unpacks the handoff, verifies identity, builds all four image
# variants independently in four separate build directories, and runs the
# complete C04 qualification sequence.
#
#   bash qualify.sh /path/to/workdir
#
# It refuses to continue if the host is not reference-capable under
# DEC-PLATFORM-001, because a smoke-only host cannot produce the evidence this
# run exists to produce. Use --allow-smoke ONLY to rehearse the mechanics; the
# output is then explicitly not release evidence and the driver will say so.

set -euo pipefail

WORK="${1:-}"
ALLOW_SMOKE=0
for a in "$@"; do [ "$a" = "--allow-smoke" ] && ALLOW_SMOKE=1; done
if [ -z "$WORK" ] || [ "$WORK" = "--allow-smoke" ]; then
  echo "usage: bash qualify.sh <workdir> [--allow-smoke]" >&2; exit 2
fi

HANDOFF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Identity is READ from IDENTITY.json, not hard-coded here.
#
# Hard-coding the BMX commit in this file is self-referential: committing the
# script changes HEAD, so the pinned value is always one commit stale. Reading
# it from a sibling file that the SHA-256 manifest covers removes the
# circularity and keeps the value tamper-evident -- step 0 verifies the
# manifest before this file is trusted.
_id() { python3 -c "import json,sys; print(json.load(open('$HANDOFF/IDENTITY.json'))['$1'])"; }
BMX_COMMIT=$(_id bmx_commit_to_build)
AMREX_COMMIT=$(_id amrex_commit)
AMREX_TREE=$(_id amrex_tree)
KERNEL_SHA=$(_id reviewed_kernel_sha256)
BASELINE_COMMIT=$(_id canonical_baseline_commit)
DIAG_COMMIT=$(_id diagnostic_repair_commit_D_C04_05)
PROV_COMMIT=$(_id provenance_repair_commit_D_C04_08)
BASELINE_KERNEL_SHA=$(_id baseline_kernel_sha256)

say() { printf '\n=== %s ===\n' "$*"; }
die() { printf '\nFATAL: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
say "0. verify the handoff itself"
cd "$HANDOFF"
sha256sum -c MANIFEST.sha256 || die "handoff manifest does not verify -- do not proceed"
echo "handoff manifest OK"

# ---------------------------------------------------------------------------
say "1. unpack to a clean workspace"
mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd)"
[ -e "$WORK/product" ] && die "$WORK/product already exists; start from an empty workdir"

git clone -q "$HANDOFF/bmx-product.bundle" "$WORK/product"
cd "$WORK/product"
git checkout -q "$BMX_COMMIT"
git clone -q "$HANDOFF/amrex-pinned.bundle" "$WORK/amrex-src"
git -C "$WORK/amrex-src" checkout -q "$AMREX_COMMIT"
rm -rf subprojects/amrex
mkdir -p subprojects
cp -a "$WORK/amrex-src" subprojects/amrex

# ---------------------------------------------------------------------------
say "2. verify identity before building anything"
[ "$(git rev-parse HEAD)" = "$BMX_COMMIT" ] || die "BMX commit mismatch"
[ "$(git -C subprojects/amrex rev-parse HEAD)" = "$AMREX_COMMIT" ] || die "AMReX commit mismatch"
[ "$(git -C subprojects/amrex rev-parse 'HEAD^{tree}')" = "$AMREX_TREE" ] || die "AMReX tree mismatch"
K=$(sha256sum src/chemistry/bmx_chem_K.H | cut -d' ' -f1)
[ "$K" = "$KERNEL_SHA" ] || die "chemistry kernel hash mismatch: got $K"
# A clean tree is a precondition: a dirty tree makes provenance report 'dirty'
# and the artefact is then not attributable to a commit alone.
[ -z "$(git status --porcelain=v1)" ] || { git status --porcelain=v1; die "source tree is not clean"; }
echo "BMX commit     : $BMX_COMMIT"
echo "AMReX commit   : $AMREX_COMMIT"
echo "AMReX tree     : $AMREX_TREE"
echo "kernel sha256  : $K  (matches reviewed candidate)"
echo "source tree    : clean"

# ---------------------------------------------------------------------------
say "3. classify the host"
set +u; source tools/repro/linux_env.sh; set -u
echo "BMX_PLATFORM_CLASS=$BMX_PLATFORM_CLASS"
if [ "$BMX_PLATFORM_CLASS" != "reference-capable" ] && [ "$ALLOW_SMOKE" -eq 0 ]; then
  die "host classifies as '$BMX_PLATFORM_CLASS', not 'reference-capable' under DEC-PLATFORM-001.
This run would not produce release evidence. Re-run with --allow-smoke only to
rehearse the mechanics."
fi

# ---------------------------------------------------------------------------
# Four INDEPENDENT configures and builds, four separate build directories.
# No image may be reused for another slot: each has its own configuration and
# build record. Two deterministic builds may legitimately produce identical
# bytes -- that is fine; substitution is not.
say "4. build four variants independently"

# Each baseline-chemistry tree is the canonical baseline PLUS the two
# integrator-owned instrumentation commits, cherry-picked. Two reasons, both
# learned from the first reference-host attempt:
#
#   1. The pristine baseline 389e9e35 predates C02 and has no tools/repro at
#      all -- its tools/ contains only C++, CMake, CMakeLists.txt and DEBUG.
#      Invoking "$src/tools/repro/configure_linux.sh" against it fails with
#      "No such file or directory". The build scripts therefore always come
#      from the PRODUCT tree, with -s pointing at the tree being built.
#   2. The pristine baseline also predates D-C04-08, so it cannot report build
#      provenance at all -- which would make the pass criterion "provenance is
#      resolved and exact for all four images" unsatisfiable by construction.
#
# The instrumentation is behaviour-neutral (G0 and the diagnostic-neutrality
# check both show no trajectory change) and bmx.print_sums defaults OFF, so an
# instrumented tree with the flag unset behaves exactly as the pristine one
# while remaining attributable to a commit. The chemistry hash is asserted at
# the baseline value below, so "baseline chemistry" is verified, not assumed.
make_baseline_tree() {
  local dst="$1"
  git clone -q "$HANDOFF/bmx-product.bundle" "$dst"
  git -C "$dst" checkout -q "$BASELINE_COMMIT"
  git -C "$dst" -c user.name=handoff -c user.email=h@h cherry-pick -n \
      "$DIAG_COMMIT" "$PROV_COMMIT"
  local bk
  bk=$(sha256sum "$dst/src/chemistry/bmx_chem_K.H" | cut -d' ' -f1)
  [ "$bk" = "$BASELINE_KERNEL_SHA" ] \
    || die "baseline chemistry drifted in $dst: $bk"
  # The checkout leaves an EMPTY subprojects/amrex submodule placeholder, and
  # `cp -a src dst` with an existing dst copies INTO it, producing
  # subprojects/amrex/amrex. Remove it first, exactly as the product tree does.
  # COMMIT the cherry-pick. Leaving it staged makes the tree dirty, so the
  # image reports commit 389e9e35 while actually containing the instrumentation
  # -- an artefact whose reported commit does not describe its own bytes. That
  # is precisely the misattribution D-C04-08 exists to prevent, and it fails the
  # "provenance resolved AND EXACT" criterion.
  #
  # Author, committer and both dates are pinned so the resulting commit hash is
  # a deterministic function of the two parent commits and the tree: the same
  # construction on any host yields the same hash, and the image is attributable
  # to it.
  GIT_AUTHOR_DATE="2000-01-01T00:00:00+0000" \
  GIT_COMMITTER_DATE="2000-01-01T00:00:00+0000" \
  git -C "$dst" -c user.name="BMX handoff" -c user.email="handoff@bmx.invalid" \
      commit -q -m "baseline chemistry + integrator instrumentation (deterministic handoff construction)"
  [ -z "$(git -C "$dst" status --porcelain=v1)" ] \
    || die "baseline tree $dst is still dirty after commit"

  rm -rf "$dst/subprojects/amrex"
  mkdir -p "$dst/subprojects"
  cp -a subprojects/amrex "$dst/subprojects/amrex"
  [ -f "$dst/subprojects/amrex/CMakeLists.txt" ] \
    || die "AMReX not correctly vendored into $dst"
}

# Two SEPARATE baseline trees and two separate product build directories: four
# independent configure+build records, no image reused for another slot. The
# resulting binaries may legitimately share bytes; substitution is what is
# forbidden, not determinism.
BASE="$WORK/baseline-src"
BASEDIAG="$WORK/baseline-diag-src"
make_baseline_tree "$BASE"
make_baseline_tree "$BASEDIAG"

mkdir -p "$WORK/build" "$WORK/runs" "$WORK/logs"
CFG="$WORK/product/tools/repro/configure_linux.sh"
BLD="$WORK/product/tools/repro/build_linux.sh"

build_one() {
  local name="$1" src="$2"
  local bd="$WORK/build/$name"
  say "  configure+build $name"
  ( bash "$CFG" -s "$src" -b "$bd" -f -- -DBMX_REQUIRE_PROVENANCE=ON ) 2>&1 \
      | tee "$WORK/logs/$name.configure.log"
  ( bash "$BLD" -b "$bd" ) 2>&1 | tee "$WORK/logs/$name.build.log"
  [ -x "$bd/bmx" ] || die "$name did not produce a binary"
  sha256sum "$bd/bmx" | tee -a "$WORK/logs/image-hashes.txt"
  # Every image must report a resolved source commit. Fail loudly if not:
  # an unattributable image cannot carry release evidence.
  ( cd "$bd" && ./bmx --describe 2>&1 | grep -E "BMX +(provenance|commit|branch|worktree)" ) \
      | tee "$WORK/logs/$name.provenance.log"
  grep -q "provenance:   RESOLVED" "$WORK/logs/$name.provenance.log" \
    || die "$name did not report RESOLVED provenance"
  echo "$name chemistry: $(sha256sum "$src/src/chemistry/bmx_chem_K.H" | cut -d' ' -f1)" \
      | tee -a "$WORK/logs/image-chemistry.txt"
}
build_one c03-baseline-release        "$BASE"
build_one c04-p07-release             "$WORK/product"
build_one c04-baseline-diag-release   "$BASEDIAG"
build_one c04-diag-release            "$WORK/product"

# ---------------------------------------------------------------------------
say "5. provenance fails closed"
# Prove the negative: a tree whose provenance cannot be established must abort
# configuration rather than emit an unattributable artefact.
FC="$WORK/failclosed"; rm -rf "$FC"; mkdir -p "$FC"
printf 'gitdir: Q:/definitely/not/here/.git/worktrees/nope\n' > "$FC/.git"
cat > "$FC/CMakeLists.txt" <<CMEOF
cmake_minimum_required(VERSION 3.14)
project(failclosed LANGUAGES NONE)
list(APPEND CMAKE_MODULE_PATH "$WORK/product/tools/CMake")
include(BMX_Provenance)
option(BMX_REQUIRE_PROVENANCE "" OFF)
bmx_resolve_provenance("\${CMAKE_CURRENT_SOURCE_DIR}")
if(BMX_REQUIRE_PROVENANCE)
  bmx_require_provenance()
endif()
CMEOF
if cmake -S "$FC" -B "$FC/b" -DBMX_REQUIRE_PROVENANCE=ON >"$WORK/logs/failclosed.log" 2>&1; then
  die "provenance did NOT fail closed -- an unattributable build would be possible"
fi
echo "fail-closed verified (configure aborted as required)"

# ---------------------------------------------------------------------------
say "6. run the complete C04 qualification sequence"
cd "$WORK/product"
python3 tools/repro/run_c04_qualification.py \
  --rgsw-root "$WORK" --skip-build \
  --json-out "$WORK/runs/c04-qualification/QUALIFICATION_REFERENCE.json" \
  2>&1 | tee "$WORK/logs/qualification.log"

# ---------------------------------------------------------------------------
say "7. environment capture"
{
  echo "date_utc      : $(date -u +%FT%TZ)"
  echo "host          : $(uname -n)"
  echo "kernel        : $(uname -srmo)"
  echo "arch          : $(uname -m)"
  echo "distro        : $( . /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" )"
  echo "platform_class: ${BMX_PLATFORM_CLASS}"
  echo "gcc           : $(gcc --version | head -1)"
  echo "g++           : $(g++ --version | head -1)"
  echo "cmake         : $(cmake --version | head -1)"
  echo "python3       : $(python3 --version 2>&1)"
  echo "mpicxx        : $(mpicxx -show 2>/dev/null | head -1)"
  echo "mpirun        : $(mpirun --version 2>&1 | head -1)"
  echo "ninja         : $(ninja --version 2>/dev/null || echo absent)"
  echo "git           : $(git --version)"
  echo "nproc         : $(nproc)"
  echo "filesystem    : $(df -PT "$WORK" | awk 'NR==2{print $2}')"
} | tee "$WORK/logs/environment.txt"

say "done"
echo "evidence  : $WORK/runs/c04-qualification/QUALIFICATION_REFERENCE.json"
echo "logs      : $WORK/logs/"
echo
echo "Read release_evidence in the JSON. It is true only if the host is"
echo "reference-capable, provenance resolved, and every check passed."
