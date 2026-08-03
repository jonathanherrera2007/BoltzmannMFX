#!/usr/bin/env bash
# C10/P12 V2 reference-host qualification and selected-resolution benchmark.

set -euo pipefail

HANDOFF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${1:-}"
if [[ -z "$WORK" ]]; then
  echo "usage: bash qualify_c10.sh /path/to/empty/workdir" >&2
  exit 2
fi
mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd)"
if [[ -e "$WORK/product" ]]; then
  echo "workdir is not empty: $WORK/product exists" >&2
  exit 2
fi

id_value() {
  python3 -c "import json; print(json.load(open('$HANDOFF/IDENTITY.json', encoding='utf-8'))['$1'])"
}
sha_file() { sha256sum "$1" | awk '{print $1}'; }
require_equal() {
  local label="$1" actual="$2" expected="$3"
  if [[ "$actual" != "$expected" ]]; then
    echo "identity failure: $label: got $actual expected $expected" >&2
    exit 1
  fi
}

SOURCE_COMMIT="$(id_value source_commit)"
SOURCE_TREE="$(id_value source_tree)"
AMREX_COMMIT="$(id_value amrex_commit)"
AMREX_TREE="$(id_value amrex_tree)"
KERNEL_SHA="$(id_value frozen_kernel_sha256)"
NUMERICAL_SHA="$(id_value numerical_contract_sha256)"
UPTAKE_SHA="$(id_value scientific_uptake_contract_sha256)"
ORDER_SHA="$(id_value operator_order_sha256)"
REVIEW_SHA="$(id_value review_sha256)"
PRESERVED_V1_OUTCOME_SHA="$(id_value preserved_v1_outcome_sha256)"
RUNNER_SHA="$(id_value runner_sha256)"
EXTRACTOR_SOURCE_SHA="$(id_value extractor_source_sha256)"

cd "$HANDOFF"
sha256sum -c MANIFEST.sha256

mkdir -p "$WORK/logs" "$WORK/results" "$WORK/artifacts" "$WORK/tools"
git clone -q "$HANDOFF/bmx-product.bundle" "$WORK/product"
git -C "$WORK/product" checkout -q --detach "$SOURCE_COMMIT"
rm -rf "$WORK/product/subprojects/amrex"
git clone -q "$HANDOFF/amrex-pinned.bundle" "$WORK/product/subprojects/amrex"
git -C "$WORK/product/subprojects/amrex" checkout -q --detach "$AMREX_COMMIT"

require_equal source_commit "$(git -C "$WORK/product" rev-parse HEAD)" "$SOURCE_COMMIT"
require_equal source_tree "$(git -C "$WORK/product" rev-parse 'HEAD^{tree}')" "$SOURCE_TREE"
require_equal amrex_commit "$(git -C "$WORK/product/subprojects/amrex" rev-parse HEAD)" "$AMREX_COMMIT"
require_equal amrex_tree "$(git -C "$WORK/product/subprojects/amrex" rev-parse 'HEAD^{tree}')" "$AMREX_TREE"
require_equal kernel "$(sha_file "$WORK/product/src/chemistry/bmx_chem_K.H")" "$KERNEL_SHA"
require_equal numerical_contract "$(sha_file "$WORK/product/contracts/p12/NUMERICAL_PREREGISTRATION_V2.json")" "$NUMERICAL_SHA"
require_equal scientific_uptake_contract "$(sha_file "$WORK/product/contracts/p12/UPTAKE_ONLY_CONTRACT_V1.json")" "$UPTAKE_SHA"
require_equal operator_order "$(sha_file "$WORK/product/contracts/p10/OPERATOR_ORDER_V1.json")" "$ORDER_SHA"
require_equal independent_review "$(sha_file "$HANDOFF/INDEPENDENT_NUMERICAL_REVIEW_V2.json")" "$REVIEW_SHA"
require_equal preserved_v1_handoff "$(sha_file "$HANDOFF/P12_48H_GRID_TIME_V1_EXACT.json")" "$PRESERVED_V1_OUTCOME_SHA"
cp "$HANDOFF/P12_48H_GRID_TIME_V1_EXACT.json" \
  "$WORK/product/evidence/stages/C10/P12_48H_GRID_TIME.json"
