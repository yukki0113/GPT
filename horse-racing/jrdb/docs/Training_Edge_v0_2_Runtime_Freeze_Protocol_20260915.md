# Training Edge v0.2 — Runtime Freeze Protocol

Date: 2026-09-15

## Purpose

Training Edge v0.2 scientific logic is already frozen and its 2026 OOT has already been opened and consumed. This protocol does **not** create a new model and does not use 2026 outcomes. It records an operational reproducibility fingerprint for the existing frozen 2013-2025 fit so daily forward scoring cannot silently drift when historical archives or numerical software change.

## Source boundary

The runtime fingerprint must be generated from:

- JRDB history 2010-2025 only;
- 2010-2012 as chronology warmup;
- frozen eligible fit rows 2013-2025;
- no 2026 row of any kind.

Expected frozen eligible fit count: `256701`.

## Scientific assets

The run must verify these frozen assets before reconstruction:

- Freeze commit: `1ae1b424597d391fdca57c8fe826d99df123221b`
- `training_edge_v0_2_core.py`: blob `fd54df516520a38bbeba895f08a510ebeffa16f8`
- `evaluate_training_edge_v0_2_oot.py`: blob `ee19330559720b148636a451ef6ea8182e766157`
- `project_training_edge_v0_2_input.py`: blob `a8e38fffc3e426fcd85042fcd7d55765cb0b3e65`
- `training_edge_v0_2_calibration.json`: blob `8c0dfb83824c3ddf5aabe4488b50746435acbe62`

## Runtime versions

The one-shot 2026 OOT succeeded with:

- Python `3.12.14`
- NumPy `2.5.3`
- pandas `3.0.5`
- SciPy `1.18.1`
- scikit-learn `1.9.1`

The runtime freeze run uses these versions exactly.

## Fingerprints

The run records:

1. deterministic semantic SHA-256 of ordered fit keys, frozen eligibility-history fields, complete CAB model inputs, and `performance_delta`;
2. C-model predictions over the ordered fit population, normalized to 12 decimal places and SHA-256 hashed;
3. CAB-model predictions over the same ordered fit population, normalized identically and SHA-256 hashed;
4. package versions, fit count and date boundary.

Prediction normalization at 12 decimal places is an operational tolerance for irrelevant sub-floating-point platform differences. It is not model rounding and does not affect scored values.

## One-shot rule

This fingerprint is generated once from the preregistered 2010-2025 boundary. After successful generation, its values are committed as `config/training_edge_v0_2_runtime_freeze.json` and daily forward scoring must fail closed when they do not match.

A mismatch is an infrastructure/data reproducibility event. It must not be resolved by changing the expected fingerprint merely to make a run pass. Any legitimate migration requires an explicit audit explaining why the operational representation changed while preserving the frozen scientific model.

## Execution

Workflow:

`.github/workflows/jrdb_training_edge_v02_runtime_freeze_issue.yml`

Issue prefix:

`[JRDB_TRAINING_V02_RUNTIME_FREEZE]`
