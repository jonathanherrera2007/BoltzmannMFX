# C13 RNG/topology decomposition v1.1 adoption

The project owner selected Option 1, prohibited nonzero-gradient side
branching, and stated that the superseding contract now binds at the exact
contract and KAT hashes supplied with the request.

The current implementation/qualification binding is therefore:

- `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_CONTRACT_V1_1.json`
  - SHA-256: `0198837e2fffcca34cc87febe13c51637f61ea9acc0c755025928fcb7e90cd17`
- `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_KAT_V1_1.json`
  - SHA-256: `607de0acab001f97544545bb16128766f657e7a7f74ee981c76a39fe08f1df1b`

The original v1 contract and KAT remain unchanged as superseded provenance.
`D-C13-04-RNG-TOPOLOGY-DECOMPOSITION` remains
`CLOSED_USER_ADOPTED_PENDING_IMPLEMENTATION_AND_REVIEW`, and
`D-C13-05-RNG-SIDE-BRANCH-GRADIENT-REACHABILITY` is now closed under the same
status.

The adopted resolution preserves frozen `setNewSegment`: every accepted side
branch has exact effective `gn==+0.0`, materializes geometry event `0x12`
draw ordinals `[0,1,2]`, and has four total candidate draws including its
predicate. Effective `gn!=0.0` is unqualified and must abort the complete O06
batch before mutation or chain advancement.

The package ZIP, manifest, sidecars, JSON, add-only patch, current-HEAD apply
check, v1 unchanged subtrees, and normative v1.1 KAT were independently
verified before this adoption record. Product `src` remained unchanged at
tree `dd10ce05a9d12a84244a3d3cf713ca9ab279e16b` through the decision-only
commit.

Classification remains
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`. C13 remains blocked pending
exact implementation, clean engineering qualification, and independent
exact-source/numerical-contract PASS. No 216-hour outcome or P15 science is
authorized by this adoption.