require_equal preserved_v1_worktree "$(sha_file "$WORK/product/evidence/stages/C10/P12_48H_GRID_TIME.json")" "$PRESERVED_V1_OUTCOME_SHA"
# The frozen V1 hash names the original Windows CRLF result, while the Git blob
# and checkout policy are LF. Refreshing the index through Git's clean filter
# records that the CRLF working copy maps to the unchanged LF blob. Require no
# staged diff: this is a byte-representation overlay, never a source change.
git -C "$WORK/product" add --renormalize -- \
  evidence/stages/C10/P12_48H_GRID_TIME.json
if ! git -C "$WORK/product" diff --cached --quiet; then
  echo "V1 exact-byte overlay changed the Git index" >&2
  exit 1
fi
require_equal outcome_runner "$(sha_file "$WORK/product/tools/repro/run_c10_p12_v2_48h.py")" "$RUNNER_SHA"
require_equal extractor_source "$(sha_file "$WORK/product/tools/repro/c10_plot_extract.cpp")" "$EXTRACTOR_SOURCE_SHA"
if [[ -n "$(git -C "$WORK/product" status --porcelain)" ]]; then
  git -C "$WORK/product" status --porcelain
  echo "source worktree is dirty before build" >&2
  exit 1
fi

set +u
source "$WORK/product/tools/repro/linux_env.sh"
set -u
if [[ "$BMX_PLATFORM_CLASS" != "reference-capable" ]]; then
  echo "host is not reference-capable: $BMX_PLATFORM_CLASS" >&2
  exit 1
fi

bash "$WORK/product/tools/repro/configure_linux.sh" \
  -s "$WORK/product" -b "$WORK/build" -f -- \
  -DBMX_REQUIRE_PROVENANCE=ON \
  2>&1 | tee "$WORK/logs/configure.log"
bash "$WORK/product/tools/repro/build_linux.sh" \
  -b "$WORK/build" -t bmx -j "$(nproc)" \
  2>&1 | tee "$WORK/logs/build.log"

"$WORK/build/bmx" --describe 2>&1 | tee "$WORK/logs/provenance.log"
grep -q "provenance:   RESOLVED" "$WORK/logs/provenance.log"
grep -q "commit:       $SOURCE_COMMIT" "$WORK/logs/provenance.log"
grep -q "worktree:     clean" "$WORK/logs/provenance.log"

mpicxx -std=c++17 -O2 -DNDEBUG \
  -I"$WORK/product/subprojects/amrex/Src/Base" \
  -I"$WORK/product/subprojects/amrex/Src/Boundary" \
  -I"$WORK/product/subprojects/amrex/Src/AmrCore" \
  -I"$WORK/product/subprojects/amrex/Src/EB" \
  -I"$WORK/product/subprojects/amrex/Src/LinearSolvers/MLMG" \
  -I"$WORK/product/subprojects/amrex/Src/Particle" \
  -I"$WORK/build/subprojects/amrex" \
  "$WORK/product/tools/repro/c10_plot_extract.cpp" \
  "$WORK/build/subprojects/amrex/Src/libamrex.a" \
  -pthread -ldl -o "$WORK/tools/c10_plot_extract" \
  2>&1 | tee "$WORK/logs/extractor-build.log"

python3 "$WORK/product/tools/repro/run_c10_static_test.py" \
  --source "$WORK/product" \
  --json-out "$WORK/results/STATIC_REFERENCE.json" \
  2>&1 | tee "$WORK/logs/static.log"

python3 "$WORK/product/tools/repro/run_c10_p12_v2_48h.py" \
  --exe "$WORK/build/bmx" \
  --source "$WORK/product" \
  --extractor "$WORK/tools/c10_plot_extract" \
  --mpiexec "$(command -v mpirun)" \
  --independent-review "$HANDOFF/INDEPENDENT_NUMERICAL_REVIEW_V2.json" \
  --run-root "$WORK/runs/c10-v2-reference" \
  --json-out "$WORK/results/P12_V2_GRID_TIME_REFERENCE.json" \
  2>&1 | tee "$WORK/logs/qualification.log"

