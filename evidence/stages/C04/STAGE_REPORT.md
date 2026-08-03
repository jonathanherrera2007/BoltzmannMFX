# C04 — implement and validate P07 carbon-only repair

- **Stage ID:** `C04`
- **Status:** `PASS` — **reference-platform qualified** (RT-1 and RT-2 both PASS, §17)
- **Date:** 2026-08-01 (fifth issue: reference-host qualification executed)
- **Role:** primary writer (Claude), product lane
- **Baseline:** `389e9e3` / tree `1c73deed`, AMReX `cbdc6580` / tree `fb714dc6`
- **Input HEAD:** `b686981f` (qualified); report issued at a later prep commit
- **Companion evidence:** `STAGE_REPORT.json`,
  `runs/c04-p07-geometry/GEOMETRY_INDEX.json`,
  `runs/c04-p07-donor-cap-fixture/DONOR_CAP_FIXTURE.json`,
  `runs/c04-diag-check/DIAGNOSTIC_CHECKS.json`,
  `runs/c04-provenance-check/PROVENANCE_CHECKS.json`,
  `LINUX_SMOKE.md`,
  **`reference/`** (the reference-host run: `QUALIFICATION_REFERENCE.json`,
  `GEOMETRY_REFERENCE.json`, `DONOR_CAP_REFERENCE.json`,
  `DIAGNOSTIC_REFERENCE.json`, `PROVENANCE_REFERENCE.json`, `logs/`)

> **`B-C04-02` is CLOSED.** All five P07 defect mappings are now demonstrated at
> runtime. The last one, the second-half fluid donor cap, is measured on the
> fluid side: the capped transfer equals the available amount **exactly**
> (`4.882812500000002e-12` vs `4.882812500000002e-12`, relative difference
> `0.00e+00`).
>
> **C04 is complete and reference-platform qualified (§17).** The full
> qualification sequence ran on a C02-compliant reference-capable host — GCE
> `n2-standard-8`, native Linux, Ubuntu 24.04.4, kernel `6.17.0-1021-gcp`, ext4 —
> and emitted `release_evidence: true` with **9/9** checks. All four images were
> built independently with distinct hashes, each reporting a **clean** worktree
> and an exact commit. **RT-1 and RT-2 both PASS** with separate evidence.
> `B-PLATFORM-01` is **CLOSED**.
>
> The reference host reproduces Windows and WSL1 numerically at full emitted
> precision: donor-cap `A_particles_final = 4.882812500000002e-12`, relative
> difference `0.00e+00`, M2 max closure residual `4.822133e-11`.
>
> *Superseded — the previous issue read:* Two *release-transition requirements*
> are outstanding, and they are independent of C04 correctness and of each
> other (§10):
>
> 1. **Reference-platform qualification** — `DEC-PLATFORM-001` makes Linux the
>    reference platform; every result below was produced on Windows. A Linux
>    portability smoke passed with numerically identical results, but only on a
>    `smoke-only` host (`B-PLATFORM-01`).
> 2. **Build provenance** — a release build must record which commit produced
>    it. Repaired under `D-C04-08` (commit `8428a5d`) and verified on both
>    platforms, but the repair has not yet been exercised through a full
>    qualification run on a reference host.
>
> Neither is a defect in the P07 repair. Both must be satisfied before evidence
> from this stage can be treated as release evidence.

---

## 1. Identity of everything this report depends on

### 1a. Source and dependency identity

| Item | Value |
|---|---|
| Canonical baseline commit | `389e9e35a1c7291a4af795b2e39f2db1f0012b61` |
| Canonical baseline tree | `1c73deedf0eb2feea833a7fddbc431ae9754d977` |
| **Final chemistry-candidate commit** | **`adb427331e180cd0b4faa74a4ab2098381b2eabb`** |
| Reviewed candidate kernel `src/chemistry/bmx_chem_K.H` | **`9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`** |
| Baseline kernel `src/chemistry/bmx_chem_K.H` | `711ae2caa6e7aabb5c084fe841d2d90edb85ee53e7abc7a859d7de00e6614678` |
| Diagnostic repair commit (`D-C04-05`) | `5481856f46ba4bd2432dd21800fe9dbec8d10a15` |
| Provenance repair commit (`D-C04-08`) | `8428a5d354025f2a222deae287679bf2e89a4a9b` |
| AMReX commit | `cbdc6580ee3d78cccdd37172e4ba077ee181f483` |
| AMReX tree | `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6` |

The AMReX commit and tree match the identities pinned in `AGENTS.md`.

### 1b. Build images — Windows development platform

The reference-host images, which are the qualified ones, are in §17b.


| image | chemistry | diagnostic | SHA-256 |
|---|---|---|---|
| `c03-baseline-release` | baseline `711ae2ca` | no | `e2effe2c375890d70cc28c40ab038ef00cc3e86cf384e25f1683f164918a9b9a` |
| `c04-p07-release` | candidate `9519fc24` | no | `64b9aaccd6a97599e8bb0df17640018e89533ed7627e947800ae33b0426bef7c` |
| `c04-baseline-diag-release` | baseline `711ae2ca` | yes | `1e55ee7892c6ee7707c642dd09dd81ebda21352bdfbf1e24153144ae2a0fdd35` |
| `c04-diag-release` | candidate `9519fc24` | yes | `bc133b41820aa94c10eb181662c614a11b6e76867f478216e82b1f81aa6de93a` |

The instrumented pair carries the **same** diagnostic patch applied to
**different** chemistry, so the differential still isolates the chemistry. The
instrumented baseline lives in its own worktree (`worktrees/baseline-diag`) so
the C03 baseline reference tree stays pristine.

### 1c. Three concerns, kept strictly apart

