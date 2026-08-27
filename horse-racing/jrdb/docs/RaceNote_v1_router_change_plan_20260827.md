# RaceNote v1 router switch - completed 2026-08-27

`src/racenote_request.py` のproduction v1.0切替は完了しています。

Applied internal-only changes:

- `ENRICHER` -> `src/racenote_history_enrichment.py`
- enrichment output -> final bundle path directly
- `_enriched_8runs_poc.json` dependency removed from request router
- `final_schema_version = 1.0` added to execution plan
- unused `shutil` dependency removed

Applied router commit:

`d5614ffe8ffcff564fede3a66e6aad752efd78aa`

The user-facing request contract remains unchanged.

## Production E2E

`#109 [RACENOTE_REQUEST] v1-e2e-20260827-kyoto11` completed successfully through the standard Issue -> Actions -> artifact path.

- workflow run: `33026405453`
- task exit: 0
- collect exit: 0
- final bundle schema: `1.0`
- request manifest final schema: `1.0`
- target/future history leakage: 0

The router switch is therefore closed as production-ready. The remaining `_poc.py` reference is internal to the production enrichment implementation and may be removed later as a contract-preserving refactor.
