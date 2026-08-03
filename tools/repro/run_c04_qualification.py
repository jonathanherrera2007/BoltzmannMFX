#!/usr/bin/env python3
"""BMX RG-SW -- complete clean C04 qualification sequence.

Runs the whole sequence in order from a clean workspace, on any platform, and
stamps the platform class into its output so smoke-only results can never be
mistaken for release evidence.

  0  identity      reviewed candidate kernel hash, AMReX commit/tree, provenance
  1  build         baseline, candidate, and both instrumented images
  2  geometry      7-fixture matrix + G0 observation-neutrality
  3  diagnostic    ComputeAndPrintSums regression guard (5 checks)
  4  donor cap     k1 sweep, saturation, exact-equality assertion (M3)
  5  provenance    D-C04-08 regression fixture (7 checks)

PLATFORM CLASSIFICATION IS NOT ADVISORY. tools/repro/linux_env.sh classifies a
Linux host `reference-capable` or `smoke-only`, per the C02 policy that WSL1 is
a syscall translation layer and "must never carry release evidence". This
driver reads that classification and refuses to emit
`release_evidence: true` unless the host is reference-capable AND provenance
resolved AND every check passed. There is no flag to override it.

Usage:
  python run_c04_qualification.py --rgsw-root <root> [--skip-build]
        [--json-out <path>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PRODUCT = os.path.abspath(os.path.join(HERE, "..", ".."))

EXPECTED_KERNEL_SHA = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
EXPECTED_BASELINE_KERNEL_SHA = "711ae2caa6e7aabb5c084fe841d2d90edb85ee53e7abc7a859d7de00e6614678"
EXPECTED_AMREX_COMMIT = "cbdc6580ee3d78cccdd37172e4ba077ee181f483"
EXPECTED_AMREX_TREE = "fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6"


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("timeout", 3600)
    return subprocess.run(cmd, **kw)


def classify_platform():
    """Read the platform class the C02 policy assigns to this host."""
    if os.name == "nt":
        return ("windows-development",
                f"Windows / {platform.platform()}",
                "Windows is the development platform; DEC-PLATFORM-001 names Linux as reference")
    env = os.path.join(HERE, "linux_env.sh")
    if not os.path.exists(env):
        return ("unknown", platform.platform(), "linux_env.sh not found")
    p = run(["bash", "-c", f'source "{env}" >/dev/null 2>&1; '
                           f'echo "$BMX_PLATFORM_CLASS"; echo "$BMX_PLATFORM_DESC"'])
    lines = [x for x in p.stdout.splitlines() if x.strip()]
    cls = lines[0].strip() if lines else "unknown"
    desc = lines[1].strip() if len(lines) > 1 else platform.platform()
    return (cls, desc, "classification from tools/repro/linux_env.sh")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rgsw-root", required=True)
    ap.add_argument("--skip-build", action="store_true",
                    help="reuse existing images instead of rebuilding")
    ap.add_argument("--json-out")
    a = ap.parse_args()

    root = os.path.abspath(a.rgsw_root)
    runs = os.path.join(root, "runs")
    case = os.path.join(PRODUCT, "exec", "fungi")
    exe = "bmx.exe" if os.name == "nt" else "bmx"

    steps, failures = [], []

    def record(name, ok, detail, extra=None):
        e = {"step": name, "status": "PASS" if ok else "FAIL", "detail": detail}
        if extra:
            e.update(extra)
        steps.append(e)
        if not ok:
            failures.append(name)
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    cls, desc, why = classify_platform()
    print("=" * 78)
    print("BMX RG-SW -- C04 qualification sequence")
    print(f"platform      : {desc}")
    print(f"platform class: {cls}   ({why})")
    if cls != "reference-capable":
        print("\n*** THIS HOST IS NOT REFERENCE-CAPABLE ***")
        print("Results below are portability evidence only and must not be recorded")
        print("as release evidence, regardless of whether every check passes.")
    print("=" * 78 + "\n")

    # ---- 0. identity -------------------------------------------------------
    kern = sha256(os.path.join(PRODUCT, "src", "chemistry", "bmx_chem_K.H"))
    record("identity_reviewed_candidate_kernel", kern == EXPECTED_KERNEL_SHA,
           f"{kern[:16]}... {'matches' if kern == EXPECTED_KERNEL_SHA else 'DOES NOT MATCH'} "
           f"the reviewed candidate", {"sha256": kern, "expected": EXPECTED_KERNEL_SHA})

    amrex = os.path.join(PRODUCT, "subprojects", "amrex")
    ac = run(["git", "-C", amrex, "rev-parse", "HEAD"]).stdout.strip()
    at = run(["git", "-C", amrex, "rev-parse", "HEAD^{tree}"]).stdout.strip()
    record("identity_amrex", ac == EXPECTED_AMREX_COMMIT and at == EXPECTED_AMREX_TREE,
           f"commit {ac[:12]}, tree {at[:12]}", {"commit": ac, "tree": at})

    prov = run([shutil.which("cmake") or "cmake",
                f"-DBMX_PROVENANCE_PROBE={PRODUCT}", "-P",
                os.path.join(PRODUCT, "tools", "CMake", "BMX_Provenance.cmake")])
    pv = dict(ln.split("=", 1) for ln in
              (x[3:] for x in (prov.stdout + prov.stderr).splitlines() if x.startswith("-- BMX_"))
              if "=" in ln)
    resolved = pv.get("BMX_PROVENANCE_STATUS") == "RESOLVED"
    record("identity_build_provenance", resolved,
           f"status={pv.get('BMX_PROVENANCE_STATUS')} commit={pv.get('BMX_GIT_COMMIT','')[:12]} "
           f"dirty={pv.get('BMX_GIT_DIRTY')}", {"provenance": pv})

    # ---- 1. build ----------------------------------------------------------
    images = {
        "baseline":      os.path.join(root, "build", "c03-baseline-release", exe),
        "candidate":     os.path.join(root, "build", "c04-p07-release", exe),
        "baseline_diag": os.path.join(root, "build", "c04-baseline-diag-release", exe),
        "candidate_diag": os.path.join(root, "build", "c04-diag-release", exe),
    }
    if a.skip_build:
        missing = [k for k, v in images.items() if not os.path.exists(v)]
        record("build_images_present", not missing,
               "reused existing images" if not missing else f"missing: {missing}",
               {"images": {k: (sha256(v) if os.path.exists(v) else None)
                           for k, v in images.items()}})
    else:
        record("build_images_present", False,
               "--skip-build not given; this driver does not rebuild. Build with "
               "configure_linux.sh/build_linux.sh (or the native_windows scripts), then re-run "
               "with --skip-build.")

    have = {k: v for k, v in images.items() if os.path.exists(v)}

    # ---- 1b. per-image provenance --------------------------------------------
    # The identity step above checks the provenance of the SOURCE TREE this
    # driver runs in. That is not the same question as whether each built IMAGE
    # is attributable. A reference-host run caught two images reporting commit
    # 389e9e35 while their trees were dirty with uncommitted instrumentation --
    # resolved, but not EXACT, and release_evidence was still emitted true.
    # Every image is now interrogated directly.
    per_image, bad_img = {}, []
    for k, v in have.items():
        d = run([v, "--describe"], cwd=os.path.dirname(v))
        txt = d.stdout + d.stderr
        st = re.search(r"BMX\s+provenance:\s+(\S+)", txt)
        cm = re.search(r"BMX\s+commit:\s+(\S+)", txt)
        wt = re.search(r"BMX\s+worktree:\s+(\S+)", txt)
        rec = {"status": st.group(1) if st else None,
               "commit": cm.group(1) if cm else None,
               "worktree": wt.group(1) if wt else None,
               "sha256": sha256(v)}
        per_image[k] = rec
        if rec["status"] != "RESOLVED" or rec["worktree"] != "clean"            or not rec["commit"] or len(rec["commit"]) != 40:
            bad_img.append(k)
    record("per_image_provenance_resolved_and_exact", not bad_img,
           ("all four images report RESOLVED provenance on a clean tree"
            if not bad_img else
            f"not exact for: {bad_img} -- a dirty tree means the reported commit "
            f"does not describe the bytes that were built"),
           {"images": per_image})

    # ---- 2. geometry matrix -----------------------------------------------
    if "baseline" in have and "candidate" in have:
        out = os.path.join(runs, "c04-p07-geometry")
        js = os.path.join(out, "GEOMETRY_INDEX.json")
        p = run([sys.executable, os.path.join(HERE, "run_p07_geometry_fixtures.py"),
                 "--baseline-exe", have["baseline"], "--repaired-exe", have["candidate"],
                 "--case-dir", case, "--out-dir", out, "--json-out", js])
        ok = p.returncode == 0 and os.path.exists(js)
        g = json.load(open(js)) if os.path.exists(js) else {}
        record("geometry_matrix", ok,
               f"{len(g.get('fixtures', []))} fixtures, failing={g.get('failing')}, "
               f"neutrality={g.get('ascii_neutrality')}",
               {"index": js})
    else:
        record("geometry_matrix", False, "baseline/candidate images unavailable")

    # ---- 3. diagnostic guard ----------------------------------------------
    if "candidate_diag" in have:
        wd = os.path.join(runs, "c04-diag-check")
        js = os.path.join(wd, "DIAGNOSTIC_CHECKS.json")
        p = run([sys.executable, os.path.join(HERE, "check_sums_diagnostic.py"),
                 "--exe", have["candidate_diag"], "--case-dir", case,
                 "--work-dir", wd, "--json-out", js])
        d = json.load(open(js)) if os.path.exists(js) else {}
        record("diagnostic_regression_guard", p.returncode == 0,
               f"{sum(1 for c in d.get('checks', []) if c['status'] == 'PASS')}/"
               f"{len(d.get('checks', []))} checks", {"index": js})
    else:
        record("diagnostic_regression_guard", False, "instrumented candidate image unavailable")

    # ---- 4. donor cap ------------------------------------------------------
    if "baseline_diag" in have and "candidate_diag" in have:
        out = os.path.join(runs, "c04-p07-donor-cap-fixture")
        js = os.path.join(out, "DONOR_CAP_FIXTURE.json")
        p = run([sys.executable, os.path.join(HERE, "run_p07_donor_cap_fixture.py"),
                 "--baseline-exe", have["baseline_diag"], "--repaired-exe", have["candidate_diag"],
                 "--case-dir", case, "--out-dir", out, "--json-out", js])
        c = json.load(open(js)) if os.path.exists(js) else {}
        record("donor_cap_fixture", p.returncode == 0,
               f"verdict={c.get('verdict')}, saturation={c.get('saturation_observed')}, "
               f"transfer_equals_available={c.get('transfer_equals_available')}",
               {"index": js})
    else:
        record("donor_cap_fixture", False, "instrumented image pair unavailable")

    # ---- 5. provenance fixture --------------------------------------------
    wd = os.path.join(runs, "c04-provenance-check")
    js = os.path.join(wd, "PROVENANCE_CHECKS.json")
    p = run([sys.executable, os.path.join(HERE, "check_build_provenance.py"),
             "--source-dir", PRODUCT, "--work-dir", wd, "--json-out", js])
    d = json.load(open(js)) if os.path.exists(js) else {}
    record("provenance_regression_fixture", p.returncode == 0,
           f"{sum(1 for c in d.get('checks', []) if c['status'] == 'PASS')}/"
           f"{len(d.get('checks', []))} checks", {"index": js})

    # ---- verdict -----------------------------------------------------------
    all_passed = not failures
    reference_capable = cls == "reference-capable"
    release_evidence = bool(all_passed and reference_capable and resolved)

    reasons = []
    if not all_passed:
        reasons.append(f"failed steps: {failures}")
    if not reference_capable:
        reasons.append(f"platform class is '{cls}', not 'reference-capable' "
                       f"(RT-1 unsatisfied)")
    if not resolved:
        reasons.append("build provenance UNAVAILABLE (RT-2 unsatisfied)")

    print("\n" + "=" * 78)
    print(f"checks passed        : {len(steps) - len(failures)}/{len(steps)}")
    print(f"platform class       : {cls}")
    print(f"RELEASE EVIDENCE     : {release_evidence}")
    if not release_evidence:
        for r in reasons:
            print(f"  - {r}")
    print("=" * 78)

    out = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "platform_class": cls, "platform": desc, "classification_source": why,
        "reference_capable": reference_capable,
        "all_checks_passed": all_passed,
        "provenance_resolved": resolved,
        "release_evidence": release_evidence,
        "not_release_evidence_because": reasons,
        "steps": steps, "failures": failures,
    }
    if a.json_out:
        os.makedirs(os.path.dirname(a.json_out), exist_ok=True)
        with open(a.json_out, "w") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
        print(f"wrote {a.json_out}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
