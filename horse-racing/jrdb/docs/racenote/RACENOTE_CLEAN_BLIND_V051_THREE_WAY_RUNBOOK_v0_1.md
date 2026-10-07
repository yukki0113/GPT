# RaceNote v0.4.6 / v0.5.0 / v0.5.1 Clean-Blind Three-Way Runbook v0.1

Status: **RESEARCH HARNESS FOR INITIAL v0.5.1 VALIDATION**  
Date: 2026-10-07

## Purpose

Use the first two v0.5.1 BTDAYs to isolate the effect of decision compression.

All three lanes share one reserved BTDAY, one market-blind `forecast_prep`, one clean Reader source, one race/horse roster, one RRDB v0.3 contract and one sealed session.

- `v046`: complete clean Reader, v0.4.6 Human-Context logic.
- `v050`: v0.5.0 `normal_view`, v0.5.0 five-role compression.
- `v051`: byte-identical `normal_view`, v0.5.1 protected-mainline six-to-five compression.

No lane may read sibling authored/frozen files, marks, prose or Decision Cores.

## 1. Seal a three-lane session

Prepare the reserved BTDAY exactly as in the existing Clean-Blind runbook. Then initialize with:

```bash
python horse-racing/jrdb/src/racenote_ab_session.py \
  --prep-root horse-racing/jrdb/backtests/BTDAY-XXXX/forecast_prep \
  --request horse-racing/jrdb/backtests/requests/BTDAY-XXXX.json \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/ab \
  --base-main-sha <forecast_prep/day_prep_handoff.json:main_sha> \
  --policy horse-racing/jrdb/docs/racenote/research-work/results/stage_c/reader_feature_policy_v0_5_candidate.json \
  --include-v051
```

The sealed session must contain `v046`, `v050`, and `v051` lane definitions. `v050/reader/*.json` and `v051/reader/*.json` must be byte-identical.

## 2. Start three isolated authoring tasks

Use three fresh tasks/threads from the same task base commit.

### v046 prompt boundary

Use only the original complete clean Reader. Follow the existing v0.4.6 Decision Core contract. Never inspect v050/v051 artifacts.

### v050 prompt boundary

Use only `ab/v050/reader/*.json`. Follow the existing v0.5.0 procedure. Never inspect v046/v051 artifacts.

### v051 prompt boundary

Use only `ab/v051/reader/*.json`. Follow
`docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_5_1_CANDIDATE.md`.

For every race:

1. form the race model;
2. create ordered `ordinary_five=[◎ anchor, ○ anchor, support A, support B, support C]`;
3. choose exactly one external asymmetric challenger outside that five when six or more runners exist; for exactly five runners use `NO_EXTERNAL_CHALLENGER`;\n4. compare the six explicitly when a sixth runner exists;
5. either `ADMIT_CHALLENGER` or `KEEP_ORDINARY_FIVE`;
6. do not change the two anchors during the challenger comparison;
7. write the required `candidate_compression` object.

The v051 task must not inspect v046 or v050 forecasts.

## 3. Save and freeze independently

Use the existing lane wrapper for all three lanes:

```bash
python horse-racing/jrdb/src/racenote_ab_lane.py save \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/ab \
  --lane v051 \
  --decisions horse-racing/jrdb/backtests/BTDAY-XXXX/ab/v051/incoming/<venue>.json
```

After every expected venue is saved:

```bash
python horse-racing/jrdb/src/racenote_ab_lane.py freeze \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/ab \
  --lane v051
```

The same command pattern applies to v046 and v050.

Do not merge one lane's forecast artifacts before the other two lanes are independently frozen.

## 4. Integration barrier

After all three exact lane Freeze artifacts are imported into one integration checkout:

```bash
python horse-racing/jrdb/src/racenote_ab_freeze_barrier.py \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/<YYYYMMDD>/ab
```

For a three-lane session the barrier status must be:

`ALL_LANES_FROZEN_CLEAN_BLIND`

Before opening results, run the same command with `--verify-only`.

## 5. Evaluation

Keep prediction and settlement evidence separate.

In addition to the existing v046/v050 metrics, compare v050 -> v051 directly:

- ◎ change count and finish-rank direction;
- ◎ win / top-2 / top-3;
- ▲ win / top-3;
- winner-in-five and average actual top-3 captured;
- external challenger admission rate;
- admitted challenger top-3 / win rate;
- ordinary-five winner/top-3 coverage before compression;
- which ordinary support slot was displaced;
- old-v046 △2 complete-drop rate;
- quinella `◎-▲`;
- exacta `◎→▲`;
- trio and trifecta;
- whether v051 preserves useful v050-only new-candidate discoveries.

Do not interpret longer-shot selection alone as success.
