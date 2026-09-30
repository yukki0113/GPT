# BTDAY-0003 — 2026-08-29

Status: FROZEN PRE-RESULT DAILY BACKTEST

- selection_id: `BTDAY-0003`
- target_date: `2026-08-29`
- venues: 札幌 / 新潟 / 中京
- venue_count: 3
- race_count: 36
- logic: `RaceNote-Human-Context-Reader-0.3.2`
- DAY PREP: PASS
- venue Freeze: 12/12 × 3
- DAY MERGE: PASS
- result_opened: `false`

## Analysis-thread entry point

Start with:

1. `day_merge/forecast_20260829_all.json`
2. `day_merge/forecast_20260829_all_audit.json`
3. `day_merge/forecast_20260829_all_handoff.json`

The merged JSON contains all 36 immutable forecast records. Venue files are preserved under `venues/` for race-by-race traceability. DAY PREP provenance and validation are under `day_prep/`.

ZIP files produced in chat are transport wrappers around these expanded artifacts and are intentionally not committed to Git; the expanded JSON/JSONL/HTML/audit/handoff files are the Git canonical archive.

Do not inspect target-day results from the Forecast execution thread. Analysis/research may open results only after using these Frozen pre-result artifacts as the prediction source of truth.
