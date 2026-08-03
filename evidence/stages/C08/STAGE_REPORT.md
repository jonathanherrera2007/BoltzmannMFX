# C08 / P10 stage report

- **Stage:** C08 — phosphorus conservation, topology, and restart
- **Status:** `PASS`
- **Original C08 input commit:**
 `2e7bb249fecdd4c0764190b3e0ee3ee26f29f0d3`
- **Authority-resume commit:**
 `d75dfe264c3b5ede102334fc2fc55dd773d6c621`
- **Qualified clean source commit:**
 `a33e37749450432fb15c1021fc554a26f4e3fc7d`
- **Qualified clean source tree:**
 `333613990076476707f7e8aa82b1119e2d9a3f58`
- **Final evidence commit:** `b0cc13ac20ba307f4ff7e981d7cf36067aa4ba60`
- **Branch:** `rgsw/c08-p10`
- **Writer:** the implementation writer, sole product-branch writer
- **C09 or later started:** no

## Result

C08 is complete. The P10 topology, amount, global-ledger, checkpoint, and
redistribution infrastructure is integrated and passes the full local
engineering suite. The only prior stage gate, independent review of the exact
operator-order freeze, is closed by `IR-20260801-P10-U02`. Every required
review correction is resolved without changing the reviewed order bytes.

The operator artifact intentionally retains its historical writer-freeze
status field. The separate review record is bound to that exact immutable
artifact hash and records the external state transition; rewriting the
reviewed file merely to change its status would invalidate the review target.

## Authority and decision boundary

- User decision `UDC-20260801-P10-U01` is binding for P10-U01 in C08.
- Its reconciliation status is `CLOSED_USER_ADOPTED`, not
 `CLOSED_SCIENTIFIC`.
- Independent scientific confirmation remains an RG-SCI residual.
- Other sections in the adopted source were not ingested by C08 and do not
 close P11–P17 science gates.
- The exact C08-only grants for the integration files and derived
 `Redistribute`/`Regrid` wrappers are preserved in `USER_APPROVAL.md`.
- No wall projection/sliding, boundary mechanics, or C09+ behavior was added.

## Frozen identities

| Identity | Value | Result |
|---|---|---|
| Chemistry kernel SHA-256 | `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02` | unchanged |
| AMReX commit | `cbdc6580ee3d78cccdd37172e4ba077ee181f483` | unchanged |
| AMReX tree | `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6` | unchanged |
| Topology contract SHA-256 | `a6a5a8a8d299ee3e0cfc30f6d359d84ed13fb9872db7cf51bfb38777b800bdfb` | bound |
| Operator-order SHA-256 | `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6` | independently approved, unchanged |
| Operator review SHA-256 | `c033b950fc83c21b05ff9a7243d34c82b18e8f389916bd8dc9b4c9834e8d778a` | bound |
| Global-ledger schema SHA-256 | `23b0593ae3c07fbe6c20a4994226f2dce0f81af60a53b4ba91d3fa0f26c5a95b` | bound |
| Decision reconciliation SHA-256 | `de467a9be4c67d165e9c9f1f82bae727bfce5f4d6251aa5dd3be25c1e200ec0b` | compiled/bound |

## Implementation and review corrections

The original C08 integration provides:

- extensive D/E/F capture and volume-based partition for pure owning-volume
 changes, two-way splits, three-way splits, and fusion-created splits;
- MPI-global topology conflict, deletion, out-of-domain, and bond-owner
 preflights;
- derived `Redistribute`/`Regrid` interception before pinned AMReX can
 invalidate particles;
- pre-deserialization checkpoint payload validation before pinned AMReX
 Restart performs its internal nonvirtual redistribution;
- checkpoint schema v2 with exact layout/order/units/decision/ledger identity;
- O01, O10, and checkpoint-write global-ledger audits;
- disabled-mode compatibility and feature-off semantic preservation.

Review remediation adds or corrects:

- actual `S_L1` propagation into negative-amount checks;
- an MPI-global L1 invariant that working and increment P blocks are finite and
 exactly empty at every ledger audit;
- ownership checking against immutable stage base `2e7bb249…`, including
 committed and uncommitted paths;
- 2-rank redistribution/checkpoint testing and 2→1 restart qualification;
- clean, self-attributing build provenance and BOM-free UTF-8 JSON;
- explicit O07/O08 technical dependency rationale and full finding
 disposition.

The exact 55-path stage scope and zero unexpected paths are recorded in
`STATIC.json`.

## Independent review

- Review ID: `IR-20260801-P10-U02`
- Review target: `contracts/p10/OPERATOR_ORDER_V1.json`
- Target SHA-256:
 `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`
- Verdict: `APPROVE_OPERATOR_ORDER_WITH_CORRECTIONS`
- Sequence change requested: no
- Required corrections resolved: yes, 12/12 findings dispositioned

The receipt is `INDEPENDENT_REVIEW.md`; exact resolutions are in
`REVIEW_DISPOSITION.md` and JSON.

## Clean build

- Configuration: native Windows Release; MPI ON; OpenMP OFF; GPU backend NONE;
 C++17; AMReX 3D double precision.
- Source commit/tree: `a33e377…` / `33361399…`.
- Source dirty before evidence outputs opened: false.
- Embedded build provenance: `a33e377… (rgsw/c08-p10, clean)`.
- Executable:
 `C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean\bmx.exe`
- Size: 2,487,808 bytes.
- SHA-256:
 `ab726982f693e1e873dc45bbcaa6e2f94cc9968852e9433f712a5bd06c1a700e`.
- Raw build log SHA-256:
 `7c365a0980b9540088dcfd9346e23223c86da257d683711fe89f387fe535f974`.
