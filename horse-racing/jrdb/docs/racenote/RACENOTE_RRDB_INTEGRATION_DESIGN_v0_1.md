# RaceNote RRDB Integration Design v0.1

Status: **R1-R5 IMPLEMENTED / REAL-DATA SMOKE PENDING**
Date: 2026-09-29

## 1. Goal

RaceReviewDB (RRDB) has already been built to preserve post-race evidence that
ordinary result summaries tend to miss:

- result quality versus finishing position
- adjusted performance
- last-3F quality
- position gain / loss
- pace / position context
- JRDB trouble information
- improvement versus the horse's own prior starts
- frozen Next-Watch hidden-value rule matches

The current Human-Context Reader v0.3 does not receive this lane in normal
RaceNote calibration execution.

This design makes RRDB a formal, result-safe RaceNote evidence lane without
changing the forecast's current flexible decision philosophy.

## 2. Existing assets to reuse

Do not rebuild RRDB logic in RaceNote.

Existing operational sources:

- RaceReviewDB CURRENT
  - stable Drive file: `RaceReviewDB_CURRENT.zip`
  - stable Drive file ID: `1UwNfrupMTHRPhkzULPvClGre4MWz2TFg`
- CURRENT resolver:
  - `src/racenote_racereview_current.py`
- RaceReview historical projection:
  - `src/racenote_racereview_adapter.py`
- Horse Evidence Card:
  - `src/racenote_horse_evidence_card.py`
- Next-Watch source selector:
  - `src/jrdb_next_watch_select.py`
- PACI reverse lookup:
  - `src/jrdb_next_watch_reverse.py`
- frozen rule version:
  - `next-watch-rules-discovery-v0.1`
- frozen rule artifact:
  - Drive file ID `1AzhPgqr8GXei4opzbI8gD7nb4-5qZ3Zr`

Identity remains:

- `horse_id = JRDB blood_registration_no`
- no horse-name fallback.

Historical boundary remains:

- `race_date < target_date`.

## 3. Architectural position

Current desired normal chain:

```text
JRDB / PACI
  -> RaceNote base
  -> Analysis history enrichment
  -> Pedigree P1/P2 enrichment
  -> RRDB enrichment
       |- historical review context
       '- latest-prior-start Next-Watch context
  -> authoritative RaceNote v1.0
  -> Reader View
  -> Human-Context Reader v0.3
  -> Forecast
  -> Freeze
```

RRDB is therefore a RaceNote evidence source, not a second forecast engine.

## 4. Per-horse RaceNote contract

Add one optional per-horse block:

```json
{
  "racereview": {
    "history_status": "AVAILABLE|NO_HISTORY|NO_HORSE_ID",
    "source_generation_id": "...",
    "as_of_exclusive": "2026-09-29",
    "latest_prior_run": {
      "race_date": "2026-09-13",
      "race_key": "...",
      "finish": 8,
      "content": {
        "performance_signal": 0.00,
        "last3f_speed_percentile": 92.0,
        "overall_position_gain": 4.0,
        "late_position_gain": 2.0,
        "performance_vs_prior3": 0.00,
        "last3f_pct_vs_prior3": 18.0
      },
      "trouble": {
        "jrdb_trouble_score": null,
        "jrdb_prev_trouble_score": null,
        "jrdb_mid_trouble_score": null,
        "jrdb_late_trouble_score": null
      },
      "review_tags": []
    },
    "next_watch": {
      "status": "MATCH|NO_MATCH|NO_PRIOR_HISTORY",
      "grade": "S|A|null",
      "rule_version": "next-watch-rules-discovery-v0.1",
      "matched_rule_ids": ["HV06"],
      "matched_rule_count": 1,
      "reason_groups": [
        "PERFORMANCE",
        "LAST3F"
      ],
      "human_summary": "前走着順以上に走破内容を評価。上がりも優秀。"
    },
    "history_profile": {
      "repeated_patterns": [],
      "hidden_strength": {},
      "fragile_form": {},
      "contradiction": {}
    },
    "scoring": false
  }
}
```

This is illustrative structure; exact numeric nullability is defined during
implementation from the existing adapter schemas.

## 5. Two distinct RRDB layers

### 5.1 Historical Review Context

Purpose:

- let Forecast read why a prior run was better / worse than the finish suggests;
- preserve pace / position / trouble / finish-quality context;
- detect repeated patterns.

This layer may use up to the existing adapter limit of 5 prior runs.

Do not duplicate basic facts already present in `recent_runs` unless required
to identify the RRDB source run.

Prefer:

- run reference
- derived / normalized RRDB facts
- review tags
- deterministic evidence items
- repeated-pattern summary

over copying full recent-run rows.

### 5.2 Next-Watch Context

Purpose:

- expose the frozen hidden-value judgment attached to the horse's most recent
  completed flat JRA start before the target date.

