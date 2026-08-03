# D-C13-04 exact decision-only package v1

## Status

This package supplies executable bytes for the missing stochastic-topology decision. It is **not adopted merely by being generated or staged**. Until the exact adoption sentence is issued, `D-C13-04` remains open and C13 remains `BLOCKED`.

## Normative artifacts

- Contract: `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_CONTRACT_V1.json`
  - SHA-256: `059f067b94673838efba143c5a4615aaf79dcacc78a456317a81578daa37eba0`
- Known-answer vectors: `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_KAT_V1.json`
  - SHA-256: `ef47fa935b64671dd2f93e93640308b9620055587083f0c5c5a55aa1f95edcb7`
- Reference verifier: `tools/c13_rng_topology_contract_kat.py`
- Exact adoption sentence: `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_ADOPTION_TEXT_V1.txt`

## Principal bindings

1. An exact 80-byte, big-endian key contains seed, seed block, `nstep`, O06/O08 event type, stable parent/target logical IDs, candidate ordinal, draw ordinal, and a zero retry ordinal.
2. Each draw is direct SHA-256 of a domain constant plus the key; the first 64 digest bits map through an exact 53-bit `[0,1)` conversion. There is no rejection or retry.
3. The draw schedule reproduces current boundaries, including strict `YEAST vol > max_vol`, the discarded tip predicate when length is short, conditional zero-gradient branch sign, one fusion predicate only after the center broad phase and all deterministic checks, and zero fusion-geometry draws.
4. O06/O08 remain in the frozen order. Candidate/event plans are globally sorted; same-slot shared participant/bond/destination conflicts abort the complete batch. Fusion plus target split is one atomic O08 event.
5. Child logical IDs are allocated monotonically from a canonical global plan and mapped to BMX-compatible AMReX `(id,cpu_namespace)` fields. `cpu_namespace` is not rank. Pinned AMReX `NextID` is held at a checkpoint-compatible nonauthoritative sentinel.
6. Raw fixed-layout RNG and topology records, deterministic JSONL mirrors, topology projection hashes, event IDs, and separate cumulative SHA-256 chains are required. Owner-rank traces are noncanonical.
7. Checkpoint schema advances prospectively to v9 with a hash-bound 320-byte `RNGTopologyState`; rank changes continue the same keys, logical allocator, counts, and chains and fail closed on any missing/mutated state.
8. Qualification is CPU MPI/OpenMP only across P0-P5. GPU-enabled P15 hard-aborts until separately qualified.

## Implementation sequence after explicit adoption

1. Commit these decision-only bytes separately.
2. Add the separate keyed RNG/canonical event/identity/ledger module without editing the frozen kernel or order artifact.
3. Replace only P15-enabled stochastic inputs and child allocation in O06/O08; extend checkpoint/restart to schema v9.
4. Run the KAT and every forced/fault/restart case across P0-P5, then all existing C13 engineering suites from a clean committed build.
5. Obtain independent exact-source and numerical-contract `PASS`.
6. Only then run the preregistered 216-hour engineering/convergence/restart/conservation/production-selection matrix.

After adoption, the decision status is `CLOSED_USER_ADOPTED_PENDING_IMPLEMENTATION_AND_REVIEW`; it is not `CLOSED_SCIENTIFIC` and C13 is not yet `PASS`.
