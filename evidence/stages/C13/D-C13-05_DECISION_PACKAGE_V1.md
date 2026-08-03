# D-C13-05 exact decision-only package v1

## Decision

Select **option 1**. Preserve the frozen `setNewSegment` behavior. Do not authorize nonzero-gradient side branching.

The frozen chemistry kernel at SHA-256 `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02` loads the stored gradient, then executes an unconditional `if (true)` block assigning `gx=gy=gz=0.0` before the SECOND_1/SECOND_2 branch computes `gn`. Under the already required IEEE-754 binary64 CPU scope, the effective gradient components and `gn` are exact positive zero. Therefore:

- a qualified accepted side branch always enters the zero-gradient sign-selection branch;
- geometry event `0x12` draw ordinal `0` is mandatory;
- accepted side-branch geometry draws are exactly `[0,1,2]`;
- the accepted candidate has exactly four materialized draws including its event `0x02` predicate; and
- `gn!=0.0` side branching is unreachable and is removed from qualification rather than implemented.

## Normative superseding artifacts

- Consolidated contract: `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_CONTRACT_V1_1.json`
  - SHA-256: `0198837e2fffcca34cc87febe13c51637f61ea9acc0c755025928fcb7e90cd17`
- Normative KAT: `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_KAT_V1_1.json`
  - SHA-256: `607de0acab001f97544545bb16128766f657e7a7f74ee981c76a39fe08f1df1b`
- Machine-readable change log: `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_V1_TO_V1_1_CHANGELOG.json`
- Reference verifier: `tools/c13_rng_topology_contract_kat_v1_1.py`
- Exact adoption text: `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_ADOPTION_TEXT_V1_1.txt`

The v1 contract/KAT remain unchanged as provenance. These v1.1 bytes become current only after the exact adoption statement is issued.

## Exact contract correction

1. The contract now binds the frozen source reachability sequence and exact +0.0 component/norm bits.
2. Accepted side-branch geometry always materializes draw ordinals `0`, `1`, and `2`; there is no conditional omission and no `gn!=0.0` schedule.
3. Candidate precondition bit 15 denotes the frozen effective `setNewSegment` zero norm. An accepted side-branch candidate records four total draws.
4. The forced `gn!=0.0` case is deleted. Its replacement deliberately supplies nonzero stored gradient inputs and proves that the frozen override still yields effective `gn==0.0` and the complete `[0,1,2]` geometry schedule.
5. Any effective nonzero norm aborts the complete O06 batch as `C13_ABORT_SIDE_BRANCH_GRADIENT_REACHABILITY_DIVERGENCE` before mutation or chain advancement.
6. Removing or bypassing the zero override remains option 2 and is explicitly prohibited absent a separately adopted behavior-change contract.

## KAT correction

The v1.1 KAT adds:

- exact SHA-256 draw vectors for side-branch sign, deflection, and azimuth at event `0x12`, ordinals `0,1,2`;
- a reachability vector using deliberately nonzero stored gradient bits but requiring exact +0.0 effective gradient and norm;
- an accepted side-branch candidate descriptor with precondition bit 15 and `materialized_draw_count=4`; and
- recomputed contract-dependent chain initialization, ledger headers/steps, and checkpoint state bytes.

## Boundaries

This package is decision-only. It does not edit product `src`, the frozen chemistry kernel, operator order, biological or transport decisions, checkpoint implementation, or runtime topology code. It does not run a build, cloud resource, paid service, 216-hour outcome, or P15 science.

The updated repository HEAD `421736bff65f59f360b56a8b4c8a7b95f1b29ed2` and clean/src-unchanged state were supplied by the user but were not independently checked because those updated repository bytes were not uploaded. The frozen source behavior was independently verified in the available archive `BMX-RG-SW-C07-product-full-0960214-20260802.zip` at SHA-256 `9402571b1a6c0cbff3edc2d13041b0c4bfd085c7b79371e5100fca329d9a0bd7`.

## Status after explicit adoption

- `D-C13-04-RNG-TOPOLOGY-DECOMPOSITION`: remains `CLOSED_USER_ADOPTED_PENDING_IMPLEMENTATION_AND_REVIEW` under the consolidated v1.1 binding.
- `D-C13-05-RNG-SIDE-BRANCH-GRADIENT-REACHABILITY`: becomes `CLOSED_USER_ADOPTED_PENDING_IMPLEMENTATION_AND_REVIEW`.
- C13 remains `BLOCKED` until exact implementation, P0-P5 forced/fault/restart qualification, clean committed rebuild, independent exact-source and numerical-contract review, and every preregistered 216-hour gate passes.
