# RaceNote BTDAY Prospective Validation Runbook v0.1

Status: **ACTIVE FOR NEW UNUSED BTDAYs — v0.4.4 CANDIDATE ONLY**
Date: 2026-10-03

## 1. Cohorts and interpretation

### Fixed historical baseline

- Logic: `RaceNote-Human-Context-Reader-0.4.2-candidate`
- Cohort: BTDAY-0023 through BTDAY-0032, inclusive
- Size: 336 clean-blind races
- Preserve existing Frozen records. Do not rerun, edit, or add v0.4.2 races.

### Completed v0.4.3 prospective cohort

- Logic: `RaceNote-Human-Context-Reader-0.4.3-candidate`
- Formal clean-blind days:
  - BTDAY-0036
  - BTDAY-0037
  - BTDAY-0040
  - BTDAY-0041
- Size: 132 races
- This cohort is now fixed for comparison. Do not add new v0.4.3 BTDAYs.
- BTDAY-0038 is excluded for pre-Freeze market exposure.
- BTDAY-0039 is excluded for authoring-input binding violation.

### New v0.4.4 prospective cohort

New unused BTDAYs selected after this policy change are forecast once with
`RaceNote-Human-Context-Reader-0.4.4-candidate`.

Do not create same-day v0.4.2 or v0.4.3 forecasts.

The comparison remains between different historical/prospective days. Report
calendar, venue, class, surface, distance and field-mix differences and
uncertainty. Do not describe an unadjusted cohort difference as a paired
same-day causal effect.

The production Forecast pointer remains unchanged until an explicit promotion
decision.

## 2. Select and prepare

1. Use `src/racenote_backtest_day_picker.py` and
   `config/racenote_backtest_day_pool_2026.json` to draw an unused eligible
   day. Respect append-only selection history and all prior used/excluded dates.
2. Produce and audit DAY PREP using the current direct GitHub/Drive/Work
   execution path. Actions are necessary only for an Actions-native step.
3. DAY PREP's lossless `reader/` and `authoritative/` may contain target-day
   market and are **not Forecast inputs**. Bind a clean immutable input first:

   ```sh
   python horse-racing/jrdb/src/racenote_prepare_forecast_input.py \
     --day-prep-root "$DAY_PREP" --output-root "$FORECAST_PREP" \
     --selection-id "$BTDAY_ID" --date "$TARGET_DATE" --main-sha "$MAIN_SHA"
   ```

4. Expose only `$FORECAST_PREP/reader/*.json` and its handoff to the judgment
   context. Verify binder PASS and expected race count before reading any
   Reader.
5. Do not inspect or paste the lossless DAY PREP Reader to check it manually.
   Target result and target-day market remain unopened throughout judgment,
   Coverage scan, Freeze and validation.
6. RRDB recommendation contract remains
   `rrdb-recommendation-signals-v0.3`.

## 3. Author v0.4.4 alone

Read:

- `FORECAST_HUMAN_CONTEXT_READER_v0_4_4_CANDIDATE.md`
- `FORECAST_REASONING_MECHANICAL_BOUNDARY_v0_1.md`
- `FORECAST_READER_FACING_PROSE_v0_1.md`

For each race the model authors:

- five unique marks ◎ / ○ / ▲ / △1 / △2;
- axis;
- race-specific reader-facing reason;
- mainline cases;
- independently selected ▲ case;
- RRDB evidence review;
- hierarchy consistency pass;
- ▲ promotion gate;
- explicit Coverage scan and boundary decision.

The prepared record uses:

- schema `RaceNote-Forecast-Research-Record-0.4.4`;
- logic `RaceNote-Human-Context-Reader-0.4.4-candidate`;
- `independent_forecast=true`;
- `baseline_marks_used_as_input=false`.

Scripts may bind identities and package authored decisions. They must not
select horses, choose the Coverage challenger, decide KEEP/SWAP, or compose
forecast prose.

## 4. Required v0.4.4 Coverage trace

Every race must contain an auditable Coverage pass.

Required structure:

```json
{
  "coverage_scan_reviewed": true,
  "coverage_scan": {
    "unmarked_count": 0,
    "direct_condition_candidate_count": 0,
    "shortlisted_horse_nos": []
  },
  "coverage_best_challenger": null,
  "coverage_challenger_case": null,
  "coverage_boundary": {
    "current_delta2": {
      "horse_no": 16,
      "horse_name": "Example Delta2"
    },
    "direct_condition_comparison": null,
    "ability_comparison": null,
    "race_model_comparison": null
  },
  "coverage_verdict": "NO_ELIGIBLE_CHALLENGER",
  "coverage_changed": false,
  "coverage_reason": "..."
}
```

For KEEP or SWAP:

- `coverage_best_challenger` must identify one horse;
- that horse must appear in `shortlisted_horse_nos`;
- `coverage_challenger_case` must explain direct condition, ability proximity,
  race-model fit and supporting evidence;
- all three boundary comparisons must use one of
  `CHALLENGER_STRONGER / DELTA2_STRONGER / ROUGHLY_EQUAL / UNCLEAR`.

For SWAP:

- final △2 must equal the challenger;
- provisional △2 must leave the final five;
- `coverage_changed=true`;
- change attribution includes `COVERAGE_CHALLENGER`.

For KEEP / NO_ELIGIBLE_CHALLENGER:

- final △2 remains provisional △2;
- `coverage_changed=false`.

Ambiguous cases default to KEEP.

## 5. Freeze, validate and save

After every expected race has a completed authored record:

```sh
python horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py \
  --prep-root "$FORECAST_PREP" --prepared-records "$PREPARED_V044" \
  --output-root "$NEW_FROZEN_V044" --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" --main-sha "$MAIN_SHA" \
  --logic-version RaceNote-Human-Context-Reader-0.4.4-candidate

python horse-racing/jrdb/src/validate_racenote_forecast_human_context.py \
  --records "$NEW_FROZEN_V044/day_merge/forecast_${COMPACT_DATE}_all.json" \
  --output "$NEW_FROZEN_V044/day_merge/validator.json"
```

Require:

- full DAY PREP race count;
- five unique marks per race;
- matching Reader identity and semantic source hashes;
- RRDB v0.3;
- market-blind and result-unopened guards;
- fixed semantic prediction hashes;
- v0.4.4 Coverage trace invariants;
- Validator PASS.

Freeze paths are new and immutable.

Save the one Frozen v0.4.4 forecast, handoff and audits to the canonical BTDAY
Git tree. Generate ordinary user-facing forecast output only from this Frozen
candidate.

Historical A/B tooling is not a gate for this prospective lane.

## 6. Results and evaluation

Result acquisition and settlement are separate steps **after** Freeze and
validation. Use the current result query path and never rewrite the Frozen
forecast.

Continue the established metrics:

- ◎ wins / win ROI;
- winner in five;
- all Top3 in five;
- ◎○ / ◎▲ quinella;
- ◎→○ / ◎→▲ exacta;
- ◎-key trio;
- ◎-first-fixed trifecta.

For v0.4.4 also report:

- eligible-challenger rate;
- KEEP rate;
- SWAP rate;
- NO_ELIGIBLE_CHALLENGER rate;
- Top3 newly captured by SWAP;
- Top3 lost by removing provisional △2;
- net Coverage gain;
- winner-in-five effect;
- all-Top3-in-five effect;
- whether ▲ role integrity remained intact.

Compare against both:

- v0.4.2 fixed 336R baseline;
- v0.4.3 fixed 132R prospective cohort.

Do not pool excluded BTDAYs into formal cohorts.

Promotion requires a later explicit research decision.
