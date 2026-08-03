# Platform reference decision — v1

- **Decision ID:** `DEC-PLATFORM-001`
- **Version:** 1
- **Status:** `ACCEPTED_PENDING_HOST_PROVISIONING`
- **Date:** 2026-07-30
- **Decided by:** user (project owner), on the writer's recommendation
- **Class:** technical policy. Contains **no** biological or scientific value,
  and does not touch any blocked decision in `B-S00-03`.
- **Supersedes:** the reference platform declared in
  `evidence/stages/C02/STAGE_REPORT.md` §3

---

## Decision

**Linux is re-declared the RG-SW reference platform.** Native Windows / MSVC /
MS-MPI is demoted to a *secondary supported platform*.

## Status qualifier — this is not yet in force

No qualifying Linux host exists on this machine. The only local Linux is
**WSL 1** (kernel `4.4.0-26100-Microsoft`), which is a syscall translation layer,
not a Linux kernel: AMReX and MPI behaviour are not equivalent, and the working
tree sits on a DrvFs mount with different I/O and locking semantics.

Therefore:

- WSL1 is classified **`smoke-only`** and may be used solely to shake out
  portability defects. Its output is **never** release evidence, never a
  reference build, and cannot satisfy a C16 acceptance row.
- The decision takes effect when a **`reference-capable`** host exists — a GCE
  Linux instance, other native Linux, or WSL2.
- `tools/repro/linux_env.sh` enforces this: it classifies the host and stamps
  `BMX_PLATFORM_CLASS` into every build and run it drives. A smoke-only host
  labels its own output as non-evidence rather than relying on discipline.

Until then the **Windows evidence remains the only executed evidence**, and it
is retained, not discarded.

## Rationale

1. **Sanitiser coverage — the decisive reason.** C16 mandates ASan/UBSan "or
   documented equivalents" on required CPU paths. MSVC provides
   `/fsanitize=address` but **no UndefinedBehaviorSanitizer**. For a code base
   doing unit-bearing floating-point work with signed arithmetic, array
   indexing, and amount/concentration conversions, UBSan is not a nice-to-have.
   On Windows this is a permanent, unclosable gap in a mandatory release gate.

2. **The Windows platform generated six defects/deviations** (see
   `evidence/stages/C02/DEFECTS.md`), one of which — D-C02-05 — silently moves
   the entire product to C++17 plus `/Zc:lambda` as a workaround for a one-line
   source issue. Anchoring a release to a platform requiring that many
   compensations is weaker than anchoring to one that requires none.

3. **Demonstrated fragility.** During C03 the toolchain was renamed
   `C:\Program` → `C:\Program1` mid-stage, and `vswhere` continued to serve the
   stale path while marking the instance `isComplete:false`. A reference
   platform that can move out from under the build, and whose own discovery tool
   misreports it, is a poor anchor. (Discovery is now hardened, but the
   underlying fragility is a property of the platform, not the script.)

4. **Available capacity is Linux.** The project owner has Google Cloud capacity
   (6 accounts x 12 vCPU). The sweep-parallel stages — C14's P15 matrix and
   C16's convergence / rank / decomposition matrix — map well onto it. That
   capacity is only usable for *claim-bearing* runs if Linux is the reference
   platform.

## Consequences — accepted

- **C02, C03, and C04 must be re-executed on a reference-capable Linux host.**
  Their Windows results are retained as historical and secondary-platform
  evidence, clearly labelled, and are not deleted.
- The recorded Windows image hashes (`e3c8ee08…`, `e2effe2c…`, `64b9aacc…`)
  describe the secondary platform only.
- **The six C02 defects must be re-triaged.** D-C02-01, -03, -04, -05 are
  expected to be *Windows-portability* defects rather than product defects,
  because `configure_linux.sh` deliberately applies none of their workarounds.
  Whether that expectation holds is a finding, not an assumption — the Linux
  configure is written to fail rather than paper over them.
  D-C02-06 (`compile_commands.json` copied into the source tree) is a source
  defect and will persist on Linux.
- `RG-SW:GO`, if ever reached, is scoped to the Linux reference platform.
  Windows support becomes a separate, weaker claim requiring its own evidence.

## Constraints on any cloud execution

These are binding on any GCE use and must be satisfied before a cloud run
carries a claim:

1. **Pin the CPU platform.** Different GCE machine families change
   floating-point behaviour (FMA contraction, AVX paths). Every claim-bearing
   run must set `--min-cpu-platform` and record machine type, CPU platform,
   compiler version, and MPI implementation alongside the frozen commit.
2. **Capacity is 6 independent pools, not one.** Separate accounts mean separate
   projects and VPCs; an MPI job cannot span them. Only sweep-parallel work
   benefits. No strong-scaling claim may be built on aggregated vCPU counts.
3. **Cloud runners are read-only consumers of a frozen commit.** The one-writer
   rule is unchanged: no cloud instance writes the product branch.
4. **Account legitimacy.** If the six accounts are separate free-tier or trial
   accounts used to exceed per-account limits, that conflicts with Google's
   terms. This must be confirmed before a pipeline depends on it. Recorded here
   because a release's reproducibility story should not rest on an
   infrastructure arrangement that cannot be sustained or disclosed.
5. **No cloud resource is provisioned, and no spend is incurred, without
   explicit per-action authorisation from the project owner.**

## What is NOT decided here

- No biological parameter, experiment design, or claim threshold. `B-S00-03`
  is untouched.
- No numerical tolerance, and no acceptance criterion is weakened. This decision
  *adds* a mandatory gate (UBSan) that the previous platform could not meet.
- Whether Windows is qualified as a secondary platform at all. That is a
  separate, later decision requiring its own evidence.
