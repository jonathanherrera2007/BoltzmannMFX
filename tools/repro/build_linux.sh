#!/usr/bin/env bash
# BMX RG-SW — build the configured Linux tree and record build identity.
#
# Usage:
#   bash build_linux.sh [-b <build>] [-t <target>] [-j <parallel>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR=""
TARGET="bmx"
PARALLEL=""

while getopts "b:t:j:" opt; do
  case "$opt" in
    b) BUILD_DIR="$OPTARG" ;;
    t) TARGET="$OPTARG" ;;
    j) PARALLEL="$OPTARG" ;;
    *) echo "usage: $0 [-b build] [-t target] [-j parallel]" >&2; exit 2 ;;
  esac
done

[[ -n "$BUILD_DIR" ]] || BUILD_DIR="$(dirname "$(dirname "$SOURCE_DIR")")/build/linux-release"

# shellcheck source=linux_env.sh
source "$SCRIPT_DIR/linux_env.sh"
[[ -n "$PARALLEL" ]] || PARALLEL="$BMX_NPROC"

[[ -f "$BUILD_DIR/CMakeCache.txt" ]] || {
  echo "build directory is not configured (no CMakeCache.txt): $BUILD_DIR" >&2
  echo "Run configure_linux.sh first." >&2
  exit 1; }

echo
echo "build  : $BUILD_DIR"
echo "target : $TARGET"
echo "jobs   : $PARALLEL"
echo

start=$(date +%s)
"$BMX_CMAKE" --build "$BUILD_DIR" --target "$TARGET" --parallel "$PARALLEL"
elapsed=$(( $(date +%s) - start ))

exe="$BUILD_DIR/bmx"
[[ -f "$exe" ]] || { echo "build reported success but $exe is absent" >&2; exit 1; }

hash=$(sha256sum "$exe" | cut -d' ' -f1)
size=$(stat -c%s "$exe")

cat <<EOF

build OK in ${elapsed} s
executable    : $exe
size_bytes    : $size
sha256        : $hash
platform      : $BMX_PLATFORM_DESC
platform_class: $BMX_PLATFORM_CLASS
compiler      : $($BMX_CXX --version | head -1)
EOF

if [[ "$BMX_PLATFORM_CLASS" == "smoke-only" ]]; then
  echo
  echo "NOTE: smoke-only platform. This image and its hash are NOT release evidence."
fi
