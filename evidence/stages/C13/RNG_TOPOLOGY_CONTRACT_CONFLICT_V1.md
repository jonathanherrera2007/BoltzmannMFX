# C13 RNG/topology contract consistency blocker

Status: **BLOCKED** at
`D-C13-05-RNG-SIDE-BRANCH-GRADIENT-REACHABILITY`.

The exact D-C13-04 contract and known-answer vectors were adopted and verified,
and the normative KAT passes. Implementation cannot continue because two
normative requirements in the adopted contract are mutually unsatisfiable
against the frozen chemistry kernel.

## Exact conflict

In frozen `src/chemistry/bmx_chem_K.H`, `setNewSegment` reads the parent's
`gx`, `gy`, and `gz`, then an unconditional `if (true)` assigns all three to
`0.0`. The SECOND_1/SECOND_2 side-branch path later computes
`gn = sqrt(gx*gx + gy*gy + gz*gz)`. Consequently, every reachable side branch
has exact binary64 `gn == 0.0`.

The adopted contract simultaneously requires:

1. O06 gradient and geometry formulas byte-for-byte equivalent to frozen
   `setNewSegment`, with only RNG and child identity replaced;
2. no sign draw/key when `gn!=0.0`; and
3. mandatory forced side-branch cases for both `gn==0` and `gn!=0` across
   P0-P5.

The `gn!=0` forced case is unreachable if requirement 1 is obeyed. Making it
reachable requires bypassing or changing the unconditional gradient zeroing,
which changes side-branch growth direction and violates both the contract's
replacement boundary and the owner's explicit no-growth-change boundary.

The KAT does not detect this: it validates serialization, stateless draws,
identities, ledgers, chains, and checkpoint state, not frozen
`setNewSegment` control-flow reachability.

## Safe disposition

No product-source change was retained. The source tree remains
`dd10ce05a9d12a84244a3d3cf713ca9ab279e16b`. No new build, runtime
qualification, independent review request, 216-hour outcome, science run,
external resource, or spend occurred.

`D-C13-04-RNG-TOPOLOGY-DECOMPOSITION` remains closed as a user-adopted
specification decision pending implementation and review. The new controlling
blocker is D-C13-05.

## Decision needed

The smaller, boundary-preserving resolution is to issue a new hash-bound
contract/KAT revision that removes the unreachable `gn!=0` side-branch forced
case and states that sign draw ordinal 0 is always materialized for every
accepted side branch under the frozen v1 formula.

The alternative is to explicitly authorize nonzero-gradient side-branch
behavior and prospectively bind its gradient source, normalization, geometry,
draw schedule, and qualification vectors. That changes topology/growth
behavior and cannot be inferred from the current adoption.

A synthetic-only `gn!=0` helper test or post-zeroing gradient injection is not
an acceptable workaround because it would falsely claim frozen-formula
equivalence.

Frozen bytes remain:

- global order: `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`;
- chemistry kernel: `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.

This is an RG-SW Stage-0 specification-consistency blocker only. It is not
independent acceptance, mentor approval, `CLOSED_SCIENTIFIC`, calibration,
predictive validation, RG-SCI progress, C13 PASS, or P15 science.
