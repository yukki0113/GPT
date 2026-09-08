# RaceNote Blind Historical Backtest Batch — 2025-08-23 v0.1

## Status

**TARGET SET FROZEN BEFORE TARGET-DATE RESULT / HJC ACQUISITION**

This batch extends `provisional_handoff_v0.1_unweighted` without changing prediction logic or settlement rules.

## Target selection

Use **all JRA races on 2025-08-23** returned by the authoritative RaceNote request for that date.

Selection rule:

```text
race_date = 2025-08-23
scope = all venues / all races
```

No race may be omitted after reading RaceNote because it looks difficult, lacks fields, has a small field, or has unusual conditions. If a source/validation failure prevents a prediction, retain the race in the batch and record the failure explicitly rather than silently dropping it.

The date is chosen mechanically as the immediately preceding JRA race day before the already-settled 2025-08-24 PoC. HJC/results for 2025-08-23 must not be acquired until every usable race prediction is frozen.

## Prediction contract

For each race:

- use RaceNote v1.0 / Reader View v0.1 only;
- preserve `as_of_exclusive = 2025-08-23`;
- apply `RaceNote_Prediction_Handoff_v0_1.md` unchanged;
- logic profile remains `provisional_handoff_v0.1_unweighted`;
- output ordered marks `◎ / ○ / ▲ / △...` and confidence;
- do not use target-race result, final odds, final popularity, HJC, SED target result, or any post-race source.

## Settlement contract

After the prediction file for the full date is committed and frozen, acquire HJC and settle with `RaceNote_Backtest_Settlement_Protocol_v0_1.md` unchanged:

- ① ◎単勝 1点
- ② ◎-○ / ◎-▲ 馬連 2点
- ③ ◎1頭軸、○ / ▲ / △1 / △2への3連複6点
- 100円均等
- six combined evaluation patterns unchanged

## Evaluation discipline

This is an expansion batch, not a tuning batch.

Do not modify weights, mark policy, ticket construction, or headline metrics from the 2025-08-24 result. Record aggregate and per-race results first. Segment analysis may be descriptive, but any logic change must define a new prediction profile and be tested on a later untouched batch.

Required sequence:

```text
target set freeze
 -> RaceNote acquisition
 -> full-date prediction freeze
 -> HJC acquisition
 -> deterministic settlement
 -> evaluation report
```
