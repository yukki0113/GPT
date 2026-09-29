# RaceNote Forecast Axis Calibration Protocol v0.1

Status: **CURRENT**
Date: 2026-09-29

## Why this exists

The project has many clean 2026 PACI days, but clean days are a finite research
resource. They should not be spent while the forecast itself still collapses
into a generic numeric-ranking behavior.

BTDAY-0001 and BTDAY-0002 consumed four clean days:
- 2026-02-08
- 2026-05-23
- 2026-03-08
- 2026-04-26

No additional unused day should be selected during calibration hold.

## Calibration objective

Before measuring accuracy, establish a forecast style where:

1. the race is interpreted before horses are ranked;
2. human forecast evidence is directly referenced;
3. no single aggregate numeric field acts as a hidden score;
4. ◎ / ○ / ▲ emerge from contextual candidate comparison;
5. the user can read the trace and understand why those marks exist.

## Materials

Primary teacher:
`racenote/evidence/human_forecast_evidence_202301.md`

Current calibration logic:
`docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_3.md`

Replay source:
already-used / ineligible dates only.

## Calibration batch size

Use 6–12 representative races per calibration iteration.

Prefer diversity:
- maiden / 1-win
- allowance / open
- sprint / route
- turf / dirt
- new horse if available
- obstacle only if RaceNote evidence is sufficient

Do not run another 48–72 race batch merely to inspect forecast style.

## Acceptance before clean blind resumes

Research thread must explicitly judge that:

- race_model is truly race-specific;
- marks are not explainable as simple numeric sorting;
- candidate comparisons read like contextual handicapping;
- human teacher principles are visible but not copied mechanically;
- output remains reproducible enough for audit.

Only then change phase from `CALIBRATION_HOLD` to `BLIND_RESEARCH_ACTIVE`.
