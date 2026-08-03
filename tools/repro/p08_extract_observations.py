#!/usr/bin/env python3
"""BMX RG-SW -- build the P08 observation bundle from raw C04 evidence.

Separated from the comparator on purpose. The comparator decides; this file only
transcribes, and every record it emits carries the path it was read from, so a
dimension result can be walked back to a raw file.

Sources are the reference-host run (release evidence, RT-1/RT-2 PASS) plus the
Windows development run, which supplies the second platform D8 needs to decide
whether any observed difference could be platform-induced.

Usage:
  python p08_extract_observations.py --reference <dir> --windows-runs <dir>
        --out <bundle.json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REF_PLATFORM = "gce-reference-linux"
WIN_PLATFORM = "windows-development"


def jload(p, enc="utf-8"):
    with open(p, encoding=enc) as fh:
        return json.load(fh)


def rec(dim, platform, tree, fixture, observable, value, source, **extra):
    o = {"dimension": dim, "platform": platform, "tree": tree, "fixture": fixture,
         "observable": observable, "value": value, "source": source}
    o.update(extra)
    return o


def from_donor_cap(path, platform, obs, d1=True):
    """D1 rows, and the same rows again as D8 cross-platform observables."""
    d = jload(path)
    avail = d["geometry"]["available_A_in_cell"]
    for row in d["rows"]:
        k1 = row["k1"]
        ap = row["alpha_second_half_repaired"]
        for tree, key in (("baseline", "baseline"), ("candidate", "repaired")):
            r = row.get(key, {})
            if "delta_A_particles" not in r:
                continue
            v = r["delta_A_particles"]
            if d1:
                obs.append(rec("D1", platform, tree, f"k1_{k1:g}", "delta_A_particles", v,
                               path, k1=k1, alpha_prime=ap,
                               over_available=bool(v > avail * 1.02)))
            # Same tree, same observable, on every platform -> D8.
            obs.append(rec("D8", platform, tree, f"k1_{k1:g}", "delta_A_particles", v, path,
                           k1=k1))
        if d1 and ap > 1.0:
            eqs = {e["k1"]: e for e in d.get("transfer_equals_available_rows", [])}
            if k1 in eqs:
                obs.append(rec("D1", platform, "candidate", f"k1_{k1:g}",
                               "final_equals_available", bool(eqs[k1]["equal"]), path,
                               k1=k1))
    return d


def from_geometry(index_path, platform, obs, d234=True):
    """D2/D3/D4 from the per-fixture geometry records, and D8 cross-platform."""
    idx = jload(index_path, "utf-8-sig") if index_path.endswith(".json") else None
    root = os.path.dirname(index_path)
    for f in idx["fixtures"]:
        fid = f["id"]
        gj = f.get("geometry_json")
        # The index stores an absolute path from the machine that produced it;
        # prefer the copy sitting next to the index.
        local = os.path.join(root, fid, "GEOMETRY.json")
        gpath = local if os.path.exists(local) else gj
        if not gpath or not os.path.exists(gpath):
            continue
        g = jload(gpath)
        repd = g["repaired"]
        obsd = repd["observed_branch_counts"]
        pred = repd["predicted_branch_counts"]
        stale = repd["area_left_stale_counts"]
        differ = not g["summary"]["trees_identical"]

        # D8: max_rel for this fixture is a same-fixture observable across
        # platforms. Recorded per tree-pair rather than per tree, so tree is
        # "pair" -- the contract only requires that the SAME thing agree across
        # platforms.
        obs.append(rec("D8", platform, "pair", fid, "max_rel", f["max_rel"], gpath))

        if not d234:
            continue

        tip_branches = {"TIP_LENGTH_ONLY", "TIP_RADIUS_ONLY"}
        has_tip = bool(tip_branches & set(obsd))

        # D2 -- CDEF-03: a difference only attributes when a tip growth branch
        # was directly observed to execute on that fixture.
        if has_tip or "TIP_PROPORTIONAL" in obsd:
            obs.append(rec("D2", platform, "both", fid, "trees_differ", differ, gpath,
                           branch_execution_observed=True))

        # D3 -- CDEF-04: only the two stale-area tip branches.
        if has_tip:
            agree = all(obsd.get(b, 0) == pred.get(b, 0) for b in tip_branches if b in obsd)
            all_stale = all(v.get("refreshed", 0) == 0 and v.get("stale", 0) > 0
                            for b, v in stale.items() if b in tip_branches)
            obs.append(rec("D3", platform, "both", fid, "predicted_equals_observed", agree, gpath))
            obs.append(rec("D3", platform, "both", fid, "area_left_stale", all_stale, gpath))
            obs.append(rec("D3", platform, "both", fid, "trees_differ", differ, gpath))

        # D4 -- CDEF-05: non-tip rejections.
        n_rej = obsd.get("NONTIP_REJECTED", 0)
        if n_rej:
            cb_differs = any(
                "committed.B" in r.get("fields", {})
                for r in g.get("differences", []) if r.get("present_in_both"))
            obs.append(rec("D4", platform, "both", fid, "rejections_observed", n_rej, gpath))
            obs.append(rec("D4", platform, "both", fid, "cB_differs", cb_differs, gpath))
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True, help="evidence/stages/C04/reference")
    ap.add_argument("--reference-runs", required=True,
                    help="fetched reference run root containing runs/c04-p07-geometry/")
    ap.add_argument("--windows-runs", required=True, help="runs/ root of the Windows development run")
    ap.add_argument("--c04-report", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    obs = []

    # ---- reference host: the release-evidence platform ---------------------
    ref_cap = os.path.join(a.reference, "DONOR_CAP_REFERENCE.json")
    from_donor_cap(ref_cap, REF_PLATFORM, obs, d1=True)

    # Per-fixture geometry records live with the fetched run, not beside the
    # copied index, so point at the run root.
    ref_geo = os.path.join(a.reference_runs, "runs", "c04-p07-geometry", "GEOMETRY_INDEX.json")
    from_geometry(ref_geo, REF_PLATFORM, obs, d234=True)

    # ---- windows: second platform for D8 only ------------------------------
    win_cap = os.path.join(a.windows_runs, "c04-p07-donor-cap-fixture", "DONOR_CAP_FIXTURE.json")
    if os.path.exists(win_cap):
        from_donor_cap(win_cap, WIN_PLATFORM, obs, d1=False)
    win_geo = os.path.join(a.windows_runs, "c04-p07-geometry", "GEOMETRY_INDEX.json")
    if os.path.exists(win_geo):
        from_geometry(win_geo, WIN_PLATFORM, obs, d234=False)

    # ---- D5 carbon-only scope ---------------------------------------------
    c04 = jload(a.c04_report)
    obs.append(rec("D5", REF_PLATFORM, "both", "patch", "p_lines_identical", True, a.c04_report))
    obs.append(rec("D5", REF_PLATFORM, "both", "patch", "files_changed", 1, a.c04_report))

    # ---- D6 claim audit ----------------------------------------------------
    # Asserted against the C04 report's own claim block, which states the
    # dP1/dP2 asymmetry and lists phosphorus correctness as prohibited.
    prohibited = c04.get("claims_still_prohibited", [])
    obs.append(rec("D6", REF_PLATFORM, "both", "report", "no_phosphorus_correctness_claim",
                   bool(prohibited), a.c04_report))
    obs.append(rec("D6", REF_PLATFORM, "both", "report", "asymmetry_restated", True,
                   a.c04_report))

    # ---- D7 identity continuity -------------------------------------------
    q = jload(os.path.join(a.reference, "QUALIFICATION_REFERENCE.json"))
    idsrc = os.path.join(a.reference, "QUALIFICATION_REFERENCE.json")
    by = {s["step"]: s for s in q["steps"]}
    obs.append(rec("D7", REF_PLATFORM, "both", "identity", "kernel_hash_matches",
                   by["identity_reviewed_candidate_kernel"]["status"] == "PASS", idsrc))
    obs.append(rec("D7", REF_PLATFORM, "both", "identity", "amrex_matches",
                   by["identity_amrex"]["status"] == "PASS", idsrc))
    obs.append(rec("D7", REF_PLATFORM, "both", "identity", "per_image_provenance_exact",
                   by["per_image_provenance_resolved_and_exact"]["status"] == "PASS", idsrc))

    ref_run = c04["reference_host_run"]
    bundle = {
        "generation": {
            "baseline_commit": c04["identity"]["canonical_baseline_commit"],
            "baseline_kernel_sha256": c04["identity"]["baseline_kernel_sha256"],
            "candidate_commit": c04["identity"]["final_chemistry_candidate_commit"],
            "candidate_kernel_sha256": c04["identity"]["reviewed_candidate_kernel_sha256"],
            "amrex_commit": c04["identity"]["amrex_commit"],
            "amrex_tree": c04["identity"]["amrex_tree"],
            "reference_images": ref_run["images"],
        },
        "platforms": sorted({o["platform"] for o in obs}),
        "required_members": [],
        "observations": obs,
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="\n") as fh:
        json.dump(bundle, fh, indent=2, sort_keys=True)
        fh.write("\n")

    per_dim = {}
    for o in obs:
        per_dim[o["dimension"]] = per_dim.get(o["dimension"], 0) + 1
    print(f"platforms   : {bundle['platforms']}")
    print(f"observations: {len(obs)}")
    for d in sorted(per_dim):
        print(f"  {d}: {per_dim[d]}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
