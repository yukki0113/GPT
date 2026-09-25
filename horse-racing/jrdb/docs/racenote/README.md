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

Forecast Gen0 is current. GPT compares each race and horse using conditions, ability, suitability, pace, training/state, recent runs, longer history, auxiliary statistics, coverage, conflicting evidence, and uncertainty. RaceNote supplies facts and provenance; prediction logic remains outside the converter, router, and Reader View.

Do not introduce fixed weights or a single score as an implicit current default. Keep prediction policy, presentation policy, and result evaluation separate.

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

## 5. Legacy boundary

The complete retained-asset inventory and import boundary is docs/racenote/legacy/README.md.
v0.2 control, v1.1-P gated prediction, Edge policy, and related frozen outputs remain
historical reproducibility/benchmark assets. They are not current Forecast Gen0 logic,
and their output is not an automatic fallback or current prediction input.

## 6. Operating rules

Use latest main, current contracts, and current source as truth. Do not reintroduce Stats Mart into RaceNote request payloads, Store resolution, workflow downloads, or active enrichment. Keep legacy builders and schemas physically retained until a separately authorized phase.

For current research, follow this guide and the Forecast Gen0 contract. For deterministic/legacy reproduction, use the dedicated legacy documents and preserved artifacts.
