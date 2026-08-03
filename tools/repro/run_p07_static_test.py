#!/usr/bin/env python3
"""BMX RG-SW - C04: run the SUPPLIED P07 static test suite, unmodified.

The supplied test resolves its inputs as::

    ROOT = Path(__file__).resolve().parents[1]
    BASELINE = ROOT / "baseline" / "src" / "chemistry" / "bmx_chem_K.H"
    CANDIDATE = ROOT / "src"      / "chemistry" / "bmx_chem_K.H"

so it needs a two-tree layout. Rather than committing a duplicate copy of the
2,908-line baseline kernel into the product tree, this harness materialises the
baseline straight from Git (`git show <commit>:<path>`) into a temporary
directory, drops the current candidate beside it, and runs the supplied test
file byte-for-byte as provided.

The test file's SHA-256 is verified before execution, so a silently altered
"passing" suite cannot masquerade as the reviewed one.

Usage:
  python run_p07_static_test.py [--product <worktree>] [--package <planning-package>]
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE_COMMIT = "389e9e35a1c7291a4af795b2e39f2db1f0012b61"
KERNEL_REL = "src/chemistry/bmx_chem_K.H"

EXPECTED = {
    "test":      "25945b64695553d19dcad65b17eeaf6fd5fc5d9a4606daae03ab501ce11e2f52",
    "baseline":  "711ae2caa6e7aabb5c084fe841d2d90edb85ee53e7abc7a859d7de00e6614678",
    "candidate": "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02",
}


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", type=Path, default=here.parents[2])
    ap.add_argument("--package", type=Path,
                    default=here.parents[4] / "planning-package")
    args = ap.parse_args()

    product = args.product.resolve()
    test_src = (args.package / "03_EXISTING_WORK" / "P07"
                / "test_p07_carbon_patch.py").resolve()

    if not test_src.is_file():
        print(f"FAIL: supplied static test not found: {test_src}")
        return 2

    test_bytes = test_src.read_bytes()
    got = sha256(test_bytes)
    if got != EXPECTED["test"]:
        print("FAIL: supplied static test does not match its reviewed hash")
        print(f"  expected {EXPECTED['test']}")
        print(f"  actual   {got}")
        return 2
    print(f"static test sha256 OK : {got}")

    # Baseline from Git, not from the working tree, so a dirty or renamed
    # baseline worktree cannot influence the comparison.
    baseline_bytes = subprocess.run(
        ["git", "-C", str(product), "show", f"{BASELINE_COMMIT}:{KERNEL_REL}"],
        capture_output=True, check=True).stdout
    got = sha256(baseline_bytes)
    if got != EXPECTED["baseline"]:
        print(f"FAIL: baseline kernel from git is {got}, expected {EXPECTED['baseline']}")
        return 2
    print(f"baseline sha256 OK    : {got}")

    candidate_path = product / KERNEL_REL
    candidate_bytes = candidate_path.read_bytes()
    got = sha256(candidate_bytes)
    if got != EXPECTED["candidate"]:
        print(f"FAIL: candidate kernel is {got}, expected {EXPECTED['candidate']}")
        return 2
    print(f"candidate sha256 OK   : {got}")

    with tempfile.TemporaryDirectory(prefix="p07_static_") as tmp:
        root = Path(tmp)
        (root / "baseline" / "src" / "chemistry").mkdir(parents=True)
        (root / "src" / "chemistry").mkdir(parents=True)
        (root / "tests").mkdir(parents=True)
        (root / "baseline" / KERNEL_REL).write_bytes(baseline_bytes)
        (root / KERNEL_REL).write_bytes(candidate_bytes)
        shutil.copyfile(test_src, root / "tests" / test_src.name)

        print()
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "-v",
             f"tests.{test_src.stem}"],
            cwd=root)
        return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
