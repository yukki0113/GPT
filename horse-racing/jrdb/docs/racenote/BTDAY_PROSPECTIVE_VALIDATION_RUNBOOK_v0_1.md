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

### Strict binding of authored decisions

For faster and safer entry, the model may write a JSON array with exactly one
decision per clean Reader and bind it using
`src/racenote_bind_authored_v044.py`. Each decision must explicitly contain:

- `venue`, `race_no`, five ordered `marks` (◎/○/▲/△1/△2);
- `race_model`, `reader_facing_reason`, `mark_reason`;
- four authored `mainline_cases` with `horse_no` and `case` for
  ◎/○/provisional △1/△2, plus `single_shot_case` for ▲;
- `rrdb_evidence` with explicit available/reviewed/used flags, authored
  `reason_not_used`, and any horse number + decision role references;
- `consistency_pass` with hierarchy and ▲ decisions/reasons, every
  Coverage field from section 4, and the provisional △2 horse number.

For the compact input, `coverage_boundary.current_delta2` and
`coverage_best_challenger` are horse numbers (or null for no challenger).
The binder fills horse names, Reader/source identities, RRDB evidence IDs
and fixed contract metadata only. It rejects missing cases or decisions; it
does not infer a challenger, verdict, comparison, reason or RRDB use.

```sh
python horse-racing/jrdb/src/racenote_bind_authored_v044.py \
  --prep-root "$FORECAST_PREP" --decisions "$AUTHORED_V044" \
  --output "$PREPARED_V044" --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" --main-sha "$MAIN_SHA"
```

The binder requires an exact race-key set and full Validator PASS before
writing `$PREPARED_V044`. Do not substitute the retired temporary packager,
which filled missing judgment with stock text.

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

After every expected race has a completed authored record, run the exact
same command first with `--preflight-only`. This checks Reader binding,
full-card coverage, v0.4.4 Coverage identities/counts, and the full prose
Validator **without creating an immutable Freeze directory**. Repair authored
records in the judgment layer until the preflight returns PASS. Then omit
`--preflight-only` to write Freeze:

```sh
python horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py \
  --prep-root "$FORECAST_PREP" --prepared-records "$PREPARED_V044" \
  --output-root "$NEW_FROZEN_V044" --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" --main-sha "$MAIN_SHA" \
  --logic-version RaceNote-Human-Context-Reader-0.4.4-candidate \
  --preflight-only
```

The regular Freeze repeats those checks before writing. A failed preflight is
an incomplete forecast, not a technical day exclusion.

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

## 7. One-request operator checklist and restart checkpoint

The stages are ordered. Keep the same selection and clean Reader on a retry.

| Stage | Canonical operation | Completion evidence |
| --- | --- | --- |
| Selection | Inspect the current pool/history. Reuse an already selected BTDAY ID; otherwise call `src/racenote_backtest_day_picker.py pick --state <pool> -n 1` once and persist the updated pool on latest main. | One selection ID, one date, PACI filename/Drive ID; no duplicate draw |
| PACI | Resolve the selected filename in the PACI Drive folder from `docs/JRDB_2026_Raw_Drive_Reference.md`; verify ZIP and PACI families. | Exact date/file identity and readable ZIP |
| DAY PREP | Run `src/build_racenote_daily.py` once for the date with the current Analysis and RRDB v0.3 assets. Resolve Parquet/DuckDB via `tools/data-storage/` if needed. | `manifest.json` and `validation_report.json` PASS; expected race count; target result unopened and as-of guards PASS |
| Clean bind | Run `src/racenote_prepare_forecast_input.py` on DAY PREP. | `day_prep_handoff.json` and `reader_stripped_manifest.json` PASS, market blind, result unopened, hash and race count fixed |
| Model judgment | Read only `$FORECAST_PREP/reader/*.json` and handoff. Author five marks, four mainline cases (◎/○/provisional △1/△2), independent ▲, RRDB review, v0.4.4 Coverage scan/comparison and race-specific prose for **each** race. | One complete authored record per Reader; no scripted marks, prose, challenger or verdict |
| Preflight / Freeze | Run Freeze `--preflight-only`, then normal Freeze and Validator. | Preflight PASS, all races Frozen, Validator PASS, semantic hashes fixed |
| Git save / output | Save clean handoff/manifest, input-binding audit, merged frozen JSON/JSONL, freeze handoff/audits, validator and frozen-record-derived reader output under `backtests/BTDAY-xxxx/YYYYMMDD/` on latest main. Render with `src/render_racenote_forecast_html.py --records <frozen-all.json> --output <forecast.html>` if HTML is needed. | Git readback of same hashes and full race count; ordinary forecast shown only from Frozen records |

Stage the Git tree deterministically after the post-Freeze Validator PASS.
The staging command verifies clean Reader hashes and identities again, copies
only forecast-safe evidence, and formats the already-frozen prose. It never
chooses marks or writes a decision trace:

```sh
python horse-racing/jrdb/src/racenote_stage_btday_archive.py \
  --day-prep-root "$DAY_PREP" --clean-prep-root "$FORECAST_PREP" \
  --frozen-root "$NEW_FROZEN_V044" \
  --output-root "horse-racing/jrdb/backtests/$BTDAY_ID/$COMPACT_DATE" \
  --selection-id "$BTDAY_ID" --date "$TARGET_DATE"
```

Commit the staged UTF-8 files against latest main via an available direct
GitHub route, then read back `day_merge/forecast_${COMPACT_DATE}_all.json`,
`validator.json` and `clean_blind_audit.json`. Compare the staged merged
SHA-256, record count, and semantic prediction hashes. Do not overwrite an
existing immutable BTDAY directory. Git staging does not require Actions.

The picker is a persistent state mutation. Never rerun `pick` for an ID
already recorded in main. If a task spans multiple sessions, checkpoint only:
BTDAY ID/date, PACI identity, main SHA used at bind, clean input root and
manifest SHA, expected/completed race count, and market/result-unopened audit.
Authored decisions and prose stay with the forecast work; do not recalculate
completed races from a changed input.

Before declaring completion, compare the exact Reader race-key set with the
prepared-record set. A few authored marks or a readable projection are not a
Freeze. When a card is large, save race-by-race authored progress and continue
through the missing keys in the same request. Report an actual unavailable
asset or failing gate by name; do not treat ordinary remaining authoring work as
an environment failure.

This lane is ordinarily A (read/audit) + C (deterministic local execution) +
B (Git save). Existing Drive PACI does not require an Actions run. Use D only
when a separate Actions-native requirement is actually present. In particular,
do not use the removed temporary BTDAY42/43 job: it synthesized model-authored
Coverage and mainline narratives from marks.
