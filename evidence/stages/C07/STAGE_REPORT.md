# C07 — P09 three-state phosphorus infrastructure

- **Stage ID:** `C07`
- **Status:** `PASS`
- **Completed:** 2026-08-01 UTC
- **Role:** sole product-branch writer (Codex) from `e7a69521`
- **Independent X01–X09 reviewer eligibility:** **no** for these bytes
- **Input commit:** `947100e966200c5dc8f1a40ef7480b5d0ead096b`
- **Input tree:** `3aaef073d25d94289f70d9f4b5afdb85de034a7d`
- **Stage commit:** recorded after commit in `COMMIT.txt` and
  `STAGE_REPORT.json#/output_git_commit`
- **Post-stage review follow-up:** `REVIEW-C07-001` closed by semantic G1/G4
  runtime evidence recorded below; implementation/evidence commit
  `1cbaabe386c9496a55e5d2cdcd562c1981f307a9`

C07 implements the P09 storage and I/O plumbing authorized by the recovered
execution prompt and the user's narrow transfer-file ownership exception. The
particle chemistry ABI is eight components in both modes; the mesh remains six
components when disabled and seven when enabled. Explicit maps keep particle
`P_E` internal-only. Enabled P09 operators remain exactly off, malformed
schemas fail closed, all allocated particle fields are initialized
deterministically, and plot metadata is semantic.

