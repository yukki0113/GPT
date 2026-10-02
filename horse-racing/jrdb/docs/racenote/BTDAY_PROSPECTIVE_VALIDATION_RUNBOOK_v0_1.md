# RaceNote BTDAY Prospective Validation Runbook v0.1

Status: **ACTIVE FOR NEW UNUSED BTDAYs — v0.4.3 CANDIDATE ONLY**
Date: 2026-10-02

## 1. Cohorts and interpretation

- Fixed historical clean-blind baseline: the already Frozen
  `RaceNote-Human-Context-Reader-0.4.2-candidate` records from
  BTDAY-0023 through BTDAY-0032, inclusive. Do not rerun, edit, or add
  v0.4.2 races to this cohort.
- Prospective candidate: new unused BTDAYs selected after this policy change,
  each forecast once with `RaceNote-Human-Context-Reader-0.4.3-candidate`.
  Do not create a same-day v0.4.2 forecast.
- BTDAY-0035 was Frozen under v0.4.2 before this policy change. Preserve it
  as a historical out-of-cohort artifact; do not include it in either
  evaluation cohort or generate a v0.4.3 pair for it.

The comparison is between different historical and prospective days.
Report differences in calendar, venue, race class, surface, distance and
field mix, and uncertainty. Do not present an unadjusted difference as a
paired same-day causal effect. The candidate remains unpromoted to the
production Forecast pointer pending evaluation.

## 2. Select and prepare

1. Use `src/racenote_backtest_day_picker.py` and
   `config/racenote_backtest_day_pool_2026.json` to draw an unused eligible
   day. Respect the append-only selection history. Do not reuse the
   BTDAY-0035 date or a baseline day.
2. Produce and audit DAY PREP using the current direct GitHub/Drive/Work
   execution path. Actions are necessary only for an Actions-native step.
3. Bind one accepted `reader_stripped` set, with target-day market objects
   removed. Target results and target-day odds/popularity remain unopened
   throughout preparation, judgment, Freeze and validation.
4. RRDB recommendation contract is `rrdb-recommendation-signals-v0.3`.

## 3. Author v0.4.3 alone

Read the v0.4.3 candidate contract and the reasoning/mechanical boundary.
The model authors each race's five unique marks, axis, race-specific
reader-facing reason, mainline and independently selected single-shot
case. It reviews all three v0.4.3 consistency passes and records their
booleans and change attribution. A change attribution describes changes
within the candidate's own judgment, **not** a comparison to v0.4.2.

The prepared record uses
`RaceNote-Forecast-Research-Record-0.4.3`, declares
`independent_forecast=true` and
`baseline_marks_used_as_input=false`, and contains no target-day market
or target result. Do not read historical baseline marks as prediction input.
Scripts may bind identities and package authored decisions; they must not
select horses or compose forecast prose.

## 4. Freeze, validate and save

After every expected race has a completed authored record:

```sh
python horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py \
  --prep-root "$PREP" --prepared-records "$PREPARED_V043" \
  --output-root "$NEW_FROZEN_V043" --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" --main-sha "$MAIN_SHA" \
  --logic-version RaceNote-Human-Context-Reader-0.4.3-candidate
python horse-racing/jrdb/src/validate_racenote_forecast_human_context.py \
  --records "$NEW_FROZEN_V043/day_merge/forecast_${COMPACT_DATE}_all.json" \
  --output "$NEW_FROZEN_V043/day_merge/validator.json"
```

Require the full DAY PREP race count, five unique marks per race, matching
Reader identity and semantic source hashes, RRDB v0.3, market-blind and
result-unopened guards, fixed semantic prediction hashes, and Validator
PASS. Freeze paths are new and immutable. Save the one Frozen v0.4.3
forecast, handoff and audits to the canonical BTDAY Git tree; make the
ordinary user-facing forecast from this v0.4.3 output.

`audit_racenote_btday_ab.py` and the former same-day A/B manifest are
historical tools, not gates for a prospective v0.4.3 day. Their absence
must not stop a valid single-version Freeze.

## 5. Results and evaluation

Result acquisition and settlement are separate steps **after** Freeze and
validation. Use the current result query path and never rewrite the
Frozen forecast.

Evaluate the candidate's ◎ wins/win ROI, winner-in-five, all-Top3-in-five,
◎○ / ◎▲ quinella, ◎→○ / ◎→▲ exacta, ◎-key trio and
◎-first-fixed trifecta on the prospective cohort. Compute the same
definitions on the fixed v0.4.2 cohort. Show both cohort sizes and
calendar/course mix; examine pass-level change attribution and ▲ integrity.
Do not add BTDAY-0035 or same-day A/B records to either defined cohort.
Promotion requires a later explicit research decision.
