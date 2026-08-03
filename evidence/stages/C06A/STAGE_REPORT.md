# C06A — reconcile decisions and prepare the mentor packet

- **Stage ID:** `C06A`
- **Status:** `PASS`
- **Date:** 2026-07-30
- **Role:** primary writer (Claude), product lane
- **Source changes:** **none** — contracts, ledgers, and packet only
- **Artifacts:** `contracts/decision_reconciliation.{md,json}`,
  `contracts/release_blockers.json`, `mentor/MENTOR_PACKET_C06A.md`

---

## 1. Executed out of index order — deliberately, and no gate was skipped

`PROMPT_INDEX.md` places C06A at step 7, after C05. It was run now, with C04
`BLOCKED` and C05 not started.

C06A is decision reconciliation over the two decision JSONs and the P09–P16
requirement documents. **It does not consume P07 runtime results**, so it is not
a dependent prompt of C04 and the gate rule ("never move to a *dependent* prompt
when the prior stage is BLOCKED") is not violated.

The reason for re-ordering: **B-S00-03 — the mentor packet — has been open since
C01 and is the longest-latency blocker in the project.** It gates C06B and every
final run C10–C15, and it depends on a human reply. Everything else I can do is
local-path work. Producing the packet now shortens the critical path.

## 2. Reconciliation result

All **59** ledger fields mapped against the **13** confirmed decisions. Each
field is accounted for exactly once — enforced programmatically; the generator
aborts on any unmapped or extra ID.

| Status | Count |
|---|---:|
| `CLOSED_SCIENTIFIC` | **16** |
| `CLOSED_TECHNICAL` | **8** |
| `CLOSED_MEASURED` | **3** |
| `PARTIAL` | **7** |
| `OPEN` | **25** (5 are P17 post-results) |

**27 of 59 closed. 20 pre-results items need the mentor.**

## 3. Avoiding both failure modes named in the reconciliation requirement

The requirement warns against assuming *"all science is settled"* or *"all
generic unknowns remain unresolved"*. Both were avoided explicitly:

- **Scope discipline.** A confirmed decision closes a field only within its
  stated scope. `P13-U03-RATE-VALUES-BOUNDS` is the sharpest case: the rates
  1e-6/1e-5/1e-4 s⁻¹ *are* confirmed, but as **sensitivities only**, with the
  decision instructing that no biological baseline be selected. It is recorded
  as closed for the sensitivity axis and explicitly **not** as a calibrated
  value. No confirmed decision was overextended into calibration.
- **Not everything is open.** 8 fields carry no biological content at all
  (checkpoint compatibility, numerical tolerances, non-finite policy, test-case
  enumeration, ledger schema) and are frozen now so implementation is not
  blocked on the mentor for engineering matters.

## 4. What reconciliation removed from the mentor's workload

This is the practical value of the stage. The pre-existing urgent packet asks 8
items; two were already answered by decisions on record:

1. **The export law form was already decided.** `MD-88955e1dff7ca225-02` says
   export occurs *"at `k_export` multiplied by local D"* — that fixes the form
   as first-order in local internal D. Asking "first-order, area-based, or
   another form?" would have re-litigated a settled decision. Only the operand
   (amount vs concentration), units, and magnitude remain.
2. **The reward conversion was fully specified.** `MD-5b43f4b235dec87e-03` gives
   `r = 3` as mass C per mass P actually exported, derives ≈7.736 mol
   A-equivalent per mol P, and states there is *no version-1 capacity or delay*
   — which also settles whether an additional interface cap exists. It does not.

## 5. Gaps that are NOT ledger fields

A field-by-field pass alone would have missed these two, both of which block
implementation:

| ID | Gap | Blocks |
|---|---|---|
| `G-EXT-01` | D membrane uptake coefficient value/range; confirmation that D uses the same reversible area-based form as carbon | P12 final run |
| `G-EXT-02` | `k_export` operand (amount vs concentration), units, value/range | P14 export enable |

Both are in the packet. `G-EXT-02` matters more than it looks: whether "local D"
means an amount or a concentration **changes the units of `k_export`**, so the
question cannot be deferred to implementation.

## 6. Review triggers carried forward

- **Renewed review before P16.** `MD-5b43f4b235dec87e-05` approves `q_P` and
  `k_gP/k_gB` as sensitivities only; using them to define or compare
  explorer/exploiter strategies requires renewed review. The packet requests it
  explicitly rather than assuming it was granted.
- **F activation remains prohibited.** Infrastructure may exist; every F
  reaction, exchange, and transport coefficient stays exactly zero.

## 7. Technical policies frozen

Nine policy areas frozen under source-safety justification, containing no
biological selection — canonical D/E/F vocabulary with legacy aliases rejected;
legacy-checkpoint reject plus schema v2; conservation tolerances; restart
comparator; non-finite and clamp policy; limiting-case test enumeration; ledger
persistence schema; shared numerical tolerances; measured operational limits.

**These are frozen for implementation, not mentor-approved.** They remain
subject to independent numerical review before final runs. A technical proposal
is not mentor approval, and this report does not treat it as such.

## 8. What may now proceed

| Scope | Status |
|---|---|
| **P09**, **P10** | implementable now, except `P10-U01` deletion/orphan/simultaneous-event semantics and the `P10-U02` global operator order |
| **P11** | implementable except particle-divider mechanics and outer x/z boundaries |
| **P12, P13, P14** | infrastructure only, **default-off**; **no final run may execute** |
| **P15, P16** | fully blocked |
| **P17** | post-results |

## 9. Mandatory validation

| Check | Result |
|---|---|
| Exactly 59 fields accounted for once | **PASS** — programmatically enforced |
| Every closure cites a decision ID or a technical contract | **PASS** — `closed_by` populated for every scientific closure; technical closures cite the policy |
| No confirmed decision overextended into calibration | **PASS** — see §3 |
| Packet contains only material unresolved questions | **PASS** — 2 items removed as already-decided; packet lists what is closed so the mentor can skip it |

## 10. Claims

**Not** claimed: any biological parameter selected here; mentor approval of the
frozen technical policies; calibration; any scientific result; formal P05–P18
acceptance; `RG-SW:GO`; `RG-SCI:GO`.

Status remains **`RESEARCH-USE-CANDIDATE — RG-SW INCOMPLETE`**, **`RG-SCI:NO-GO`**.

## 11. Next actions

- **User:** send `mentor/MENTOR_PACKET_C06A.md`. This is the only action that
  moves the project's longest-latency blocker. **B-S00-03 stays open until it is
  actually sent** — a ready packet is not a sent packet.
- **Writer:** resolve `B-C04-01` (particle-geometry observables), then C05.
- On reply: `S03_NORMALIZE_MENTOR_RESPONSE.md`, then `C06B`.
