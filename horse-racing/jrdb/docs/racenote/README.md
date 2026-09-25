# RaceNote current guide

## 1. Current architecture

Current production path:

    2010-2025 accepted Historical Warehouse / 2026 PACI
      -> RaceNote base bundle
      -> Analysis Parquet canonical
      -> DuckDB direct enrichment
      -> RaceNote v1.0 bundle
      -> Forecast Gen0 / Freeze / Guard / downstream delivery

Stats Mart is legacy-only. Analysis SQLite is explicit audit/rollback compatibility only.
Archive is an optional immutable delivery cache and is never the historical source of truth.


RaceNote is a facts/evidence/provenance layer for GPT comparison and prediction.

    PACI / Historical Warehouse
      -> RaceNote base bundle
      -> JRDB Analysis canonical enrichment
      -> Reader View / GPT Forecast
      -> Freeze / Guard / downstream delivery

The active architecture is JRDB + Historical Warehouse + Analysis canonical. Stats Mart is a frozen legacy cache and is not an active dependency.

## 2. Current prediction direction

Forecast Gen0 research remains current, but the 2026-09-25 redesign changes the
preferred reading order for the next forecast generation:

```text
DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY
```

RaceNote now treats historical ability as an anchor rather than the default
first ordering signal. GPT should read condition/race trends first, then
RaceReview historical running content, then simple ability context, and only
after that perform relative horse-to-horse comparison.

Implemented research assets:

- `src/racenote_general_evidence.py`
- `schema/racenote_general_evidence_schema_v0_1.json`
- `docs/racenote/GENERAL_EVIDENCE_PRIORITY_v0_1.md`

Current pre-Freeze trend evidence includes horse condition history, frame,
sire, jockey, and as-of-safe race-level running-style statistics. Popularity
remains post-Freeze because current popularity is market information.

Do not introduce fixed weights or a single score as an implicit current
default. Keep prediction policy, presentation policy, and result evaluation
separate.

The trend-first redesign is now finalized as **RaceNote-Forecast-Gen0.3**.
Gen0.2 was never activated and is retained only as a pre-redesign reference.
The planned first activation remains `Gen0-G001`, now using Gen0.3.

## 3. Current data boundaries

- 2010–2025 historical RaceNote input: accepted JRDB Historical Warehouse
- 2026 current/future input: PACI daily route
- Analysis canonical: the only active enrichment source
- Raw: rollback/audit and explicit 2010 previous-result boundary fallback
- Archive: optional immutable delivery cache; Warehouse remains the canonical rebuild source
- Stats Mart: legacy-only, retained for old research and reproducibility

All history statistics are computed as-of-exclusive from Analysis canonical. Existing RaceNote v1.0 schema and Forecast/Freeze/Guard semantics remain unchanged.

## 4. RaceReviewDB historical review evidence

RaceReviewDB may be consumed through the additive sidecar adapter
`src/racenote_racereview_adapter.py`. The adapter joins by JRDB blood
registration number (`horse.basic.horse_id`), queries history with
`race_date < target_date`, and emits only the stable v0.1 Review fields
needed for historical evidence.

The adapter is implemented but is not an automatic Forecast-generation
activation. It does not mutate the authoritative RaceNote v1.0 bundle, does
not open current market/JRDB-consensus information, and does not consume
unfinished RaceReviewDB semantic labels or uncalibrated causal track-bias
signals. See `docs/racenote/RACEREVIEW_ADAPTER_v0_1.md`.

The first downstream Horse Evidence Card slice is also implemented:

- `src/racenote_horse_evidence_card.py`
- `schema/racenote_horse_evidence_card_schema_v0_1.json`
- `docs/racenote/HORSE_EVIDENCE_CARD_v0_1.md`

It converts historical Review evidence into primary/supporting positives,
concerns, mixed context, repeatability, hidden-strength candidates,
fragile-form candidates, contradiction, uncertainty, and comment evidence.
It does not score horses and remains non-active for Forecast generation.

The next aggregation layer is also implemented as a research input:

- `src/racenote_general_evidence.py`
- `schema/racenote_general_evidence_schema_v0_1.json`
- `docs/racenote/GENERAL_EVIDENCE_PRIORITY_v0_1.md`

This layer joins Independent RaceNote evidence with the RaceReview Horse
Evidence Card and enforces the ordinal reading policy
`DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR`. It does not create rankings,
marks, or probabilities.

The downstream Pairwise Comparison research contract is also implemented:

- `src/racenote_pairwise_comparison.py`
- `schema/racenote_pairwise_comparison_schema_v0_1.json`
- `docs/racenote/PAIRWISE_COMPARISON_v0_1.md`

Pairwise does not mechanically select a horse. It validates GPT-authored
relative comparisons, requires direct evidence at every final-order boundary,
requires reversal conditions, and requires an explicit reason whenever lower
priority evidence overrides contrary trend/RaceReview evidence.

Scenario Robustness v0.1 is also implemented:

- `src/racenote_scenario_robustness.py`
- `schema/racenote_scenario_robustness_schema_v0_1.json`
- `docs/racenote/SCENARIO_ROBUSTNESS_v0_1.md`

It tests SLOW / MEDIUM / FAST pace scenarios, derives whether the Pairwise
axis is ROBUST / CONDITIONAL / FRAGILE, and records horse-by-horse rank
sensitivity without automatically replacing the Pairwise order.

The next-generation Forecast contract is now implemented:

- `src/racenote_forecast_gen0_3.py`
- `src/racenote_edge_performance_adapter.py`
- `schema/racenote_forecast_gen0_schema_v0_3.json`
- `config/racenote_forecast_gen0_ledger_v0_3.json`
- `docs/racenote/FORECAST_GEN0_3_PREDICTION_CONTRACT_v0_3.md`

Gen0.3 consumes General Evidence -> Pairwise -> Scenario -> Base Forecast,
then allows only EdgeDB Performance evidence to adjust the final forecast.
JRDB consensus, current market, Edge Value, RL/Value and Bet Plan remain
post-Freeze layers.

## 5. Legacy boundary

The complete retained-asset inventory and import boundary is docs/racenote/legacy/README.md.
v0.2 control, v1.1-P gated prediction, Edge policy, and related frozen outputs remain
historical reproducibility/benchmark assets. They are not current Forecast Gen0 logic,
and their output is not an automatic fallback or current prediction input.

## 6. Operating rules

Use latest main, current contracts, and current source as truth. Do not reintroduce Stats Mart into RaceNote request payloads, Store resolution, workflow downloads, or active enrichment. Keep legacy builders and schemas physically retained until a separately authorized phase.

For current research, follow this guide and the Forecast Gen0 contract. For deterministic/legacy reproduction, use the dedicated legacy documents and preserved artifacts.