This is the operational answer to:

> "Was this horse's last race one of the runs RRDB says we should remember?"

Use the tightened operational S/A rule currently used by reverse lookup.

S:

- HV06
- OR HV13
- OR HV05 + one of HV07 / HV11 / HV12

A:

- at least one hidden-value rule
- and not S.

Do not promote grade merely because multiple hierarchical duplicate HV codes
coexist.

The integration must call shared rule logic rather than re-encoding thresholds
inside RaceNote.

## 6. Forecast semantics

RRDB is one evidence lane.

It must not become:

- S = automatic ◎
- A = automatic mark
- fixed numeric bonus
- fixed priority above every other lane
- a replacement for direct current-condition evidence.

Human-Context Reader should behave as:

1. read current race context;
2. inspect direct race evidence;
3. inspect RRDB when present;
4. ask whether the prior result understated / overstated the horse;
5. use it only when relevant to the current race.

Examples:

- prior run had clear trouble and strong hidden performance:
  RRDB can materially upgrade the interpretation of recent form;
- prior run was aided by pace / position:
  RRDB may weaken superficial good form;
- S/A exists but current race conditions differ materially:
  note it, but do not force a higher mark;
- no RRDB match:
  this is neutral, not negative.

## 7. Trace / observability

Add Forecast trace field:

```json
"rrdb_evidence": {
  "available": true,
  "reviewed": true,
  "used_in_decision": true,
  "horse_refs": [
    {
      "horse_no": 11,
      "horse_name": "...",
      "next_watch_grade": "S",
      "matched_rule_ids": ["HV06"],
      "decision_role": "UPGRADE_RECENT_FORM"
    }
  ],
  "reason_not_used": null
}
```

Allowed `decision_role` examples:

- `UPGRADE_RECENT_FORM`
- `DOWNGRADE_APPARENT_FORM`
- `SUPPORT_REPEATABILITY`
- `SUPPORT_COUNTERARGUMENT`
- `CONTEXT_ONLY`

If RRDB is available but not used, record:

- `used_in_decision=false`
- concise `reason_not_used`.

This proves the model actually saw the lane without forcing it to matter.

## 8. De-duplication with recent_runs

A major design goal is to avoid counting the same evidence twice.

If `recent_runs.race_comment` already says:

- "出遅れ"
- "外を回る"
- "直線詰まる"

and RRDB derives a trouble / hidden-value signal from the same run, Forecast
must treat them as one evidence story, not two independent votes.

Add source-run identity:

- `race_date`
- `race_key`
- `horse_id`

and, where possible, one shared `source_run_ref`.

Reader instructions:

> multiple fields derived from the same historical run are corroborating detail,
> not additive votes.

## 9. Firewall

Pre-Freeze allowed:

- completed historical RRDB rows with `race_date < target_date`
- frozen Next-Watch classification reconstructed only from the prior source run
  and earlier history
- stable RRDB derived features
- JRDB historical trouble fields.

Forbidden:

- target race result
- same-day post-race review
- future RRDB rows
- next-start result
- current market / final popularity / final odds
- any Next-Watch label whose construction uses the target result.

The enrichment must fail if any RRDB source run has:

`race_date >= target_date`.

## 10. Provenance

RaceNote metadata must record:

```json
"racereview_enrichment": {
  "version": "RRDB-RaceNote-0.1",
  "status": "ACTIVE",
  "current_generation_id": "...",
  "review_schema_version": "...",
  "review_logic_version": "...",
  "baseline_version": "...",
  "next_watch_rule_version": "next-watch-rules-discovery-v0.1",
  "as_of_exclusive": "target_date",
  "horse_identity": "JRDB_BLOOD_REGISTRATION_NO",
  "name_fallback": false,
  "scoring": false
}
```

Reader View must preserve this losslessly.

## 11. Implementation strategy

### Step R1 — Shared reusable RRDB core

Extract reusable functions from:

- `racenote_racereview_adapter.py`
- `jrdb_next_watch_reverse.py`

Do not make RaceNote invoke the PACI reverse CLI.

New reusable module recommendation:

- `src/racenote_rrdb_enrichment.py`

Input:

- target date
- target horse identities from RaceNote
- resolved RaceReviewReader / relation paths
- frozen Next-Watch rule contract.

Output:

- per-horse `racereview` blocks.

### Step R2 — RaceNote production connection

Connect R1 after Analysis/P1/P2 enrichment and before Reader View.

RaceNote generation should still succeed when RRDB has no history for a horse.

Source availability policy:

- valid RRDB + no horse history -> `NO_HISTORY`
- no horse_id -> `NO_HORSE_ID`
- RRDB source resolution failure -> request-level explicit warning / policy to be
  decided during implementation; do not silently fabricate empty evidence.

