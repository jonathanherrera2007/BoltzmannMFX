# C09/P11 stage report — PASS

- **Stage:** `C09/P11`
- **Status:** `PASS`
- **Branch:** `rgsw/c09-p11`
- **Stage base:** `0f6636e6080126d2ce58efcef942525bce9b524c`
  / tree `7984ef6601d934a33e01f46ed5d1b819a383751d`
- **Qualified source:** `72414be0f8e52aa438dd04ab5b04cff5bcda5839`
  / tree `2fd93f00110054cb1dfcc50172305d77ab5d542f`
- **Qualified executable SHA-256:**
  `33a191e180288783a0e9fc5f7ca25ac08e298b43e68fa37f0414e5b19c37b996`
- **Final evidence commit:** `37a06c13c051afcdd56706be97b46b4cc3326549`
- **Writer:** Codex, sole product-branch writer; not an independent reviewer of
  its authored bytes
- **External/cloud resources:** none; spend USD 0
- **C10 or later work:** not started

## Outcome and authority boundary

C09 implements and qualifies the default-off P11 split-plate geometry on the
three-state layout. No C09-local blocker remains.

The binding decision identity is `UDC-20260801-P11-SECTION-9`, activated by the
user's instruction to continue through C09. It consumes only section 9 of the
preserved user-approved decision contract. Its reconciliation status is
`CLOSED_USER_ADOPTED`, not `CLOSED_SCIENTIFIC`: it is neither mentor approval
nor independent scientific review. No later contract section was ingested.

## Frozen identities

| Item | Identity |
|---|---|
| P11 geometry contract | `6a4329f013c857c664a11d669747845006a6c0c9d34f568625b6939d1462acba` |
| Decision reconciliation | `ddade9c36ee8be93da7a6f332fed31863a21c4d5e04cd377dca493c7ef6a7b64` |
| Chemistry kernel | `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02` |
| Pinned AMReX commit | `cbdc6580ee3d78cccdd37172e4ba077ee181f483` |
| Pinned AMReX tree | `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6` |

`src/chemistry/bmx_chem_K.H` is byte-frozen and unchanged by C09.

## Implemented behavior

- Exact default-off binding for schema, contract ID, local quasi-2D stage,
  three-state mesh layout, approved domains, periodicity, and face alignment.
- Finite-radius capsule classification for the split plate, solid-edge
  precedence, fungal-only aperture passage, and periodic y canonicalization.
- Hard nonpenetration by projection with tangent retention. Reflection,
  penalty forces, and deletion are prohibited. Simultaneous constraints use
  the frozen order: internal support, outer x, then outer z.
- One final owned-particle event traversal after topology and redistribution
  per update, with MPI-global counts and stable particle/update identity.
- P_D and P_F x-normal coefficients are set to exact zero at x=0 on every
  active AMR level. Outer x/z retain homogeneous Neumann conditions and y is
  periodic.
- Checkpoint schema v3 records the P11 enabled state, schema, contract
  identity/hash, stage, exact domain bounds, and periodicity. Mismatches abort
  before field or particle deserialization.
- `rejected_growth` is reserved and remains exactly zero. C09 adds no growth,
  B/E debit, chemistry, export, carbon reward, or C10+ behavior.

## Build

The definitive clean native Windows Release build passed in 225 seconds with
MPI ON, OpenMP OFF, GPU backend NONE, and C++17. It produced a 2,511,360-byte
executable from the exact qualified source commit above.

- Executable SHA-256:
  `33a191e180288783a0e9fc5f7ca25ac08e298b43e68fa37f0414e5b19c37b996`
- Raw log SHA-256:
  `ed02a0a69f238b013f8f59b0d790f1e5d1b858e4c319f2b514006288a2dc8dc2`
- CMake cache SHA-256:
  `0a3a1b0ada9e40d3c7ecf8d41c1a6bac442cd4a876f40ca945e62c1e74a1c484`

The two compiler warnings are inherited MSVC C4244 instantiations in pinned
AMReX/`std::numeric`; no C09 source warning was emitted.

## Qualification results