| | reviewed chemistry candidate | conservation diagnostic | build provenance |
|---|---|---|---|
| what | the P07 carbon repair | `bmx::ComputeAndPrintSums` | `D-C04-08` worktree provenance |
| files | `src/chemistry/bmx_chem_K.H` | `src/bmx.cpp`, `src/bmx.H`, `src/setup/bmx_init.cpp` | `CMakeLists.txt`, `src/CMakeLists.txt`, `src/io/bmx_build_info.cpp`, `tools/CMake/BMX_Provenance.cmake` |
| commit | `adb4273` | `5481856` | `8428a5d` |
| owner | C04 writer | integrator | integrator |
| behavioural change to the model | the repair itself | **none** | **none** |

Both instrumentation commits are **separate** from the chemistry candidate and
touch no chemistry, exchange law, geometry, growth or donor-cap behaviour. The
reviewed candidate kernel hashes to `9519fc24…ffba02` before and after each of
them; verified at the start of the clean re-run, after each instrumentation
commit, and at the end.

### 1d. Evidence-producing artefacts, all tracked and committed

| Artefact | Purpose |
|---|---|
| `tools/repro/run_p07_donor_cap_fixture.py` | donor-cap fixture, the `k1` sweep, and the exact-equality assertion (M3) |
| `tools/repro/fixtures/fungi_init_cfg_small_stored_area.dat` | opens the `α < 1 < α'` window |
| `tools/repro/analyze_p07_geometry.py` | branch predicted-vs-observed classifier |
| `tools/repro/run_p07_geometry_fixtures.ps1` | geometry matrix driver |
| `tools/repro/fixtures/fungi_init_cfg_selfconsistent.dat` | `G7` self-consistent control |
| `tools/repro/check_sums_diagnostic.py` | diagnostic regression guard (5 checks) |
| `tools/repro/check_build_provenance.py` | provenance regression fixture (7 checks) |
| `tools/CMake/BMX_Provenance.cmake`, `tools/CMake/bmx_provenance.H.in` | provenance resolver |

All are tracked in git and committed; the worktree carries no uncommitted
evidence-producing file. `tools/repro/run_p07_donor_cap_probe.ps1` is also
tracked but is marked **SUPERSEDED** in its header and JSON output (§4b).

## 2. Method: direct observation, not inference

The first C04 matrix inferred branch execution from structural statistics of the
stdout log (count of differing lines, max relative difference). Those cannot
attribute a difference to a branch, and they produced three false conclusions
(§6). Two observables replace them, neither of which requires touching the
kernel:

- **Geometry / particle side** — `amr.par_ascii_int` dumps every particle real
  and integer field per step at precision 15.
- **Fluid side** — `bmx.print_sums` reports mesh and particle content at full
  precision. This is what the particle dump structurally cannot provide, and it
  is what closes the donor-cap row.

Both are pure output. Neutrality is proven, not assumed:

| check | result |
|---|---|
| particle dump on vs off (fixture `G0`) | **1308 non-timing stdout lines textually identical, line for line** |
| diagnostic on vs off | **708 non-diagnostic lines textually identical, line for line** |

For every geometry fixture two independent determinations are made and required
to agree: the branch **predicted** by evaluating the kernel's own predicates
(`bmx_chem_K.H:2038-2105`) against observed radius/c_length, and the branch
**observed** from exact field-change classification at full emitted precision.
Exactness is
essential — the radius-only and length-only branches are distinguished from the
proportional branch precisely by one field being left unchanged at full
emitted precision, and
CDEF-05's rollback restores `vol` to `orig_cell_vol` exactly.

## 3. All five defect mappings, demonstrated

| Mapping | Site | Fixture | Evidence | Verdict |
|---|---|---|---|---|
| **CDEF-01/02** donor cap A/C | `:2188`, `:2220` | `donor_cap` | transfer saturates at the cell content across a 50× `k1` span; final content equals available **exactly** | **DEMONSTRATED** |
| **CDEF-03** stale area, 1st half | `:1623` | `G1`–`G3` | `carbon_exchange_area` refresh changes `cA`/`cC` | **DEMONSTRATED** |
| **CDEF-04** tip length-only | `:2072` | `G1` | 76/76 transitions, stored area unchanged 76/76 | **DEMONSTRATED** |
| **CDEF-04** tip radius-only | `:2064` | `G2` | 40/40 transitions, stored area unchanged 40/40 | **DEMONSTRATED** |
| **CDEF-05** non-tip rejection | `:2098` | `G4` | 188 observed rejections, `cB` rel = 1.000 | **DEMONSTRATED** |

### 3a. Geometry matrix (clean re-run, 7/7)

| Fixture | Target branch | Predicted | Observed | Stored area | Verdict |
|---|---|---|---|---|---|
| `G1_tip_length_only` | `:2072` (CDEF-04) | 76 | **76** | stale 76/76 | PASS |
| `G2_tip_radius_only` | `:2064` (CDEF-04) | 40 | **40** | stale 40/40 | PASS |
| `G3_tip_proportional` | `:2044` contrast | 40 | **40** | refreshed | PASS |
| `G4_nontip_rejected` | `:2098` (CDEF-05) | 188 | **188** | — | PASS |
| `G5_nontip_radial` | `:2084` contrast | — | — | — | unreachable as predeclared |
| `G6_no_growth_stock_init` | control, stock init | — | `NO_GROWTH` 20 | — | PASS (differs, §6b) |
| `G7_no_growth_exact_init` | control, exact init | — | `NO_GROWTH` 20 | — | **PASS (numerically identical)** |

Predicted and observed agree in every fixture with nonzero growth. G3 is the
contrast that proves the observable distinguishes "stale" from "never changes":
there the area *is* rewritten.

### 3b. The repair's effect, attributed to an observed branch

