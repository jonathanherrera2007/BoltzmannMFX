# C13 / P15 Stage 0 report

## Verdict

**C13/P15 Stage 0 remains `BLOCKED`, now at
`D-C13-05-RNG-SIDE-BRANCH-GRADIENT-REACHABILITY`.**

The project owner adopted the exact D-C13-04 RNG/topology contract and its
normative known-answer vectors. Their hashes match and the KAT passes.
`D-C13-04-RNG-TOPOLOGY-DECOMPOSITION` is therefore closed as a user-adopted
specification decision pending implementation and review.

Implementation stopped before a product-source commit because the adopted
contract contains a reachability requirement that contradicts its own frozen
formula-equivalence requirement. No C13 scientific outcome, 216-hour run,
C14/P16 work, remote operation, external resource, or spend occurred.

## Current identity

- Branch: `rgsw/c13-p15-stage0`
- Adoption input: `096021480271fde968eb7227e30affcaaa111232`
- Decision-package commit: `a9f383c7bde137b2e2ad74d7353a87203bfc2374`
- Adoption-evidence commit: `1f877be92190dd4bffa1b701f3aa8260235170c2`
- Blocker-evidence payload commit:
  `91836c51529480ba0db44ec32d446d568dacd547`
- Adoption HEAD tree: `24149f9c620c0608b67f9f6565dcec4428eeceaf`
- Product `src` tree before and after this attempt:
  `dd10ce05a9d12a84244a3d3cf713ca9ab279e16b`
- Pinned AMReX commit/tree:
  `cbdc6580ee3d78cccdd37172e4ba077ee181f483` /
  `fb714dc6e693c18f7c441d1d1febe4a5e8bf9ea6`

The previous deterministic Stage-0 candidate remains at implementation commit
`7cd952ec22172a023de25f84952263c896458730`, with clean-build recorder
`a475b3f968e17327f2ffe28d0d48a781d35e3e65` and executable SHA-256
`57eb7cfdbf2e8cec705f65046f84220d8832278ed0ea3634efccdc513e97041b`.
Its 49 analytical, 25 static, 17 short-native, and 2 feature-off checks remain
historical evidence for deterministic scope only; they do not qualify the
unimplemented RNG/topology contract.

## Adopted D-C13-04 binding

- Contract:
  `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_CONTRACT_V1.json`
- Contract SHA-256:
  `059f067b94673838efba143c5a4615aaf79dcacc78a456317a81578daa37eba0`
- Normative KAT:
  `contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_KAT_V1.json`
- KAT SHA-256:
  `ef47fa935b64671dd2f93e93640308b9620055587083f0c5c5a55aa1f95edcb7`
- Classification:
  `USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`
- KAT result: PASS

This closes the missing RNG/key/identity/ledger specification. It does not
establish implementation qualification, independent acceptance, or C13 PASS.

## Controlling blocker

Frozen `setNewSegment` reads `gx`, `gy`, and `gz`, then unconditionally runs
`if (true)` and sets all three to `0.0`. The SECOND_1/SECOND_2 side-branch path
later computes `gn = sqrt(gx*gx + gy*gy + gz*gz)`. Therefore every reachable
side branch has exact `gn == 0.0`.

The adopted contract simultaneously requires:

1. O06 gradient and geometry formulas byte-for-byte equivalent to frozen
   `setNewSegment`, replacing only RNG and child identity;
2. a conditional draw schedule in which sign draw ordinal 0 is absent when
   `gn!=0.0`; and
3. mandatory `gn==0` and `gn!=0` side-branch cases across P0-P5.

The `gn!=0` case is unreachable under requirement 1. Making it reachable
changes side-branch growth direction and violates the owner's explicit
no-growth-change adoption boundary. A synthetic helper cannot cure the
contradiction because the mandated case is an integrated P0-P5 topology case.

The complete proof and disposition are in
`RNG_TOPOLOGY_CONTRACT_CONFLICT_V1.json` and `.md`. The committed JSON blob
SHA-256 at the payload commit is
`61c2669ce433683c99b9726e6436deb67deb4a9f5e18af591176003889caea94`.

## Work and tests in this continuation

The normative KAT command returned 0:

```text
python tools/c13_rng_topology_contract_kat.py contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_KAT_V1.json
PASS: contract SHA; 6 draws; 4 identities; candidate; 3 event IDs; projection; RNG/topology records; event subset; 2 chain inits; 2 file/batch/chain vectors; checkpoint state
```

Static source/contract inspection confirmed the contradictory dataflow and
requirements. Incomplete implementation wiring was removed before commit.
No product-source change is retained, so a build or runtime suite would not
test the adopted implementation and was not misreported as qualification.

## Required decision

The recommended resolution is a new hash-bound contract/KAT revision that
preserves frozen growth semantics, removes the unreachable `gn!=0`
side-branch forced case, and states that sign draw ordinal 0 is always
materialized for accepted side branches under the frozen v1 formula.

The alternative is an explicit prospective authorization for nonzero-gradient
side-branch behavior, including exact gradient source, normalization, geometry,
draw schedule, and qualification vectors. That is a growth/topology behavior
change and requires independent review; it cannot be inferred here.

## Frozen bytes and claim boundary

- Global operator order remains
  `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`.
- Frozen chemistry kernel remains
  `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`.
- No conservation/restart claim is added because no new executable or state
  was produced.
- No 216-hour outcome or P15 science was run.

This is an RG-SW Stage-0 specification-consistency blocker only. It is not
independent acceptance, mentor approval, `CLOSED_SCIENTIFIC`, calibration,
predictive validation, RG-SCI progress, release qualification, or C13 PASS.
