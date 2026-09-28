# RaceNote Reset — Phase 1 Status

Date: 2026-09-28
Status: COMPLETE

## Phase 1 objective

Define the new RaceNote as an evidence note for GPT forecasting, without implementing forecast logic.

## Completed

### 1. Canonical design
`DESIGN_V1.md`

Defines:
- evidence-note responsibility,
- fact / descriptive evidence / forecast-judgment boundary,
- one-race-one-note structure,
- race/race-day/trend/field/runner/coverage/provenance families,
- market/result separation,
- newcomer/steeplechase missing-evidence handling,
- explicit non-goals.

### 2. Canonical schema
`schema/racenote_v1.schema.json`

Schema version:
`RaceNote-Evidence-1.0`

Top-level contract:
- metadata
- race
- race_day
- trend_context
- field_context
- runners
- coverage
- provenance

### 3. Evidence-boundary validator
`src/validate_racenote_v1.py`

Checks:
- evidence-note kind,
- result hidden,
- market hidden/supplement-only,
- runner coverage,
- unique horse numbers,
- required runner evidence families,
- named/local/base Trend blocks,
- provenance,
- forecast/ranking/mark leakage.

### 4. Legacy reuse matrix
`PHASE1_REUSE_MATRIX.md`

Classifies old assets into:
- reusable data infrastructure,
- refactor-before-reuse,
- legacy-only prediction logic.

## Trend decisions fixed in Phase 1

### Named OP / graded races
Primary:
- same named race under comparable conditions.

If insufficient:
- comparable OP+ races preserving venue/course/distance/meeting context as support.

This fallback is intended for cases such as:
- new graded races,
- interrupted histories,
- alternative-venue periods,
- major course renovation.

### Ordinary / class races
Primary/fallback should preserve class.

For example, a 2勝クラス special race should expand first into comparable 2勝クラス races, not OP+.

Local and Base Trend coexist.
Base Trend never overwrites Local Trend.

Small samples remain visible rather than being automatically discarded.

## Runner-evidence decisions fixed in Phase 1

Recent runs must preserve:
- class/grade,
- race identity,
- surface/distance,
- finish,
- race context,
- Ability/IDM context,
- RaceReview references.

Ability summaries may exist, but run-level class/grade context must survive.

RaceReview may contain deterministic descriptive tags, but no final horse rating.

Missingness is explicit and must not become neutral scoring.

## Explicitly not decided yet

Phase 1 does not define:
- exact Trend extraction SQL,
- minimum sample thresholds,
- similarity/backoff distance formulas,
- specialized newcomer evidence,
- specialized steeplechase evidence,
- Forecast prompt,
- ◎○▲△,
- betting policy,
- newspaper integration.

These belong to later phases.

## Next phase

Phase 2 should implement the Evidence Note builder:
1. construct one real RaceNote v1 from existing reusable assets;
2. preserve source/as-of provenance;
3. render a GPT-readable view;
4. validate that the Note contains enough information to forecast one race;
5. still produce no forecast.