| Evidence | Result |
|---|---|
| Geometry unit predicates | PASS, 153 checks |
| Approved enabled geometries | PASS, central rank 1/rank 2, central AMR rank 2, small, and large |
| Decomposition invariance | PASS, exact rank-1/rank-2 and level-0/level-1 event identity |
| Production motion | PASS, internal-frame tangential slide and outer-z projection |
| Fail-closed runtime cases | PASS, 8/8 |
| Divider mask | PASS, nonzero P_D input `6e-10 cm^2/s`, P_F zero, every masked face zero afterward |
| Checkpoint/restart | PASS, rank 1, 2→2, and 2→1 |
| Checkpoint corruption | PASS, 8/8 rejected before payload loading |
| Feature-off semantics | PASS, G1/G4, 72 dumps and 420 particle records, zero differing values |
| Retained P10 topology | PASS, 1 and 2 ranks |
| Retained P10 redistribution | PASS, including 2→1 restart |
| Static ownership/provenance | PASS, zero unexpected paths |
| Python syntax / `git diff --check` | PASS / PASS |

The mask test is non-noop: the engineering fixture gives P_D a nonzero
pre-mask coefficient (`6e-10 cm^2/s`) while inactive P_F remains exactly zero.
Central level 0 masks 96 faces, central level 1 masks 160, and the large-domain
level 0 masks 192; `nonzero_faces=0` after masking in every case.

The motion fixtures exercise production code, not only header predicates. The
internal-frame case records one attempted penetration, one projection, and one
tangential motion. The outer-z case records one attempted penetration, one
projection, and zero tangential motion.

Feature-off comparison uses clean C08 reference commit
`a33e37749450432fb15c1021fc554a26f4e3fc7d`, tree
`333613990076476707f7e8aa82b1119e2d9a3f58`, executable
`5c0d593945adc983846a6b24b82764a8aaf302d9a60e69af0afe1e42ebbfa1fc`.
At 15-digit particle-output precision, G1 exercised 76 target branches and G4
exercised 188; all semantic fields and reserved slots matched.

## Exact qualification commands and exit codes

