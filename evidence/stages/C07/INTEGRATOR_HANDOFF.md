# C07 integrator handoff — `B-C07-01` (RESOLVED)

**Resolution:** The user explicitly reassigned the minimum
`src/des/bmx_calc_txfr.cpp` seam to Codex for C07 only, with the kernel frozen
and C08+ behavior prohibited. C07 implemented the map below and passed the
clean build, enabled/disabled runtime matrix, E-internal-only checks, and the
frozen P07 feature-off comparator. The current `STAGE_REPORT.md` supersedes the
historical blocked status in this handoff.

## Purpose and boundary

This is the cross-owner handoff required by the recovered C07 execution prompt.
It is **not** execution of C13 and does not authorize C08 or any later stage.
No integration-owned or product-source file was edited to prepare it.

The supplied prompt pack is user attachment `pasted-text.txt`, SHA-256
`d314e0b16234e92e26108a0b8bbac87d1337b09c3f226ff17ac486421f5da3e3`.
Its complete C07 prompt is lines 643–693 and its complete C13 prompt is lines
949–998.

- C07 assigns primary ownership to chemistry definitions, fluid parsing and
  initialization, particle initialization, and plot scaffolding. It says
  central transfer files require integrator ownership and orders a handoff when
  a necessary change crosses ownership.
- C13 assigns `src/des/bmx_calc_txfr.cpp` and explicit mesh↔particle mapping to
  the integrator.
- The writer handoff independently freezes `src/chemistry/bmx_chem_K.H` and
  assigns `bmx_calc_txfr.cpp` to C13.

## Frozen input

| Item | Value |
|---|---|
| Product base | `794205c2eb9a3d193ffa9cacc66e5509354d1684` |
| Candidate chemistry commit | `adb427331e180cd0b4faa74a4ab2098381b2eabb` |
| HEAD/candidate chemistry tree | `423d11cb32c9773bb89c028900b4fcd48d6e4d02` |
| AMReX commit/tree | `cbdc6580ee3d78cccdd37172e4ba077ee181f483` / `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6` |
| Frozen kernel SHA-256 | `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02` |

## Exact collision

1. `src/chemistry/bmx_chem.H:16-17` uses one macro for the chemistry count and
   for all three particle chemistry blocks.
2. Frozen `src/chemistry/bmx_chem_K.H` uses that macro as the particle block
   stride and loop bound. C07 must therefore compile that path with particle
   stride 8 to obtain the canonical reserved layout.
3. `src/des/bmx_calc_txfr.cpp:128-132` uses the same macro as the mesh
   interpolation count and aborts unless it equals `X_k->nComp()`.
4. Canonical mesh count is 6 when disabled and 7 when enabled. Canonical
   particle count is always 8.
5. `bmx_calc_txfr_fluid` at `:22-45` also assumes a contiguous identity map from
   particle increments to mesh components. In enabled mode this would send
   particle slot 6 (`P_E`) to mesh slot 6 (`P_F`), violating E internal-only.

No value of the shared macro is correct: 6 fails the particle layout; 8 makes
the transfer interpolation abort and leaves an invalid enabled deposition map.

## Minimal authorized seam required before C07 can resume

The integrator should provide a precursor commit based on the frozen input, or
stage authority should explicitly reassign this narrow seam to C07. The seam
must provide all of the following without changing scientific behavior:

1. Decouple active mesh interpolation count (runtime 6 or 7) from particle
   chemistry stride (compile-time 8).
2. Size any GPU-local mesh interpolation buffer to a reviewed compile-time
   maximum of 7, while interpolating and copying exactly the active mesh count.
3. Remove the equality assumption between `X_k->nComp()` and particle stride;
   validate the active mesh schema instead.
4. Use the C07 semantic maps rather than contiguous deposition:
   - disabled mesh→particle and particle→mesh: `0→0, 1→1, 2→2, 3→3, 4→4, 5→5`;
   - enabled mesh→particle and particle→mesh:
     `0→0, 1→1, 2→2, 3→3, 4→4, 5→5, 6→7`.
5. Never transfer particle slot 6 (`P_E`) to mesh. Never synthesize a mesh E.
6. Preserve the disabled first-six path byte-for-byte in ordering and
   numerically under the frozen P07 comparator.
7. Do not edit `src/chemistry/bmx_chem_K.H`; its SHA-256 must remain
   `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.
8. Do not add P10 conservation/topology semantics, P11 geometry, P12 uptake,
   P13 reactions/growth, or P14 export/reward behavior.

The integrator may choose a different implementation shape only if it proves
the same invariants and preserves the ownership and frozen-byte constraints.

## Required return evidence

Return a commit hash and a compact report containing:

- exact diff and ownership authorization;
- clean build command and exit code;
- disabled 6↔8 map test and enabled 7↔8 map test;
- negative proof that E cannot reach mesh;
- invalid-count/layout rejection tests;
- frozen-kernel hash and chemistry-tree impact;
- feature-off P07 comparator result;
- confirmation that no later-stage behavior was introduced.

After that evidence is accepted, C07 may resume on its owned files, run its full
mandatory validation, replace the blocked report with a complete current
report, and commit. C08 remains prohibited until C07 is `PASS`.
