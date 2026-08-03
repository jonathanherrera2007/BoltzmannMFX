# C04 — reference-host decision packet

- **Stage state:** `C04 = BLOCKED_REFERENCE_PLATFORM_QUALIFICATION`
- **Date:** 2026-07-31
- **C04 is not complete.** Windows and WSL1 results are **preparation / smoke
  evidence only**. The next authoritative action is one clean qualification run
  on a host admissible under `DEC-PLATFORM-001`.

---

## 1. Stage-identifier reconciliation — `D-C04-05` vs `D-C04-08`

**These are two distinct work items. No renumbering occurred and no ownership
history is ambiguous.** Stated explicitly because the question was raised:

| | `D-C04-05` | `D-C04-08` |
|---|---|---|
| Work | conservation/fluid diagnostic (`bmx::ComputeAndPrintSums`) | build provenance for linked worktrees |
| Origin | recorded as a C04 finding, then authorized as narrowly scoped integrator work | discovered *during* the Linux portability smoke, authorized separately afterwards |
| Commit | `5481856f46ba4bd2432dd21800fe9dbec8d10a15` | `8428a5d354025f2a222deae287679bf2e89a4a9b` |
| Files | `src/bmx.cpp`, `src/bmx.H`, `src/setup/bmx_init.cpp`, `tools/repro/check_sums_diagnostic.py` | `CMakeLists.txt`, `src/CMakeLists.txt`, `src/io/bmx_build_info.cpp`, `tools/CMake/BMX_Provenance.cmake`, `tools/CMake/bmx_provenance.H.in`, `tools/repro/check_build_provenance.py` |

**File overlap between the two commits: zero.** Verified with
`comm -12` over both commits' file lists. Both are integrator-owned; neither
touches chemistry.

## 2. Frozen inventory

### 2a. Working state

```
$ git status --porcelain=v1
?? evidence/stages/C07/          # C07 plan, deliberately untracked (C07 is blocked)
```

- branch `rgsw/product`, HEAD `9941e167b3f4e0cf06f852c8b8181a77d8032610`
- no tracked modifications
- ignored: `/compile_commands.json` (D-C02-06), `__pycache__/`, `*.py[cod]`

### 2b. Ordered C04 commit stack (full 40-character IDs)

| # | Commit | Role |
|---|---|---|
| 1 | `adb427331e180cd0b4faa74a4ab2098381b2eabb` | **chemistry candidate** — P07 carbon repair |
| 2 | `9e1cfb17ccee7e7796f74d3e4a04a5ea66d50e05` | geometry observables; closes `B-C04-01` |
| 3 | `a75dc8caac6fa890664a88ba8ce8c5043c85e275` | evidence: record hash |
| 4 | `3890d6928fd019f1e47215fa9075be8adf019f8d` | small-stored-area attempt + dependency |
| 5 | `5481856f46ba4bd2432dd21800fe9dbec8d10a15` | **`D-C04-05` diagnostic repair** (integrator) |
| 6 | `f1bdecaba705d1beaab3025d54b32a325978eb88` | donor cap demonstrated; closes `B-C04-02` |
| 7 | `04ff64d37fc7b711b0d943fa19c733293523f582` | evidence: record hash |
| 8 | `48375fc42b36d238241656796ae4e7938a42ff21` | Linux portability smoke |
| 9 | `8428a5d354025f2a222deae287679bf2e89a4a9b` | **`D-C04-08` provenance repair** (integrator) |
| 10 | `2f8d66adecf88600395660b33ae8557acf80d2cc` | **record corrections** (five) |
| 11 | `aba613d396189b1fea477683db04f447ab40888d` | evidence: record hash |
| 12 | `4332f206c03b187a5574c2e9cabc5329a915b6ea` | **portable geometry driver + qualification driver** |
| 13 | `01528a1e24d43d7be8b714e9da39fe0498f5d042` | evidence: record hash |
| 14–19 | `c531cb6f…`, `d189cbc8…`, `d53cc58f…`, `e5ccb875…`, `18b1a7e3…`, `d85c2a26…` | handoff preparation |
| 20 | `9941e167b3f4e0cf06f852c8b8181a77d8032610` | line-ending renormalization (**HEAD**) |

Earlier stages C01–C03 and C06A precede these on the same branch.

### 2c. Identity

