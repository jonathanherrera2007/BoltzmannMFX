# C13 Stage-0 integrator handoff

C13/P15 Stage 0 is blocked at
`D-C13-05-RNG-SIDE-BRANCH-GRADIENT-REACHABILITY` on branch
`rgsw/c13-p15-stage0`.

## Resume identity

- D-C13-04 decision package: `a9f383c7bde137b2e2ad74d7353a87203bfc2374`
- D-C13-04 adoption evidence: `1f877be92190dd4bffa1b701f3aa8260235170c2`
- D-C13-05 blocker-evidence payload:
  `91836c51529480ba0db44ec32d446d568dacd547`
- Current product `src` tree:
  `dd10ce05a9d12a84244a3d3cf713ca9ab279e16b`
- Prior deterministic implementation:
  `7cd952ec22172a023de25f84952263c896458730`
- Prior clean-build recorder:
  `a475b3f968e17327f2ffe28d0d48a781d35e3e65`
- Pinned AMReX commit/tree:
  `cbdc6580ee3d78cccdd37172e4ba077ee181f483` /
  `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6`

## What is bound

`D-C13-04-RNG-TOPOLOGY-DECOMPOSITION` is closed as
`CLOSED_USER_ADOPTED_PENDING_IMPLEMENTATION_AND_REVIEW` under
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`.

- Contract SHA-256:
  `059f067b94673838efba143c5a4615aaf79dcacc78a456317a81578daa37eba0`
- KAT SHA-256:
  `ef47fa935b64671dd2f93e93640308b9620055587083f0c5c5a55aa1f95edcb7`
- Normative KAT: PASS

The prior deterministic Stage-0 work still has 49 analytical, 25 static, 17
short-native, and 2 feature-off passes. Those results do not qualify the
unimplemented RNG/topology contract.

The controlling conflict artifact is
`evidence/stages/C13/RNG_TOPOLOGY_CONTRACT_CONFLICT_V1.json` at committed
Git-blob SHA-256
`61c2669ce433683c99b9726e6436deb67deb4a9f5e18af591176003889caea94`.

## Why implementation stopped

Frozen `setNewSegment` unconditionally zeros `gx`, `gy`, and `gz` before
computing the side-branch gradient norm, so every reachable side branch has
exact `gn==0.0`.

The adopted contract requires frozen-formula-equivalent geometry and only
permits replacing RNG/NextID, but also mandates an integrated `gn!=0`
side-branch case across P0-P5 and gives it a distinct draw-consumption rule.
Satisfying that case requires a growth/topology behavior change prohibited by
the current adoption. Removing it changes the contract. The writer therefore
retained no partial source implementation.

## Binding required before source work resumes

Choose and freeze exactly one prospective resolution:

1. Recommended: preserve frozen growth semantics; remove the unreachable
   `gn!=0` forced case in a new contract/KAT revision and bind sign draw
   ordinal 0 as always materialized for accepted side branches.
2. Alternative: authorize nonzero-gradient side-branch behavior and bind the
   exact gradient source, normalization, geometry, draw schedule, and vectors.
   Treat it as a growth/topology change requiring independent review.

Do not use a synthetic helper or post-zeroing gradient injection as a claimed
integrated qualification case.

## Continuation after a consistent binding

1. Commit the amended decision-only binding before product implementation.
2. Implement the exact stateless RNG, canonical event/child identity, and
   checkpointed ledgers without editing `src/chemistry/bmx_chem_K.H` or the
   frozen global order unless the new authority explicitly changes that
   boundary.
3. Run the normative KAT and all forced split/branch/fusion cases across P0-P5,
   including rejection/fault and rank-change restart paths.
4. Rebuild from clean committed source and rerun every prior C13 analytical,
   static, native, feature-off, conservation, restart, and decomposition gate.
5. Freeze the exact source candidate and obtain independent exact-source and
   numerical-contract PASS.
6. Only then may any preregistered 216-hour qualification outcome begin.

Frozen identities remain:

- global order:
  `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`
- chemistry kernel:
  `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`

No 216-hour outcome, P15 science, C14/P16 work, external resource, spend, push,
or remote branch operation occurred.
