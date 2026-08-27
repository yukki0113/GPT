# RaceNote v1 router switch plan - 2026-08-27

Production promotion requires `src/racenote_request.py` to stop invoking the PoC CLI directly.

Required internal-only changes:

- `ENRICHER` -> `src/racenote_history_enrichment.py`
- enrichment output -> final bundle path directly
- remove `_enriched_8runs_poc.json` dependency
- add `final_schema_version = 1.0` to execution plan

The user-facing request contract remains unchanged.
