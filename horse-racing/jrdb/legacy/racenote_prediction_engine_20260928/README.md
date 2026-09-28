# RaceNote Legacy Prediction Engine Freeze — 2026-09-28

## Status

The former RaceNote prediction-engine line is frozen as of 2026-09-28.

Authoritative snapshot branch:

`archive/racenote-prediction-engine-20260928`

Snapshot commit:

`5ba73cecd70f0d90e2d44600359cb5b3b28dac43`

This branch is the lossless rollback/reference point for all RaceNote assets that existed before the project redefinition.

## Why it was frozen

The original RaceNote concept was to prepare a compact, readable evidence asset so GPT could forecast a race without re-scraping or re-investigating source data.

During newspaper/batch development, RaceNote gradually acquired deterministic forecast responsibilities:
- baseline ranking,
- evidence-priority rules,
- pairwise ordering,
- semantic authoring,
- mark assignment,
- betting-layer logic.

Research showed that these layers made race-by-race flexibility difficult to preserve. The project is therefore being reset around the original separation:

- **RaceNote** prepares evidence.
- **GPT Forecast** reasons about one race at a time.
- **Batch/Presentation** only orchestrates and aggregates those forecasts.

The old prediction engine remains valuable research evidence but is no longer the design target for the new RaceNote line.

## Frozen prediction-engine family

The following families are Legacy prediction/research assets. They may be read and reused as evidence, but should not be extended as the default new RaceNote forecast architecture.

### Forecast / ranking / comparison
- `racenote_forecast_gen0*.py`
- `racenote_all_runner_synthesis.py`
- `racenote_pairwise_comparison.py`
- `racenote_semantic_pairwise_research_v0_*.py`
- `racenote_semantic_author_research_v0_*.py`
- `racenote_gen0_3_day_rehearsal_author.py`
- `racenote_best_bet_research_v0_1.py`

### Mark / betting / presentation logic tied to forecast ranks
- `racenote_mark_policy_research_v0_1.py`
- `racenote_edge_prediction_policy.py`
- `run_racenote_edge_prediction_freeze.py`
- `run_racenote_v11p_*.py`
- `settle_racenote_backtest.py`
- `racenote_prediction_presentation*.py`

### Prediction-engine workflows
Examples include:
- `racenote_gen0_3_blind_marks_pipeline_v0_1.yml`
- `racenote_gen0_3_day_author.yml`
- `racenote_gen0_3_realdata_author.yml`
- `racenote_mark_policy_research_v0_1.yml`
- `racenote_semantic_author_research_v0_*.yml`
- `racenote_semantic_pairwise_research_v0_2.yml`
- `racenote_edge_prediction_freeze_issue.yml`
- `racenote_v11p_*.yml`

These workflows are retained for reproducibility/history. New RaceNote development must not depend on their ranking/mark semantics unless explicitly copied into a new evidence-only role.

## Legacy research documentation

Existing backtests, Blind Marks reviews, v0.x/v1.x prediction-design documents, semantic reviews, mark-policy audits and Best Bet v0.1 materials remain valid records of what was tried.

They are not specifications for the new RaceNote.

In particular:
- `racenote_blind_marks_v0_1_backtest_*.md`
- `racenote_gen0_3_*review*.md`
- `racenote_semantic_*.md`
- `racenote_best_bet_*.md`
- `RaceNote_v0_*.md`
- `RaceNote_v1_*.md`
- prediction/betting-layer audit documents

should be treated as Legacy research evidence.

## Shared/reusable asset candidates

These are **not automatically Legacy forecast logic**. They are candidates for reuse because they collect, normalize, verify, or present source evidence rather than deciding the forecast.

Examples:
- JRDB parsing and master-code infrastructure
- historical warehouse/readers/adapters
- `racenote_history_engine.py`
- `racenote_history_enrichment.py`
- `racenote_jrdb.py`
- `racenote_jrdb_pipeline.py`
- `racenote_racereview_adapter.py`
- `racenote_racereview_current.py`
- `racenote_jra_track_facts.py`
- `racenote_race_day_facts.py`
- archive/raw/warehouse adapters and audits
- provenance/hash/as-of validation
- result-hidden firewall concepts

Reuse is **case by case**. A module containing embedded ranking semantics must be stripped or adapted before inclusion in the new RaceNote.

## Important borderline assets

The following are useful but contain assumptions from the old forecast architecture and therefore must not be copied blindly:

- `racenote_general_evidence.py`
  - useful evidence extraction,
  - but currently embeds `DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR` interpretation.

- `racenote_horse_evidence_card.py`
  - potentially useful presentation structure,
  - must be checked for ranking/interpretation leakage.

- `racenote_gen0_2_input_firewall.py`
  - separation of independent/consensus/market views is conceptually reusable,
  - new schema compatibility must be designed independently.

- `racenote_scenario_robustness.py`
  - evidence may be reusable,
  - deterministic forecast consequences are not assumed reusable.

## Human forecast evidence

The manually authored 2023 forecasts are **not Legacy logic**. They are primary design evidence for how the user naturally reasons about races.

A copy is kept in the new namespace:

`horse-racing/jrdb/racenote/evidence/human_forecast_evidence_202301.md`

## Phase 0 rule

Until Phase 1 explicitly promotes an asset:

> Nothing from the old prediction engine is considered part of the new RaceNote specification merely because it already exists.

This prevents the new design from inheriting old ranking assumptions by accident.
