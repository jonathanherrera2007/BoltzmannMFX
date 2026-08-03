# C10/P12 V2 execution commands

All commands ran from the clean product checkout at
`0f38760b4daba3acbfd4b658c9ac522523b5c69b`. Raw run directories were outside
the repository so the runner's clean-tree gate remained meaningful.

## Review identity preflight

```powershell
Get-FileHash -Algorithm SHA256 `
  C:\Users\Shadow\Downloads\INDEPENDENT_NUMERICAL_REVIEW_V2.json
git status --porcelain
git rev-parse HEAD
```

Observed review SHA-256:
`bda12aef209793b4537915e374e09caf100397c0fdf8678ed00118ff987a3ea2`.

## Full-volume extractor build

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools\repro\build_c10_plot_extract.ps1 `
  -SourceDir C:\b\BMX-shadow-handoff-20260721\BMX-RG-SW-C07-product `
  -BuildDir C:\b\BMX-shadow-handoff-20260721\build-c10-v2-prereview-0f38760 `
  -OutputDir C:\b\BMX-shadow-handoff-20260721\c10-v2-tools-0f38760
```

Extractor executable SHA-256:
`968ab9c05073cec8cd1bbb339a63379acea153ea54640c43403f6ae93c3815ff`.

## Qualifying V2 run

```powershell
& C:\Users\Shadow\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe `
  tools\repro\run_c10_p12_v2_48h.py `
  --exe C:\b\BMX-shadow-handoff-20260721\build-c10-v2-prereview-0f38760\bmx.exe `
  --source . `
  --extractor C:\b\BMX-shadow-handoff-20260721\c10-v2-tools-0f38760\c10_plot_extract.exe `
  --mpiexec "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe" `
  --independent-review C:\Users\Shadow\Downloads\INDEPENDENT_NUMERICAL_REVIEW_V2.json `
  --run-root C:\b\BMX-shadow-handoff-20260721\c10-v2-outcomes-0f38760-20260802-r2 `
  --json-out C:\b\BMX-shadow-handoff-20260721\c10-v2-results-0f38760-20260802-r2\P12_V2_GRID_TIME.json
```

Canonical runner output:

```json
{
  "status": "PASS",
  "selected_grid": "L0",
  "selected_dt_s": 1800.0,
  "json_out": "C:\\b\\BMX-shadow-handoff-20260721\\c10-v2-results-0f38760-20260802-r2\\P12_V2_GRID_TIME.json"
}
```

## Non-claim invocation correction

The first invocation used the same command except that `--extractor` pointed to
AMReX's stock `fextract.exe` and the run root lacked the `-r2` suffix. That tool
emits a 1-D `.slice` file and ignores the C10 helper's positional-output
interface. The runner aborted with `FileNotFoundError` after one L0-low canonical
trajectory and emitted no result JSON. No output from that root was reused.

## Post-run validation

The runner's CRLF result was imported as the repository-policy LF JSON review
copy. A deterministic stored ZIP was also created from the external result;
its `P12_V2_GRID_TIME.json` member is byte-identical to the runner output.

```powershell
& C:\Users\Shadow\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -c `
  "from pathlib import Path; import zipfile; b=Path(r'C:\b\BMX-shadow-handoff-20260721\c10-v2-results-0f38760-20260802-r2\P12_V2_GRID_TIME.json').read_bytes(); z=zipfile.ZipFile(r'evidence\stages\C10V2\P12_V2_GRID_TIME.raw.zip','w'); i=zipfile.ZipInfo('P12_V2_GRID_TIME.json',(1980,1,1,0,0,0)); i.compress_type=zipfile.ZIP_STORED; i.external_attr=0o100644<<16; z.writestr(i,b); z.close()"
```

Observed identities:

- exact generated member: 158,169 bytes,
  `e25ff8256a1ab151cea3b007228b261bd1c4d8b83fa34234d71371d62b2d0ab0`;
- committed LF JSON: 154,079 bytes,
  `d7ed0cce4af86517d1206427ff4bdc47eb931fbec6d4a87bcf30e33e48ea3742`;
- stored ZIP: 158,309 bytes,
  `d85e08240788f023e5f59ec16b31ebc11a0e790ff061af2cdbc26f1239ca23e9`.

```powershell
C:\Users\Shadow\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m json.tool evidence\stages\C10V2\P12_V2_GRID_TIME.json
C:\Users\Shadow\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m json.tool evidence\stages\C10V2\INDEPENDENT_NUMERICAL_REVIEW_V2.json
C:\Users\Shadow\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools\repro\run_c10_static_test.py --source . --json-out <external-path>
git diff --check
```

Static/ownership result: `PASS`. This file records the Windows secondary-host
execution, which used no external resources and spent USD 0. The later
authorized Linux reference execution is recorded under `reference/`.
