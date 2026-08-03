# C10/P12 V2 final independent acceptance request

Status: `FULFILLED` by `FINAL_INDEPENDENT_ACCEPTANCE.json`, acceptance
`IA-20260802-C10-V2-FINAL`, SHA-256
`de1fb8ba26696a84ff0f0233e9fe269e091a384eb5034e86fc74250cbb72de58`.

## Requested decision

Independently review the exact C10/P12 implementation and the accumulated
Windows plus pinned-Linux V2 evidence. Return `PASS` or `FAIL` for final
engineering acceptance. This request does not authorize C11 and does not ask
the reviewer to approve biological calibration or mentor-level scientific
claims.

The implementation writer is Codex. A reviewer who is not independent of that
writer must not issue the acceptance artifact.

## Exact implementation and frozen contracts

- implementation commit: `0f38760b4daba3acbfd4b658c9ac522523b5c69b`
- implementation tree: `511e3d1ec6ec5148aa0548b6256c85b52a3b68a2`
- frozen kernel: `9519fc24ec7ea15fe391c23eb1b3739e0ad399f22f58dc87c303306ad6ffba02`
- global order: `bb63c219a860687d91ce1acf06a667c9208abf026b32f18acfc64884bb696dd6`
- V2 numerical contract: `43d64a8f4ec6c8c00379fc3d9605441cb900479fcdd8db9e78e6fc1edd28f81f`
- uptake contract: `2094aed3c8ef21a257d2c597352793384d01a1efc3d72936d5c5108d308f8804`
- independent prerun review: `bda12aef209793b4537915e374e09caf100397c0fdf8678ed00118ff987a3ea2`

## Outcome evidence to review

- exact Windows result: `e25ff8256a1ab151cea3b007228b261bd1c4d8b83fa34234d71371d62b2d0ab0`
- Linux reference result: `b3d72145bfd9310d4d0f2ea171bbcb0e814debe36bbac56ac6e52103e7b89d43`
- Linux timing result: `2473d2f8675077d6e9ede062f128b1a8307035bd23f21f8bf03ce5f75ed0d2e5`
- Linux static result: `deeaa66d60aa8d479bb0530727a597e484f22ccbfed5582c981d7fe9af131c85`
- Linux final assertion: `5b9874354d34fa400a94cf03a87f74c5bb77cb48ce4c5703522c6202e0d462c1`
- raw Linux archive: `5421afd5bf82b6bc6d705937caf0f67b59d71d2044c5e86ea5a866e2e251d6ab`
- compact Linux archive: `66c14705a35fdf68e7efe132054455c2a8730d6a1cf26d52847abf6c543224ab`

## Required review confirmations

Confirm or reject each item explicitly:

1. The Linux host satisfies the reference-platform contract: native Ubuntu,
   `n2-standard-8`, and required plus observed `Intel Cascade Lake`.
2. Source, dependency, kernel, operator-order, numerical-contract, uptake-law,
   review, executable, and extractor identities are attributable and exact.
3. The qualification matrix passes the frozen numerical gates without primary
   clipping and selects L0 with `dt = 1800 s` under the frozen rule.
4. Windows and Linux coupled comparisons, temporal comparisons, saturation
   prediction, production selection, and canonical claim values agree exactly.
5. The measured near-null low/high contrast is reported against the saturation
   prediction without tuning or biological amplification claims.
6. The timing measurement and 151-configuration projections are correctly
   bounded to the C10 uptake-only fixture and are not presented as P15 runtime
   guarantees.
7. The CRLF/Git-LF overlay is a byte-representation repair that preserved the
   Git source tree and did not change a model, parameter, order, or gate.
8. The post-outcome manifest-current-directory recovery was packaging-only and
   did not rerun or alter outcomes.
9. The GCE instance and boot disk were deleted after evidence retrieval.
10. The accumulated evidence is sufficient to close
    `D-C10-02-NUMERICAL-CONVERGENCE` from an engineering standpoint.

## Required artifact fields

The returned JSON should include at least:

```json
{
  "artifact_type": "C10_V2_FINAL_INDEPENDENT_ACCEPTANCE",
  "status": "PASS_OR_FAIL",
  "implementation_commit": "0f38760b4daba3acbfd4b658c9ac522523b5c69b",
  "implementation_tree": "511e3d1ec6ec5148aa0548b6256c85b52a3b68a2",
  "reviewer_identity": "...",
  "reviewer_is_implementation_writer": false,
  "read_only_review": true,
  "windows_result_sha256": "e25ff8256a1ab151cea3b007228b261bd1c4d8b83fa34234d71371d62b2d0ab0",
  "reference_result_sha256": "b3d72145bfd9310d4d0f2ea171bbcb0e814debe36bbac56ac6e52103e7b89d43",
  "reference_timing_sha256": "2473d2f8675077d6e9ede062f128b1a8307035bd23f21f8bf03ce5f75ed0d2e5",
  "confirmations": {
    "reference_host_qualified": true,
    "provenance_exact": true,
    "frozen_gates_pass": true,
    "cross_platform_claim_values_exact": true,
    "contrast_claim_bounded": true,
    "timing_claim_bounded": true,
    "crlf_overlay_packaging_only": true,
    "manifest_recovery_packaging_only": true,
    "cloud_resources_deleted": true,
    "c10_engineering_closure_accepted": true
  },
  "c11_authorized": false,
  "findings": []
}
```

That condition is fulfilled by the byte-identical artifact identified above.
C10 is recorded `PASS` and `D-C10-02` is closed. The artifact explicitly does
not authorize C11, which remains unstarted.
