# C01 — package, source, dependency, and worktree audit

- **Stage ID:** `C01`
- **Status:** `PASS`
- **Started / completed:** 2026-07-30
- **Role:** primary writer (Claude), product lane
- **Input commit / tree:** `389e9e35a1c7291a4af795b2e39f2db1f0012b61` / `1c73deedf0eb2feea833a7fddbc431ae9754d977`
- **Output commit:** see `COMMIT.txt` in this directory (recorded in the follow-up commit; see §8)
- **AMReX commit:** `cbdc6580ee3d78cccdd37172e4ba077ee181f483`
- **Machine-readable report:** `STAGE_REPORT.json`
- **Immutable identity record:** `SOURCE_IDENTITY_VERIFIED.json`
- **Environment record:** `ENVIRONMENT.md`

---

## 1. Goal and outcome

Prove the exact planning package, canonical source, pinned AMReX dependency, Git
metadata, worktree isolation, and clean starting point.

**All five identity requirements matched exactly. No production source was
modified. Nothing was built, run, or tested.**

## 2. Identity verification

| Item | Expected | Actual | Verdict |
|---|---|---|---|
| Planning package SHA-256 | `014607d3…c74a1` | `014607d3…c74a1` | **MATCH** |
| Package internal manifest | 153 members | 153 OK / 0 failed | **PASS** |
| BMX commit | `389e9e35…12b61` | `389e9e35…12b61` | **MATCH** |
| BMX tree | `1c73deed…4d977` | `1c73deed…4d977` | **MATCH** |
| AMReX commit | `cbdc6580…81f483` | `cbdc6580…81f483` | **MATCH** |
| AMReX tree | `fb714dc6…bf9ea6` | `fb714dc6…bf9ea6` | **MATCH** |
| AMReX gitlink inside canonical BMX tree | `cbdc6580…81f483` | `cbdc6580…81f483` | **MATCH** |

Canonical commit metadata: *"Add phosphorus transport and growth sensitivity
review"*, Jonathan Herrera, Thu Jul 9 15:44:58 2026 -0700. 370 tracked files.

Two fields in the package's `SOURCE_IDENTITY.json` could **not** be independently
recomputed and are recorded as such in `SOURCE_IDENTITY_VERIFIED.json`:
`bmx_snapshot_tree_sha256` (folding algorithm unspecified) and
`bmx_manifest_sha256` (the referenced manifest file is not in the package).
Neither weakens the result — the Git tree SHA-1 match plus the file-level
comparison in §4 is a strictly stronger check.

## 3. Source acquisition — provenance and why it is sound

The canonical objects were **not** downloaded. They already existed in a
pre-existing lane repository:

`…\2026-07-25\github-plugin-github-openai-curated-remote-3\work\BoltzmannMFX`

That repository is a **live multi-lane scratch workspace** — HEAD `dfe1eef` on
`codex/bmx-connected-poster-pilot`, five registered worktrees (four marked
`prunable`, pointing at WSL-style `/mnt/c/...` paths). It is explicitly **not**
treated as a baseline and **not** used as a working tree.

It is nevertheless a sound *object source*, because Git commit and tree SHA-1s
are self-verifying: after cloning, all four required identities reproduced
exactly. No trust is placed in the lane workspace's own state.

Two deliberate hardening choices:

- `git clone --no-hardlinks` for both BMX and AMReX, so the product's object
  store is **physically independent**. A later `gc`/`prune`/worktree-prune in the
  lane repository cannot corrupt or truncate this product.
