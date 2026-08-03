#!/usr/bin/env bash
# Recover C10 evidence packaging after the original driver verified its
# relative-path manifest from the handoff directory. This never runs outcomes.

set -euo pipefail
WORK="${1:-}"
if [[ -z "$WORK" || ! -d "$WORK/results" ]]; then
  echo "usage: bash finalize_reference.sh /path/to/completed/workdir" >&2
  exit 2
fi
WORK="$(cd "$WORK" && pwd)"
cd "$WORK"

# Prove the initially generated products and archives were intact before any
# repackaging. The original driver failed only because it omitted this cd.
sha256sum -c artifacts/REFERENCE_MANIFEST.sha256 \
  > logs/pre_repack_manifest_verify.log

cp "$HOME/c10-driver.log" logs/driver-final.log
cp "$HOME/c10-driver-attempt1.log" logs/driver-attempt1.log
cp "$HOME/c10-driver-attempt2.log" logs/driver-attempt2.log
if [[ -f "$HOME/c10-work-attempt1/results/STATIC_REFERENCE.json" ]]; then
  cp "$HOME/c10-work-attempt1/results/STATIC_REFERENCE.json" \
    results/ATTEMPT1_STATIC_FAILURE.json
fi

python3 - "$WORK" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

work = Path(sys.argv[1])
qualification_path = work / "results/P12_V2_GRID_TIME_REFERENCE.json"
timing_path = work / "results/REFERENCE_TIMING_AND_PROJECTIONS.json"
static_path = work / "results/STATIC_REFERENCE.json"
qualification = json.loads(qualification_path.read_text())
timing = json.loads(timing_path.read_text())
static = json.loads(static_path.read_text())
checks = {
    "qualification_pass": qualification["status"] == "PASS",
    "selected_grid_l0": qualification["selected_production_grid"] == "L0",
    "selected_dt_1800": qualification["selected_production_dt_s"] == 1800.0,
    "source_commit_exact": qualification["source"]["commit"] ==
        "0f38760b4daba3acbfd4b658c9ac522523b5c69b",
    "timing_pass": timing["status"] == "PASS",
    "static_pass": static["status"] == "PASS",
}
if not all(checks.values()):
    raise SystemExit("completed reference products do not pass final assertions")

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

report = {
    "artifact_type": "C10_REFERENCE_POSTPROCESS_RECOVERY",
    "status": "PASS",
    "checks": checks,
    "qualification_sha256": sha256(qualification_path),
    "timing_sha256": sha256(timing_path),
    "static_sha256": sha256(static_path),
    "postprocess_failure": (
        "The original driver invoked sha256sum -c with a manifest path while "
        "its current directory was the handoff root; relative manifest entries "
        "therefore resolved incorrectly."
    ),
    "recovery_scope": "evidence verification and packaging only",
    "outcomes_rerun": False,
}
(work / "results/FINAL_ASSERTION.json").write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
PY

tar -czf artifacts/C10_REFERENCE_EVIDENCE.tar.gz \
  results logs build/CMakeCache.txt build/bmx tools/c10_plot_extract

{
  find results logs -type f -print0 | sort -z | xargs -0 sha256sum
  sha256sum build/CMakeCache.txt build/bmx tools/c10_plot_extract
  sha256sum artifacts/C10_REFERENCE_RAW.tar.gz
  sha256sum artifacts/C10_REFERENCE_EVIDENCE.tar.gz
} > artifacts/REFERENCE_MANIFEST.sha256

sha256sum -c artifacts/REFERENCE_MANIFEST.sha256 \
  | tee artifacts/REFERENCE_MANIFEST_VERIFY.log
echo "C10_REFERENCE_POSTPROCESS PASS"
