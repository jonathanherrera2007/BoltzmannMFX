# Redactions in this public snapshot

This repository is a **sanitized release snapshot**, not the development repository.
This file records every difference from the private original so the changes are
auditable rather than silent.

Snapshot base commit (private repo): `a5094a9bfbe8b9bc1063543ba31af83556b9c499`
— *"Adopt C13 RNG topology v1.1 binding"*

## 1. No development history

Published as a single snapshot lineage. The private repository's history was **not**
rewritten and **not** published: rewriting it would have changed every commit SHA, and
dozens of commit hashes are cited across `evidence/` as the project's attribution chain.

**Consequence:** commit hashes named inside `evidence/` refer to the private development
repository and will not resolve here. SHA-256 *content* hashes still verify, except where
noted below.

## 2. Excluded content

- `mentor/` — 1 file(s)
- `docs/reviews/` — 4 file(s)

Removed rather than redacted: correspondence and review material authored by or addressed
to third parties, containing unpublished scientific judgements that are not the repository
owner's to publish. Replacing a name would not have changed that.

## 3. Redacted files

Personal names replaced with role descriptions; one personal email replaced. No scientific
value, parameter, tolerance, equation, gate, operator order, or result was altered.

| File | Replacements | SHA-256 before | SHA-256 after |
| --- | --- | --- | --- |
| `.gitmodules` | SSH submodule URL → HTTPS | `1d59299bc9ee0887…` | `e7431b6fd02abef7…` |
| `contracts/decision_reconciliation.json` | status token naming a person ×1 | `4bba5de6bb3bcb27…` | `4034f058565cfa12…` |
| `contracts/decision_reconciliation.md` | status token naming a person ×1 | `1730996484f41b0b…` | `91e81effa200c80b…` |
| `contracts/USER_ADOPTED_DECISION_CONTRACT_20260801_V2.json` | status token naming a person ×1 | `ef5ae6da48e1ec85…` | `6772aa314005b395…` |
| `contracts/USER_ADOPTED_DECISION_CONTRACT_20260801_V2.txt` | status token naming a person ×1, personal name ×6, personal name ×1, personal name ×4 | `34e8414c09e6528f…` | `d8e3501e75a75cf6…` |
| `contracts/USER_APPROVED_DECISION_CONTRACT_20260801.txt` | status token naming a person ×1, personal name ×9 | `283eace4f34e0a3d…` | `da61907656a9e8cb…` |
| `evidence/handoff/WRITER_HANDOFF.md` | personal email address ×1 | `abcb90924106c2ef…` | `7cb06fec78aa1a42…` |
| `evidence/stages/C04/STAGE_REPORT.json` | personal email address ×1 | `f92e8005e3739a81…` | `ec107ac26ca867b0…` |
| `subprojects/README.md` | SSH submodule URL → HTTPS | `f1f8921436635f33…` | `f961f1c891b42395…` |

### Known consequence

`src/chemistry/bmx_chem_layout.H` compiles in a `decision_contract_sha256` that was
computed from the **pre-redaction** bytes of an adopted decision contract. That constant
was deliberately left unchanged so the published source still corresponds to the source
that was built, qualified, and reviewed. The cost is that the file no longer hashes to the
constant naming it. Checkpoint validation compares against the compiled constant on both
write and read, so it remains self-consistent.

## 4. Deliberately retained

Local filesystem paths appear throughout `evidence/`. They were **kept**: they are
provenance records, several manifests hash the artifacts containing them, and the
usernames they expose are already public via the hosting account.

## 5. Also changed

`.gitmodules` and `subprojects/README.md` use the HTTPS URL for AMReX instead of SSH, so
the submodule can be initialised without repository credentials.

## 6. Agent and tool identities

Names of the AI coding tools used during development were replaced with neutral role
labels — "implementation writer" and "independent reviewer" — and the agent-instruction
file was removed. Local cache paths containing tool names were generalised.

The **two-party structure is preserved and is load-bearing**: the independent review
artifacts assert that the reviewer was not the implementation writer, and that assertion
is what the review is worth. Only the identities were generalised, never the separation.

No phase, stage, contract, or decision identifier was altered; those are the evidence
structure and renaming them would break cross-references and the compiled contract IDs.

