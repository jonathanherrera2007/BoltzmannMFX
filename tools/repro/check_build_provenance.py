#!/usr/bin/env python3
"""BMX RG-SW -- regression fixture for build provenance (D-C04-08).

WHAT FAILED
-----------
A linked worktree stores its `.git` as a FILE containing an absolute
`gitdir:` path, written in the syntax of the machine that created the worktree.
A worktree created on Windows records `C:/Users/.../repo/.git/worktrees/product`,
which is meaningless on Linux. Two things then went wrong at once:

  * CMake's IS_ABSOLUTE is evaluated with HOST syntax, so on Linux it reports
    FALSE for "C:/..." and the pointer was joined onto the source directory,
    producing "<src>/C:/Users/...". That is the exact string in the observed
    failure.
  * `git describe` therefore failed, AMReX's generate_buildinfo() stored an
    empty hash, and writeBuildInfo() skipped the line because it was empty --
    so a build with no provenance looked like one that simply did not print it.

The consequence is that a Linux release build would have been unattributable.

WHAT IS CHECKED
---------------
Each case manufactures a `.git` state and drives the SAME CMake code the build
uses (BMX_Provenance.cmake in -P probe mode), so this cannot drift from the
implementation:

  1. ordinary checkout          .git is a DIRECTORY            -> RESOLVED
  2. relative worktree pointer  portable by construction       -> RESOLVED
  3. foreign absolute pointer   the D-C04-08 failure itself    -> RESOLVED
                                (translated across platforms)
  4. unresolvable pointer       points nowhere on any host     -> UNAVAILABLE
  5. not a repository           no .git at all                 -> UNAVAILABLE
  6. fail-closed                unresolvable + REQUIRE=ON      -> configure FAILS

Case 3 is the regression guard proper. Case 6 is what stops an unattributable
artefact from being produced silently.

Usage:
  python check_build_provenance.py --source-dir <product worktree>
                                   --work-dir <scratch> [--json-out <path>]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

RE_KV = re.compile(r"^-- (BMX_[A-Z_]+)=(.*)$", re.M)


def probe(cmake, module, src):
    """Run the resolver exactly as the build does, in script mode."""
    p = subprocess.run([cmake, f"-DBMX_PROVENANCE_PROBE={src}", "-P", module],
                       capture_output=True, text=True, timeout=300)
    out = p.stdout + p.stderr
    return {m.group(1): m.group(2).strip() for m in RE_KV.finditer(out)}, out


def _force_rmtree(path):
    """rmtree that survives git's read-only object files on Windows."""
    def onexc(func, target, exc):
        try:
            os.chmod(target, 0o700)
            func(target)
        except Exception:            # noqa: BLE001 -- best effort cleanup
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=onexc)
    else:
        shutil.rmtree(path, onerror=lambda f, t, e: onexc(f, t, e))


def make_case(work, name, src_repo, kind):
    """Build a source tree whose .git is in the requested state."""
    d = os.path.join(work, name)
    if os.path.isdir(d):
        _force_rmtree(d)
    os.makedirs(d)
    dotgit = os.path.join(d, ".git")

    real_gitdir = read_gitdir(src_repo)

    if kind == "directory":
        # An ordinary checkout: a real .git DIRECTORY. Create a throwaway repo
        # so the case is genuine rather than simulated.
        subprocess.run(["git", "init", "-q", d], check=True, capture_output=True)
        with open(os.path.join(d, "f.txt"), "w") as fh:
            fh.write("x\n")
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        subprocess.run(["git", "-C", d, "add", "f.txt"], check=True, capture_output=True)
        subprocess.run(["git", "-C", d, "commit", "-qm", "init"],
                       check=True, capture_output=True, env=env)
    elif kind == "relative":
        rel = os.path.relpath(real_gitdir, d).replace("\\", "/")
        with open(dotgit, "w") as fh:
            fh.write(f"gitdir: {rel}\n")
    elif kind == "foreign_absolute":
        # The D-C04-08 failure: a Windows-syntax absolute pointer. Reconstruct
        # it from the real gitdir so the case is the actual defect, not a guess.
        foreign = to_windows_syntax(real_gitdir)
        with open(dotgit, "w") as fh:
            fh.write(f"gitdir: {foreign}\n")
    elif kind == "unresolvable":
        with open(dotgit, "w") as fh:
            fh.write("gitdir: Q:/definitely/not/here/.git/worktrees/nope\n")
    elif kind == "not_a_repo":
        pass
    else:
        raise ValueError(kind)
    return d