| Fixture | Field | Baseline | Repaired | rel |
|---|---|---|---|---|
| G4 (CDEF-05) | `cB` | 1.838014e-10 | **1.583784e-05** | **1.000** |
| G2 (CDEF-04) | `cC` | 4.277881e-06 | 3.786592e-06 | 1.148e-01 |
| G1 (CDEF-04) | `cA` | 1.747464e-10 | 1.698896e-10 | 5.481e-02 |
| G7 (control) | — | — | — | **0** |

G4 is decisive: `cB` differs by five orders of magnitude, `rel = 1.000`, on the
fixture where 188 non-tip rejections were directly counted. The baseline leaves
`cB` debited by growth it then rejected; the repair restores
`cB = cB_before_growth`.

## 4. CDEF-01 / CDEF-02 — the donor cap

### 4a. What the branch does

```
baseline:  dA2 = -fA_tmp*fluid_vol ;  dfA = -fA_tmp        // zeroes the fluid AND
                                                           // debits the particle
repaired:  dA2 =  fA_tmp*fluid_vol ;  dfA = dA2/fluid_vol  // credits the particle
                                                           // exactly what the fluid held
```

### 4b. Why the earlier probe was wrong

The previous issue reported "NOT REACHED under any `k1` tested". That was a
**detector artefact, not a property of the model**. It watched for a sign flip
in the particle-side transfer, and a sign flip can only occur when the
*baseline* cap fires — only the baseline assignment reverses direction. A
repaired-side-only activation is invisible to it.

Two confounds also suppressed the exchange entirely, and both had to be removed
before anything could be measured:

1. **The particle sits where there is no fluid A.** It is at `z = 0.0752`, just
   above `fluid.surface_location = 0.075`, and the initial field is zero above
   the surface. No uptake is possible there at all. Fixed by raising the surface
   above the domain so the field is uniform.
2. **`rA = -k2*cA + kr2*cB*cC` (`:1849`) drains A far faster than the exchange
   moves it.** With `k2 = 4.0` the reaction dominates completely. Fixed by
   zeroing `k2`/`kr2`, and `kv`/`kg`, so the *only* process touching A is the
   membrane exchange.

`tools/repro/run_p07_donor_cap_probe.ps1` is retained but marked **SUPERSEDED**
in its own header and in its JSON output, so its negative result cannot be cited
as evidence about the code.

### 4c. How the window is opened

Both trees use the **stored** area in the first half; only the repaired tree
recomputes the **true** area for the second. Storing an area 100× smaller than
`2*pi*r*(r+L)` therefore holds the first half far under the cap while letting the
repaired second half exceed it:

```
alpha  = 0.5*dtp*A_stored*k1/fluid_vol      both trees, first half
alpha' = 0.5*dtp*A_true  *k1/fluid_vol      repaired only, second half
fluid_vol = grid_vol/npart  (:1438),  dtp = fixed_dt/4 = 0.0625
```

### 4d. Result — saturation, and exact equality

```
     k1     alpha  alphaprime    baseline dA    repaired dA  rep/available  capped
    0.5    0.0033       0.327   1.261737e-13   4.569058e-12       0.935743   False
      1    0.0065       0.653   2.494785e-13   4.868219e-12       0.997011   False
      2    0.0131       1.307   4.877042e-13   4.871033e-12       0.997587    True
      5    0.0327       3.267   1.139173e-12   4.871033e-12       0.997587    True
     20    0.1307      13.069   3.287037e-12   4.871033e-12       0.997587    True
    100    0.6535      65.345   4.870056e-12   4.871032e-12       0.997587    True
```

The **shape** is the proof, not any single number:

- **The baseline transfer grows linearly with `k1`** — 1.26e-13 → 4.87e-12 over
  a 200× span. Uncapped, exactly as expected when the second half uses the small
  stored area.
- **The repaired transfer saturates at `4.871033e-12`, identical to seven
  significant figures across `k1` = 2, 5, 20, 100** — a 50× span. A transfer that
  stops tracking its own driving rate is a cap; nothing else produces that.
- Saturation begins precisely where the arithmetic says it must, between
  `alpha' = 0.653` and `alpha' = 1.307`.

The mandatory row itself, stated exactly. After the cap fires, everything the
cell held is in the particle:

| `k1` | `A_particles_final` | available = `fA0 * V_cell` | rel |
|---|---|---|---|
| 2 | `4.882812500000001e-12` | `4.882812500000002e-12` | 1.65e-16 |
| **5** | **`4.882812500000002e-12`** | **`4.882812500000002e-12`** | **0.00e+00** |
| **20** | **`4.882812500000002e-12`** | **`4.882812500000002e-12`** | **0.00e+00** |
| 100 | `4.882812499999993e-12` | `4.882812500000002e-12` | 1.82e-15 |

At `k1 = 5`: the particle held `1.1780000000000001e-14`, took in
`4.8710325000000015e-12`, and the sum is `4.882812500000002e-12` — the cell's
entire content, to the last bit. The 0.24% that looked like a shortfall in the
`rep/available` column is exactly the particle's pre-existing content.

Conservation holds throughout: `dA_fluid = -dA_particles`, max relative residual
**4.822e-11** of the cell content (roundoff — see §4e). The repair **transfers**; the
baseline sign would have destroyed.

Without the cap the uncapped request at `k1 = 5` is `1.595e-11`, **3.267× the
available amount**, which would drive `fA_tmp` negative and abort the run at
`:2298` ("Negative fluid concentration at second update"). No run aborted.

### 4e. The three residual figures, defined

Three different numbers appear above and in earlier issues of this report —
`4.6e-23`, `0.000e+00`, `4.822e-11`. They are **three distinct metrics**, not
three estimates of one quantity. Naming them precisely:

