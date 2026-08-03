#!/usr/bin/env python3
"""Static C09 ownership, provenance, geometry-contract, and scope checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


KERNEL_SHA256 = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
AMREX_COMMIT = "cbdc6580ee3d78cccdd37172e4ba077ee181f483"
AMREX_TREE = "fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6"
C09_STAGE_BASE = "0f6636e6080126d2ce58efcef942525bce9b524c"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(source: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={source.as_posix()}", *args],
        cwd=source,
        text=True,
        stderr=subprocess.STDOUT,
    ).rstrip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--stage-base", default=C09_STAGE_BASE)
    args = parser.parse_args()

    source = args.source.resolve()
    json_out = args.json_out.resolve()
    stage_base = git(source, "rev-parse", f"{args.stage_base}^{{commit}}")
    committed_paths = git(
        source, "diff", "--name-only", f"{stage_base}...HEAD"
    ).splitlines()
    status_lines = git(source, "status", "--porcelain=v1", "-uall").splitlines()
    working_paths = [line[3:].replace("\\", "/") for line in status_lines if line]
    changed_paths = sorted(set(committed_paths) | set(working_paths))

    allowed_exact = {
        "contracts/decision_reconciliation.json",
        "contracts/decision_reconciliation.md",
        "contracts/release_blockers.json",
        "src/chemistry/bmx_cell_interaction_K.H",
        "src/chemistry/bmx_chem_layout.H",
        "src/chemistry/bmx_phosphorus_geometry_K.H",
        "src/des/bmx_pc.H",
        "src/des/bmx_pc_interaction.cpp",
        "src/diffusion/bmx_define_coeffs_on_faces.cpp",
        "src/io/bmx_checkpoint_schema.H",
        "src/io/bmx_checkpoint_schema.cpp",
        "src/io/bmx_chk.cpp",
        "src/io/bmx_restart.cpp",
        "src/timestepping/bmx_evolve.cpp",
    }
    allowed_prefixes = (
        "contracts/p11/",
        "evidence/stages/C09/",
        "tools/repro/c09_",
        "tools/repro/run_c09_",
    )
    unexpected_paths = [
        path for path in changed_paths
        if path not in allowed_exact and not path.startswith(allowed_prefixes)
    ]

    geometry_path = source / "contracts/p11/GEOMETRY_CONTRACT_V1.json"
    geometry_hash = sha256(geometry_path)
    geometry_record = json.loads(geometry_path.read_text(encoding="utf-8"))
    geometry = (source / "src/chemistry/bmx_phosphorus_geometry_K.H").read_text(
        encoding="utf-8"
    )
    interaction = (source / "src/des/bmx_pc_interaction.cpp").read_text(
        encoding="utf-8"
    )
    cell_interaction = (
        source / "src/chemistry/bmx_cell_interaction_K.H"
    ).read_text(encoding="utf-8")
    diffusion = (
        source / "src/diffusion/bmx_define_coeffs_on_faces.cpp"
    ).read_text(encoding="utf-8")
    evolve = (source / "src/timestepping/bmx_evolve.cpp").read_text(
        encoding="utf-8"
    )
    checkpoint = (source / "src/io/bmx_checkpoint_schema.cpp").read_text(
        encoding="utf-8"
    )
    checkpoint_header = (
        source / "src/io/bmx_checkpoint_schema.H"
    ).read_text(encoding="utf-8")
    restart = (source / "src/io/bmx_restart.cpp").read_text(encoding="utf-8")
    layout = (source / "src/chemistry/bmx_chem_layout.H").read_text(
        encoding="utf-8"
    )
    decisions_path = source / "contracts/decision_reconciliation.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    blockers = json.loads(
        (source / "contracts/release_blockers.json").read_text(encoding="utf-8")
    )

    decision_text = json.dumps(decisions, sort_keys=True)
    blocker_text = json.dumps(blockers, sort_keys=True)
    audit_order = [
        evolve.index("CleanupFusion"),
        evolve.index("AuditP11GeometryEvents"),
        evolve.index("CalculateFungalCM"),
    ]

    checks = {
        "frozen_kernel_sha256": sha256(source / "src/chemistry/bmx_chem_K.H")
        == KERNEL_SHA256,
        "frozen_kernel_unmodified": "src/chemistry/bmx_chem_K.H" not in changed_paths,
        "amrex_commit_pinned": git(source / "subprojects/amrex", "rev-parse", "HEAD")
        == AMREX_COMMIT,
        "amrex_tree_pinned": git(
            source / "subprojects/amrex", "rev-parse", "HEAD^{tree}"
        ) == AMREX_TREE,
        "geometry_contract_frozen_hash": geometry_hash
        == "6a4329f013c857c664a11d669747845006a6c0c9d34f568625b6939d1462acba"
        and geometry_hash in geometry
        and geometry_hash in (
            source / "contracts/p11/GEOMETRY_CONTRACT_V1.sha256"
        ).read_text(encoding="utf-8"),
        "contract_is_user_adopted_not_scientific": (
            geometry_record["authority"]["binding_classification"]
            == "CLOSED_USER_ADOPTED"
            and "not mentor approval" in geometry_record["authority"]["claim_boundary"]
            and "UDC-20260801-P11-SECTION-9" in decision_text
            and '"status": "CLOSED_USER_ADOPTED"' in decision_text
        ),
        "decision_hash_bound": sha256(decisions_path) in layout,
        "p11_questions_removed_from_active_blockers": (
            "P11-U04" not in blocker_text and "P11-U05" not in blocker_text
        ),
        "feature_default_off_and_exact_binding": all(
            token in geometry for token in (
                'parameters.query("enabled", enabled)',
                'parameters.get("schema_version", binding.version)',
                'parameters.get("contract_id", binding.contract)',
                'parameters.get("stage", binding.stage)',
                "enabled != 0 && enabled != 1",
            )
        ),
        "exact_domain_periodicity_and_face_alignment": all(
            token in geometry for token in (
                "geometry.isPeriodic(0)",
                "!geometry.isPeriodic(1)",
                "geometry.isPeriodic(2)",
                "barrier x lower face",
                "divider x face",
                "barrier x upper face",
                "aperture z lower face",
                "aperture z upper face",
            )
        ),
        "finite_capsule_and_solid_precedence": all(
            token in geometry for token in (
                "struct Capsule",
                "segmentRectangleDistanceSquared2D",
                "capsuleContactsSolid",
                "if (!fungal_segment || classification.solid_contact)",
                "classification.true_crossing",
            )
        ),
        "hard_projection_retains_tangent": all(
            token in geometry for token in (
                "constrainMotion",
                "projectOuterAxis",
                "sweptCapsulePenetratesSolid",
                "velocity[0] = Real(0.0)",
                "rotation_rejected",
            )
        ) and "constrainP11ParticleMotion" in cell_interaction
        and "P11 particle geometry rejected" in interaction,
        "pd_pf_divider_mask_only": all(
            token in geometry for token in (
                "component == config.mesh_pd_component",
                "component == config.mesh_pf_component",
                "direction == 0",
                "isDividerFace",
            )
        ) and "maskedFaceCoefficient" in diffusion,
        "one_final_event_pass_after_topology": (
            audit_order == sorted(audit_order)
            and interaction.count("void BMXParticleContainer::AuditP11GeometryEvents") == 1
            and "ParallelDescriptor::ReduceLongSum(window_contacts)" in interaction
            and "contact_id_checksum" in interaction
            and "attempted_penetration=" in interaction
            and "projected_motion=" in interaction
            and "tangential_motion=" in interaction
            and "rejected_growth=" in interaction
            and "duplicate or out-of-order update id" in interaction
        ),
        "event_pass_has_no_chemistry_export_reward_write": all(
            token not in interaction[
                interaction.index("void BMXParticleContainer::AuditP11GeometryEvents"):
            ]
            for token in ("first_data", "exported_p", "carbon", "reward")
        ),
        "checkpoint_schema_v3_and_geometry_identity": all(
            token in checkpoint for token in (
                "BMX_SCHEMA_V3_BEGIN",
                "p11_geometry_contract_sha256",
                "p11_geometry_prob_lo_",
                "p11_geometry_periodic_",
                "P11 geometry domain or periodicity mismatch",
            )
        ) and "Checkpoint version: 3" in checkpoint_header,
        "restart_validates_before_fields_and_particles": (
            restart.index("readValidateAndRestoreMetadata")
            < restart.index("checkpoint_box_arrays")
            < restart.index("requireCheckpointParticlesSafe")
            < restart.index('pc->Restart(restart_file, "particles")')
        ),
        "no_c10_or_later_behavior": all(
            token not in "\n".join(
                [geometry, interaction, cell_interaction, diffusion, evolve, checkpoint, restart]
            ).lower()
            for token in (
                "p12_",
                "p13_",
                "p14_",
                "p15_",
                "p16_",
                "carbon_reward",
                "fungal_export",
            )
        ),
        "ownership_scope_clean": not unexpected_paths,
    }
    passed = all(checks.values())
    report = {
        "artifact_type": "C09_STATIC_TEST",
        "stage": "C09/P11",
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "changed_paths": changed_paths,
        "ownership_stage_base": stage_base,
        "unexpected_paths": unexpected_paths,
        "hashes": {
            "kernel_sha256": sha256(source / "src/chemistry/bmx_chem_K.H"),
            "geometry_contract_sha256": geometry_hash,
            "decision_reconciliation_sha256": sha256(decisions_path),
        },
        "claim_boundary": (
            "Static engineering evidence for C09/P11 only. The geometry decisions "
            "are user-adopted and explicitly are not mentor approval, calibrated "
            "biology, independent numerical review, or release qualification."
        ),
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "failed": [key for key, value in checks.items() if not value],
        "unexpected_paths": unexpected_paths,
        "json_out": str(json_out),
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
