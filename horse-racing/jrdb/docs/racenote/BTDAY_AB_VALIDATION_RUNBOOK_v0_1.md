# RaceNote BTDAY A/B Validation Runbook v0.1

Status: **ACTIVE FOR v0.4.2 vs v0.4.3 CANDIDATE VALIDATION**  
Date: 2026-10-02

## 1. Purpose

Validate whether
`RaceNote-Human-Context-Reader-0.4.3-candidate`
improves on
`RaceNote-Human-Context-Reader-0.4.2-candidate`
without hindsight.

This runbook is for **new unused BTDAYs**.

## 2. Versions

Baseline A:
- `FORECAST_HUMAN_CONTEXT_READER_v0_4_2_CANDIDATE.md`
- logic id `RaceNote-Human-Context-Reader-0.4.2-candidate`

Candidate B:
- `FORECAST_HUMAN_CONTEXT_READER_v0_4_3_CANDIDATE.md`
- logic id `RaceNote-Human-Context-Reader-0.4.3-candidate`

Shared:
- RRDB `rrdb-recommendation-signals-v0.3`
- same Reader input
- same target-day market-blind boundary
- same reader-facing prose contract

## 3. Non-negotiable blindness

Before either Forecast is generated:
- target result must remain unopened;
- target-day odds / popularity / market fields must remain unavailable;
- no result-derived research label may enter the request.

Both A and B must be frozen before any target result is opened.

## 4. Same-input requirement

For each race:
1. prepare one accepted `reader_stripped` input;
2. bind its semantic hash;
3. run v0.4.2 from that input in an A-only Work context;
4. independently run v0.4.3 from the **same** input in a separate, new B-only Work context;
5. Freeze both outputs;
6. only then proceed to results.

Do not let v0.4.3 read the v0.4.2 marks as evidence.
Do not ask v0.4.3 merely to "edit" the baseline marks.
Neither Work context may read the other's Forecast marks, decision trace,
reader-facing reason, or HTML while creating its own prediction. A/B comparison
and access to both Frozen outputs occur only in the later audit context.

After A is Frozen, the B-only handoff contains only:
- BTDAY ID and target date;
- canonical DAY PREP path / identifier and `reader_stripped` path;
- main SHA and RRDB contract;
- expected race count;
- market-blind and result-unopened audit state.

The B-only handoff must not contain A's marks (including horse names attached
to marks), decision trace, reader-facing reason, or HTML. Existing partial A
drafts remain in the A context; their existence does not require B to run in
that context and does not stop A from finishing. Both individual Freezes must
complete before A/B audit or result acquisition.

The comparison must be two independent Forecast decisions sharing only the
pre-race evidence.

## 5. Suggested storage

Within each new BTDAY date directory:

```text
day_merge/
  forecast_YYYYMMDD_all_v042.json
  forecast_YYYYMMDD_all_v043.json
  forecast_YYYYMMDD_ab_manifest.json
  forecast_YYYYMMDD_ab_audit.json
```

Existing per-version HTML may be generated when useful:

```text
forecast_YYYYMMDD_v042.html
forecast_YYYYMMDD_v043.html
```

Do not overwrite a Frozen baseline file.

## 6. A/B manifest minimum fields

```json
{
  "schema_version": "racenote-btday-ab-manifest-v0.1",
  "target_date": "YYYY-MM-DD",
  "baseline_logic_id": "RaceNote-Human-Context-Reader-0.4.2-candidate",
  "candidate_logic_id": "RaceNote-Human-Context-Reader-0.4.3-candidate",
  "rrdb_contract": "rrdb-recommendation-signals-v0.3",
  "same_reader_input_required": true,
  "market_blind": true,
  "result_opened_before_both_freezes": false,
  "main_sha_at_freeze": "...",
  "baseline_prediction_hash": "...",
  "candidate_prediction_hash": "..."
}
```

## 7. Pre-result A/B audit

PASS requires:
- all expected races exist for both versions;
- every race has five unique marks;
- identity/race counts match between A and B;
- Reader semantic hash matches per race;
- RRDB contract is v0.3 for both;
- market blind guards PASS;
- result_opened=false until both freezes complete;
- prediction hashes fixed.

Also report:
- number of races where five-horse set differs;
- number where ◎ differs;
- number where ○ differs;
- number where ▲ differs;
- number where only △ boundary differs.

These are pre-result diagnostics only.

### Deterministic Freeze and audit commands

