# Training Edge v0.2 runtime config

- `training_edge_v0_2_runtime_versions.json`: exact numerical runtime observed in successful OOT run `34925686309`.
- `training_edge_v0_2_runtime_freeze.pending.json`: temporary marker until the one-shot 2010-2025 runtime fingerprint completes.
- final target: `training_edge_v0_2_runtime_freeze.json`.

The final fingerprint is an operational reproducibility guard. It does not change Training Edge v0.2 scientific semantics or reopen the consumed 2026 OOT.


## Retirement status — 2026-10-02

This configuration is retained for historical reproduction and audit only. Training Edge v0.2 is not a production scorer; runtime freeze work and HOLDOUT/OOT are closed. Do not build, score, recalibrate, or extend it during normal operation.

- runtime fingerprint and versions: frozen reproduction evidence
- calibration: frozen input
- runtime_freeze.pending.json: stale pre-freeze evidence, not a pending task

No file here requests a runtime freeze or Training Research generation. See docs/RL_Retirement_Contract_20261002.md and docs/RL_Retired_Asset_Inventory_20261002.md.
