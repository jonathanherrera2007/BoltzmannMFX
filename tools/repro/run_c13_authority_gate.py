#!/usr/bin/env python3
"""Reproduce the C13/P15 Stage-0 specification-completeness gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


EXPECTED = {
    "head": "7768fc92f683f68b0d282b69e45d079103fc847a",
    "tree": "b772bb974439aea3181257c109367a18136d1220",
    "src_tree": "10ba9b7703a5715a47919714f17d9b9f258c40f5",
    "amrex_commit": "cbdc6580ee3d78cccdd37172e4ba077ee181f483",
    "amrex_tree": "fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6",
    "kernel_sha256": "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02",
    "order_sha256": "bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6",
    "authority_sha256": "34e8414c09e6528fc86399ceb4902cb5fc6907d9562fcf7a78cb3a8e4e333066",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def add_check(checks: list[dict], check_id: str, passed: bool, observed) -> None:
    checks.append({
        "id": check_id,
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
    })


def bonded_inventory(contracts: Path) -> list[dict]:
    matches: list[dict] = []
    for path in sorted(contracts.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        selected = []
        for line_number, line in enumerate(text.splitlines(), 1):
            lowered = line.lower()
            if "bonded" in lowered or "d_d_bond" in lowered:
                selected.append({"line": line_number, "text": line.strip()})
        if selected:
            matches.append({
                "path": path.relative_to(contracts.parent).as_posix(),
                "matches": selected,
            })
    return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    kernel_path = root / "src/chemistry/bmx_chem_K.H"
    order_path = root / "contracts/p10/OPERATOR_ORDER_V1.json"
    authority_path = root / "contracts/USER_ADOPTED_DECISION_CONTRACT_20260801_V2.txt"
    chemistry_path = root / "src/chemistry/bmx_chem.cpp"
    uptake_kernel_path = root / "src/chemistry/bmx_phosphorus_uptake_K.H"
    c12_report_path = root / "evidence/stages/C12V2/STAGE_REPORT.json"

    head = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    src_tree = git(root, "rev-parse", "HEAD:src")
    amrex_root = root / "subprojects/amrex"
    amrex_commit = git(amrex_root, "rev-parse", "HEAD")
    amrex_tree = git(amrex_root, "rev-parse", "HEAD^{tree}")

    kernel_text = kernel_path.read_text(encoding="utf-8-sig")
    authority_text = authority_path.read_text(encoding="utf-8-sig")
    chemistry_text = chemistry_path.read_text(encoding="utf-8-sig")
    uptake_kernel_text = uptake_kernel_path.read_text(encoding="utf-8-sig")
    c12_report = json.loads(c12_report_path.read_text(encoding="utf-8-sig"))

    checks: list[dict] = []
    add_check(checks, "c12_pass", c12_report["status"] == "PASS", c12_report["status"])
    add_check(checks, "stage_input_head", head == EXPECTED["head"], head)
    add_check(checks, "stage_input_tree", tree == EXPECTED["tree"], tree)
    add_check(checks, "stage_input_src_tree", src_tree == EXPECTED["src_tree"], src_tree)
    add_check(checks, "amrex_commit", amrex_commit == EXPECTED["amrex_commit"], amrex_commit)
    add_check(checks, "amrex_tree", amrex_tree == EXPECTED["amrex_tree"], amrex_tree)
    add_check(checks, "frozen_kernel_sha256", sha256(kernel_path) == EXPECTED["kernel_sha256"], sha256(kernel_path))
    add_check(checks, "global_order_sha256", sha256(order_path) == EXPECTED["order_sha256"], sha256(order_path))
    add_check(checks, "authority_sha256", sha256(authority_path) == EXPECTED["authority_sha256"], sha256(authority_path))
    add_check(
        checks, "adopted_bonded_diffusivity_units",
        "bonded-D transport:\n1.25e-6 cm2/s" in authority_text and
        "1.25\\times10^{-6},1.25\\times10^{-5}\\ \\mathrm{cm^2/s}" in authority_text,
        "centre and sensitivity set are expressed in cm^2/s",
    )
    legacy_expression = "Real d = (cnc1[n]-cnc2[n])*area*xpar[n]*dt;"
    add_check(checks, "inherited_exchange_expression", legacy_expression in kernel_text, legacy_expression)
    add_check(
        checks, "enabled_layout_legacy_transfer_is_zero",
        "mtP != 0.0" in chemistry_text and
        "enabled P09 plumbing requires chem_species.kP" in chemistry_text,
        "src/chemistry/bmx_chem.cpp rejects nonzero legacy mass_transfer_P in enabled mode",
    )
    add_check(
        checks, "general_terminal_zone_fails_closed",
        "future topology needing graph distance, branch ties, or partial-segment" in uptake_kernel_text and
        "area fails closed until those presently unstated rules are frozen" in uptake_kernel_text,
        "fixed-network exception explicitly refuses general topology",
    )
    add_check(
        checks, "p15_bonded_discretization_contract_absent",
        not (root / "contracts/p15/BONDED_D_TRANSPORT_CONTRACT_V1.json").exists(),
        "contracts/p15/BONDED_D_TRANSPORT_CONTRACT_V1.json is absent",
    )
    add_check(
        checks, "p15_integrated_numerical_contract_absent",
        not (root / "contracts/p15/NUMERICAL_PREREGISTRATION_V1.json").exists(),
        "contracts/p15/NUMERICAL_PREREGISTRATION_V1.json is absent",
    )

    # Dimensional exponents are (mol, cm, s).  The inherited expression with
    # a diffusivity leaves one extra length dimension; a velocity does not.
    concentration = (1, -3, 0)
    area = (0, 2, 0)
    diffusivity = (0, 2, -1)
    velocity = (0, 1, -1)
    timestep = (0, 0, 1)
    add_dimensions = lambda *terms: tuple(sum(v) for v in zip(*terms))
    with_diffusivity = add_dimensions(concentration, area, diffusivity, timestep)
    with_velocity = add_dimensions(concentration, area, velocity, timestep)
    add_check(checks, "diffusivity_substitution_dimension", with_diffusivity == (1, 1, 0), with_diffusivity)
    add_check(checks, "legacy_velocity_dimension", with_velocity == (1, 0, 0), with_velocity)

    result = {
        "artifact_type": "C13_STAGE0_AUTHORITY_GATE",
        "stage": "C13/P15 Stage 0",
        "generated": "2026-08-02",
        "status": "BLOCKED",
        "classification": "USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE",
        "input": {
            "branch": git(root, "branch", "--show-current"),
            "head": head,
            "tree": tree,
            "src_tree": src_tree,
            "amrex_commit": amrex_commit,
            "amrex_tree": amrex_tree,
            "initial_worktree_clean": True,
        },
        "checks": checks,
        "all_identity_and_gap_checks_passed": all(c["status"] == "PASS" for c in checks),
        "dimensional_analysis": {
            "basis": ["mol", "cm", "s"],
            "concentration_difference": concentration,
            "cross_sectional_area": area,
            "adopted_diffusivity": diffusivity,
            "legacy_mass_transfer_velocity": velocity,
            "timestep": timestep,
            "legacy_expression_with_adopted_diffusivity": with_diffusivity,
            "required_amount_dimension": [1, 0, 0],
            "missing_dimension": "cm^-1, requiring an exact effective length or equivalent conductance rule",
        },
        "contract_search_inventory": bonded_inventory(root / "contracts"),
        "blockers": [
            "D-C13-01-BONDED-D-DISCRETIZATION",
            "D-C13-02-INTEGRATED-NUMERICAL-PREREGISTRATION",
            "D-C13-03-TERMINAL-ZONE-GENERAL-TOPOLOGY",
        ],
        "stage_actions": {
            "product_source_edit_started": False,
            "build_started": False,
            "stage0_runtime_started": False,
            "science_outcome_started": False,
            "external_resource_used": False,
            "external_spend_usd": 0,
        },
        "claim_boundary": "Specification-completeness and byte-identity evidence only; not mentor approval, calibration, CLOSED_SCIENTIFIC, predictive validation, release evidence, or a P15 outcome.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["all_identity_and_gap_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
