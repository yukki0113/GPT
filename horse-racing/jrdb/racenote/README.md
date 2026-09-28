# RaceNote — Reset Namespace

Status: **Phase 0 / reset boundary**

This directory is reserved for the redesigned RaceNote project.

## New definition

RaceNote is an **evidence note for GPT forecasting**, not a deterministic forecast engine.

Its job is to collect, normalize, contextualize and present the information needed for a GPT model to forecast one race without having to re-scrape JRDB or reconstruct the evidence from scratch.

RaceNote itself should not decide:
- ◎○▲△,
- a fixed horse ranking,
- a universal evidence hierarchy,
- or a deterministic betting conclusion.

Those belong to a separate Forecast layer.

## Architecture target

```text
source data
    ↓
RaceNote
  evidence preparation / context / provenance
    ↓
GPT Forecast
  one race = one independent reasoning task
    ↓
Batch / Newspaper
  orchestration and aggregation only
```

## Current phase

Phase 0 only establishes the boundary.

No new RaceNote schema is authoritative yet.
No old prediction-engine schema is implicitly carried forward.

Legacy snapshot:
`archive/racenote-prediction-engine-20260928`

Legacy boundary document:
`horse-racing/jrdb/legacy/racenote_prediction_engine_20260928/README.md`

Human forecast evidence:
`evidence/human_forecast_evidence_202301.md`