Let `V_cell` be the fine-cell fluid volume seen by the particle
(`fluid_vol = grid_vol/npart`, `bmx_chem_K.H:1438`) and `fA0` the initial fluid
A concentration. All amounts are **concentration × volume in native BMX units**
— lengths are cm, so an amount is (BMX concentration unit)·cm³. The inputs do
not declare a unit symbol for A, so no mol label is asserted here.

| | Metric | Formula | Normalization | Units |
|---|---|---|---|---|
| **M1** | exchange closure residual, absolute | `R_abs = ΔA_particles + ΔA_fluid` over the run | none | amount |
| **M2** | exchange closure residual, relative | `R_rel = \|R_abs\| / (fA0·V_cell)` | cell content | dimensionless |
| **M3** | cap equality residual, relative | `E_rel = \|A_particles_final − fA0·V_cell\| / (fA0·V_cell)` | cell content | dimensionless |

M1 and M2 ask *"was anything created or destroyed?"* M3 asks the mandatory row,
*"did the capped transfer equal the available amount?"* They are independent:
a transfer could conserve perfectly (M2 ≈ 0) while stopping at the wrong value
(M3 large), which is exactly the failure mode the baseline sign produces.

Reconciliation of the three figures:

| Figure | Metric | Where it comes from |
|---|---|---|
| `4.632050e-23` (reported earlier as `4.6e-23`) | **M1** | a single row — repaired tree, `k1 = 5`. An absolute amount, not a max and not normalized. |
| `4.822133e-11` | **M2** | the **maximum over all 12 rows**, attained at `k1 = 0.5` **baseline**, where `R_abs = 2.354557e-22`. Note this worst case is a row in which the cap does **not** fire; the repaired cap rows sit near `9.5e-12`. |
| `0.000e+00` | **M3** | `k1 = 5` and `k1 = 20`, repaired. Exact at double precision (`E_abs = 0.000e+00`). |

Full M3 across the capped rows: `1.654e-16` (k1=2), `0.000e+00` (k1=5),
`0.000e+00` (k1=20), `1.820e-15` (k1=100) — all at or below 2 ulp.

M2's worst case `4.822e-11` corresponds to `R_abs = 2.354557e-22` against a cell
content of `4.882812500000002e-12`; both are consistent with double-precision
accumulation over four chemistry substeps and neither indicates a conservation
defect. No tolerance was chosen after seeing these values — they are reported,
not tested against a threshold, because C04 declares no conservation acceptance
row. The conservation contract belongs to P10.

## 5. The instrumentation repair (`D-C04-05`, commit `5481856`)

Dead code that had rotted while unused. Both defects would have produced
confident nonsense on first re-enable:

1. Particle content was read at components **22/23/24** as A/B/C. Correct only
   while `realIdx::first_data` was 22; it is now **28**, so those indices
   actually read `dvdt`, `tau_split`, `bond_scale`. Offsets are now derived from
   `realIdx::first_data`.
2. Mesh components were hard-coded **0/1/2**, but the order comes from the
   `fluid.chem_species` input. Indices are now resolved **by name**, and a
   reordered list aborts rather than silently pairing mesh B with particle A.

The particle block and the mesh list agree at slots 0–2 but **diverge at slot 4**
(kernel `cE` vs input `F`, tracked as `D-C07-01`), so the diagnostic reports only
A/B/C and asserts the agreement it depends on.

**Volume closure is now reported, not enforced.** The dead version aborted on a
1e-12 relative mismatch. That assertion had never actually run, and enabling it
kills the fungi case within ~20 steps: `volSum()` tracks the deposited
volume-fraction field while `computeParticleVolume()` sums particle geometry, and
the two separate as segments grow (observed: particle volume 5.89e-10 → 6.89e-10
with the residual crossing the tolerance). A read-only diagnostic must not
terminate a run — aborting is itself a behavioural change, and a far larger one
than the drift it reports. The residual is emitted as data
(`SUMS volume_residual`, `volume_residual_rel`) and recorded as `D-C04-07` for
P10 rather than hidden by deleting the check or widened away by loosening it.

Gated on `bmx.print_sums`, **default off** — with the flag unset the function
returns before reading anything, so all previously captured evidence remains
valid.

**Regression guard** `tools/repro/check_sums_diagnostic.py`, **5/5 PASS**:

| Check | Result |
|---|---|
| field map matches `first_data` and species order | `first_data=28`, A=mesh0/part28, B=1/29, C=2/30 |
| particle totals vs independent ASCII-dump reference | **rel 0.0** for A, B, C |
| fluid totals vs analytic initial condition | rel ≤ 3.9e-14 |
| reordered species list is rejected | exit 22, diagnostic-owned abort |
| enabling the diagnostic is trajectory-neutral | 708 lines identical |

## 6. Corrections to earlier issues of this report

**a. `D-C04-02` — `F3` was a no-op fixture.** It set `max_seg_radius = 1.0e-6` to
"force the tip radius-only/length-only branches", but stock `max_seg_radius`
(2.5e-4) already equals the initial radius, so `radius < radius_max` is false at
t = 0 and the tip path is length-only from step 1. `F3` and its stock reference
were running identical code paths.

**b. `D-C04-03` — the initial condition is not self-consistent.** The claim that
`2*pi*r*(r+L)` "gives exactly the stored 5.105e-6" is wrong:

```
2*pi*r*(r+L)   = 5.105088062083415e-06
stored in init = 5.105e-06                (four significant figures)
relative       = 1.725e-05
```

The repair recomputes the area rather than reading the stored field, so it
corrects that rounding on the first step even with growth off. `N1` was declared
identical from normalized stdout logs, too coarse to resolve 1.7e-5. `G7`
repeats the control with the area at full precision and the trees **are**
numerically identical at full emitted precision, isolating the discrepancy to
the input file.