| Item | Value |
|---|---|
| Reviewed kernel `src/chemistry/bmx_chem_K.H` | `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02` |
| Baseline kernel | `711ae2caa6e7aabb5c084fe841d2d90edb85ee53e7abc7a859d7de00e6614678` |
| Canonical baseline commit | `389e9e35a1c7291a4af795b2e39f2db1f0012b61` |
| Canonical baseline tree | `1c73deedf0eb2feea833a7fddbc431ae9754d977` |
| AMReX commit | `cbdc6580ee3d78cccdd37172e4ba077ee181f483` |
| AMReX tree | `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6` |
| Submodules | one: `subprojects/amrex`, no nested submodules |

### 2d. Proof that no chemistry byte changed after the candidate

The strongest available form — the whole directory tree object, not one file:

```
src/chemistry tree @ adb4273 : 423d11cb32c9773bb89c028900b4fcd48d6e4d02
src/chemistry tree @ HEAD    : 423d11cb32c9773bb89c028900b4fcd48d6e4d02   identical
bmx_chem_K.H blob @ adb4273  : 970e66c42780ee5bfa1e110a9218cb58aefcad41
bmx_chem_K.H blob @ HEAD     : 970e66c42780ee5bfa1e110a9218cb58aefcad41   identical
commits touching src/chemistry/ after adb4273 : none
```

`.gitattributes` sets `* -text` by default, so C/C++ sources are never
line-ending normalized; only named text patterns are.

## 3. C02 host-admissibility contract

Controlling documents, both repository-controlled:

- `contracts/platform/PLATFORM_REFERENCE_DECISION.md` — `DEC-PLATFORM-001`,
  status `ACCEPTED_PENDING_HOST_PROVISIONING`, explicitly **supersedes** the
  reference platform declared in `evidence/stages/C02/STAGE_REPORT.md` §3
  (which declared *Windows/MSVC/MS-MPI*).
- `tools/repro/linux_env.sh` — the mechanical enforcement.

### 3a. The admissibility text

Admission (`DEC-PLATFORM-001` §32–33):

> The decision takes effect when a **`reference-capable`** host exists — a GCE
> Linux instance, other native Linux, or WSL2.

Exclusion (§29–31):

> WSL1 is classified **`smoke-only`** and may be used solely to shake out
> portability defects. Its output is **never** release evidence, never a
> reference build, and cannot satisfy a C16 acceptance row.

Enforcement (§34–36):

> `tools/repro/linux_env.sh` enforces this: it classifies the host and stamps
> `BMX_PLATFORM_CLASS` into every build and run it drives.

The classifier itself (`linux_env.sh:49-66`): if `/proc/version` matches
`microsoft`, the host is `reference-capable` only when the kernel matches
`*microsoft-standard*` or a major version ≥ 5; otherwise `smoke-only`. A host
with no `microsoft` marker is `reference-capable`.

**Inadmissible** is not a class the script emits — it is expressed by refusal to
classify at all: `_require` aborts under `set -euo pipefail` when any of `gcc`,
`g++`, `cmake`, `mpicxx`, `mpirun` is absent. `make` is optional; `ninja` is
preferred with Unix Makefiles as fallback. `python3` is additionally required by
the qualification drivers.

Cloud constraints (§86–106), binding on any GCE use: pin `--min-cpu-platform`
and record machine type/CPU platform/compiler/MPI (§91); six pools are
independent and MPI cannot span them (§95); cloud runners are read-only
consumers of a frozen commit (§98–99); account legitimacy must be confirmed
(§100–104); **no cloud resource is provisioned and no spend incurred without
explicit per-action authorization from the project owner** (§105).

### 3b. Admissibility matrix

| Candidate host | Verdict | Controlling requirement |
|---|---|---|
| **Organization / lab-managed native Linux** | **QUALIFIES** | §33 "other native Linux"; `linux_env.sh` → `reference-capable` (no `microsoft` in `/proc/version`). Conditional on the five mandatory tools being present. |
| **Organization-approved hosted Linux CI runner** | **UNRESOLVED — owner decision** | Not named in §33. Mechanically it would classify `reference-capable`, but §98–99 treat cloud runners as read-only consumers of a frozen commit, and §91 requires a pinned CPU platform that ephemeral runners typically cannot guarantee. Whether a hosted runner is "other native Linux" or a cloud runner under §86–106 is not determined by the text. |
| **WSL2** | **QUALIFIES** | **Explicitly named in §33.** `linux_env.sh` classifies it `reference-capable` by kernel test. ⚠️ Condition below. |
| **Ordinary cloud Linux VM (GCE)** | **UNRESOLVED — owner decision** | The platform class qualifies (§33 "a GCE Linux instance"), but §105 authorization and §100–104 account legitimacy are unsatisfied *preconditions*, and §91 CPU pinning must be configured. These are owner decisions; no resource may be provisioned without explicit per-action authorization. |
| **Docker / container on Windows** | **UNRESOLVED — owner decision** | Not contemplated anywhere in `DEC-PLATFORM-001`. Docker Desktop runs on a WSL2 backend, so a container would likely self-classify `reference-capable` via the host kernel — which is precisely the silent qualification the enforcement was written to prevent. Recorded as a gap in `linux_env.sh`, not resolved here. |
| **Current WSL1** | **DOES NOT QUALIFY** | §29–31 explicitly, and `linux_env.sh` returns `smoke-only` for kernel `4.4.0-26100-Microsoft`. |
| **WSL2 *on this machine*** | **UNAVAILABLE** | admissible by §33, but this host is a Blade/Shadow cloud VM with no tenant-accessible firmware and no nested virtualization exposed — see §3c. |