Use the same accepted, market-stripped DAY PREP directory for both versions.
The two prepared record files contain independently model-authored marks, prose,
and decision traces. Candidate B uses
`RaceNote-Forecast-Research-Record-0.4.3` and records the three reviewed
consistency passes in `decision_trace.consistency_pass`; the v0.4.2 schema
and default Freeze invocation remain valid.

```sh
python horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py \
  --prep-root "$PREP" --prepared-records "$PREPARED_A" \
  --output-root "$FROZEN_A" --selection-id "$SELECTION_ID" \
  --date "$TARGET_DATE" --main-sha "$MAIN_SHA"
python horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py \
  --prep-root "$PREP" --prepared-records "$PREPARED_B" \
  --output-root "$FROZEN_B" --selection-id "$SELECTION_ID" \
  --date "$TARGET_DATE" --main-sha "$MAIN_SHA" \
  --logic-version RaceNote-Human-Context-Reader-0.4.3-candidate
python horse-racing/jrdb/src/validate_racenote_forecast_human_context.py \
  --records "$FROZEN_A/day_merge/forecast_${COMPACT_DATE}_all.json" \
  --output "$FROZEN_A/day_merge/validator.json"
python horse-racing/jrdb/src/validate_racenote_forecast_human_context.py \
  --records "$FROZEN_B/day_merge/forecast_${COMPACT_DATE}_all.json" \
  --output "$FROZEN_B/day_merge/validator.json"
python horse-racing/jrdb/src/audit_racenote_btday_ab.py \
  --prep-root "$PREP" --baseline-root "$FROZEN_A" \
  --candidate-root "$FROZEN_B" --main-sha "$MAIN_SHA" \
  --output-dir "$AB_AUDIT_DIR"
```

Copy the two merged forecast files and the generated `ab_manifest.json` /
`ab_audit.json` to the filenames in section 5 only after both validators
and the A/B audit PASS. A failed audit produces no PASS manifest. Freeze
output directories must be new staging paths; do not rerun the packager
against a previously frozen output directory.

## 8. Result acquisition

After both versions are Frozen:
- use `jrdb_result_query_runner.py` as standard entrypoint;
- use JRDB Raw SED/HJC before web;
- do not rewrite either Forecast after result acquisition.

## 9. Primary comparison

Per version calculate:

Forecast quality:
- ◎ wins / win rate;
- ◎ top2 / top3;
- winner in five;
- all Top3 in five.

Bet quality, 100 yen per ticket:
- ◎ win;
- ◎○ quinella;
- ◎▲ quinella;
- ◎→○ exacta;
- ◎→▲ exacta;
- ◎-key trio, choose 2 from ○▲△1△2 = 6 tickets;
- ◎ 1st-fixed trifecta, ordered 2nd/3rd from ○▲△1△2 = 12 tickets;
- five-horse trio box 10 as candidate-set diagnostic.

## 10. Change-attribution comparison

For every race where A != B, record:
- what changed;
- which v0.4.3 pass caused it:
  - HIERARCHY_CONSISTENCY
  - SINGLE_SHOT_PROMOTION
  - COVERAGE_CHALLENGER
- pre-Freeze rationale;
- whether the changed horse was direct-condition evidence driven;
- whether RRDB/RaceReview hidden evidence materially contributed.

Do not label a change GOOD/BAD until after result settlement.

## 11. Evaluation discipline

Do not judge v0.4.3 from one corrected-looking race.

Review at day-set level and cumulative A/B level.

A high-payout exotic hit is legitimate and remains in the primary ROI.
Optional concentration diagnostics may show dependence on largest payouts, but
largest-payout removal is not a primary metric.

Do not promote a version solely from ROI if:
- ◎ win quality collapses;
- five-horse coverage materially worsens;
- gains come from a very small number of unstable Coverage swaps;
- ▲ role is being flattened into ordinary rank 3.

## 12. Initial target

Accumulate approximately **3〜4 new BTDAYs / around 100 races** before making
a normal promotion decision.

This is a research target, not a hard statistical threshold.
If evidence is contradictory, continue validation rather than forcing a
version decision.

## 13. Promotion rule

v0.4.3 may be considered for promotion only after:
1. multiple new unused BTDAYs were frozen under both A and B;
2. no result/market leakage occurred;
3. improvement is not limited to one payout accident;
4. Hierarchy gains do not materially damage Coverage;
5. Coverage challenger changes remain conservative;
6. ▲ role integrity remains intact.

Until then:
**v0.4.2 remains the baseline and v0.4.3 remains an A/B candidate.**
