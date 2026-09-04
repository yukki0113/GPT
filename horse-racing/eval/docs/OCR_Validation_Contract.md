# Eval OCR validation contract

## Purpose

Eval OCR must be safe even when numeric recognition is wrong. A PACI join verifies identity/key consistency only; it does not prove the Eval value itself was read correctly.

## Fixed rank-color order

The source of truth is the legend printed in the master_eval image:

1. red
2. blue
3. orange
4. green
5. yellow

This order must never be inferred from OCR numeric values.

Validation compares OCR values directly against this image-side order. Equal Eval values are allowed to share a rank/color. A boundary tie may be partly colored and partly uncolored; equality at the boundary is legal.

## 2/9 ambiguity recheck

A two-digit OCR result beginning with `9` is not rewritten mechanically. It is re-read with independent per-cell methods because 2026-09-05 exposed repeated stacked-OCR failures `24->94`, `21->91`, `23->93`, and `29->99`.

A different value is adopted only when repeated re-read evidence is stronger than the initial stacked result. If re-reads do not establish a stable answer, the cell is marked `requires_review` and overall OCR validation fails.

## Audit provenance

OCR validation/debug JSON retains, per Eval cell:

- `venue`
- `race_no`
- `horse_no`
- `initial_ocr_value`
- `final_ocr_value`
- `color`
- `recheck_triggered`
- `recheck_reason`
- `candidate_values`
- `resolution_method`
- `requires_review`

The normal CSV contract remains unchanged:

`date,venue,race_no,horse_no,eval`

## Release gate

For the Chat direct-image path, PACI enrichment must not be treated as formal completion unless the OCR validation report is `ok` first. Operationally the gate is:

`ocr_validation_status == ok AND paci_join_validation_status == success`

An OCR validation error must stop the formal completion path even if a PACI join could otherwise succeed.
