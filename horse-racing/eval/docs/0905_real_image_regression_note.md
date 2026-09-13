# 2026-09-05 real-image regression audit

The 2026-09-05 production image exposed the OCR safety failure that led to the fixed image-side color order, independent `9x` re-read, color-conflict re-read, per-cell provenance, and fail-closed manual-review gate.

The production image itself is intentionally not committed.

## Evidence levels

- Reusable source behavior is protected by `tests/test_eval_ocr_regressions.py` and `docs/OCR_Validation_Contract.md`.
- The operational 2026-09-05 image was re-inspected and the known/derived suspect cells were corrected in the operational output after the incident.
- This repository note does **not** claim that the latest-main OCR pipeline has been re-run end-to-end against the uncommitted 2026-09-05 production image after every subsequent source change.

If an exact real-image regression against 2026-09-05 is required, obtain the operational source image, run current `src/extract_eval_table.py`, require `validation.status == ok`, and compare the resulting five-column CSV/audit against the incident-known cells. Do not treat PACI join success as evidence that the Eval numeric OCR is correct.