python3 "$HANDOFF/benchmark_c10_reference.py" \
  --source "$WORK/product" \
  --exe "$WORK/build/bmx" \
  --mpiexec "$(command -v mpirun)" \
  --run-root "$WORK/runs/c10-selected-timing" \
  --json-out "$WORK/results/REFERENCE_TIMING_AND_PROJECTIONS.json" \
  --repeats 5 \
  2>&1 | tee "$WORK/logs/timing.log"

{
  echo "date_utc=$(date -u +%FT%TZ)"
  echo "hostname=$(hostname)"
  echo "kernel=$(uname -srmo)"
  echo "distro=$(. /etc/os-release && echo "$PRETTY_NAME")"
  echo "filesystem=$(df -PT "$WORK" | awk 'NR==2 {print $2}')"
  echo "machine_type=$(curl -fsS -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/machine-type | awk -F/ '{print $NF}')"
  echo "cpu_platform=$(curl -fsS -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/cpu-platform)"
  echo "zone=$(curl -fsS -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/zone | awk -F/ '{print $NF}')"
  echo "gcc=$(gcc --version | head -1)"
  echo "gxx=$(g++ --version | head -1)"
  echo "cmake=$(cmake --version | head -1)"
  echo "python=$(python3 --version 2>&1)"
  echo "mpicxx=$(mpicxx --showme:command 2>/dev/null || mpicxx -show 2>/dev/null)"
  echo "mpirun=$(mpirun --version | head -1)"
  echo "ninja=$(ninja --version)"
  echo "git=$(git --version)"
  echo "nproc=$(nproc)"
  echo "source_commit=$SOURCE_COMMIT"
  echo "source_tree=$SOURCE_TREE"
  echo "bmx_sha256=$(sha_file "$WORK/build/bmx")"
  echo "extractor_sha256=$(sha_file "$WORK/tools/c10_plot_extract")"
} | tee "$WORK/logs/environment.txt"

tar -czf "$WORK/artifacts/C10_REFERENCE_RAW.tar.gz" \
  -C "$WORK" runs/c10-v2-reference runs/c10-selected-timing
tar -czf "$WORK/artifacts/C10_REFERENCE_EVIDENCE.tar.gz" \
  -C "$WORK" results logs build/CMakeCache.txt build/bmx tools/c10_plot_extract

(
  cd "$WORK"
  sha256sum \
    results/P12_V2_GRID_TIME_REFERENCE.json \
    results/REFERENCE_TIMING_AND_PROJECTIONS.json \
    results/STATIC_REFERENCE.json \
    logs/environment.txt \
    build/CMakeCache.txt build/bmx tools/c10_plot_extract \
    artifacts/C10_REFERENCE_RAW.tar.gz \
    artifacts/C10_REFERENCE_EVIDENCE.tar.gz \
    > artifacts/REFERENCE_MANIFEST.sha256
)
(
  cd "$WORK"
  sha256sum -c artifacts/REFERENCE_MANIFEST.sha256
)

python3 - <<PY
import json
from pathlib import Path
q = json.loads(Path("$WORK/results/P12_V2_GRID_TIME_REFERENCE.json").read_text())
t = json.loads(Path("$WORK/results/REFERENCE_TIMING_AND_PROJECTIONS.json").read_text())
s = json.loads(Path("$WORK/results/STATIC_REFERENCE.json").read_text())
assert q["status"] == "PASS"
assert q["selected_production_grid"] == "L0"
assert q["selected_production_dt_s"] == 1800.0
assert t["status"] == "PASS"
assert s["status"] == "PASS"
print("C10_REFERENCE_HOST_QUALIFICATION PASS")
PY

echo "result=$WORK/results/P12_V2_GRID_TIME_REFERENCE.json"
echo "timing=$WORK/results/REFERENCE_TIMING_AND_PROJECTIONS.json"
echo "manifest=$WORK/artifacts/REFERENCE_MANIFEST.sha256"
