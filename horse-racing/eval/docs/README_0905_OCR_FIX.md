# 0905 OCR fix summary

The 2026-09-05 production image exposed repeated stacked OCR confusion between leading `2` and `9`, together with a validation design that inferred rank-color order from the OCR values being checked.

The source fixes make rank-color order image-side and fixed, add independent re-read for `9x`, preserve per-cell OCR provenance, and require manual review when re-read evidence is inconclusive. See `OCR_Validation_Contract.md` and `tests/test_eval_ocr_regressions.py`.
