# C10/P12 reference-host and final-acceptance handoff — fulfilled

Reference-host reproduction, timing and final independent acceptance are all
complete and `PASS`.

- implementation: `0f38760b4daba3acbfd4b658c9ac522523b5c69b`;
- reference result: `b3d72145bfd9310d4d0f2ea171bbcb0e814debe36bbac56ac6e52103e7b89d43`;
- timing result: `2473d2f8675077d6e9ede062f128b1a8307035bd23f21f8bf03ce5f75ed0d2e5`;
- acceptance: `de1fb8ba26696a84ff0f0233e9fe269e091a384eb5034e86fc74250cbb72de58`.

The pinned GCE `n2-standard-8` / Intel Cascade Lake result selects L0
(`8 x 8 x 4`) with `dt = 1800 s` and exactly matches the Windows claim values.
The VM and disk are deleted.

`D-C10-02-NUMERICAL-CONVERGENCE` is closed and C10 may be recorded PASS. This
handoff grants no cloud action and no C11 or later-stage authorization.
