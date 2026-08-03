# BMX phosphorus extension

**This is a derivative work.** It adds phosphorus transport to
[BoltzmannMFX (BMX)](https://github.com/PNNL-CompBio/BoltzmannMFX), a fungal-growth
simulator developed at Pacific Northwest National Laboratory, copyright Battelle Memorial
Institute, distributed under a BSD-style licence. BMX is itself built on
[AMReX](https://github.com/AMReX-codes/amrex), included here as a pinned submodule.

**Upstream baseline:** `66852df5cee68f297436d541552e4a8960815348` — the last commit
authored by the BMX maintainers (Bruce J. Palmer, November 2024). Everything after that
point in this repository is my work.

## What is original here

Measured against that upstream commit:

| | |
| --- | --- |
| Commits | 104 |
| Model source | 48 files changed, **+10,142 / −345** lines |
| — of which new files | 16 files, ~7,800 lines |
| Whole repository | 424 files changed, **+82,510** lines |

The larger figure includes the test and qualification harnesses, the frozen contracts, and
the per-stage evidence records, which together are the majority of the work.

For scale, upstream `src/` is roughly 16,600 lines of C++. The phosphorus extension adds
about 10,100 to it.

The contribution can be isolated exactly:

```bash
git diff 66852df HEAD -- src/     # the model changes
git diff 66852df HEAD             # everything, including evidence and tooling
```

An intermediate commit, `389e9e35a1c7291a4af795b2e39f2db1f0012b61`, is pinned throughout
the evidence records as the project's canonical starting point. That commit is also mine —
it is the first phosphorus work, made before the staged process began. Stage reports
measure against it rather than against upstream.

## What the phosphorus work establishes

Conservation of phosphorus within frozen numerical tolerances, verified at every operator
boundary and checkpoint; correct operator engagement and provable non-engagement in
controls; agreement with analytical solutions where they exist; mesh and timestep
convergence; deterministic, restart-equivalent and platform-invariant reproduction; and
exact attribution of every result to a commit, executable, and contract hash.

## What it does not establish

That the model is biologically correct. Every scientific parameter is provisionally
adopted pending expert review and is labelled
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE` in the decision ledger.
Literature-derived rate constants are marked as priors, not calibrations. Release status
is **RG-SCI: NO-GO** and stays there until independent calibration and held-out validation
exist. Every stage report carries an explicit claim boundary.

## Layout

| Path | Contents | Origin |
| --- | --- | --- |
| `src/chemistry/`, `src/des/`, `src/io/` | Model source; the phosphorus files are the addition | mixed |
| `contracts/` | Frozen operator order, topology, ledger, numerical preregistrations | this work |
| `evidence/stages/` | Per-stage reports, raw evidence, independent review artifacts | this work |
| `tools/repro/` | Reproduction harnesses, fixtures, qualification runners | this work |
| `exec/`, `doc/`, build system | Example problems and documentation | upstream BMX |
| `subprojects/amrex` | Pinned submodule | AMReX project |

## Suggested reading order

1. `evidence/stages/C10V2/STAGE_REPORT.md` — the most complete single stage record
2. `contracts/p10/OPERATOR_ORDER_V1.json` — the frozen global operator order
3. `evidence/stages/C10V2/INDEPENDENT_NUMERICAL_REVIEW_V2.json` and
   `FINAL_INDEPENDENT_ACCEPTANCE.json` — review performed by a reviewer separate from the
   implementation writer
4. `contracts/decision_reconciliation.json` — all 59 tracked decisions and their status

## A representative result

Before any run, the uptake law and the two approved environmental concentrations predicted
that a 2.807× concentration ratio would produce only a 1.039× flux ratio, because both
conditions sit above 94% of transporter saturation. The prediction was frozen in the
contract. The measured 48-hour result was 1.0403 — agreement to 0.11%, stable across a
64-fold change in mesh resolution.

That is a statement about model behaviour and experimental design, not about biology.

## Redactions

See `REDACTIONS.md`. Development history is not published; that file records every
difference from the private original and explains why.

## Licence

`LICENSE` — Battelle Memorial Institute, BSD-style, inherited from upstream BMX and
applying to this repository as a whole. AMReX is a submodule under its own licence.
