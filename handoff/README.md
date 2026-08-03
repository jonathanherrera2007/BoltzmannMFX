# BMX RG-SW — C04 reference-host qualification handoff

**Stage state: `C04 = BLOCKED_REFERENCE_PLATFORM_QUALIFICATION`.**
C04 is *not* complete. Its correctness gate is met on Windows and rehearsed on
WSL1, but both are **preparation/smoke evidence only**. The next authoritative
action is one clean qualification run on a host that satisfies
`DEC-PLATFORM-001`.

This handoff is self-contained. It does not require the originating machine, the
linked worktree it was produced from, or any network access.

---

## 1. What must be true of the host

From `contracts/platform/PLATFORM_REFERENCE_DECISION.md` (`DEC-PLATFORM-001`,
status `ACCEPTED_PENDING_HOST_PROVISIONING`), §32–33:

> The decision takes effect when a **`reference-capable`** host exists — a GCE
> Linux instance, other native Linux, or WSL2.

and §29–31:

> WSL1 is classified **`smoke-only`** … Its output is **never** release
> evidence, never a reference build, and cannot satisfy a C16 acceptance row.

The mechanical gate is `tools/repro/linux_env.sh`, which sets
`BMX_PLATFORM_CLASS` and is consumed by every driver. `qualify.sh` refuses to
run on a non-reference host unless `--allow-smoke` is passed, and the
qualification driver then marks its own output `release_evidence: false`.

**Required tools** (absent → the host cannot even be classified; `linux_env.sh`
exits non-zero): `gcc`, `g++`, `cmake`, `mpicxx`, `mpirun`.
`make` is optional. `ninja` is preferred; Unix Makefiles is the fallback.
`python3` is required by the qualification drivers.

**If the host is a cloud VM**, five further constraints in `DEC-PLATFORM-001`
§86–106 are binding — notably §105, *"No cloud resource is provisioned, and no
spend is incurred, without explicit per-action authorisation from the project
owner"*, and §100–104 account legitimacy. Those are owner decisions, not
operator decisions.

## 2. Contents

| File | Purpose |
|---|---|
| `bmx-product.bundle` | complete BMX history, verified, all refs |
| `amrex-pinned.bundle` | AMReX at the pinned commit, complete history |
| `qualify.sh` | one-command entrypoint |
| `MANIFEST.sha256` | SHA-256 of every file here |
| `IDENTITY.json` | machine-readable identity of everything pinned |
| `README.md` | this file |

Fixture inputs, drivers, and configuration all travel **inside the bundle** as
tracked repository content, so there is no second place for them to drift.

## 3. Identity being qualified

| Item | Value |
|---|---|
| BMX commit to build | see `IDENTITY.json` -> `bmx_commit_to_build` (**authoritative**; not repeated here so it cannot go stale) |
| Chemistry candidate commit | `adb427331e180cd0b4faa74a4ab2098381b2eabb` |
| Reviewed kernel `src/chemistry/bmx_chem_K.H` | `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02` |
| Canonical baseline commit | `389e9e35a1c7291a4af795b2e39f2db1f0012b61` |
| Baseline kernel | `711ae2caa6e7aabb5c084fe841d2d90edb85ee53e7abc7a859d7de00e6614678` |
| Diagnostic repair (`D-C04-05`) | `5481856f46ba4bd2432dd21800fe9dbec8d10a15` |
| Provenance repair (`D-C04-08`) | `8428a5d354025f2a222deae287679bf2e89a4a9b` |
| AMReX commit | `cbdc6580ee3d78cccdd37172e4ba077ee181f483` |
| AMReX tree | `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6` |

`qualify.sh` verifies every one of these before building anything and aborts on
any mismatch.

## 4. Run it

```bash
sha256sum -c MANIFEST.sha256          # verify the handoff first
bash qualify.sh /path/to/empty/workdir
```

That single command: verifies the handoff, clones both bundles into a clean
workspace, verifies commit/tree/kernel identity and a clean source tree,
classifies the host, builds **four variants independently in four separate
build directories** each configured `-DBMX_REQUIRE_PROVENANCE=ON`, confirms each
binary reports the intended commit, proves provenance fails closed, runs the
complete C04 qualification sequence, and captures the environment.

Expected wall time: roughly 20–40 min, dominated by four ~200-object builds.

### Expected artifact layout

```
<workdir>/
  product/                     BMX at bmx_commit_to_build, AMReX vendored in
  baseline-src/                BMX at 389e9e35…
  baseline-diag-src/           389e9e35… + the two instrumentation commits
  build/c03-baseline-release/       ┐
  build/c04-p07-release/            │ four independent build dirs,
  build/c04-baseline-diag-release/  │ no image reused across slots
  build/c04-diag-release/           ┘
  logs/*.configure.log  *.build.log  *.provenance.log
  logs/image-hashes.txt  environment.txt  qualification.log
  runs/c04-qualification/QUALIFICATION_REFERENCE.json   <-- the verdict
```

The four binary hashes are **not required to differ**. Two deterministic builds
may legitimately produce identical bytes. What is required is that each image
has its own independent configure and build record — substitution or reuse is
not permitted, and `qualify.sh` never reuses one.

## 5. Reading the result

Open `runs/c04-qualification/QUALIFICATION_REFERENCE.json`.

`release_evidence` is `true` **only** when the host is `reference-capable`
**and** provenance resolved **and** every check passed. There is no override
flag. If it is `false`, `not_release_evidence_because` states why.

C04 may transition only if, in addition:

- provenance is resolved and exact for all four independently built images
- the mandatory donor-cap equality row passes
  (`A_particles_final == fA0 * V_cell`)
- geometry fixtures pass, including `G0` observation-neutrality
- provenance regression fixtures pass, including the fail-closed case
- the chemistry candidate bytes are unchanged
- **RT-1** and **RT-2** each carry their own verdict and evidence pointer

RT-1 and RT-2 may be exercised in the same execution but remain separate
requirements with separate machine-readable verdicts.

## 6. If it fails

Do **not** edit source, and do **not** re-label the run as smoke evidence.
Preserve the entire `<workdir>` — logs, build dirs, JSON — and classify the
first causal failure as one of:

| Class | Meaning |
|---|---|
| host / infrastructure | missing tool, wrong class, resource limit |
| packaging | handoff extraction, bundle, checksum |
| build-system / provenance | configure, link, `BMX_REQUIRE_PROVENANCE` |
| fixture / harness | driver or analyzer defect |
| chemistry / numerical | a genuine model result change |

Report the first causal failure **and** its downstream consequences, then
request authorization before changing anything outside the already-approved
ownership scope. A chemistry/numerical classification in particular must not be
acted on without authorization — the chemistry candidate is frozen.

## 7. Known limitations carried into this run

- AMReX's own `HASH1` may remain empty; AMReX is a pinned submodule and is
  deliberately not modified. BMX's own provenance is authoritative.
- `D-C02-06` (`compile_commands.json` copied into the source tree) is a source
  defect and will persist on Linux; it dirties the tree after configure. The
  repository `.gitignore` covers it.
- The six C02 defects are expected to be Windows-portability defects rather than
  product defects. `configure_linux.sh` applies none of their workarounds
  deliberately, so whether that expectation holds is a **finding** of this run.
