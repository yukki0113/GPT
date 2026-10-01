# RaceNote RRDB Integration Design v0.2

Status: **ACTIVE — RRDB RECOMMENDATION v0.2**
Date: 2026-10-01
Supersedes: `RACENOTE_RRDB_INTEGRATION_DESIGN_v0_1.md` for current operation

## 1. Purpose

RaceReviewDB (RRDB) is a historical reinterpretation lane for RaceNote Forecast.

It does not choose marks and it does not provide a recommendation grade.
Its purpose is to show when a visible prior result may understate, overstate, or
misdescribe what the horse actually demonstrated.

Current operational recommendation contract:

`rrdb-recommendation-signals-v0.2`

Canonical source:

`horse-racing/jrdb/src/jrdb_recommendation_signals.py`

## 2. Current evidence contract

Current operational signals:

- `TIME_CLASS_PLUS1`
- `FRONT_SURVIVE_GAP05`
- `REAR_HIGH_LAST3F90`
- `HV01`
- `HV02`

Each signal is accompanied by measured strength values relevant to that signal.

S/A grades are disabled.

Do not derive a replacement grade from:

- matched signal count;
- combinations of signal IDs;
- arbitrary thresholds on measured strength;
- the former Next-Watch hierarchy.

The former S/A Next-Watch contract is historical-reproduction-only.

## 3. Operational lookback

Current recommendation consumption uses a 730-day target-date-relative lookback.

For target date D:

- source run must satisfy `race_date < D`;
- source run must satisfy `race_date >= D - 730 days`;
- horse identity is JRDB blood registration number;
- horse-name fallback is prohibited.

No target-race result, next-start result, current odds, final popularity, or
future RRDB row may be read pre-Freeze.

## 4. RaceNote per-horse shape

Current RaceNote enrichment exposes:

`racereview.recommendation`

with fields including:

- `status`: MATCH / NO_MATCH / NO_PRIOR_HISTORY;
- `contract_version`;
- `grade = null`;
- `grade_status = DISABLED`;
- `matched_signal_ids`;
- `matched_signal_count`;
- `signals[]` containing signal label and measured strength;
- `human_summary`;
- `lookback_days`;
- source-run context when available.

A deprecated `racereview.next_watch` compatibility stub may remain, but Forecast
must not use it for current interpretation.

## 5. Forecast reading semantics

Forecast must read RRDB as:

```text
visible prior result
  -> inspect recommendation signal + strength + source-run context
  -> reinterpret the run
  -> ask whether that meaning transfers to today's race
  -> re-compare the horse with today's rivals
```

Important:

- a recommendation MATCH is not an automatic upgrade;
- NO_MATCH is neutral, not negative;
- signal count is not strength;
- measured strength is evidence, not a score;
- multiple signals from one source run are corroborating descriptions, not
  additive votes;
- current-race relevance decides whether RRDB changes the forecast.

Examples:

- upper-class time evidence may matter strongly when today's class and distance
  make that performance transferable;
- front-survival evidence may matter when today's pace/position setup lets the
  same strength reappear;
- rear high-last3F evidence may matter when the prior pace worked against that
  style and today's setup is friendlier;
- HV01/HV02 may upgrade a poor visible finish when adjusted time content remains
  genuinely relevant today;
- any of the above may remain context-only when today's conditions differ.

## 6. Interaction with marks

RRDB must not become:

- automatic ◎ / ○ / ▲ / △;
- a fixed numeric bonus;
- a mandatory tie-breaker;
- a requirement that a MATCH horse be marked;
- a requirement that NO_MATCH horse be downgraded.

The Human-Context Reader remains responsible for the whole-race comparison.

## 7. Decision trace

`decision_trace.rrdb_evidence` should show that RRDB was reviewed and, when used,
which horse/source-run evidence changed or supported interpretation.

Current trace should prefer:

- `recommendation_contract_version`;
- `matched_signal_ids`;
- concise measured-strength references when materially relevant;
- `decision_role`;
- `source_run_ref` when available.

Legacy fields such as `next_watch_grade` or `matched_rule_ids` may remain only
for historical record compatibility and should be null/unused in new records.

Allowed decision-role concepts remain:

- UPGRADE_RECENT_FORM
- DOWNGRADE_APPARENT_FORM
- SUPPORT_REPEATABILITY
- SUPPORT_COUNTERARGUMENT
- CONTEXT_ONLY

If RRDB is available but not used in the decision, record a concise reason.

## 8. De-duplication

Evidence derived from the same historical run must not be counted twice.

If recent_runs, RRDB history, and recommendation signals all describe the same
run, Forecast should construct one coherent story from them rather than treating
them as independent votes.

## 9. Provenance

RaceNote metadata should preserve:

- RRDB generation identity;
- recommendation contract version;
- grade status DISABLED;
- operational lookback days;
- target-date-exclusive boundary;
- blood-registration-number identity;
- name_fallback=false;
- scoring=false.

## 10. Legacy boundary

Historical assets remain valid for reproduction of old turns:

- `RaceReviewDB_NextWatch_Operation_v0_1.md`
- `jrdb_next_watch_rules.py`
- frozen Next-Watch rule artifacts
- old S/A trace fields in Frozen BTDAYs

Do not reinterpret or rewrite those Frozen runs.

BTDAY-0017 and later should use the current recommendation contract when their
RaceNote inputs are generated under the new RRDB semantics.

## 11. Acceptance

Current RRDB integration is correct when:

- RaceNote exposes `racereview.recommendation`;
- current signals match `rrdb-recommendation-signals-v0.2`;
- grades remain disabled;
- measured strengths remain visible;
- 730-day and target-date-exclusive boundaries hold;
- Forecast reviews RRDB without converting it to a score or automatic mark;
- same-run evidence is deduplicated;
- legacy S/A assets are not used by current Forecast.
