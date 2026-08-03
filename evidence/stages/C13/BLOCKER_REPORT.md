# C13 / P15 Stage 0 blocker report

Status: **BLOCKED before RNG/topology implementation, independent exact-source
review, and every 216-hour qualification outcome**.

The exact D-C13-04 contract and KAT are adopted and hash-verified, so the
original missing-specification blocker is closed pending implementation and
review. A new internal consistency blocker controls:
`D-C13-05-RNG-SIDE-BRANCH-GRADIENT-REACHABILITY`.

## Root cause

Frozen `setNewSegment` in `src/chemistry/bmx_chem_K.H` reads the parent's
gradient, then unconditionally sets `gx=gy=gz=0.0`. The side-branch path later
computes `gn` from those values, making exact `gn==0.0` invariant for every
reachable SECOND_1/SECOND_2 branch.

The adopted contract requires byte-for-byte-equivalent frozen gradient and
geometry formulas, permits replacement only of RNG and child identity, and
also mandates both `gn==0` and `gn!=0` forced side-branch cases across P0-P5.
It further assigns a different draw schedule to `gn!=0`, where ordinal 0 must
be absent.

Those clauses cannot all be implemented. A reachable `gn!=0` case requires
changing or bypassing the frozen zeroing, which changes growth direction and
is expressly outside the current authorization. Dropping the case or changing
its draw schedule changes the adopted contract. Neither choice belongs to the
writer.

## Evidence and disposition

The normative KAT passes all serialized key, draw, identity, candidate, event,
ledger, chain, and checkpoint-state vectors. That does not test
`setNewSegment` reachability, so it does not waive this blocker.

No product-source change was retained. The `src` tree remains
`dd10ce05a9d12a84244a3d3cf713ca9ab279e16b`. No new build, runtime
qualification, independent review request, 216-hour outcome, P15 science,
external resource, or spend occurred.

Full machine-readable proof is in
`evidence/stages/C13/RNG_TOPOLOGY_CONTRACT_CONFLICT_V1.json`, committed at
`91836c51529480ba0db44ec32d446d568dacd547` with Git-blob SHA-256
`61c2669ce433683c99b9726e6436deb67deb4a9f5e18af591176003889caea94`.

## Required authority

Recommended: preserve frozen growth behavior and issue a new hash-bound
contract/KAT revision that removes the unreachable `gn!=0` side-branch forced
case and declares sign draw ordinal 0 always materialized for accepted side
branches under the frozen v1 formula.

Alternative: explicitly authorize and prospectively bind nonzero-gradient
side-branch behavior, including gradient source, normalization, geometry,
draw schedule, and qualification vectors. That is a topology/growth change
and needs independent review.

Do not use a synthetic-only helper or inject a nonzero gradient after the
frozen zeroing while claiming formula equivalence.

Frozen global-order and kernel hashes remain respectively
`bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`
and
`9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.

This is not implementation qualification, independent acceptance, mentor
approval, `CLOSED_SCIENTIFIC`, calibration, predictive validation, RG-SCI
progress, C13 PASS, or P15 science.