**c. `D-C04-06` — `F1` did not demonstrate the donor-cap fix.** The claim that
`F1`'s `max_rel = 1.0` was "the unique signature of the donor-cap sign fix" is
not supported: under `F1`'s exact configuration the recorded A amount is
`-1.872873e-17` baseline vs `-1.872870e-17` repaired, same sign to five
significant figures. The cap does not fire there. It fires under §4c, which `F1`
did not construct.

**d. A defect in my own harness.** `analyze_p07_geometry.py` had `dadt`/`dvdt` at
`realIdx` 22/23 instead of 21/22 — the trailing numbers in the enum comments are
1-based position markers, not indices. It was reading `dvdt` as `dadt` and
`tau_split` as `dvdt`. Caught by checking against physics: the length-only branch
predicts `dadt = 2*pi*r*(rV*L/V0) = 2.160e-10` and the corrected column reads
`2.162e-10`. The matrix was re-run; verdicts unchanged, because the mis-indexed
fields were a tiebreaker rather than the deciding discriminator. The parser now
asserts the model's self-describing layout fields (`num_reals`, `real_tot`,
`first_real_inc`) and rejects non-positive geometry.

## 7. Findings handed to other lanes

| ID | Finding | Owner |
|---|---|---|
| `D-C04-04` | `:2084` (non-tip radial growth) is unreachable from a single-segment initial condition: a non-tip segment requires a split, `checkSplit:46` requires `radius >= max_rad`, and the split paths never change `radius`, so every non-tip segment takes the rejection path. Not a P07 mapping. | review |
| `D-C04-07` | Volume closure drifts during evolution — `volSum()` and `computeParticleVolume()` separate as segments grow, past the 1e-12 relative tolerance the dead assertion used. Now reported as `SUMS volume_residual`. A genuine conservation question. | integrator (P10) |
| `D-C07-01` | `input_fungi` declares slot 4 as `F` while the kernel names and uses it as `E`. Dormant today; becomes live when `P_E` is introduced. | writer (C07) |
| `D-C04-08` | Build provenance did not survive linked worktrees across platforms. **REPAIRED** in commit `8428a5d` (§15). | integrator — done |

## 8. Mandatory validation

| Row | Status | Evidence |
|---|---|---|
| Static suite passes | **PASS** | 6/6 |
| Donors never become materially negative | **PASS** | aborts at `:2298`/`:2331` never triggered; all runs exit 0 |
| **Capped transfer equals available amount** | **PASS** | §4d — `4.882812500000002e-12` vs `4.882812500000002e-12`, rel `0.00e+00` |
| Second-half carbon exchange uses accepted post-growth area | **PASS** | G1 76/76, G2 40/40, contrast G3 |
| Rejected growth restores geometry and B state | **PASS** | G4, 188 rejections, `cB` rel 1.000 |
| No-trigger controls unchanged | **PASS** | G7 numerically identical at full emitted precision; G6 quantifies the input-file rounding |
| Clean build and runtime pass | **PASS** | candidate hash unchanged, all runs exit 0 |

## 9. Clean reproduction

```bash
# 1. verify the reviewed candidate is intact
sha256sum src/chemistry/bmx_chem_K.H   # 9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02

# 2. geometry matrix (candidate images, no instrumentation)
powershell -NoProfile -ExecutionPolicy Bypass -File tools/repro/run_p07_geometry_fixtures.ps1

# 3. diagnostic regression guard (instrumented repaired image)
python tools/repro/check_sums_diagnostic.py \
  --exe   ../../build/c04-diag-release/bmx.exe \
  --case-dir exec/fungi --work-dir ../../runs/c04-diag-check \
  --json-out ../../runs/c04-diag-check/DIAGNOSTIC_CHECKS.json

# 4. donor-cap fixture (both instrumented images)
python tools/repro/run_p07_donor_cap_fixture.py \
  --baseline-exe ../../build/c04-baseline-diag-release/bmx.exe \
  --repaired-exe ../../build/c04-diag-release/bmx.exe \
  --case-dir exec/fungi --out-dir ../../runs/c04-p07-donor-cap-fixture \
  --json-out ../../runs/c04-p07-donor-cap-fixture/DONOR_CAP_FIXTURE.json
```

All run directories were deleted before the final execution; every number above
comes from that clean re-run. Each fixture directory also contains the exact
`command.txt` used.

## 10. Blockers

### 10a. Release-transition requirements

These two gate the transition from "C04 correctness demonstrated" to "C04
evidence usable as release evidence". Both are independent of the P07 repair and
of each other; satisfying one does not satisfy the other.

| # | Requirement | State | Evidence / owner |
|---|---|---|---|
| **RT-1** | **Reference-platform qualification.** The C02–C04 evidence must be produced on a C02-compliant reference Linux host. | **NOT MET** — the only Linux host is WSL1, classified `smoke-only`; WSL2 cannot start (virtualization disabled in firmware). Portability smoke passed with numerically identical results. | `LINUX_SMOKE.md`; owner **user** (provision a host) |
| **RT-2** | **Build provenance.** A release build must record the commit that produced it, and must fail rather than emit an unattributable artefact. | **REPAIRED, NOT YET EXERCISED IN QUALIFICATION** — `D-C04-08` commit `8428a5d`; resolver 7/7 on Windows and Linux; binaries now report `48375fc42b36…` on both. Still to be run with `BMX_REQUIRE_PROVENANCE=ON` as part of a full reference-host qualification. | `runs/c04-provenance-check/PROVENANCE_CHECKS.json`; owner **integrator** |

RT-1 is the binding one: RT-2 cannot be closed out in a qualification run until a
reference host exists to run it on.

### 10b. Blocker list

