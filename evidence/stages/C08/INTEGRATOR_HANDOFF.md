# C08 final handoff — PASS

**Stage status:** `PASS`

C08/P10 implementation, independent operator-order review, correction
disposition, clean build, and local qualification are complete. No C08 blocker
remains. C09 and later work were not started and require separate user
authorization.

## Frozen qualified identities

- Qualified source commit:
  `a33e37749450432fb15c1021fc554a26f4e3fc7d`
- Qualified source tree:
  `333613990076476707f7e8aa82b1119e2d9a3f58`
- Executable SHA-256:
  `ab726982f693e1e873dc45bbcaa6e2f94cc9968852e9433f712a5bd06c1a700e`
- Chemistry kernel SHA-256:
  `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`
- Pinned AMReX commit/tree:
  `cbdc6580ee3d78cccdd37172e4ba077ee181f483` /
  `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6`
- Operator-order SHA-256:
  `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`
- Decision-reconciliation SHA-256:
  `de467a9be4c67d165e9c9f1f82bae727bfce5f4d6251aa5dd3be25c1e200ec0b`

## Independent review

The user supplied independent review `IR-20260801-P10-U02`, which approves the
exact operator-order hash above with corrections and requests no sequence
change. The reviewed artifact remains byte-identical; its historical
`WRITER_FROZEN_PENDING_INDEPENDENT_REVIEW` field records the writer-freeze
state at which it was reviewed. The separate hash-bound review record closes
that transition without rewriting the reviewed bytes.

All review findings are dispositioned in `REVIEW_DISPOSITION.md` and JSON.
Notably:

- P10-U01 is `CLOSED_USER_ADOPTED`, not `CLOSED_SCIENTIFIC`; only its C08 scope
  was ingested and later-stage science gates remain open.
- Negative-amount tolerance uses the actual `S_L1` scale.
- Ledger audits reject nonempty working/increment P blocks.
- Ownership scope is diffed from immutable pre-C08 commit `2e7bb249…`.
- Redistribution and checkpoint guards pass at 2 ranks and across 2→1 restart.
- Build evidence and embedded provenance both identify a clean source commit.

## Qualification evidence

- `BUILD.json`: PASS, clean attributed Release build
- `AMOUNT_UNIT.json`: PASS
- `TOPOLOGY_AMOUNT.json`: PASS, including 2-rank split
- `CHECKPOINT_RESTART.json`: PASS, including 2-rank and 2→1 restart
- `REDISTRIBUTION_GUARDS.json`: PASS, 1→1
- `REDISTRIBUTION_GUARDS_MPI2.json`: PASS, 2→2
- `REDISTRIBUTION_GUARDS_MPI2_TO_1.json`: PASS, 2→1
- `FEATURE_OFF_SEMANTIC.json`: PASS on G1 and G4
- `SCHEMA_RUNTIME.json`: PASS, 9/9
- `STATIC.json`: PASS, 55 stage paths and zero unexpected paths
- `git diff --check`: PASS

## Carry-forward boundary

C08 provides RG-SW infrastructure and engineering evidence only. It does not
claim reference-host/release qualification, calibrated or predictive biology,
RG-SCI readiness, publication readiness, or formal P05–P18 acceptance. The
remaining P11–P17 decisions and mentor-owned science gates in
`contracts/release_blockers.json` are unchanged except that the now-reviewed
P10-U02 entry is removed.

External/cloud resources used: none. Spend: USD 0.