All commands ran from the product root. `python` below denotes the bundled
runtime at
`C:\Users\Shadow\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.

1. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\repro\run_c09_native_build.ps1 -SourceDir . -BuildDir C:\b\BMX-shadow-handoff-20260721\build-c09-native-release-definitive -LogPath .\evidence\stages\C09\raw\native_build.log -JsonOut .\evidence\stages\C09\BUILD.json -Parallel 4` — exit 0.
2. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/repro/run_c09_geometry_unit.ps1 -SourceDir . -BuildDir C:\b\BMX-shadow-handoff-20260721\build-c09-native-release-definitive -RunDir C:\b\BMX-shadow-handoff-20260721\runs\c09-geometry-unit-definitive -JsonOut evidence/stages/C09/GEOMETRY_UNIT.json` — exit 0.
3. `python tools/repro/run_c09_geometry_runtime.py --exe C:\b\BMX-shadow-handoff-20260721\build-c09-native-release-definitive\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c09-geometry-runtime-definitive --json-out evidence/stages/C09/GEOMETRY_RUNTIME.json --mpiexec "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe"` — exit 0.
4. `python tools/repro/run_c09_checkpoint_tests.py --exe C:\b\BMX-shadow-handoff-20260721\build-c09-native-release-definitive\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c09-checkpoint-definitive --json-out evidence/stages/C09/CHECKPOINT_RESTART.json --mpiexec "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe"` — exit 0.
5. `python tools/repro/run_c09_feature_off.py --c08-source C:\b\BMX-shadow-handoff-20260721\c08-reference-a33 --c08-exe C:\b\BMX-shadow-handoff-20260721\build-c08-reference-a33\bmx.exe --c09-exe C:\b\BMX-shadow-handoff-20260721\build-c09-native-release-definitive\bmx.exe --case-dir exec/fungi --out-dir C:\b\BMX-shadow-handoff-20260721\runs\c09-feature-off-definitive --json-out evidence/stages/C09/FEATURE_OFF_SEMANTIC.json` — exit 0.
6. `python tools/repro/run_c08_topology_split.py --exe C:\b\BMX-shadow-handoff-20260721\build-c09-native-release-definitive\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c09-p10-topology-regression-definitive --json-out evidence/stages/C09/P10_TOPOLOGY_REGRESSION.json --mpiexec "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe"` — exit 0.
7. `python tools/repro/run_c08_redistribution_guards.py --exe C:\b\BMX-shadow-handoff-20260721\build-c09-native-release-definitive\bmx.exe --source . --run-root C:\b\BMX-shadow-handoff-20260721\runs\c09-p10-redistribution-regression-definitive --json-out evidence/stages/C09/P10_REDISTRIBUTION_REGRESSION.json --mpiexec "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe" --ranks 2 --restart-ranks 1` — exit 0.
8. `python tools/repro/run_c09_static_test.py --source . --stage-base 0f6636e6080126d2ce58efcef942525bce9b524c --json-out evidence/stages/C09/STATIC.json` — exit 0.
9. `python -m py_compile tools/repro/run_c09_geometry_runtime.py tools/repro/run_c09_checkpoint_tests.py tools/repro/run_c09_feature_off.py tools/repro/run_c09_static_test.py` — exit 0.
10. `git diff --check` — exit 0.
11. `Get-FileHash src/chemistry/bmx_chem_K.H -Algorithm SHA256` — exit 0, exact expected hash.

An earlier feature-off invocation used obsolete flag names and exited 1 in
`argparse`, before BMX launch or evidence-file creation. The corrected command
5 above is the authoritative invocation and passed.

## Files changed and why

- `contracts/decision_reconciliation.{json,md}`,
  `contracts/release_blockers.json`, and `contracts/p11/*`: freeze the exact
  P11 contract and reconcile C09-only user authority without overstating it.
- `src/chemistry/bmx_cell_interaction_K.H`,
  `src/chemistry/bmx_chem_layout.H`,
  `src/chemistry/bmx_phosphorus_geometry_K.H`, `src/des/bmx_pc.H`,
  `src/des/bmx_pc_interaction.cpp`,
  `src/diffusion/bmx_define_coeffs_on_faces.cpp`,
  `src/io/bmx_checkpoint_schema.{H,cpp}`, `src/io/bmx_chk.cpp`,
  `src/io/bmx_restart.cpp`, and `src/timestepping/bmx_evolve.cpp`: implement
  the C09 geometry, production motion, event, no-flux, and restart paths.
- `tools/repro/c09_geometry_unit.cpp` and `tools/repro/run_c09_*`: build and
  qualify exact C09 behavior, provenance, and ownership.
- `evidence/stages/C09/*`: preserve build, raw log, tests, report, and handoff.

The machine-readable report lists every path in these groups. The local
`evidence/stages/C09/.gitattributes` mirrors C08's raw-log policy: it preserves
the exact CRLF build-log bytes and disables trailing-space diagnostics only for
that raw capture. Static scope is
computed from immutable C09 base `0f6636e…`, not from an empty working tree,
and reports zero unexpected paths.

## Conservation, restart, and claim effects

C09 event and projection paths do not mutate chemistry, export, carbon reward,
or the phosphorus ledger. The reserved rejected-growth count remains zero.
Restart now binds enabled P11 state to exact schema-v3 geometry identity before
payload loading; default-off schema-v3 restart remains supported.

This is Windows CPU engineering qualification only. It is not reference-host
or release evidence, independent numerical review, mentor/scientific approval,
calibration, predictive biology, full-plate validity, RG-SW:GO, RG-SCI:GO,
publication readiness, or formal P05–P18 acceptance.

## Blockers and carry-forward boundary

C09-local blockers: none. The global release-blocker ledger retains 28 later
items. C10/P12 remains unstarted and is still gated by its experiment contract,
controls, replicates, seed policy, and independent numerical/release-host
qualification requirements. This report supplies no authority to begin it.

Two earlier C09 evidence attempts are preserved outside the product repository
at `runs/c09-evidence-pre-motion` and `runs/c09-evidence-pre-nonzero-mask`.
They are superseded and are not cited as authoritative qualification evidence.