| ID | Blocker | Owner | Status |
|---|---|---|---|
| **B-PLATFORM-01** | `DEC-PLATFORM-001` re-declares Linux the reference platform. **Every result above is Windows/MSVC.** A Linux portability smoke was executed and all C04 results reproduce **numerically identically at full emitted precision** under g++ 13.3.0 (§14), but the only Linux host available is WSL1, which C02 policy classifies `smoke-only` and forbids as release evidence. WSL2 cannot start (virtualization disabled in firmware). Provisioning a reference-capable host is a **user action**. | user | **OPEN — blocks C05 and C07** |
| B-S00-03 | Biology decisions unresolved; mentor packet unsent | user / mentor | OPEN |
| B-C02-01 | Six defects worked around in build config | writer + review | OPEN |
| B-C03-02 | C02 image hash not reproducible after install-path rename | writer | OPEN |
| ~~B-C04-01~~ | ~~CDEF-04 / CDEF-05 runtime reachability~~ | writer | **CLOSED** — §3a, §3b |
| ~~B-C04-02~~ | ~~CDEF-01 / CDEF-02 donor cap unreachable~~ | writer | **CLOSED** — §4d |

## 11. Deliberate asymmetry left by the patch — for the reviewer

`dP1`/`dP2` continue to use the stale `new_cell_area` while carbon moves to the
refreshed `carbon_exchange_area`. This is intentional (the P07 phosphorus
exclusion boundary), and the 91/91 P-line check confirms no phosphorus line
changed. The consequence must be stated plainly: **phosphorus retains exactly the
CDEF-03 staleness that carbon just had repaired.** "P07 passed" must never be
read as "phosphorus area handling is correct."

## 12. Claims

**Established, on Windows/MSVC:** the reviewed candidate is bound to the exact
expected bytes; passes its static suite; compiles; runs; is numerically
identical at full emitted precision when no
reviewed predicate triggers under a self-consistent initial condition; and all
five defect mappings execute at runtime with the repaired behaviour directly
observed — including the donor cap, whose capped transfer equals the available
amount to machine precision.

**Not claimed:** that this evidence is platform-qualified (it is not — see
`B-PLATFORM-01`); conservation correctness of the model as a whole (`D-C04-07` is
open); any scientific result; P07 phase success; formal P05–P18 acceptance;
`RG-SW:GO`; `RG-SCI:GO`.

## 13. Next step

Not C05, and not C07. C04's own gate is met, but both release-transition
requirements in §10a are outstanding and the gate rule binds on them. **RT-1** is
the binding one and needs a reference-capable Linux host, which is a user action
(§14). **RT-2** is repaired (§15) but cannot be closed out until there is a
reference host to run a qualification build on with
`BMX_REQUIRE_PROVENANCE=ON`.

## 14. Linux portability smoke — full record in `LINUX_SMOKE.md`

The Linux route was executed as far as the hardware allows.

**What it establishes.** The six Windows workarounds from
`evidence/stages/C02/DEFECTS.md` are Windows-specific rather than product
defects: `configure_linux.sh` applies none of them and 200/200 objects compiled
and linked with g++ 13.3.0. Every C04 result then reproduced **numerically identically at full emitted
precision**
across MSVC/Windows and g++/Linux:

| Result | Windows | Linux |
|---|---|---|
| Donor cap `A_particles_final` @ k1=5 | `4.882812500000002e-12` | `4.882812500000002e-12` |
| Donor cap relative difference | `0.00e+00` | `0.00e+00` |
| Saturation plateau, k1 = 2…100 | `4.871033e-12` | `4.871033e-12` |
| G1 length-only / area stale | 76 / 76 | 76 / 76 |
| G4 rejections / length-only | 188 / 133 | 188 / 133 |
| G4 `max_rel` | `9.999936e-01` | `9.999936e-01` |
| Diagnostic regression guard | 5/5 PASS | 5/5 PASS |

**What it does not establish.** The host is WSL1. `tools/repro/linux_env.sh`
classifies it `smoke-only` under the policy written at C02 — *"a syscall
translation layer, not a Linux kernel… must never carry release evidence"* — and
that classification is honoured rather than argued around. WSL2 cannot start
because virtualization is disabled in firmware, which an agent must not change.
So this is a portability result, not platform qualification, and
`B-PLATFORM-01` stays open.

**New finding `D-C04-08`:** each worktree's `.git` file stores an absolute
Windows path, so under Linux `git rev-parse` fails and `get_git_info` stamps
**empty build provenance**. Harmless for a smoke build; a genuine defect for
release evidence, where the build must record which commit produced it. Owner:
integrator, before any Linux release build.

The agreement materially reduces the risk that re-execution on a
reference host changes anything. It is not a substitute for that re-execution.

## 15. Build provenance repair (`D-C04-08`, commit `8428a5d`)

Integrator-owned. No chemistry, exchange law, geometry, growth or donor-cap
behaviour changes; the candidate kernel still hashes to `9519fc24…ffba02`.

### 15a. Three compounding defects

A Linux build could not say which commit produced it, for three reasons at once:

1. **`get_git_info()` captured nothing on any platform.** It was invoked as
   `get_git_info( )` with no arguments, so its `${ARGC} GREATER 0` guards never
   fired and `${ARGV0}`/`${ARGV1}` were never set. It only printed, and nothing
   consumed it. This was true on Windows too — the Windows build "worked" only
   because AMReX independently produced a hash.
2. **The worktree pointer is not portable.** A linked worktree stores `.git` as
   a **file** holding an absolute `gitdir:` path in the syntax of the machine
   that created it. AMReX's `generate_buildinfo()` runs `git describe` in the
   source directory, which fails there, yielding an empty hash.
