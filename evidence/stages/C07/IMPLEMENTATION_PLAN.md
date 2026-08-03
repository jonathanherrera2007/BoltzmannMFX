# C07 / P09 — three-state phosphorus infrastructure: implementation plan

**Status:** DRAFT, carried into the Claude-to-Codex writer handoff.
Written per `CLAUDE.md` ("use plan mode before editing a new phase").

> **Section 0 below is STALE and retained only as history.** It was written on
> 2026-07-30, when C04 was `BLOCKED` and no reference-capable Linux host
> existed. Both conditions are now resolved:
>
> - **C04 is `PASS` and reference-platform qualified.** All five defect mappings
>   are demonstrated at runtime; the qualification sequence emitted
>   `release_evidence: true` on a GCE reference host. The P07 image is a sound
>   feature-off regression reference.
> - **`B-PLATFORM-01` is CLOSED.** A reference host exists and the route to
>   re-provision one is documented in the writer handoff.
>
> The rest of the plan (§1 finding, §2 layout, §3 refactor, §4 files, §5 tests,
> §6 exclusions, §7 sequence) is still believed current, **but it is a draft**.
> The incoming writer should re-derive it against actual source bytes rather
> than execute it as written.

---

## 0. Two dependencies you should weigh first — SUPERSEDED, see the note above

**(a) C04 is BLOCKED, and C07's feature-off comparator points at P07.**
C07's mandatory validation includes *"feature-off reference matches P07 within
the frozen comparator."* The P07 image exists and is committed
(`64b9aacc…`), so it is usable as a regression reference — but its own
validation is incomplete (`B-C04-01`: CDEF-04/05 reachability undemonstrated).
Consequence: **C07 can be implemented and self-tested now, but cannot reach
`PASS` until C04's gate is met.** I will mark it accordingly rather than claim a
green stage.

**(b) `DEC-PLATFORM-001` moves the reference platform to Linux.**
Source changes are platform-independent and port unchanged. **Evidence does
not** — every build/run result produced now on Windows will be re-executed on
Linux. So this plan invests in *source and tests*, not in Windows evidence.

Neither blocks writing the code. Both bound what the stage may claim.

---

## 1. Finding to record before implementing: `D-C07-01`

`input_fungi` declares `fluid.chem_species = A B C D F P`, making slot 4 **F**.
The kernel names slot 4 **E** (`fE = mesh_vals[4]`, `cE = p_vals[4]`) and uses it
actively:

| Site | Code |
|---|---|
| `bmx_chem_K.H:1856-1860` | `rE = k5*cC*cD - kr5*cE*cA` (reaction 5: C + D → E + A) |
| `bmx_chem_K.H:1988-1989` | `rV = kbv*cE*orig_cell_vol`, `rE = -kb*cE` (bacterial growth) |

So configuration and kernel disagree about what slot 4 *is*. Today this is
masked: the fungi case sets slot 4's diffusion coefficient and initial
concentration to zero, so the discrepancy is dormant on the fungal path.

It stops being dormant here, because phosphorus introduces `P_E`. Two different
E-like quantities would then coexist, one of them mislabelled in plot and
checkpoint output — precisely the kind of thing that misleads a scientist
reading results.

**Handling:** implement `AGENTS.md`'s frozen order exactly (slot 4 = `F`),
change **no** legacy behaviour, and record `D-C07-01` as an open naming defect
requiring resolution before release. I will not rename legacy variables or
alter reaction 5. Recording it, not fixing it, is the correct scope here.

## 2. Frozen layout to implement

From `AGENTS.md` (canonical architecture) plus decisions closed in C06A:

| Mode | Mesh | Particle |
|---|---|---|
| **Disabled (legacy)** | `A B C D F P` (6) | 8 slots reserved; 0–5 used, **6 and 7 exactly zero** |
| **Enabled** | `A B C D F P_D P_F` (7) | `A B C D F P_D P_E P_F` (8) |

Key properties, each traceable to a closed decision:

- Legacy generic `P` (currently `P_COMP = 5`) becomes **`P_D`** in enabled mode —
  D is the sole active mobile and exportable P currency (`MD-88955e1dff7ca225-01`,
  `MD-5b43f4b235dec87e-04`).
- **`P_E` is particle-only.** It must have no mesh representation, no diffusion,
  no membrane exchange, no bonded transport, no export
  (`MD-5b43f4b235dec87e-04`). This is why mesh has 7 and particle has 8.
- **`P_F` exists on both** but every F coefficient stays exactly zero
  (`MD-5b43f4b235dec87e-07`, `-01`).
- Reject: simultaneous `P` and `P_D`; mesh `P_E`; missing enabled `P_F`;
  reordered legacy components; any nonzero F-active coefficient.

## 3. The core refactor

