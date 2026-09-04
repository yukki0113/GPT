# Eval OCR regression tests

`test_eval_ocr_regressions.py` protects the production failures found on 2026-09-05.

Covered contracts:

- stacked OCR `94/91/93/99` must be independently re-read instead of being accepted only because it is a valid two-digit value;
- a stable, correct 90s value remains valid when independent re-reads confirm it;
- rank colors use the master_eval image legend (`red -> blue -> orange -> green -> yellow`) rather than an order inferred from OCR values;
- lower/uncolored cells cannot outrank higher ranked colors;
- equal-value ties and partly colored boundary ties remain legal.

The production image itself is not committed. Real-image regression is executed from the operational image and recorded in the audit/report, while unit tests keep the reusable logic under source control.
