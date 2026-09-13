# Eval tests

This directory protects the durable contracts used by the Eval project. Daily images and other operational raw data are not committed; reusable behavior is protected with focused fixtures and contract tests.

## OCR regression

`test_eval_ocr_regressions.py` protects the production failures found on 2026-09-05.

Covered contracts include:

- stacked OCR `94/91/93/99` must be independently re-read instead of being accepted only because it is a valid two-digit value;
- a stable, correct 90s value remains valid when independent re-reads confirm it;
- rank colors use the master_eval image legend (`red -> blue -> orange -> green -> yellow`) rather than an order inferred from OCR values;
- lower/uncolored cells cannot outrank higher ranked colors;
- equal-value ties and partly colored boundary ties remain legal;
- unresolved re-read ambiguity remains fail-closed through manual-review state.

The production image itself is not committed. Exact real-image regression uses the operational image when available; repository tests protect the reusable logic.

## Phase2 JRDB pre-race features

- `test_build_phase2_jrdb_kyi_features.py` — leakage-safe BAC/KYI projection and KYI feature contract.
- `test_build_phase2_jrdb_training_features.py` — KYI runner identity with CHA/CYB LEFT JOIN and training/finish feature contract.
- `test_build_phase2_jrdb_previous_features.py` — KYI previous-result-key to PACI ZED exact-link; no approximate fallback.
- `test_build_phase2_jrdb_feature_bundle.py` — component key-set, identity, provenance and one-to-one merge contract.

The Eval modules do not own JRDB fixed-width offsets; common JRDB parser/adapters remain the source of truth.

## Post-race backfill

- `test_backfill_phase2_sed.py` — SED result-layer backfill helpers and canonical-key safety.

Current-race result data belongs to the post-race layer and must not be silently reused as a pre-race Phase2 feature.
