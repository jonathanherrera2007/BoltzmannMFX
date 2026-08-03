# C08 redistribution interception authority - closure record

- **Stage:** C08 / P10
- **Status:** CLOSED
- **Blocker ID:** `B-C08-04-REDISTRIBUTION-INTERCEPTION-AUTHORITY`
- **Closed by:** exact user authorization recorded in `USER_APPROVAL.md`, then Codex C08 integration
- **C09 or later work performed:** no

## Authorization

The user granted C08-only authority to modify `src/des/bmx_pc.H` and
`src/des/bmx_pc.cpp` solely to wrap inherited `Redistribute` and `Regrid`
overloads with the existing preflight guard before delegating to pinned AMReX.
The grant expressly excluded wall projection/sliding and C09+ behavior.

## Implemented seam

`BMXParticleContainer` now hides the inherited four product entry points: one
`Redistribute` signature and all three `Regrid` overloads. Each wrapper calls
`BMXPhosphorus::requireRedistributionSafe(*this)` before the exact pinned-base
delegate. This covers initialization, mechanics, topology, restart's product
calls, and regrid without editing each caller or the pinned dependency.

The first negative-ID probe exposed two pinned-AMReX details that required
root-cause fixes within existing C08 ownership:

1. AMReX particle reductions skip invalid particles. The guard therefore
   reduces each tile's raw real-particle AoS so `id() <= 0` remains observable
   before compaction.
2. `ParticleContainer::Restart` performs its own nonvirtual redistribution
   before returning. `bmx::Restart` now prevalidates the serialized AMReX
   identity and coordinate payload before calling `pc->Restart`, using the
   pinned native integer/real readers. This prevents a malformed negative ID
   or unresolved nonperiodic coordinate from disappearing inside Restart.

No `Restart` wrapper, pinned-AMReX edit, particle projection, sliding, or C09
boundary mechanics were introduced.

## Closure evidence

- Clean native Release build: PASS; executable SHA-256
  `ab726982f693e1e873dc45bbcaa6e2f94cc9968852e9433f712a5bd06c1a700e`.
- Static ownership/provenance audit: PASS with no unexpected paths.
- Nonperiodic ASCII particle: exact
  `P10_ABORT_OUT_OF_DOMAIN_PARTICLE` before ledger/output.
- Periodic ASCII particle: wrapped to approximately `0.0001` and retained.
- Negative serialized identity: exact
  `P10_ABORT_UNMAPPED_PARTICLE_DELETION` before particle deserialization.
- Nonperiodic serialized coordinate: exact
  `P10_ABORT_OUT_OF_DOMAIN_PARTICLE` before particle deserialization.
- The complete guard matrix passes at 1→1, 2→2, and 2→1 ranks.
- Full C08 regression suite: PASS.
- Frozen kernel SHA-256:
  `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.
- Pinned AMReX commit/tree:
  `cbdc6580ee3d78cccdd37172e4ba077ee181f483` /
  `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6`.
- External/cloud spend: USD 0.

The separate `B-C08-03-INDEPENDENT-OPERATOR-ORDER-REVIEW` gate is closed by
the user-supplied independent review receipt `IR-20260801-P10-U02`, bound to
the unchanged operator-order SHA-256
`bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`.
Its correction dispositions are recorded in `REVIEW_DISPOSITION.md`.