Today `NUM_CHEM_COMPONENTS = 6` indexes **both** mesh and particle arrays. That
conflation is what makes a particle-only state impossible. `AGENTS.md` requires
they be distinct and connected by explicit reviewed maps.

```
NUM_CHEM_COMPONENTS 6                    ->  NUM_MESH_CHEM_COMPONENTS     (6 or 7)
                                             NUM_PARTICLE_CHEM_COMPONENTS (8, always)
MAX_CHEM_REAL_VAR 28 + 3*6 = 46          ->  28 + 3*8 = 52
```

The particle real block keeps its three sub-blocks (committed / working /
increments), each widening from 6 to 8, with `p_inc_offset = 2*num_particle`.

**Particle storage is 8 in both modes.** A fixed particle ABI means the layout
does not change when the feature is toggled, so a checkpoint is readable
regardless of mode — the alternative would make mode a hidden ABI variable.

This widening changes the particle ABI, so legacy checkpoints become
unreadable. That is already handled: C06A froze `P09-U03` as *reject legacy
checkpoints before particle deserialization*, with schema v2 metadata.

## 4. Files, in dependency order

| # | File | Change |
|---|---|---|
| 1 | `src/chemistry/bmx_chem.H` | split component counts; add `pIdx` semantic indices; enabled/disabled mode flag; keep `P_COMP` as the legacy alias with a static assertion tying it to `P_D` |
| 2 | `src/chemistry/bmx_chem.cpp` | runtime counts, offsets, device metadata; mesh↔particle maps; configuration validation and rejection rules |
| 3 | `src/mods/bmx_fluid_parms.cpp` | parse and validate the enabled mesh species list; reject the invalid combinations in §2 |
| 4 | `src/setup/bmx_init_fluid.cpp` | deterministic mesh initialisation for `P_D`/`P_F` |
| 5 | `src/des/bmx_pc_init.cpp` | deterministic particle initialisation of all 8 slots, including zeroing 6–7 in disabled mode |
| 6 | `src/io/bmx_plt.cpp` | semantic component names; **must not** present `P_E` as a mesh species |
| 7 | `src/chemistry/bmx_chem_K.H` | **index-safety only** — replace hard-coded `NUM_CHEM_COMPONENTS` loops/offsets with the correct mesh or particle count. No reaction, transport, or exchange behaviour. |

File 7 is the risk concentration: `bmx_chem_K.H` is the kernel C04 just patched.
Every edit there is mechanical index correctness, and the feature-off regression
is what proves it.

Central transfer files (`bmx_calc_txfr.cpp`, `bmx_pc.H`, `bmx_evolve.cpp`) are
**integrator-owned (C13)** and out of scope, per the C07 prompt.

## 5. Tests

| Test | Asserts |
|---|---|
| `AT_P09_LAYOUT_CARDINALITY` | mesh 6/7, particle 8 in both modes; offsets and `MAX_CHEM_REAL_VAR` consistent |
| `AT_P09_MESH_PARTICLE_MAP` | bidirectional map is total and injective where defined; **no mesh index maps to `P_E`** |
| `AT_P09_E_INTERNAL_ONLY` | `P_E` absent from every mesh path, diffusion coefficient list, and plot mesh name table |
| `AT_P09_F_ZERO_DEFAULT` | every F coefficient exactly zero; nonzero F-active config rejected |
| `AT_P09_INVALID_LAYOUT` | rejects simultaneous `P`+`P_D`, mesh `P_E`, missing enabled `P_F`, reordered legacy |
| `AT_P09_INITIALIZATION` | all new fields deterministically initialised; slots 6–7 exactly zero in disabled mode |
| `AT_P09_NEUTRALITY_GUARD` | **feature-off run is bit-identical to the P07 reference** |

The neutrality guard is the one that matters. C03 and C04 already give me the
tooling: the normalized-raw-log comparator and the `kv=0` style controls.

## 6. Explicitly NOT in this stage

No uptake, reaction, growth-limitation, export, reward, geometry, or transport
behaviour. No P10 topology or transfer semantics. No biological value chosen. No
legacy variable renamed. No change to reaction 5 or bacterial growth. Beyond
explicit initialisation and the widened layout, behaviour must not move.

## 7. Proposed sequence

1. Record `D-C07-01`.
2. Layout constants and semantic indices (file 1) — build only.
3. Runtime counts, maps, validation (files 2–3) + layout/map/validation tests.
4. Initialisation (files 4–5) + initialisation tests.
5. Index-safety sweep of `bmx_chem_K.H` (file 7) + **feature-off regression**.
6. Plot/diagnostic names (file 6).
7. Build, run the full test set, run the neutrality guard, write the stage report.

Steps 2–6 each keep the tree buildable, so a regression is attributable to one
step rather than to the whole change.