3. **The report failed open.** `writeBuildInfo()` printed the line only
   `if (strlen(githash1) > 0)`, so a build carrying *no* provenance was
   indistinguishable from one that simply did not print it.

### 15b. The subtle part

CMake's `IS_ABSOLUTE` is evaluated with **host** syntax. On Linux it reports
FALSE for `C:/Users/...`, so the pointer was joined onto the source directory,
producing `<src>/C:/Users/...` — which is the exact string in the observed
failure. The drive-letter form is now recognised explicitly rather than trusting
`IS_ABSOLUTE`.

### 15c. What the repair does

`tools/CMake/BMX_Provenance.cmake` resolves provenance independently of AMReX
(a pinned submodule that must not be modified). It handles `.git` as a
**directory** (ordinary checkout) and as a **file** (linked worktree,
submodule), never assuming the directory form; resolves relative pointers
against the source tree; and translates absolute pointers written in another
platform's syntax. Results are compiled in via a generated `bmx_provenance.H`
and printed **unconditionally**, including an explicit `UNAVAILABLE` plus a
warning. `BMX_REQUIRE_PROVENANCE` (default OFF) makes configure **fail** rather
than emit an unattributable artefact.

| | before | after |
|---|---|---|
| Windows commit | (AMReX hash only) | `48375fc42b36d238241656796ae4e7938a42ff21` |
| Linux commit | **empty** | `48375fc42b36d238241656796ae4e7938a42ff21` |
| Linux note | — | `linked worktree, absolute gitdir, translated across platforms` |
| dirty state | not reported | reported (`clean`/`dirty`, from `status --porcelain`) |

### 15d. Regression fixture — 7/7 on Windows **and** Linux

`tools/repro/check_build_provenance.py` drives the same CMake module the build
uses, in `-P` probe mode, so it cannot drift from the implementation.

| Check | Expected | Result |
|---|---|---|
| live worktree resolves | RESOLVED | PASS |
| ordinary checkout (`.git` is a directory) | RESOLVED | PASS |
| worktree, relative pointer | RESOLVED, same commit | PASS |
| **worktree, foreign absolute pointer** (the `D-C04-08` failure) | RESOLVED, same commit | **PASS** |
| worktree, unresolvable pointer | UNAVAILABLE | PASS |
| not a repository | UNAVAILABLE | PASS |
| unresolvable + `BMX_REQUIRE_PROVENANCE=ON` | configure FAILS | PASS |

The two worktree cases assert not merely that *some* commit is returned but that
it **matches the live worktree's commit**, so a resolver that silently found the
wrong repository would fail.

### 15e. Known limitation

AMReX's own `HASH1` remains empty on Linux. That code is inside the pinned
submodule and is deliberately not modified. BMX's own provenance is now
authoritative and is what a reviewer should read; the AMReX line is
supplementary and may be absent.

## 16. Complete qualification sequence

`tools/repro/run_c04_qualification.py` runs the whole sequence in order from a
clean workspace on any platform:

| # | Step | What it establishes |
|---|---|---|
| 0 | identity | candidate kernel hash, AMReX commit/tree, build provenance |
| 1 | build | four images present and hashed |
| 2 | geometry | 7-fixture matrix + `G0` observation-neutrality |
| 3 | diagnostic | `ComputeAndPrintSums` guard, 5 checks |
| 4 | donor cap | `k1` sweep, saturation, exact-equality assertion (M3) |
| 5 | provenance | `D-C04-08` fixture, 7 checks |

**Platform classification is enforced, not advisory.** The driver reads
`BMX_PLATFORM_CLASS` from `tools/repro/linux_env.sh` and emits
`release_evidence: true` only when the host is `reference-capable` **and**
provenance resolved **and** every check passed. There is no override flag.

`run_p07_geometry_fixtures.ps1` was PowerShell-only, which by itself prevented
the sequence from executing end-to-end on Linux. It is now ported to
`run_p07_geometry_fixtures.py`; both drivers were run on Windows and agree on
all seven fixtures (same verdicts, same `max_rel` to within 1e-15), so the port
introduced no change.

### 16a. Results

| | Windows | Linux |
|---|---|---|
| platform class | `windows-development` | `smoke-only` |
| checks passed | **8/8** | **8/8** |
| geometry matrix | 7 fixtures, 0 failing, neutrality PASS | same |
| diagnostic guard | 5/5 | 5/5 |
| donor cap | `CAP_FIRES_AND_TRANSFER_EQUALS_AVAILABLE` | same |
| provenance fixture | 7/7 | 7/7 |
| **`release_evidence`** | **false** | **false** |
| reason | not the reference platform | platform class is `smoke-only` (RT-1) |

Both runs pass every check and both are correctly refused release-evidence
status. That is the intended behaviour: the sequence is proven executable
end-to-end and ready to run unchanged the moment a reference-capable host
exists.

### 16b. Deviation to disclose

The Linux run reused the two instrumented images for all four image slots, with
`bmx.print_sums` left at its default of OFF for the non-instrumented roles. That
is behaviourally sound — the diagnostic returns before reading anything when the
flag is unset, and `G0`/diagnostic neutrality both show no trajectory change —
but it is not the same artefact layout as the Windows run, where four distinct
images were built. A reference-host qualification must build all four
separately.

### 16c. What remains for RT-1

On a C02-compliant reference Linux host:

```bash
source tools/repro/linux_env.sh        # must print class: reference-capable
bash tools/repro/configure_linux.sh -b <build>/c03-baseline-release -s <baseline> -f
bash tools/repro/configure_linux.sh -b <build>/c04-p07-release      -s <product>  -f
# ... and the two instrumented variants, then:
python3 tools/repro/run_c04_qualification.py --rgsw-root <root> --skip-build \
        --json-out <root>/runs/c04-qualification/QUALIFICATION_REFERENCE.json
```