### 3c. WSL2 is admissible by contract but UNAVAILABLE on this host

Investigated on 2026-07-31 after the instruction "enable virtualization in
firmware and re-run qualification on WSL2". **There is no firmware to enter.**

| Probe | Result |
|---|---|
| `Win32_ComputerSystem` manufacturer / model | `Blade` / `Shadow Computer` |
| `Win32_BIOS` | `Blade 1.1.3` (virtual firmware) |
| CPU | `AMD EPYC 7543P 32-Core Processor` |
| `HyperVisorPresent` | **`True`** — Windows is already a guest |
| `systeminfo` Hyper-V requirements | *"A hypervisor has been detected. Features required for Hyper-V will not be displayed."* |
| `Win32_Processor.VirtualizationFirmwareEnabled` | `True` (the *virtual* firmware already reports it on) |

This is a **Shadow PC**: a cloud-hosted Windows desktop. There is no POST
screen, no UEFI setup utility, and no physical BIOS reachable by the operator.
WSL2 requires **nested** virtualization to be exposed by the host hypervisor,
which is a capability of the hosting provider (Blade), not a setting available
to the tenant. `wsl --status` continues to report virtualization unavailable.

**Correction to the previous packet:** it recommended WSL2 as "the shortest
path … needs only virtualization enabled in firmware". That assumed physical
hardware and is **wrong for this environment**. WSL2 remains admissible *by
contract* (§33) but is **not reachable on this host**, so it should not be
treated as the near-term route.

**CONCLUSIVELY TESTED 2026-07-31.** The owner enabled the missing components
and rebooted. Every software prerequisite is now present:

| Probe (after reboot, uptime 2m20s) | Result |
|---|---|
| `wsl.exe --install --no-distribution` | completed |
| `vmcompute` (Host Compute Service) | **present, Running** |
| `hns` (Host Network Service) | **present, Running** |
| WSL version / kernel | `2.7.11.0` / `6.18.33.2-2` |
| `bcdedit` `hypervisorlaunchtype` | not set → defaults to **Auto**, so it did try |
| `wsl --set-version Ubuntu 2` | `Wsl/Service/CreateVm/HCS/HCS_E_HYPERV_NOT_INSTALLED` |

and the Windows hypervisor recorded why, at the exact boot timestamp:

> `Microsoft-Windows-Hyper-V-Hypervisor`, **Error**, 2026-07-31 10:22:32 —
> *"Hypervisor launch failed; Either SVM not present or not enabled in BIOS."*

**SVM** is AMD's Secure Virtual Machine extension (AMD-V). The hypervisor
attempted to launch and the CPU did not offer it. With no tenant-accessible
firmware and no nested virtualization exposed by Blade, **WSL2 is definitively
unavailable on this host.** This is direct evidence from the hypervisor, not
inference from missing components — the components are all present.

Whether Blade can enable nested virtualization for this instance is a question
for the provider. It is not an agent action, and not a firmware toggle.

⚠️ **WSL2 condition, should a WSL2 host become available.** WSL2 is admissible by the
text. But one of the two reasons §23–25 gives for excluding WSL1 is that *"the
working tree sits on a DrvFs mount with different I/O and locking semantics"* —
and `linux_env.sh` only **warns** on a `drvfs`/`9p` working tree, it does not
downgrade the class. To honour the contract's own stated rationale, a WSL2 run
should place the working tree on the ext4 VHD (e.g. `~/bmx`), not under
`/mnt/c`. This is a recommendation drawn from the contract's reasoning, not an
additional rule.

## 4. The reference-host run, defined exactly

