#!/usr/bin/env python3
"""Static C08 ownership, provenance, contract-binding, and fail-closed checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


KERNEL_SHA256 = "9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02"
AMREX_COMMIT = "cbdc6580ee3d78cccdd37172e4ba077ee181f483"
AMREX_TREE = "fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6"
C08_STAGE_BASE = "40a28b3"


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
    parser.add_argument(
        "--stage-base",
        default=C08_STAGE_BASE,
        help="immutable pre-C08 commit used for the ownership-scope diff",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    json_out = args.json_out.resolve()
    layout = (source / "src/chemistry/bmx_chem_layout.H").read_text(encoding="utf-8")
    chemistry = (source / "src/chemistry/bmx_chem.cpp").read_text(encoding="utf-8")
    exchange = (source / "src/des/bmx_pc_xchng.cpp").read_text(encoding="utf-8")
    fusion = (source / "src/des/bmx_pc_fusion.cpp").read_text(encoding="utf-8")
    split = (source / "src/des/bmx_split_particles.cpp").read_text(encoding="utf-8")
    phosphorus = (source / "src/des/bmx_pc_phosphorus.cpp").read_text(
        encoding="utf-8"
    )
    particle_header = (source / "src/des/bmx_pc.H").read_text(encoding="utf-8")
    particle_source = (source / "src/des/bmx_pc.cpp").read_text(encoding="utf-8")
    transfer = (source / "src/des/bmx_calc_txfr.cpp").read_text(encoding="utf-8")
    evolve = (source / "src/timestepping/bmx_evolve.cpp").read_text(
        encoding="utf-8"
    )
    bmx_header = (source / "src/bmx.H").read_text(encoding="utf-8")
    bmx_source = (source / "src/bmx.cpp").read_text(encoding="utf-8")
    schema = (source / "src/io/bmx_checkpoint_schema.cpp").read_text(encoding="utf-8")
    checkpoint = (source / "src/io/bmx_chk.cpp").read_text(encoding="utf-8")
    restart = (source / "src/io/bmx_restart.cpp").read_text(encoding="utf-8")
    redistribution_guard_test = (
        source / "tools/repro/run_c08_redistribution_guards.py"
    ).read_text(encoding="utf-8")
    checkpoint_test = (
        source / "tools/repro/run_c08_checkpoint_tests.py"
    ).read_text(encoding="utf-8")

    operator_contract = source / "contracts/p10/OPERATOR_ORDER_V1.json"
    ledger_contract = source / "contracts/p10/GLOBAL_LEDGER_SCHEMA_V1.json"
    topology_contract = source / "contracts/p10/TOPOLOGY_EVENT_CONTRACT_V1.json"
    operator_hash = sha256(operator_contract)
    ledger_hash = sha256(ledger_contract)
    topology_hash = sha256(topology_contract)
    decision_hash = sha256(source / "contracts/decision_reconciliation.json")
    operator_record = json.loads(operator_contract.read_text(encoding="utf-8"))
    operator_review = json.loads(
        (source / "contracts/p10/OPERATOR_ORDER_V1.review.json").read_text(
            encoding="utf-8"
        )
    )
    operator_review_hash = sha256(
        source / "contracts/p10/OPERATOR_ORDER_V1.review.json"
    )
    ledger_record = json.loads(ledger_contract.read_text(encoding="utf-8"))
    topology_record = json.loads(topology_contract.read_text(encoding="utf-8"))

    stage_base = git(source, "rev-parse", f"{args.stage_base}^{{commit}}")
    committed_paths = git(
        source, "diff", "--name-only", f"{stage_base}...HEAD"
    ).splitlines()
    status_lines = git(source, "status", "--porcelain=v1", "-uall").splitlines()
    working_paths = [line[3:].replace("\\", "/") for line in status_lines if line]
    changed_paths = sorted(set(committed_paths) | set(working_paths))
    allowed_exact = {
        "contracts/USER_APPROVED_DECISION_CONTRACT_20260801.sha256",
        "contracts/USER_APPROVED_DECISION_CONTRACT_20260801.txt",
        "contracts/decision_reconciliation.json",
        "contracts/decision_reconciliation.md",
        "contracts/release_blockers.json",
        "src/bmx.H",
        "src/bmx.cpp",
        "src/chemistry/bmx_chem_layout.H",
        "src/des/CMakeLists.txt",
        "src/des/Make.package",
        "src/des/bmx_calc_txfr.cpp",
        "src/des/bmx_pc.H",
        "src/des/bmx_pc.cpp",
        "src/des/bmx_pc_fusion.cpp",
        "src/des/bmx_pc_xchng.cpp",
        "src/des/bmx_split_particles.cpp",
        "src/io/CMakeLists.txt",
        "src/io/Make.package",
        "src/io/bmx_chk.cpp",
        "src/io/bmx_restart.cpp",
        "src/timestepping/bmx_evolve.cpp",
    }
    allowed_prefixes = (
        "contracts/p10/",
        "evidence/stages/C08/",
        "src/des/bmx_pc_phosphorus.",
        "src/io/bmx_checkpoint_schema.",
        "tools/repro/c08_",
        "tools/repro/run_c08_",
    )
    unexpected_paths = [
        path
        for path in changed_paths
        if path not in allowed_exact and not path.startswith(allowed_prefixes)
    ]

    exchange_body = chemistry[
        chemistry.index("BMXChemistry::getExchangeParameters") :
    ]
    exchange_body = exchange_body[: exchange_body.index("return ret;")]
    restart_order = [
        restart.index("validateVersionLine"),
        restart.index("readValidateAndRestoreMetadata"),
        restart.index("checkpoint_box_arrays"),
        restart.index("requireCheckpointParticlesSafe"),
        restart.index('pc->Restart(restart_file, "particles")'),
    ]

    def guard_precedes_base(signature: str, base_call: str) -> bool:
        start = particle_source.index(signature)
        guard = particle_source.index(
            "BMXPhosphorus::requireRedistributionSafe(*this)", start
        )
        delegate = particle_source.index(base_call, start)
        return start < guard < delegate

    checks = {
        "frozen_kernel_sha256": sha256(source / "src/chemistry/bmx_chem_K.H")
        == KERNEL_SHA256,
        "frozen_kernel_unmodified": "src/chemistry/bmx_chem_K.H" not in changed_paths,
        "amrex_commit_pinned": git(source / "subprojects/amrex", "rev-parse", "HEAD")
        == AMREX_COMMIT,
        "amrex_tree_pinned": git(
            source / "subprojects/amrex", "rev-parse", "HEAD^{tree}"
        )
        == AMREX_TREE,
        "operator_contract_hash_bound": operator_hash in layout
        and operator_hash in (
            source / "contracts/p10/OPERATOR_ORDER_V1.sha256"
        ).read_text(encoding="utf-8"),
        "ledger_contract_hash_bound": ledger_hash in layout
        and ledger_hash in (
            source / "contracts/p10/GLOBAL_LEDGER_SCHEMA_V1.sha256"
        ).read_text(encoding="utf-8"),
        "decision_reconciliation_hash_bound": decision_hash in layout,
        "topology_contract_hash_bound": topology_hash in layout
        and topology_hash
        in (source / "contracts/p10/TOPOLOGY_EVENT_CONTRACT_V1.sha256").read_text(
            encoding="utf-8"
        ),
        "user_approval_source_bound": topology_record["status"]
        == "USER_APPROVED_BINDING_C08"
        and topology_record["approval"]["source_sha256"]
        == sha256(source / "contracts/USER_APPROVED_DECISION_CONTRACT_20260801.txt"),
        "operator_contract_writer_freeze_preserved": operator_record["status"]
        == "WRITER_FROZEN_PENDING_INDEPENDENT_REVIEW",
        "operator_order_independent_review_received": (
            operator_review["review_target_sha256"] == operator_hash
            and operator_review["operator_order_approved"] is True
            and operator_review["operator_sequence_change_required"] is False
            and operator_review["verdict"]
            == "APPROVE_OPERATOR_ORDER_WITH_CORRECTIONS"
            and operator_review_hash
            in (
                source / "contracts/p10/OPERATOR_ORDER_V1.review.sha256"
            ).read_text(encoding="utf-8")
            and operator_review_hash
            in (source / "contracts/decision_reconciliation.json").read_text(
                encoding="utf-8"
            )
        ),
        "ledger_other_exits_exactly_zero": all(
            field["rule"] == "exactly zero in v1"
            for field in ledger_record["fields"]
            if field["name"].startswith("other_exit")
        ),
        "checkpoint_schema_v2_ready": "checkpoint_schema_ready = true" in layout
        and 'operator_order_id = "bmx-p10-global-order-v1"' in layout
        and 'global_ledger_schema_id =\n      "bmx-p10-global-ledger-v1"' in layout,
        "checkpoint_writer_is_v2": "BMXCheckpointSchema::version_line" in checkpoint
        and "Checkpoint version: 1" not in checkpoint,
        "required_schema_fields_present": all(
            token in schema
            for token in (
                "mesh_component_names",
                "particle_component_names",
                "layout_hash_sha256",
                "operator_order_contract_sha256",
                "topology_event_contract_sha256",
                "units_contract_id",
                "decision_contract_sha256",
                "global_ledger_schema_sha256",
                "ledger_reference_total_p",
                "ledger_structural_p",
                "ledger_exported_p",
                "ledger_other_exit_events",
            )
        ),
        "restart_validates_complete_header_before_particles": restart_order
        == sorted(restart_order),
        "pure_volume_amount_restore_integrated": (
            "captureParticleAmounts" in transfer
            and "writePartition" in transfer
            and "xferMeshToParticleAndUpdateChem" in transfer
        ),
        "global_ledger_boundaries_integrated": (
            'AuditP10Ledger("O01_PRE_UPDATE_LEDGER", true)' in evolve
            and 'AuditP10Ledger("O10_POST_UPDATE_LEDGER", true)' in evolve
            and "volWgtSum" in bmx_source
            and "requireAuditBuffersEmpty(*pc, boundary)" in bmx_source
            and "void requireAuditBuffersEmpty (" in phosphorus
            and "p10_restart_metadata_expected" in bmx_header
        ),
        "simultaneous_batches_use_global_preflight": (
            "requireDisjointTopologyBatch(*this, local_events)" in fusion
            and "requireDisjointTopologyBatch(*this, local_events)" in split
            and "MPI_Allgatherv" in phosphorus
        ),
        "orphan_preflight_precedes_zero_state_prune": (
            phosphorus.index("if (invalid_bond_record || orphan_found)")
            < phosphorus.index("complete live-owner/orphan preflight above")
        ),
        "all_redistribution_paths_intercepted_before_amrex_invalidation": (
            particle_header.count("void Redistribute (") == 1
            and particle_header.count("void Regrid (") == 3
            and particle_source.count("BMXParticleContainer::Redistribute (") == 1
            and particle_source.count("BMXParticleContainer::Regrid (") == 3
            and particle_source.count(
                "BMXPhosphorus::requireRedistributionSafe(*this)"
            ) == 4
            and guard_precedes_base(
                "BMXParticleContainer::Redistribute (",
                "BMXNeighborBase::Redistribute(lev_min, lev_max, nGrow, local)",
            )
            and guard_precedes_base(
                "BMXParticleContainer::Regrid (const DistributionMapping& dmap,",
                "BMXNeighborBase::Regrid(dmap, ba)",
            )
            and guard_precedes_base(
                "BMXParticleContainer::Regrid (const DistributionMapping& dmap,\n"
                "                              const BoxArray& ba, int lev)",
                "BMXNeighborBase::Regrid(dmap, ba, lev)",
            )
            and guard_precedes_base(
                "BMXParticleContainer::Regrid (\n    const Vector<DistributionMapping>& dmap,",
                "BMXNeighborBase::Regrid(dmap, ba)",
            )
        ),
        "restart_internal_redistribution_prevalidated": (
            "void requireCheckpointParticlesSafe (" in phosphorus
            and "Version_Two_Dot_One_" in phosphorus
            and "amrex::readIntData" in phosphorus
            and "ReadParticleRealData" in phosphorus
            and "P09 checkpoint rejected before particle deserialization"
            in phosphorus
            and restart.index("requireCheckpointParticlesSafe")
            < restart.index('pc->Restart(restart_file, "particles")')
        ),
        "redistribution_guard_runtime_cases_declared": all(
            token in redistribution_guard_test
            for token in (
                "nonperiodic_out_of_domain",
                "periodic_wrap",
                "negative_id",
                "checkpoint_out_of_domain",
                "P10_ABORT_OUT_OF_DOMAIN_PARTICLE",
                "P10_ABORT_UNMAPPED_PARTICLE_DELETION",
            )
        )
        and 'parser.add_argument("--ranks"' in redistribution_guard_test
        and '"--restart-ranks"' in redistribution_guard_test,
        "mpi_checkpoint_rank_change_declared": all(
            token in checkpoint_test
            for token in (
                'parser.add_argument("--mpiexec"',
                '"mpi_restart_2_to_2"',
                '"mpi_restart_2_to_1"',
                '"restart_2_to_1_particle_equivalent"',
            )
        ),
        "negative_guard_uses_external_scale": (
            "negativeAboveIntegratedTolerance (amrex::Real amount,\n"
            "                                         amrex::Real s_l1)"
            in (source / "src/des/bmx_pc_phosphorus.H").read_text(
                encoding="utf-8"
            )
            and "negativeAboveIntegratedTolerance(old_amount, s_l1)" in phosphorus
            and "negativeAboveIntegratedTolerance(mesh.d, inventory_s_l1)"
            in phosphorus
        ),
        "bonded_exchange_has_integrated_audit": (
            "requireIntegratedConservation" in exchange
            and "bonded exchange and MPI redistribution" in exchange
        ),
        "exchange_E_F_coefficients_zero_by_construction": (
            "DeviceVector<Real> ret(NUM_PARTICLE_CHEM_COMPONENTS, 0.0)"
            in exchange_body
            and "ret[0] = mtA" in exchange_body
            and "ret[1] = mtB" in exchange_body
            and "ret[2] = mtC" in exchange_body
            and "ret[P_COMP] = mtP" in exchange_body
            and "P_E" not in exchange_body
            and "P_F" not in exchange_body
        ),
        "active_F_inputs_rejected": all(
            token in chemistry
            for token in (
                "chem_species.kP",
                "chem_species.krP",
                "chem_species.mass_transfer_P",
                "chem_species.p_growth_limit",
            )
        ),
        "ownership_scope_clean": not unexpected_paths,
    }
    passed = all(checks.values())
    report = {
        "artifact_type": "C08_STATIC_TEST",
        "stage": "C08",
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "changed_paths": changed_paths,
        "ownership_stage_base": stage_base,
        "unexpected_paths": unexpected_paths,
        "hashes": {
            "kernel_sha256": sha256(source / "src/chemistry/bmx_chem_K.H"),
            "operator_contract_sha256": operator_hash,
            "ledger_contract_sha256": ledger_hash,
            "topology_contract_sha256": topology_hash,
            "decision_reconciliation_sha256": decision_hash,
            "operator_review_sha256": operator_review_hash,
        },
        "claim_boundary": (
            "static engineering checks only; the adopted P10-U01 contract is bound, "
            "every product Redistribute/Regrid entry point is intercepted before "
            "pinned AMReX invalidation, and checkpoint payloads are prevalidated before "
            "pinned Restart's internal redistribution; the user-supplied independent "
            "review receipt is bound to the unchanged operator-order artifact hash"
        ),
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "failed": [key for key, value in checks.items() if not value],
                "unexpected_paths": unexpected_paths,
                "json_out": str(json_out),
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
