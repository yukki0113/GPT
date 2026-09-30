# BTDAY-0004 — 2026-03-14

Status: **FROZEN PRE-RESULT DAILY BACKTEST**

- selection_id: `BTDAY-0004`
- target_date: `2026-03-14`
- venues: 中京 / 中山 / 阪神
- venue_count: 3
- race_count: 36
- logic: `RaceNote-Human-Context-Reader-0.3.2`
- reader-facing policy: `FORECAST_HUMAN_CONTEXT_READER_v0_3_2.md §4.2.2`
- DAY PREP: PASS
- venue Freeze: 12/12 × 3
- DAY MERGE: PASS
- result_opened: `false`

## Analysis-thread entry point

Use these files in order:

1. `day_merge/forecast_20260314_all.json`
2. `day_merge/forecast_20260314_all_audit.json`
3. `day_merge/forecast_20260314_all_handoff.json`

The merged JSON is the canonical pre-result prediction source for all 36 races.

Venue-level files are under:

- `venues/chukyo/`
- `venues/nakayama/`
- `venues/hanshin/`

DAY PREP provenance is under `day_prep/`.

## Freeze / interpretation notes

- DAY MERGE is deterministic packaging only; marks and reader-facing reasons were not recomputed.
- Target-day results were not opened in Forecast.
- §4.2.2 changes explanation only. When RRDB reinterpretation materially affected comparison, the reader-facing comment explains the underlying race content in natural language rather than exposing internal UPGRADE / DOWNGRADE / S / A labels.
- 8R 阪神スプリングジャンプ retains the recurring information gap that obstacle-specific evidence is limited.
- P3 sibling evidence remains unavailable and was not inferred.

Post-race result join, scoring, and research belong to the separate analysis/research flow.