Entrypoint: `bash qualify.sh <empty-workdir>` (one command). It performs, in
order, aborting on any failure:

1. verify `MANIFEST.sha256` before trusting any file in the handoff
2. clone both bundles into a clean workspace
3. verify BMX commit, AMReX commit **and** tree, the chemistry-kernel SHA-256,
   and that the source tree is clean
4. classify the host; **refuse** unless `reference-capable`
5. build **four variants independently**, four separate build directories, each
   configured `-DBMX_REQUIRE_PROVENANCE=ON`:
   `c03-baseline-release`, `c04-p07-release`, `c04-baseline-diag-release`,
   `c04-diag-release` — **no image is reused for another slot**
6. record each binary's SHA-256 and confirm each reports its intended commit via
   `--describe`
7. prove provenance **fails closed** on an unresolvable tree
8. run the complete C04 qualification sequence
9. capture host, kernel, arch, distro, gcc, g++, cmake, python3, mpicxx, mpirun,
   ninja, git, nproc, filesystem
10. every configure/build/run writes its own log; stdout, stderr and exit codes
    are retained

Binary hashes are **not required to differ** — two deterministic builds may
legitimately produce identical bytes. What is required is an independent
configure and build record per slot.

## 5. Non-negotiable pass criteria

C04 may transition only if **all** hold:

| # | Criterion |
|---|---|
| 1 | host classification is `reference-capable` under `DEC-PLATFORM-001` |
| 2 | provenance resolved and exact for all four independently built images |
| 3 | all qualification checks pass |
| 4 | `release_evidence` is exactly `true` |
| 5 | **RT-1** passes with its own evidence references |
| 6 | **RT-2** passes with its own evidence references |
| 7 | mandatory donor-cap equality row passes (`A_particles_final == fA0·V_cell`) |
| 8 | corrected residual definitions (M1/M2/M3, §4e of the stage report) intact |
| 9 | geometry fixtures pass, including `G0` observation-neutrality |
| 10 | provenance regression fixtures pass, including fail-closed |
| 11 | trajectory-neutrality checks pass, described with correct comparison semantics |
| 12 | no unexplained deviations and no image reuse remain |
| 13 | chemistry candidate bytes unchanged |

RT-1 and RT-2 may be exercised in one execution but **remain separate
requirements with separate machine-readable verdicts and evidence pointers**.

## 6. Failure handling

If the reference run fails: **do not edit source**, and **do not reinterpret the
run as smoke evidence**. Preserve the entire workdir — logs, build directories,
JSON. Classify the **first causal** failure as one of

`host/infrastructure` · `packaging` · `build-system/provenance` ·
`fixture/harness` · `chemistry/numerical`

report it together with all downstream consequences, and request authorization
before any change outside the already-approved ownership scope. A
`chemistry/numerical` classification in particular must not be acted on without
authorization — the chemistry candidate is frozen.

## 7. Handoff

| | |
|---|---|
| Archive | `handoff/C04_REFERENCE_HOST_HANDOFF.tar.gz` |
| SHA-256 | `989190abb6c3cd2be29a4fca817ab00415f7bc24df93e1afbf3abfc7da2974cb` |
| Size | 77,547,010 bytes |
| Pinned commit | `9941e167b3f4e0cf06f852c8b8181a77d8032610` |
| Generator | `tools/repro/make_handoff.py` (committed; bundles are derived and are not) |

Contents: `bmx-product.bundle` (verified, complete history), `amrex-pinned.bundle`
(verified, complete history), `qualify.sh`, `IDENTITY.json`, `README.md`,
`MANIFEST.sha256`.

### Clean-extraction verification — PASS

Extracted into `/tmp` on Linux with no path back to the originating worktree:

| Check | Result |
|---|---|
| manifest verifies | 5/5 OK |
| clones without reference to the linked worktree | `.git` is a **DIRECTORY** (ordinary checkout) |
| source tree clean after checkout | **YES** |
| chemistry kernel hash | `9519fc24…ffba02` ✓ |
| `configure_linux.sh` passthrough present, LF endings | ✓ |
| provenance in the extracted clone | `RESOLVED`, `ordinary checkout`, `clean`, exact commit |
| `qualify.sh` on a smoke-only host | passes all identity checks, then **refuses**, exit 1 |

This verification is **preparation evidence only**. It is not release evidence.

Two defects were caught by this verification rather than by inspection, both now
fixed: the first archive was cut before the `configure_linux.sh` passthrough was
committed (the run would have failed at the first configure), and files
committed with CRLF before `.gitattributes` made a fresh clone report a dirty
tree.