The frozen C04/P07 chemistry kernel was not edited. Its SHA-256 remains
`9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.

Claude's subsequent read-only review correctly found that C07's original
feature-off comparator used normalized stdout from three no-trigger controls.
That evidence did not exercise or observe the widened chemistry blocks, so its
feature-off claim was too strong. `REVIEW-C07-001` is closed by the follow-up
qualification in section 6: the 46-real P07 and 52-real C07 executables have
exactly identical semantic particle trajectories through G1 growth and G4
growth/split/rejection, and every C07 reserved slot is exactly zero at every
dump. The original stdout controls remain supplemental evidence only.

---

## 1. Authority and ownership resolution

The authoritative handoff, applicable `AGENTS.md`, mandatory planning-package
sequence, P09 preparation, confirmed decisions 02/04/06/07, C01–C05 and C06A
reports, recovered C07/C13 prompts, current source, and superseded-marked draft
plan were reconciled before implementation.

The recovered prompt pack is the user attachment `pasted-text.txt`, SHA-256
`d314e0b16234e92e26108a0b8bbac87d1337b09c3f226ff17ac486421f5da3e3`.
Its C07 prompt is lines 643–693. The prompt normally reserves central transfer
files for the integrator.

The user then supplied the exact missing authority:

> I authorize Codex, as the sole writer, to modify
> `src/des/bmx_calc_txfr.cpp` during C07 only as needed to separate the
> 6/7-component mesh from the 8-component particle layout and implement
> explicit maps. Keep `bmx_chem_K.H` frozen and do not introduce C08+ behavior.

That closes `B-C07-01`. The exception was used only in
`src/des/bmx_calc_txfr.cpp`; no other integrator-owned product file changed.
`evidence/stages/C07/INTEGRATOR_HANDOFF.md` is retained as the historical
root-cause record and marked resolved.

Because the sandbox permits writes only in the handoff workspace, work was
performed in the writable clone
`C:\b\BMX-shadow-handoff-20260721\BMX-RG-SW-C07-product`, based exactly on the
clean authoritative product HEAD. After commits, the authoritative
`rgsw/product` worktree is fast-forwarded to those commits and rechecked clean.

## 2. Frozen input identity

| Item | Verified value |
|---|---|
| Authoritative product branch | `rgsw/product` |
| Input commit / tree | `947100e966200c5dc8f1a40ef7480b5d0ead096b` / `3aaef073d25d94289f70d9f4b5afdb85de034a7d` |
| Candidate chemistry commit | `adb427331e180cd0b4faa74a4ab2098381b2eabb` |
| Input `src/chemistry` tree | `423d11cb32c9773bb89c028900b4fcd48d6e4d02` |
| Pinned AMReX commit / tree | `cbdc6580ee3d78cccdd37172e4ba077ee181f483` / `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6` |
| Frozen kernel SHA-256 | `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02` |
| P07 reference executable SHA-256 | `64b9aaccd6a97599e8bb0df17640018e89533ed7627e947800ae33b0426bef7c` |
| Pre-stage status | clean |

## 3. Implemented P09 contract

| Surface | Disabled | Enabled |
|---|---|---|
| Mesh layout | `A B C D F P` (6) | `A B C D F P_D P_F` (7) |
| Particle layout | `A B C D F P reserved_P_E reserved_P_F` (8) | `A B C D F P_D P_E P_F` (8) |
| Mesh→particle map | `0→0,1→1,2→2,3→3,4→4,5→5` | `0→0,1→1,2→2,3→3,4→4,5→5,6→7` |
| Particle→mesh map | slots 0–5 only | slots 0–5 plus `7→6`; slot 6 has no mesh target |

The implementation provides:

- separate compile-time particle stride 8 and active runtime mesh count 6/7;
- three eight-wide particle blocks: committed, working, and increment;
- deterministic zero initialization of the complete real and integer particle
  allocation before explicit input values are populated;
- explicit enabled particle initialization through
  `chem_species.initial_particle_P = P_D P_E P_F`; no value is defaulted;
- exact schema rejection for simultaneous `P`/`P_D`, mesh `P_E`, missing
  `P_F`, reordered phosphorus layouts, and legacy aliases;
- exact-zero gates for mesh `P_F` diffusion and all pre-existing generic-P
  reaction/exchange/growth controls in enabled mode;
- one-pass explicit deposition maps and mapped interpolation with no mesh E;
- 24 semantic particle plot names plus enabled mesh names `P_D`/`P_F`;
- schema-v2 metadata constants (layout descriptor/hash, component counts,
  units-decision source and decision-contract hashes) that remain explicitly
  `checkpoint_schema_ready=false` while P10 operator order and global-ledger
  integration are unbound.

The checkpoint constants are scaffolding only, exactly as C07 requests. C07
does **not** claim a checkpoint-v2 writer, restart round trip, or legacy
checkpoint compatibility. The fail-closed readiness token prevents later code
from presenting the incomplete scaffold as a complete compatibility contract.

No uptake, D/E reaction, growth limitation, F activation, bonded transport,
export/reward, topology, geometry, or global operator-order behavior was added.

## 4. Root-cause and operator-order audit

The original blocker was a representation collision: the frozen kernel uses
`NUM_CHEM_COMPONENTS` as the particle block stride, while
`bmx_calc_txfr.cpp` used it as the mesh interpolation count. No single value
could represent particle 8 and mesh 6/7. The authorized repair makes the legacy
macro an eight-slot particle-stride alias, obtains mesh count from
`FLUID::nchem_species`, and maps each active mesh component explicitly.

Multiple `ParticleToMesh` calls were rejected as an implementation shape:
AMReX's multilevel wrapper performs a final component copy, so later calls can
overwrite components deposited by earlier calls. C07 instead uses one mapped
functor pass for each existing deposition scheme. The trilinear path retains
the original weight construction, normalization, loop nesting, and atomic-add
ordering. The disabled path still calls the original functors without a new
branch inside their numerical loops.

`D-C07-01` remains open: configuration calls slot 4 `F`, while the frozen
kernel names and actively uses that legacy slot as `E`. C07 preserves the
frozen bytes and assigns no new meaning to that slot.

## 5. Files changed

### Product source

| File | C07 reason |
|---|---|
| `src/chemistry/bmx_chem_layout.H` | canonical counts, indices, names, schema classifier, maps, and fail-closed metadata scaffold |
| `src/chemistry/bmx_chem.H` | distinct mesh/particle constants and eight-slot particle ABI |
| `src/chemistry/bmx_chem.cpp` | mode-aware initialization and default-off validation |
| `src/mods/bmx_fluid_parms.cpp` | mesh schema/count/diffusion validation and mesh→particle IDs |
| `src/setup/bmx_init_fluid.cpp` | validated deterministic mesh initialization |
| `src/des/bmx_pc_init.cpp` | deterministic complete-record and eight-slot particle initialization |
| `src/io/bmx_plt.cpp` | semantic names for all particle chemistry fields |
| `src/des/bmx_calc_txfr.cpp` | user-authorized explicit 6/7↔8 transfer seam only |

`src/chemistry/bmx_chem_K.H` is absent from the diff.

### Reproduction and evidence

- `tools/repro/c07_layout_unit.cpp`
- `tools/repro/run_c07_layout_unit.ps1`
- `tools/repro/run_c07_static_test.py`
- `tools/repro/run_c07_schema_tests.py`
- `tools/repro/run_c07_feature_off.py`
- `tools/repro/analyze_p07_geometry.py` (46/52-real ABI-aware semantic parser)
- `tools/repro/run_c07_semantic_feature_off.py`
- `tools/repro/native_windows_env.ps1`
- `tools/repro/configure_native_windows.ps1`
- `evidence/stages/C07/{STAGE_REPORT.md,STAGE_REPORT.json,STATIC_TEST.json,SCHEMA_TESTS.json,FEATURE_OFF.json,INTEGRATOR_HANDOFF.md,COMMIT.txt}`

The native environment scripts now resolve and pass the Windows SDK manifest
tool (`mt.exe`). The first configure attempt exposed `CMAKE_MT-NOTFOUND` before
any product compilation; the SDK already contained `mt.exe` beside `rc.exe`.
After the resolver fix, fresh configure and build passed.

## 6. Build and mandatory validation

Environment: Microsoft Windows NT `10.0.26200.0`, MSVC `19.44.35228`, CMake
`4.4.0`, Ninja, Release, double precision, CPU, MPI enabled, OpenMP/GPU/Hypre
disabled, pinned AMReX.

| Check | Exact command summary | Result |
|---|---|---|
| Diff hygiene | `git diff --check` | PASS |
| Static/layout/ownership | bundled Python `tools/repro/run_c07_static_test.py --root . --json-out ...` | PASS, 10/10 |
| Standalone map unit | `powershell -ExecutionPolicy Bypass -File tools/repro/run_c07_layout_unit.ps1 ...` | PASS |
| Fresh configure | `powershell ... configure_native_windows.ps1 -SourceDir ... -BuildDir ... -Fresh` | PASS |
| Clean build | `powershell ... build_native_windows.ps1 -BuildDir ... -Parallel 8` | PASS, 200/200 |
| Runtime schema matrix | bundled Python `tools/repro/run_c07_schema_tests.py --exe ... --source . ...` | PASS, 9/9 |
| Smoke | `powershell ... run_smoke_native_windows.ps1 -BuildDir ... -RunRoot ...` | PASS: describe, init, one step, one step on 2 MPI ranks |
| Feature-off stdout controls (supplemental) | bundled Python `tools/repro/run_c07_feature_off.py --p07-exe ... --c07-exe ...` | PASS, 3/3, zero normalized differing lines; no-trigger fixtures do not establish semantic equivalence |
| Feature-off semantic growth/split comparison | bundled Python `tools/repro/run_c07_semantic_feature_off.py --p07-exe ... --c07-exe ...` | PASS, G1/G4, 72 dumps and 420 particle records exactly identical; 2,520 reserved-slot observations exactly zero |
| Frozen kernel | `Get-FileHash src/chemistry/bmx_chem_K.H -Algorithm SHA256` | PASS, exact frozen hash |

Final executable:

- path: `C:\b\BMX-shadow-handoff-20260721\build-c07-native-release\bmx.exe`
- size: 2,405,376 bytes
- SHA-256: `f86889fc0def576f520340c91f14847aed7f2facf0362349852b1e259bcb1b67`
- `CMakeCache.txt` SHA-256:
  `d7bfb8303d2262071c922cbc9d19bbc54d4b9e41a0ebe567ace0a72883dbdd91`
- `compile_commands.json` SHA-256:
  `8b6059e2417504d9b337a15db7614f13b3019452ae2ea6708548302bdf2a0eff`

Runtime schema results:

- accepted disabled schema at initialization;
- accepted enabled schema through one complete step, exercising mapped
  interpolation and deposition;
- accepted enabled plot output with mesh `P_D/P_F`, no mesh `P_E`, and all 24
  semantic particle names;
- rejected simultaneous `P`/`P_D`, mesh `P_E`, missing `P_F`, reordered
  layout, nonzero `P_F` diffusion, and missing explicit internal P
  initialization (all expected nonzero exit 22).

The supplemental stdout controls use the frozen C03 normalizer unchanged and,
exactly as C04 reviewed, remove only the unavoidable `BMX git hash:`
provenance line. Results:

| Fixture | Ranks | Normalized SHA-256 in P07 and C07 | Differing lines |
|---|---:|---|---:|
| `N2_init_only` | 1 | `75741020163811e7cfbbe16a1a9f3dba0be003b2ab0cf57017695fed675977e6` | 0 |
| `N1_no_growth` | 1 | `b972c33e07f0fc494d4979e22f03f1b21246d71473948ea80eaa63ed2d5da31e` | 0 |
| `N3_no_growth_2rank` | 2 | `7b8fca046ca8fc2235ea3afff1c2dd717f8821abd48461697068b36e027ffeae` | 0 |

Checked-in machine-readable evidence is in `STATIC_TEST.json`,
`SCHEMA_TESTS.json`, `FEATURE_OFF.json`, and `FEATURE_OFF_SEMANTIC.json`.

The verdict-bearing semantic follow-up compares every particle at every dump,
at AMReX particle-ASCII precision 15. It covers topology identifiers and bond
counts; radius, length, area, volume, `dadt`, and `dvdt`; and the first six
committed, working, and increment values:

| Fixture | Exercised path | Dumps / particle records | Semantic differences | C07 reserved-slot audit |
|---|---:|---:|---:|---:|
| `G1_tip_length_only` | 76 length-only transitions; 2 split/new events | 41 / 79 | 0 | 474 observations, 0 nonzero |
| `G4_nontip_rejected` | 188 rejections; 19 split/new events | 31 / 341 | 0 | 2,046 observations, 0 nonzero |

This directly exercises the widened loop bounds and split paths absent from the
original controls. It is Windows engineering evidence, not release-host or
scientific evidence. Raw logs and scratch outputs are under
`C:\b\BMX-shadow-handoff-20260721\runs\c07-*`.

## 7. Blockers and gates

`B-C07-01` is **CLOSED** by the user's exact ownership exception and the passing
transfer/build/runtime evidence above.

`REVIEW-C07-001` is **CLOSED** by `FEATURE_OFF_SEMANTIC.json`. The original
normalized-stdout result is retained but is no longer the basis for the
feature-off equivalence claim.

C05's authoritative release blocker list is carried unchanged:

| ID | Status after C07 | C07 effect |
|---|---|---|
| `B-S00-03` | OPEN — mentor packet unsent | Does not block P09 infrastructure; still gates C06B and P12/P15/P16 science contracts. |
| `B-C02-01` | OPEN | Carried; not changed by C07. |
| `B-C03-02` | OPEN | Carried; not changed by C07. |
| `D-C04-07` | OPEN | Carried; not changed by C07. |

Stale C06A entries `B-C04-01` and `B-PLATFORM-01` are not reopened.
`B-S00-01` remains closed at C02. `D-C07-01` remains the open slot-4 naming
finding described above.

No GCE instance or other external resource was launched. External spend was
USD 0. The C07 execution prompt does not authorize cloud launch, and local
mandatory validation completed successfully.

## 8. Claim boundary and handoff

Established by C07: the authorized three-state **engineering infrastructure**
builds, validates enabled and disabled schemas, keeps E off mesh, rejects active
F plumbing, initializes and names the new storage deterministically, and is
feature-off semantically identical to the frozen P07 reference across the G1
growth and G4 growth/split/rejection trajectories at particle-dump precision
15, with the added reserved slots exactly zero throughout.

Not established: checkpoint schema-v2 readiness, legacy checkpoint migration,
P10 conservation/topology/restart semantics, uptake, reaction, growth,
transport, export/reward behavior, calibrated biology, predictive validity,
full-plate validity, publication or production readiness, formal P05–P18
acceptance, `RG-SW:GO`, or `RG-SCI:GO`.

Codex authored these bytes and must not later be described as an independent
X01–X09 reviewer of them. C07 ends here. C08 and all later stages were not
started.
