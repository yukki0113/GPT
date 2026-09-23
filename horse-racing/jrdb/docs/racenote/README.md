# RaceNote current guide

## 1. Current architecture

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

## 4. Legacy boundary

v0.2 control, v1.1-P gated prediction, Edge policy, and related frozen outputs remain historical reproducibility/benchmark assets. Their prediction meaning is not changed by this Phase A cutover. Only RaceNote input compatibility may be updated where required.

## 5. Operating rules

Use latest main, current contracts, and current source as truth. Do not reintroduce Stats Mart into RaceNote request payloads, Store resolution, workflow downloads, or active enrichment. Keep legacy builders and schemas physically retained until a separately authorized phase.

For current research, follow this guide and the Forecast Gen0 contract. For deterministic/legacy reproduction, use the dedicated legacy documents and preserved artifacts.
