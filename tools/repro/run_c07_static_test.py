#!/usr/bin/env python3
"""Static C07/P09 ownership, layout, initialization, and neutrality guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


KERNEL_SHA256 = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()

    def text(rel: str) -> str:
        return (root / rel).read_text(encoding="utf-8")

    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append({"id": name, "status": "PASS" if condition else "FAIL", "detail": detail})

    kernel = root / "src/chemistry/bmx_chem_K.H"
    kernel_sha = hashlib.sha256(kernel.read_bytes()).hexdigest()
    check("kernel_frozen", kernel_sha == KERNEL_SHA256, kernel_sha)

    layout = text("src/chemistry/bmx_chem_layout.H")
    chem_h = text("src/chemistry/bmx_chem.H")
    chem_cpp = text("src/chemistry/bmx_chem.cpp")
    fluid = text("src/mods/bmx_fluid_parms.cpp")
    pc_init = text("src/des/bmx_pc_init.cpp")
    transfer = text("src/des/bmx_calc_txfr.cpp")
    plot = text("src/io/bmx_plt.cpp")

    check("distinct_counts", "particle_components = 8" in layout and
          "enabled_mesh_components = 7" in layout and
          "disabled_mesh_components = 6" in layout and
          "NUM_CHEM_COMPONENTS NUM_PARTICLE_CHEM_COMPONENTS" in chem_h,
          "particle=8, mesh enabled=7, mesh disabled=6")
    check("explicit_maps", "maps-enabled:0>0,1>1,2>2,3>3,4>4,5>5,6>7" in layout and
          "particle_component == P_E" in layout and "return -1" in layout,
          "enabled mesh slot 6 maps to particle P_F slot 7; P_E has no mesh map")
    check("schema_rejections", all(token in layout for token in
          ("cannot contain both P and P_D", "P_E is internal-only",
           "enabled P_D layout requires mesh P_F",
           "legacy P_uptake/P_growth/P_delivery aliases")),
          "all canonical invalid-layout branches are explicit")
    check("f_and_later_operators_default_off",
          "P_F diffusion must be exactly zero" in fluid and
          "enabled P09 plumbing requires chem_species.kP" in chem_cpp,
          "P_F diffusion and legacy P reaction/exchange/growth gates are exact-zero")
    check("deterministic_particle_initialization",
          "r < MAX_CHEM_REAL_VAR" in pc_init and
          "n < MAX_CHEM_INT_VAR" in pc_init and
          "getParticleInitialConcentrations" in pc_init and
          "initial_particle_P" in chem_cpp,
          "all three eight-slot blocks are zeroed; enabled P values require explicit input")
    check("mapped_transfer_seam",
          "P09OneToOneDeposition" in transfer and
          "P09TrilinearDeposition" in transfer and
          "mesh_comp == 6 ? BMXChemLayout::P_F" in transfer and
          "const int interp_ncomp = FLUID::nchem_species" in transfer and
          "interp_ncomp = NUM_CHEM_COMPONENTS" not in transfer,
          "enabled deposition and interpolation use the reviewed 7-to-8 map")
    check("semantic_particle_plot_names",
          "chem_committed_" in plot and "chem_working_" in plot and
          "chem_increment_" in plot and "particleName" in plot,
          "all 24 chemistry fields have semantic block/component names")
    check("checkpoint_metadata_scaffold_fail_closed",
          "checkpoint_schema_minimum = 2" in layout and
          "layout_hash_sha256" in layout and
          "decision_contract_sha256" in layout and
          "units_decision_source_sha256" in layout and
          'operator_order_id = "UNBOUND:P10-U02"' in layout and
          "checkpoint_schema_ready = false" in layout,
          "schema-v2 identifiers are declared; unresolved later contracts cannot be emitted as ready")

    diff = subprocess.run(
        ["git", "diff", "--name-only", "e7a695217076b7aab6d06294a5ad5d4afff82ca2", "--", "src"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "src"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    untracked = [line[3:] for line in status if line.startswith("?? ")]
    diff = sorted(set(diff) | set(untracked))
    allowed = {
        "src/chemistry/bmx_chem.H",
        "src/chemistry/bmx_chem.cpp",
        "src/chemistry/bmx_chem_layout.H",
        "src/mods/bmx_fluid_parms.cpp",
        "src/setup/bmx_init_fluid.cpp",
        "src/des/bmx_pc_init.cpp",
        "src/des/bmx_calc_txfr.cpp",
        "src/io/bmx_plt.cpp",
    }
    check("ownership_boundary", set(diff) <= allowed,
          "changed src files: " + ", ".join(diff))

    report = {
        "stage": "C07",
        "test": "static_layout_and_ownership",
        "kernel_sha256": kernel_sha,
        "checks": checks,
        "passed": all(row["status"] == "PASS" for row in checks),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
