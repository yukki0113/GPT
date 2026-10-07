# RaceNote v0.5.1 / v0.5.2 Clean-Blind A/B Runbook v0.1

Status: **RESEARCH HARNESS — PROSPECTIVE TWO-LANE TEST**  
Date: 2026-10-07

## Purpose

The next prospective RaceNote experiment uses only two independently authored lanes:

- `v051`: protected-mainline six-to-five compression;
- `v052`: protected candidate set plus aggressive role assignment.

v0.4.6 remains available for retrospective baseline comparison but is not prospectively authored in this profile.

Both lanes share one reserved BTDAY, one market-blind forecast_prep, one clean Reader source, one race/horse roster, one RRDB v0.3 contract and one sealed session.

The v051 and v052 model-facing Reader bytes must be identical and both are projection-equivalent to v0.5.0 normal_view.

## 1. Seal the v051/v052 pair

```bash
python horse-racing/jrdb/src/racenote_ab_session.py \
  --prep-root horse-racing/jrdb/backtests/BTDAY-XXXX/<YYYYMMDD>/forecast_prep \
  --request horse-racing/jrdb/backtests/requests/BTDAY-XXXX.json \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/<YYYYMMDD>/ab \
  --base-main-sha <forecast_prep/day_prep_handoff.json:main_sha> \
  --policy horse-racing/jrdb/docs/racenote/research-work/results/stage_c/reader_feature_policy_v0_5_candidate.json \
  --pair-v051-v052
```

The sealed session must enable exactly `v051` and `v052` as authoring lanes.

Internal v046/v050 Reader manifests may remain present for deterministic source/projection verification; they are not enabled authoring lanes.

## 2. Independent authoring

Run v051 and v052 in separate threads/tasks.

Neither lane may inspect:

- sibling marks;
- sibling Decision Cores;
- sibling reader-facing prose;
- sibling authored/frozen files;
- target results;
- target final odds/popularity;
- payouts.

### v051

Follow `FORECAST_HUMAN_CONTEXT_READER_v0_5_1_CANDIDATE.md`.

### v052

Follow `FORECAST_HUMAN_CONTEXT_READER_v0_5_2_CANDIDATE.md`.

The v052 thread must use only `ab/v052/reader/*.json` as normal model input.

## 3. Save / Freeze

```bash
python horse-racing/jrdb/src/racenote_ab_lane.py save \
  --ab-root <ab-root> \
  --lane v052 \
  --decisions <ab-root>/v052/incoming/<venue>.json

python horse-racing/jrdb/src/racenote_ab_lane.py freeze \
  --ab-root <ab-root> \
  --lane v052
```

Use the same pattern for v051.

## 4. Barrier

After both exact lane Freeze artifacts are integrated:

```bash
python horse-racing/jrdb/src/racenote_ab_freeze_barrier.py --ab-root <ab-root>
python horse-racing/jrdb/src/racenote_ab_freeze_barrier.py --ab-root <ab-root> --verify-only
```

Required status:

`BOTH_LANES_FROZEN_CLEAN_BLIND`

The barrier must contain exactly `v051` and `v052`.

## 5. Evaluation

Do not collapse prediction accuracy and betting ROI into one score.

Primary comparison:

- ◎ win/top2/top3;
- ▲ win/top3;
- winner-in-five;
- average actual top3 captured;
- challenger admission rate;
- admitted challenger win/top3;
- displaced ordinary horse win/top3;
- ◎ single win/place ROI;
- ◎-○ and ◎-▲ quinella ROI;
- ◎→○ and ◎→▲ exacta ROI;
- trio ROI;
- trifecta ROI.

Also record:
- how often v052 ◎ differs from ordinary_five[0];
- finish-rank direction when it differs;
- whether re-ranking creates actual additional ◎ wins;
- whether v052 retains a meaningfully asymmetric ▲ profile without using target market information.

## 6. Compatibility

Existing legacy v046/v050 two-lane sessions and existing v046/v050/v051 three-lane sessions remain valid and must continue to load/freeze/verify unchanged.

`--pair-v051-v052` applies only when creating a new sealed session.
