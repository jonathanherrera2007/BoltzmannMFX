# C13 RNG/topology decomposition adoption

The project owner explicitly adopted
`UDC-20260802-C13-RNG-TOPOLOGY-DECOMPOSITION-V1` for RG-SW C13/P15
Stage-0 implementation and qualification. The exact adopted contract is
`contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_CONTRACT_V1.json` at SHA-256
`059f067b94673838efba143c5a4615aaf79dcacc78a456317a81578daa37eba0`.
Its normative known-answer vectors are
`contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_KAT_V1.json` at SHA-256
`ef47fa935b64671dd2f93e93640308b9620055587083f0c5c5a55aa1f95edcb7`.

The exact adoption message matches
`contracts/p15/RNG_TOPOLOGY_DECOMPOSITION_ADOPTION_TEXT_V1.txt`, SHA-256
`f64eb1598bcf174d9480ca2f7e930423242b22b56373ae3867296cef2b394850`.
The supplied package ZIP was verified at SHA-256
`68d576d69f62d0ff877dd7bfed06be33d54ac3b9048efe39181d8a92ca8a78c8`,
and its normative KAT passed before implementation.

`D-C13-04-RNG-TOPOLOGY-DECOMPOSITION` is therefore
`CLOSED_USER_ADOPTED_PENDING_IMPLEMENTATION_AND_REVIEW`. This closes the
missing specification decision only. C13 remains blocked pending exact
implementation, clean engineering qualification, and independent exact-source
and numerical-contract review.

Classification remains
`USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE`. The adoption does not
change the frozen global order or chemistry kernel and does not authorize any
216-hour outcome, P15 science, mentor-approval claim, calibration, predictive
validation, RG-SCI progress, or C13 PASS.