with `-DBMX_REQUIRE_PROVENANCE=ON` on every configure, which closes RT-2 in the
same pass. `release_evidence` becomes `true` only if all of that holds.

## 17. Reference-host qualification — RT-1 and RT-2 both PASS

Executed 2026-08-01T02:19:10Z on Google Compute Engine under owner
authorization (`DEC-PLATFORM-001` §104 legitimacy, §105 spend ≤ USD 100/account).

### 17a. Host

| | |
|---|---|
| Instance | `bmx-c04-qual`, `n2-standard-8`, zone `us-west1-b` |
| `--min-cpu-platform` | **Intel Cascade Lake** — §91 satisfied |
| OS / kernel | Ubuntu 24.04.4 LTS / `6.17.0-1021-gcp`, x86_64, **ext4** |
| **Platform class** | **`reference-capable`** (from `tools/repro/linux_env.sh`) |
| Toolchain | gcc/g++ 13.3.0, cmake 3.28.3, Open MPI 4.1.6, ninja 1.11.1, python3 3.12.3, git 2.43.0 |

### 17b. Four independently built images, all attributable

| Image | SHA-256 | Commit | Worktree | Chemistry |
|---|---|---|---|---|
| `c03-baseline-release` | `e74b4377…` | `7743106d…` | **clean** | `711ae2ca…` |
| `c04-p07-release` | `d2655f1e…` | `b686981f…` | **clean** | `9519fc24…` |
| `c04-baseline-diag-release` | `320bb021…` | `7743106d…` | **clean** | `711ae2ca…` |
| `c04-diag-release` | `661766e9…` | `b686981f…` | **clean** | `9519fc24…` |

Four distinct binaries from four independent configure+build records, every one
configured `-DBMX_REQUIRE_PROVENANCE=ON`. **No image reused for another slot** —
the WSL1 deviation is eliminated. `7743106d…` is the deterministic
baseline-plus-instrumentation construction (fixed author, committer and dates,
so the hash is a function of its parents and tree).

### 17c. Verdict

```
[PASS] identity_reviewed_candidate_kernel      9519fc24... matches the reviewed candidate
[PASS] identity_amrex                          commit cbdc6580, tree fb714dc6
[PASS] identity_build_provenance               RESOLVED, clean
[PASS] build_images_present
[PASS] per_image_provenance_resolved_and_exact all four RESOLVED on a clean tree
[PASS] geometry_matrix                         7 fixtures, failing=0, neutrality PASS
[PASS] diagnostic_regression_guard             5/5
[PASS] donor_cap_fixture                       CAP_FIRES_AND_TRANSFER_EQUALS_AVAILABLE
[PASS] provenance_regression_fixture           7/7
checks passed : 9/9        RELEASE EVIDENCE : True
```

`not_release_evidence_because` is empty.

### 17d. RT-1 and RT-2 — separate verdicts

| | RT-1 reference platform | RT-2 build provenance |
|---|---|---|
| **State** | **PASS** | **PASS** |
| Basis | host classified `reference-capable`; full sequence ran there; `release_evidence: true` | all four images RESOLVED with 40-char commits on clean trees; fail-closed aborted as required; fixture 7/7 |
| Evidence | `reference/QUALIFICATION_REFERENCE.json`, `reference/logs/environment.txt`, `reference/GEOMETRY_REFERENCE.json`, `reference/DONOR_CAP_REFERENCE.json` | `reference/PROVENANCE_REFERENCE.json`, the four `reference/logs/*.provenance.log`, `reference/logs/failclosed.log` |

Exercised in one execution, but carrying separate verdicts and separate
evidence pointers as required.

### 17e. Cross-platform agreement

| Result | Windows/MSVC | WSL1/gcc | **GCE reference/gcc** |
|---|---|---|---|
| donor cap `A_particles_final` @ k1=5 | `4.882812500000002e-12` | `4.882812500000002e-12` | **`4.882812500000002e-12`** |
| donor cap relative difference | `0.00e+00` | `0.00e+00` | **`0.00e+00`** |
| M2 max relative closure residual | `4.822133e-11` | `4.822133e-11` | **`4.822133e-11`** |
| geometry fixtures | 7/7 | 7/7 | **7/7** |

### 17f. Four harness defects the reference host exposed

None were visible on Windows or WSL1, because both reused already-built images
rather than building four variants from scratch on a clean host.

| # | Defect | Class | Fixed in |
|---|---|---|---|
| 1 | pristine baseline `389e9e35` has no `tools/repro`; `build_one` used each tree's own configure script | fixture/harness | `1e0f09a2` |
| 2 | pristine baseline predates `D-C04-08`, so criterion 2 was unsatisfiable by construction | fixture/harness | `1e0f09a2` |
| 3 | `cp -a` into an existing submodule placeholder nested AMReX at `subprojects/amrex/amrex` | fixture/harness | `18549ab5` |
| 4 | **baseline trees left the cherry-pick uncommitted**, so two images reported `389e9e35` on a **dirty** tree — resolved but *not exact* — and the driver still emitted `release_evidence: true` | fixture/harness | `b686981f` |

Defect 4 produced a **false PASS**. The driver had only checked the provenance
of the source tree it ran in, which is a different question from whether each
built image is attributable. It now interrogates every image directly and
requires `RESOLVED`, a 40-character commit, and a clean worktree. That check is
what turned the second reference run from a spurious 8/8 into an honest failure,
and the third into a real 9/9.

### 17g. Cloud hygiene

Instance **deleted** immediately after evidence capture. `gcloud compute
instances list` and `disks list` both return zero items. Estimated cost under
USD 2 against a USD 100 cap. §98–99 honoured: the instance was a read-only
consumer of a frozen commit and never wrote the product branch.