- CMake cache SHA-256:
 `03f2d09f1d1b6346971ba05edc9c3c9b0f75392768c776a7d65579de2296658e`.
- Warnings: only the existing CMake/provenance diagnostics and pinned
 MSVC/AMReX `<numeric>` C4244 instantiations; no BMX source build failure.

## Qualification results

| Evidence | Coverage | Result |
|---|---|---|
| `BUILD.json` | fresh clean native Release build and provenance | PASS |
| `AMOUNT_UNIT.json` | amount algebra, partitions, tolerance floor and scaled branch | PASS |
| `TOPOLOGY_AMOUNT.json` | control, growth, split at 1 rank, split at 2 ranks | PASS |
| `CHECKPOINT_RESTART.json` | valid/disabled roundtrip, 11 corruptions, 2→2 and 2→1 restart | PASS |
| `REDISTRIBUTION_GUARDS.json` | four guard cases, 1→1 | PASS 4/4 |
| `REDISTRIBUTION_GUARDS_MPI2.json` | four guard cases, 2→2 | PASS 4/4 |
| `REDISTRIBUTION_GUARDS_MPI2_TO_1.json` | four guard cases, checkpoint write 2 / restart 1 | PASS 4/4 |
| `FEATURE_OFF_SEMANTIC.json` | G1 growth and G4 split/rejection semantic fields | PASS |
| `SCHEMA_RUNTIME.json` | valid disabled/enabled plus seven fail-closed mutations | PASS 9/9 |
| `STATIC.json` | frozen pins, contract hashes, seams, immutable-base ownership | PASS; 55 paths, zero unexpected |
| `git diff --check` | whitespace/error check | PASS |

The MPI checkpoint comparison reports exact identifiers/discrete fields and
zero floating differences for both 2→2 and 2→1. Same-rank selected checkpoint
payloads are byte-exact. Corrupt serialized identity and nonperiodic-coordinate
cases abort before particle deserialization in all recorded rank modes.

## Exact final commands

The Python executable was
`C:\Users\Shadow\.cache\agent-runtimes\primary-runtime\dependencies\python\python.exe`.
Every command exited 0.

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/repro/run_c08_native_build.ps1 -SourceDir . -BuildDir C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean -LogPath evidence\stages\C08\raw\native_build.log -JsonOut evidence\stages\C08\BUILD.json -Parallel 4

powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/repro/run_c08_amount_unit.ps1 -SourceDir . -BuildDir C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean -RunDir C:\b\BMX-shadow-handoff-20260721\runs\c08-amount-unit-review-final -JsonOut evidence\stages\C08\AMOUNT_UNIT.json

python tools/repro/run_c08_topology_split.py --exe C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c08-topology-review-final --json-out evidence\stages\C08\TOPOLOGY_AMOUNT.json --mpiexec "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe"

python tools/repro/run_c08_checkpoint_tests.py --exe C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c08-checkpoint-review-final --json-out evidence\stages\C08\CHECKPOINT_RESTART.json --mpiexec "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe"

python tools/repro/run_c08_redistribution_guards.py --exe C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c08-redistribution-review-final-1r --json-out evidence\stages\C08\REDISTRIBUTION_GUARDS.json

python tools/repro/run_c08_redistribution_guards.py --exe C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c08-redistribution-review-final-2r --json-out evidence\stages\C08\REDISTRIBUTION_GUARDS_MPI2.json --mpiexec "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe" --ranks 2 --restart-ranks 2

python tools/repro/run_c08_redistribution_guards.py --exe C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c08-redistribution-review-final-2to1 --json-out evidence\stages\C08\REDISTRIBUTION_GUARDS_MPI2_TO_1.json --mpiexec "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe" --ranks 2 --restart-ranks 1

python tools/repro/run_c07_schema_tests.py --exe C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c08-schema-review-final --json-out evidence\stages\C08\SCHEMA_RUNTIME.json

python tools/repro/run_c07_semantic_feature_off.py --p07-exe C:\b\BMX-shadow-handoff-20260721\runs\c08-reference\c04-p07-bmx.exe --c07-exe C:\b\BMX-shadow-handoff-20260721\build-c08-native-release-review-final-clean\bmx.exe --case-dir exec\fungi --out-dir C:\b\BMX-shadow-handoff-20260721\runs\c08-feature-off-review-final-ab726982 --json-out evidence\stages\C08\FEATURE_OFF_SEMANTIC.json

python tools/repro/run_c08_static_test.py --source . --json-out evidence/stages/C08/STATIC.json

git diff --check
```

## Conservation, restart, and claim effects

- No P source/sink semantics were added.
- F remains coefficient-zero and E remains internal-only.
- Raw deletion, unresolved nonperiodic loss, material-bearing orphan bonds, and
 overlapping topology batches remain collective pre-mutation aborts.
- Working/increment buffers cannot silently escape the ledger at audit points.
- Checkpoint/restart preserves the schema, exact identifiers, global ledgers,
 and semantic particle fields across same-rank and rank-change restart.
- Feature-off G1/G4 semantic fields remain equivalent to the frozen P07
 comparator.

## Blockers and prohibited claims

C08 blockers: none.

The later-stage blocker list remains authoritative in
`contracts/release_blockers.json`; C08 removed only the independently resolved
P10-U02 entry. This stage does not authorize C09 or any later work.

Still prohibited:

- reference-host or release qualification from Windows-local evidence alone;
- `RG-SW:GO` or `RG-SCI:GO`;
- calibrated/predictive biology or full-plate validity;
- publication readiness;
- formal P05–P18 acceptance.

External/cloud resources: none. External spend: USD 0.