- AMReX objects were taken from `<lane>/.git/modules/subprojects/amrex`
  (the submodule's real object store), so the whole acquisition was offline.

**The lane repository was not modified.** Verified after the fact: HEAD still
`dfe1eef`, 0 dirty entries, all 5 worktrees still registered. Its prunable
worktrees were deliberately left alone — they are another lane's evidence.

## 4. Snapshot-versus-checkout comparison

`planning-package/04_SOURCE_SNAPSHOT` compared file-by-file against the checkout:

| Result | Count |
|---|---|
| Files in snapshot | 108 |
| **Byte-identical** | **108** |
| Identical only after EOL normalisation | 0 |
| Content different | 0 |
| Missing in checkout | 0 |

**No unexpected source differences.** Not even an EOL-class difference. The
snapshot is a strict subset (108 of 370 tracked files); files absent from the
snapshot are expected omissions, not differences.

## 5. Git metadata recorded

| Property | Value |
|---|---|
| `core.autocrlf` | `false` (set explicitly in every clone) |
| `core.fileMode` | `false` |
| `.gitattributes` | not present |
| EOL — LF text files | 192 |
| EOL — binary (`-text`) | 177 |
| EOL — CRLF or mixed | **0** |
| Files where index EOL ≠ worktree EOL | **0** |
| Symlinks (mode 120000) | **0** |
| Executable files (mode 100755) | 5 |
| Gitlinks (mode 160000) | 1 (`subprojects/amrex`) |

Because `core.autocrlf=false` and there is no `.gitattributes`, working-tree
bytes equal blob bytes exactly — independently confirmed by the 108/108
byte-identical result in §4.

The 5 executable-mode files are `.github/workflows/dependencies/documentation.sh`,
`docs/models/model1/model1.tex`, `exec/pair_test/sep.pl`, `exec/wall_test/zloc.pl`,
`tools/DEBUG/amrex-max-vel`.

**Carry-forward constraint:** `core.fileMode=false` is required on this Windows
host. Executable bits survive in the index but are not enforceable in the working
tree. **Build and run scripts must not depend on the working-tree executable
bit** — invoke interpreters explicitly (`sh script.sh`, `python script.py`).

Remotes were renamed `origin` → `canonical-upstream` in all clones. This is
deliberate: it removes the default push target, so an accidental bare
`git push` has nothing to push to. Pushing remains prohibited without explicit
user authorization.

## 6. Workspace layout and isolation

```
BMX-RG-SW/
├── planning-package/          extracted, hash-verified, reference only
├── repo/                      git store + pristine canonical checkout (never edited)
└── worktrees/
    ├── baseline/              detached 389e9e3   — untouched baseline (C03)
    ├── product/               branch rgsw/product — primary writer (this lane)
    └── review/                detached 389e9e3   — independent reviewer, read-only
```

All four checkouts verified at commit `389e9e3` / tree `1c73dee`, each with
AMReX bound at `cbdc658` / tree `fb714dc`, each reporting a **clean
`git status`** before this stage's own evidence files were added.

`repo/` is kept as a never-edited pristine reference distinct from `baseline/`,
because C03 will fill `baseline/` with build and run outputs; a pristine tree
remains available for diffing.

Isolation from P05:

| Check | Result |
|---|---|
| P05 workspace | `…\perform-a-strict-read-only-import\work\p05-production-readiness` |
| Path overlap with product | **none** (disjoint prefixes) |
| Shared branches | none |
| Shared object store | none |
| Shared build/output dirs | none |
| P05 touched by this stage | **no** |
| Writers on `rgsw/product` | **1** |

## 7. Repository guidance files installed

`AGENTS.md` and `CLAUDE.md` were placed at the product worktree root from the
supplied templates, verbatim, with one addition: a clearly-labelled
"Local binding" subsection in `AGENTS.md` recording the real local package path,
since the package's `/mnt/data/...` origin path does not exist on this host. The
fixed identity hashes above it are unchanged.

## 8. Files changed

| Path | Reason |
|---|---|
| `AGENTS.md` | shared durable agent rules (pack README step 3) |
| `CLAUDE.md` | Claude entry point importing `AGENTS.md` |
| `evidence/session/SESSION_BOOTSTRAP.md` | S00 evidence, relocated into the product worktree so all evidence is version-controlled in one place |
| `evidence/stages/C01/STAGE_REPORT.md` | this report |
| `evidence/stages/C01/STAGE_REPORT.json` | machine-readable report |
| `evidence/stages/C01/SOURCE_IDENTITY_VERIFIED.json` | immutable verified identity record |
| `evidence/stages/C01/ENVIRONMENT.md` | environment recapture |
| `evidence/stages/C01/COMMIT.txt` | resulting commit hash (written by the follow-up commit) |

No production source file was created, modified, or deleted.

Because a stage report cannot contain the hash of the commit that contains it,
C01 produces two commits: the stage commit, then a one-line follow-up commit
recording that hash in `COMMIT.txt`. No history was amended or rewritten.

## 9. Commands

All commands were run from `BMX-RG-SW`. Exit code 0 unless noted.

```
Get-FileHash <zip> -Algorithm SHA256
Expand-Archive -Path <zip> -DestinationPath planning-package -Force
sha256sum -c MANIFEST.sha256                       # 153 OK, 0 failed

git -c core.autocrlf=false clone --no-hardlinks --no-checkout <lane> repo
git -C repo remote remove origin
git -C repo remote add canonical-upstream https://github.com/jonathanherrera2007/BoltzmannMFX.git
git -C repo checkout --detach 389e9e35a1c7291a4af795b2e39f2db1f0012b61

git -c core.autocrlf=false clone --no-hardlinks --no-checkout \
    <lane>/.git/modules/subprojects/amrex repo/subprojects/amrex
git -C repo/subprojects/amrex checkout --detach cbdc6580ee3d78cccdd37172e4ba077ee181f483
git -C repo submodule init

git -C repo worktree add --detach worktrees/baseline 389e9e3…
git -C repo worktree add -b rgsw/product worktrees/product 389e9e3…
git -C repo worktree add --detach worktrees/review 389e9e3…
# AMReX cloned and detached at cbdc658… in each of the three worktrees

git rev-parse HEAD 'HEAD^{tree}' ; git submodule status ; git status --porcelain
git ls-files --eol ; git ls-files -s
cmp / sha256sum over 04_SOURCE_SNAPSHOT vs checkout   # 108/108 byte-identical
```

## 10. Tests

C01 defines no software tests. Its mandatory validation is identity and state
verification, all of which passed:

| Check | Result |
|---|---|
| Exact commit and tree comparisons | **PASS** (7/7, §2) |
| Clean `git status` for each new worktree | **PASS** (4/4, §6) |
| Exact AMReX identity | **PASS** (commit, tree, and gitlink) |
| No path overlap with P05 | **PASS** |
| No unexpected source differences from snapshot | **PASS** (108/108 byte-identical) |

## 11. Conservation / restart / claim effects

None. No model code, numerical behaviour, or scientific contract was touched.

## 12. Blockers

| ID | Blocker | Owner | Dependency | Latest safe boundary |
|---|---|---|---|---|
| B-S00-01 | No qualified build platform. Native Windows has **no C++ compiler**; the only complete toolchain is WSL **1** Ubuntu 24.04, which is unproven for AMReX/MPI. | writer | C02 build spike | Blocks C02 and everything downstream. Does not block anything already done. |
| B-S00-03 | All biology-dependent decisions unresolved; mentor packet not yet sent. | user / mentor | `mentor/MENTOR_QUESTIONS_URGENT.md` | Final runs in C10, C11, C12, C14, C15 and contract freeze in C06B |

B-S00-02 (no isolated worktrees) is **resolved** by this stage.

No blocker is unresolved within C01's own mandatory scope, so `PASS` is valid.

## 13. Claims that remain prohibited

Nothing has been built, executed, or tested. Specifically prohibited and **not**
claimed: formal P05–P18 acceptance; empirical calibration; predictive validity;
full-plate validity; production qualification; publication readiness;
`RG-SW:GO`; `RG-SCI:GO`; any statement that the platform is qualified, that the
source compiles, or that any scientific result exists.

Current honest label: **`RESEARCH-USE-CANDIDATE — RG-SW INCOMPLETE`**,
**`RG-SCI:NO-GO`**, **formal acceptance: NO**.

## 14. Next valid prompt

`prompts/claude/C02_FIRST_FOUR_HOUR_BUILD_SPIKE.md`

Note for C02: the one-hour native-Windows prerequisite budget has effectively
already been spent by inspection — there is no compiler, no generator, and no
MSBuild on this host. C02 should confirm that quickly and move to the Linux
route, and must treat WSL1 as a candidate to be *proven*, not assumed.