def read_gitdir(src):
    """The real, resolved git dir of the product worktree."""
    dotgit = os.path.join(src, ".git")
    if os.path.isdir(dotgit):
        return dotgit
    txt = open(dotgit).read().strip()
    m = re.match(r"gitdir:\s*(.+)$", txt)
    p = m.group(1).strip().replace("\\", "/")
    if not os.path.exists(p):
        p2 = to_posix_syntax(p)
        if os.path.exists(p2):
            return p2
    return p


def to_windows_syntax(p):
    m = re.match(r"^/(?:mnt|cygdrive)/([A-Za-z])/(.*)$", p)
    if m:
        return f"{m.group(1).upper()}:/{m.group(2)}"
    m = re.match(r"^/([A-Za-z])/(.*)$", p)
    if m:
        return f"{m.group(1).upper()}:/{m.group(2)}"
    return p


def to_posix_syntax(p):
    m = re.match(r"^([A-Za-z]):[/\\](.*)$", p)
    if m:
        for pre in ("/mnt/", "/", "/cygdrive/"):
            cand = f"{pre}{m.group(1).lower()}/{m.group(2)}"
            if os.path.exists(cand):
                return cand
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--cmake", default="cmake")
    ap.add_argument("--generator", default="Ninja",
                    help="generator for the fail-closed probe project; pass '' to use the CMake default")
    ap.add_argument("--json-out")
    a = ap.parse_args()

    src = os.path.abspath(a.source_dir)
    module = os.path.join(src, "tools", "CMake", "BMX_Provenance.cmake")
    os.makedirs(a.work_dir, exist_ok=True)

    results, failures = [], []

    def record(name, ok, detail):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        if not ok:
            failures.append(name)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    # --- the live product worktree, on this host ---------------------------
    kv, _ = probe(a.cmake, module, src)
    ok = kv.get("BMX_PROVENANCE_STATUS") == "RESOLVED" and len(kv.get("BMX_GIT_COMMIT", "")) == 40
    record("live_worktree_resolves", ok,
           f"status={kv.get('BMX_PROVENANCE_STATUS')} commit={kv.get('BMX_GIT_COMMIT','')[:12]} "
           f"dirty={kv.get('BMX_GIT_DIRTY')} note={kv.get('BMX_PROVENANCE_NOTE')}")
    live_commit = kv.get("BMX_GIT_COMMIT", "")

    # --- manufactured .git states ------------------------------------------
    for name, kind, expect in [
        ("ordinary_checkout_directory", "directory", "RESOLVED"),
        ("worktree_relative_pointer", "relative", "RESOLVED"),
        ("worktree_foreign_absolute_pointer", "foreign_absolute", "RESOLVED"),
        ("worktree_unresolvable_pointer", "unresolvable", "UNAVAILABLE"),
        ("not_a_repository", "not_a_repo", "UNAVAILABLE"),
    ]:
        try:
            d = make_case(a.work_dir, name, src, kind)
        except Exception as e:              # noqa: BLE001
            record(name, False, f"could not construct case: {e}")
            continue
        kv2, _ = probe(a.cmake, module, d)
        got = kv2.get("BMX_PROVENANCE_STATUS")
        ok = got == expect
        detail = f"expected {expect}, got {got}"
        if expect == "RESOLVED":
            commit = kv2.get("BMX_GIT_COMMIT", "")
            ok = ok and len(commit) == 40
            detail += f", commit={commit[:12]}"
            # The two worktree cases point at the product's own git dir, so
            # they must report the product's commit, not merely *some* commit.
            if kind in ("relative", "foreign_absolute"):
                same = commit == live_commit
                ok = ok and same
                detail += f", matches live worktree={same}"
        else:
            detail += f", note={kv2.get('BMX_PROVENANCE_NOTE','')[:80]}"
        record(name, ok, detail)

    # --- fail-closed --------------------------------------------------------
    # An unresolvable tree configured with BMX_REQUIRE_PROVENANCE=ON must abort
    # rather than emit an unattributable binary. Driven through a tiny project
    # so only the provenance logic is exercised, not the whole BMX configure.
    fc = os.path.join(a.work_dir, "fail_closed")
    if os.path.isdir(fc):
        _force_rmtree(fc)
    os.makedirs(fc)
    with open(os.path.join(fc, ".git"), "w") as fh:
        fh.write("gitdir: Q:/definitely/not/here/.git/worktrees/nope\n")
    # CMake treats backslashes as escapes inside quoted strings, so a Windows
    # abspath must be written with forward slashes.
    src_cmake = src.replace("\\", "/")
    with open(os.path.join(fc, "CMakeLists.txt"), "w") as fh:
        fh.write(
            "cmake_minimum_required(VERSION 3.14)\n"
            "project(bmx_provenance_failclosed LANGUAGES NONE)\n"
            f'list(APPEND CMAKE_MODULE_PATH "{src_cmake}/tools/CMake")\n'
            "include(BMX_Provenance)\n"
            "option(BMX_REQUIRE_PROVENANCE \"\" OFF)\n"
            "bmx_resolve_provenance(\"${CMAKE_CURRENT_SOURCE_DIR}\")\n"
            "if(BMX_REQUIRE_PROVENANCE)\n"
            "  bmx_require_provenance()\n"
            "endif()\n"
            "message(STATUS \"configured with status ${BMX_PROVENANCE_STATUS}\")\n")

    # Pin the generator. With LANGUAGES NONE there is still a generator probe,
    # and CMake's Windows default (NMake Makefiles) is not installed here, which
    # would make BOTH runs fail and hide the real result.
    gen = ["-G", a.generator] if a.generator else []
    off = subprocess.run([a.cmake, "-S", fc, "-B", os.path.join(fc, "b_off"),
                          *gen, "-DBMX_REQUIRE_PROVENANCE=OFF"],
                         capture_output=True, text=True, timeout=300)
    on = subprocess.run([a.cmake, "-S", fc, "-B", os.path.join(fc, "b_on"),
                         *gen, "-DBMX_REQUIRE_PROVENANCE=ON"],
                        capture_output=True, text=True, timeout=300)
    ok = off.returncode == 0 and on.returncode != 0 and \
        "provenance could not be established" in (on.stdout + on.stderr)
    detail = (f"REQUIRE=OFF exit={off.returncode} (must be 0), "
              f"REQUIRE=ON exit={on.returncode} (must be non-zero)")
    if off.returncode != 0:
        detail += f" | REQUIRE=OFF stderr: {(off.stdout + off.stderr).strip()[-200:]}"
    record("fail_closed_when_provenance_required", ok, detail)

    out = {"source_dir": src, "live_commit": live_commit,
           "checks": results, "failures": failures,
           "status": "PASS" if not failures else "FAIL"}
    if a.json_out:
        os.makedirs(os.path.dirname(a.json_out), exist_ok=True)
        with open(a.json_out, "w") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
        print(f"\nwrote {a.json_out}")
    print(f"\nstatus: {out['status']}" + (f"  failures: {failures}" if failures else ""))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
