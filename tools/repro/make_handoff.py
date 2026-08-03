#!/usr/bin/env python3
"""BMX RG-SW -- generate the C04 reference-host handoff.

Cuts a self-contained, transferable package pinned to the CURRENT HEAD:
two verified git bundles, the entrypoint, a machine-readable identity record,
and a SHA-256 manifest.

Deliberately reproducible from a commit rather than assembled by hand -- an
earlier hand-cut archive was pinned to a commit whose configure_linux.sh lacked
the `--` passthrough that qualify.sh depends on, so the run would have failed on
the reference host at the first configure.

The bundles are DERIVED artefacts and are not committed; this script is.

Usage:
  python tools/repro/make_handoff.py [--out <dir>]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile

PRODUCT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
NAME = "C04_REFERENCE_HOST_HANDOFF"

AMREX_COMMIT = "cbdc6580ee3d78cccdd37172e4ba077ee181f483"
AMREX_TREE = "fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6"


def git(*args, cwd=PRODUCT):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{p.stdout}{p.stderr}")
    return p.stdout.strip()


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(PRODUCT), "..", "handoff"))
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    hd = os.path.join(out, NAME)

    # A dirty tree would produce a handoff whose provenance reports 'dirty' and
    # whose contents do not match any commit. Refuse.
    dirty = [ln for ln in git("status", "--porcelain=v1").splitlines()
             if ln and not ln.startswith("?? ")]
    if dirty:
        raise SystemExit("source tree has uncommitted tracked changes:\n  " +
                         "\n  ".join(dirty) + "\nCommit or stash before cutting a handoff.")

    head = git("rev-parse", "HEAD")
    kernel = sha256(os.path.join(PRODUCT, "src", "chemistry", "bmx_chem_K.H"))

    if os.path.isdir(hd):
        shutil.rmtree(hd)
    os.makedirs(hd)

    print(f"pinning       : {head}")
    print(f"kernel sha256 : {kernel}")

    shutil.copy(os.path.join(PRODUCT, "handoff", "qualify.sh"), hd)
    shutil.copy(os.path.join(PRODUCT, "handoff", "README.md"), hd)

    print("bundling BMX ...")
    git("bundle", "create", os.path.join(hd, "bmx-product.bundle"), "--all")

    # AMReX's ref must live under refs/heads/ or `git clone` sees an empty
    # repository and checks nothing out.
    print("bundling AMReX ...")
    amrex = os.path.join(PRODUCT, "subprojects", "amrex")
    git("update-ref", "refs/heads/bmx-pinned", AMREX_COMMIT, cwd=amrex)
    try:
        git("bundle", "create", os.path.join(hd, "amrex-pinned.bundle"),
            "refs/heads/bmx-pinned", cwd=amrex)
    finally:
        git("update-ref", "-d", "refs/heads/bmx-pinned", cwd=amrex)

    for b in ("bmx-product.bundle", "amrex-pinned.bundle"):
        git("bundle", "verify", os.path.join(hd, b))
        print(f"  verified {b}")

    ident = {
        "handoff": NAME,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "stage_state": "C04 = BLOCKED_REFERENCE_PLATFORM_QUALIFICATION",
        "bmx_commit_to_build": head,
        "chemistry_candidate_commit": "adb427331e180cd0b4faa74a4ab2098381b2eabb",
        "reviewed_kernel_sha256": kernel,
        "canonical_baseline_commit": "389e9e35a1c7291a4af795b2e39f2db1f0012b61",
        "baseline_kernel_sha256":
            "711ae2caa6e7aabb5c084fe841d2d90edb85ee53e7abc7a859d7de00e6614678",
        "diagnostic_repair_commit_D_C04_05": "5481856f46ba4bd2432dd21800fe9dbec8d10a15",
        "provenance_repair_commit_D_C04_08": "8428a5d354025f2a222deae287679bf2e89a4a9b",
        "amrex_commit": AMREX_COMMIT,
        "amrex_tree": AMREX_TREE,
        "amrex_upstream": "https://github.com/AMReX-codes/amrex.git",
        "controlling_contract":
            "contracts/platform/PLATFORM_REFERENCE_DECISION.md (DEC-PLATFORM-001)",
        "classification_gate": "tools/repro/linux_env.sh -> BMX_PLATFORM_CLASS",
        "entrypoint": "bash qualify.sh <workdir>",
        "verdict_file": "<workdir>/runs/c04-qualification/QUALIFICATION_REFERENCE.json",
        "release_evidence_requires": [
            "platform class reference-capable",
            "provenance resolved for all four independently built images",
            "all qualification checks pass",
            "RT-1 verdict with evidence", "RT-2 verdict with evidence",
            "chemistry candidate bytes unchanged"],
        "four_image_slots": ["c03-baseline-release", "c04-p07-release",
                             "c04-baseline-diag-release", "c04-diag-release"],
        "image_reuse_permitted": False,
        "identical_binary_hashes_permitted": True,
        "identical_binary_hashes_note":
            ("two deterministic builds may legitimately produce the same bytes; what is "
             "required is an independent configure and build record per slot"),
    }
    with open(os.path.join(hd, "IDENTITY.json"), "w", newline="\n") as fh:
        json.dump(ident, fh, indent=2, sort_keys=True)

    files = sorted(f for f in os.listdir(hd)
                   if os.path.isfile(os.path.join(hd, f)) and f != "MANIFEST.sha256")
    with open(os.path.join(hd, "MANIFEST.sha256"), "w", newline="\n") as m:
        for f in files:
            m.write(f"{sha256(os.path.join(hd, f))}  {f}\n")

    tgz = os.path.join(out, NAME + ".tar.gz")
    for p in (tgz, tgz + ".sha256"):
        if os.path.exists(p):
            os.remove(p)
    with tarfile.open(tgz, "w:gz") as tf:
        tf.add(hd, arcname=NAME)
    digest = sha256(tgz)
    with open(tgz + ".sha256", "w", newline="\n") as fh:
        fh.write(f"{digest}  {NAME}.tar.gz\n")

    print("\nmanifest:")
    print(open(os.path.join(hd, "MANIFEST.sha256")).read().rstrip())
    print(f"\narchive : {tgz}")
    print(f"size    : {os.path.getsize(tgz):,} bytes")
    print(f"sha256  : {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