### Step R3 — Reader View

No semantic compression initially.

First version should preserve `racereview` losslessly.

Optimize context size only after real RaceNote size measurement.

### Step R4 — Human-Context Reader

Update v0.3 instructions:

- RRDB must be read when present;
- no fixed weight;
- latest hidden-value S/A may change interpretation of recent form;
- same-run duplicates are not additive.

### Step R5 — Forecast trace

Extend v0.3 research record / validator with `rrdb_evidence`.

Validation:

- if RaceNote says RRDB available, `reviewed` must be true;
- `used_in_decision` may be true or false;
- if false, `reason_not_used` is required;
- if true, cited horse/run must exist in RaceNote RRDB evidence.

## 12. Testing

Focused tests:

1. horse_id join only
2. no name fallback
3. strict `race_date < target_date`
4. same-day RRDB excluded
5. latest prior run resolved correctly
6. tightened S/A grading matches reverse selector
7. hidden-value duplicated rules do not falsely promote S
8. no-history horse stays neutral
9. Reader View round-trip
10. RRDB source generation recorded
11. no target-result / market field exposed
12. Forecast validator requires RRDB reviewed when available.

Real-data calibration:

- reuse already-consumed / ineligible races only;
- do not spend a new clean PACI day;
- select 5-10 races containing:
  - at least one S/A reverse match
  - at least one historical trouble case
  - at least one no-match horse
  - one race with recent-run comment and RRDB overlap to test de-duplication.

## 13. Relationship to P1/P2 pedigree

Treat both exactly as optional context lanes:

- pedigree:
  "background suitability / population context"
- RRDB:
  "what actually happened in prior races beyond raw finishing position"

Neither is a fixed score.

Current desired behavioral balance:

```text
direct race evidence
+ race-specific context
+ RRDB prior-run interpretation where relevant
+ pedigree background where relevant
+ ability / training / trend
-> holistic comparison
```

No universal hierarchy is frozen.

## 14. P3 siblings / obstacle evidence

Out of scope.

Do not mix:

- sibling pedigree P3
- obstacle-specific evidence

into RRDB integration work.

## 15. Acceptance criteria

RRDB integration is PASS when:

- normal RaceNote generation includes `racereview` per horse;
- current RRDB generation provenance is visible;
- historical rows are strictly target-date exclusive;
- Next-Watch matches equal the canonical reverse selector for the same horse/date;
- no name fallback occurs;
- Reader View is lossless;
- Human-Context Reader demonstrably reads the lane;
- Forecast may explicitly ignore an RRDB signal with reason;
- no fixed score / bonus / automatic mark is introduced;
- no unused calibration date is consumed for integration validation.

## 16. Recommendation

Implement R1-R5 without changing Human-Context Reader's core selection logic.

The main purpose is not to make RRDB "stronger".

The purpose is to ensure:

> RRDB is always available to the predictor, visibly reviewed, and allowed to
> matter when the race context makes it relevant.

That preserves the current successful flexible forecast style while finally
connecting the RRDB investment to the normal RaceNote / Forecast path.


## 17. Implementation status — 2026-09-29

Implemented on main:

- `src/jrdb_next_watch_rules.py`
  - shared tightened S/A grading
  - reason-group compression
  - short human summary
- `src/jrdb_next_watch_select.py`
  - now reuses shared grading
- `src/jrdb_next_watch_reverse.py`
  - now reuses shared grading
- `src/racenote_rrdb_enrichment.py`
  - formal per-horse `racereview` enrichment
  - existing RaceReview adapter + Horse Evidence Card reuse
  - strict target-date-exclusive historical lookup
  - latest-prior-run Next-Watch reconstruction
  - RaceNote provenance publication
- `src/racenote_history_enrichment.py`
  - production entrypoint can run RRDB enrichment after Analysis/P1/P2 when
    RRDB source + frozen rule artifact are supplied
- `schema/racenote_forecast_research_record_v0_3_1.json`
  - adds mandatory `rrdb_evidence` trace
- `src/validate_racenote_forecast_human_context.py`
  - current schema requires RRDB reviewed
  - used RRDB requires cited horse refs
  - unused RRDB requires a reason
- Human-Context Reader / config / Forecast bootstrap updated.

Backward compatibility:

- CAL-001 / CAL-002 v0.3 records are not rewritten.
- validator still accepts historical v0.3 records.
- current pointer now uses v0.3.1 for future calibration.

Still pending before declaring full operational PASS:

- focused repository test execution;
- one 5-10 race already-used/ineligible real-data smoke showing:
  - S/A match equality with reverse selector;
  - historical trouble visibility;
  - NO_MATCH neutrality;
  - recent_runs / RRDB same-run de-duplication;
  - Reader View lossless round-trip.

No unused clean PACI day should be consumed by this smoke.
