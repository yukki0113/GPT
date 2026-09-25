# RaceReviewDB Next-Watch Backtest Plan v0.1

Status: IN_PROGRESS
Date: 2026-09-25
Repository: yukki0113/GPT
Component: RaceReviewDB

## 1. Purpose

This backtest evaluates whether RaceReviewDB post-race signals predict a horse's
next JRA start.

The objective is not to retroactively explain winners. The objective is to
identify repeatable, leakage-safe rules that can classify post-race horses into:

- Next-watch S
- Next-watch A
- exploratory / unconfirmed
- no signal

The first implementation must remain interpretable. Machine-learning models are
out of scope for v0.1.

## 2. Core principle

For every source race, features must be constructed only from information that
was available at the end of that race date.

No future RaceReviewDB state may leak into the source-race features.

The RaceReviewDB consumer rule remains:

race_date < target_date

When comparing the source race with the horse's own history, only earlier starts
may be used.

## 3. Study periods

Discovery period:

2026-05-01 through 2026-07-31

Holdout period:

2026-08-01 through 2026-09-22

Future operational period:

2026-09-23 onward

Rules may be explored and selected on Discovery.

After a candidate rule is frozen, its thresholds must not be altered while
evaluating Holdout.

A rule that succeeds only in Discovery is not sufficient for S/A promotion.

## 4. Observation grain

One candidate observation is:

source horse-start -> immediately following JRA horse-start

The source row is one horse in one completed source race.

The target outcome is that same horse's next JRA start.

Stable horse identity must use RaceReviewDB horse_id
(JRDB blood_registration_no), never horse name.

## 5. Initial population

Include:

- JRA flat races
- valid horse_id
- normal completed source race
- source date within the selected analysis period
- a later JRA next start available within the available result horizon

Initial exclusions:

- cancellation / exclusion
- race interruption / abnormal result unsuitable for ordinary comparison
- jump races
- records without stable horse_id

Long layoffs are retained initially as an analyzable attribute rather than
silently discarded, unless data quality requires an explicit exclusion later.

## 6. Signal families

### 6.1 Time performance

Primary fields:

- horse_adjusted_delta_sec
- horse_adjusted_delta_per_1000m
- time_class_equivalent
- time_class_equivalent_numeric
- winner_gap_sec

Main hypothesis:

A horse can run better than its finishing position suggests.

### 6.2 Closing performance

Primary fields:

- last3f_sec
- last3f_rank
- last3f_speed_percentile
- closing_gain_sec
- last3f_leader_diff_sec

Main hypothesis:

Strong closing performance in defeat can retain predictive value at the next
start.

### 6.3 Position dynamics

Primary fields:

- corner1_position
- corner2_position
- corner3_position
- corner4_position
- early_position_gain
- middle_position_gain
- late_position_gain
- overall_position_gain

Main hypothesis:

How a horse moved through the race may contain more information than final
position alone.

### 6.4 Pace / trip opposition

Primary fields:

- pace_shape
- race_running_style_code
- corner4_frontness
- related race-context fields

Candidate concepts include:

- forward horse surviving a strong pace
- rear horse closing into a slow pace

These are hypotheses to test, not accepted truths.

### 6.5 JRDB trouble evidence

Primary fields:

- jrdb_trouble_score
- jrdb_prev_trouble_score
- jrdb_mid_trouble_score
- jrdb_late_trouble_score
- jrdb_late_break_score
- jrdb_position_score

Trouble signals must be tested both alone and in combination with actual
performance evidence.

### 6.6 Within-horse improvement

For each source horse-start, derive leakage-safe comparisons against that
horse's earlier RaceReviewDB history, for example:

- current performance versus previous 3-start mean
- current performance versus previous 5-start mean
- current percentile within prior starts
- new recent best indicator
- standardized improvement where sample size permits

The exact derived metrics must be versioned and documented before rule search.

## 7. Next-start outcomes

Phase 1 evaluates prediction without market information.

Required outcomes:

- next_finish
- next_win
- next_top3
- next_top5
- finish_improvement
- days_to_next_start

finish_improvement is descriptive only and must not replace absolute next-start
success metrics.

Phase 2 may join market/result data outside RaceReviewDB:

- next popularity rank
- next win odds
- win payout / return
- place payout / return

This separates:

1. ability-prediction value
2. betting-market value

A rule may predict improvement while offering no betting edge if the market
already prices it correctly.

## 8. Baselines

Every signal or rule must be compared against an appropriate baseline.

At minimum report:

- all eligible observations
- source finishing-position band
- surface
- distance category
- class group

Popularity-conditioned baselines belong to Phase 2.

Raw success rate without a baseline lift is not sufficient evidence.

## 9. Single-signal screening

Start with one variable at a time.

Continuous fields should first be evaluated using stable quantile or
domain-readable buckets rather than an optimized threshold search.

Examples:

- last3f_speed_percentile bands
- horse_adjusted_delta_per_1000m bands
- closing_gain_sec bands
- position-gain bands
- trouble-score bands

For every bucket report:

- N
- next win rate
- next top3 rate
- next top5 rate
- average / median next finish
- average / median finish improvement
- baseline lift

The purpose is to identify whether the signal contains any monotonic or
localized next-start relationship.

## 10. Combination search

After single-signal screening, test interpretable two-condition combinations.

Only conditions with a racing or statistical rationale should enter the initial
combination search.

Then test a limited set of three-condition combinations using only signals that
already show plausible evidence.

Do not brute-force every possible threshold combination.

For every rule preserve:

- rule_id
- human-readable condition
- exact machine condition
- feature version
- Discovery N and metrics
- Holdout N and metrics
- status

## 11. Minimum sample policy

Small-sample winners must not be promoted.

Initial guidance:

- Discovery candidate rule: N >= 30
- stronger S-candidate preference: N >= 50
- Holdout evidence: preferably N >= 20

These are guardrails, not significance claims.

Rules below the minimum are marked:

INSUFFICIENT_SAMPLE

and must not receive S/A status solely because of a high observed hit rate.

## 12. Rule grades

Do not define S/A from intuition before the backtest.

Candidate statuses:

- EXPLORATORY
- REJECTED
- HOLDOUT_PENDING
- A_CANDIDATE
- S_CANDIDATE
- ACCEPTED_A
- ACCEPTED_S

Conceptual requirements:

### ACCEPTED_A

- interpretable rule
- sufficient Discovery sample
- meaningful lift over baseline
- Holdout direction retained
- no material leakage or data-quality concern

### ACCEPTED_S

- multiple complementary signals
- stronger and practically useful lift
- sufficient sample
- Holdout reproduction
- no evidence that result depends on one tiny segment or accidental threshold

Numeric promotion thresholds must be chosen only after the first empirical
distribution is available.

## 13. Segment analysis

Do not begin by splitting into many small segments.

First evaluate the overall population.

Then inspect plausible heterogeneity for:

- turf / dirt
- sprint / mile / middle / staying distance
- maiden / allowance / open / graded class groups
- age group if justified

Segment-specific rules require adequate sample and separate Holdout evidence.

## 14. Leakage controls

At minimum enforce:

- source features use source race and strictly earlier history only
- horse self-comparison uses only earlier starts
- Holdout thresholds are frozen before Holdout evaluation
- target next-start results are never included in feature construction
- future standard/bias state is not substituted for the source-date as-of state

Any dataset builder must include explicit source_date and target_next_date so
leakage can be audited.

## 15. Planned artifacts

### 15.1 Candidate feature table

Suggested file:

next_watch_candidate_signals.parquet

One row per source horse-start.

### 15.2 Next-start outcome table

Suggested file:

next_watch_next_start_results.parquet

One row per source horse-start with resolved next-start outcome.

### 15.3 Joined backtest fact

Suggested file:

next_watch_backtest_fact.parquet

Immutable analysis-ready join between candidate features and next-start
outcomes.

### 15.4 Rule result mart

Suggested file:

next_watch_rule_backtest.parquet

One row per rule x evaluation period / relevant segment.

### 15.5 Accepted rule contract

Suggested file:

next_watch_rules_v0_1.json

Contains only frozen accepted or candidate rules with versioned definitions.

### 15.6 Human-readable report

Suggested file:

RaceReviewDB_NextWatch_Backtest_Report_v0_1.md

## 16. v0.1 non-goals

Do not use v0.1 to:

- optimize a black-box machine-learning model
- maximize in-sample return
- search arbitrary thousands of threshold combinations
- retroactively choose rules using Holdout results
- claim a profitable betting strategy from hit rate alone
- promote descriptive track-bias shadow fields as calibrated causal features

## 17. Completion condition

v0.1 backtest work is complete when:

- leakage-safe candidate fact is built
- next-start mapping is audited
- Discovery single-signal results exist
- interpretable combinations are evaluated
- candidate rules are frozen
- Holdout is evaluated without threshold edits
- accepted/rejected rules and reasons are recorded
- the process is reproducible from canonical RaceReviewDB and canonical result
  sources

---

# 18. Chat execution turn plan

The implementation should be split into bounded turns so each turn performs one
substantial operation, produces a durable checkpoint, and can be resumed without
depending on Chat context.

Each turn must finish with:

- status: PASS / BLOCKED / PARTIAL
- files or commits changed
- row counts and key audit facts
- next turn
- resume IDs / paths

Avoid combining large Drive acquisition, full-period computation, extensive
rule search, and publication in one turn.

## Turn 1 - Source and schema audit

Goal:

Confirm which existing RaceReviewDB/current-result assets are sufficient for the
backtest.

Tasks:

- inspect RaceReviewDB CURRENT schema and date coverage
- identify result source for next-start resolution
- identify whether popularity/odds are available for Phase 2
- freeze source keys and joins
- write a short audit result into this plan or a companion implementation note

No large backtest execution.

Completion:

BACKTEST_INPUT_CONTRACT_READY

Turn 1 status:

PASS

Frozen companion contract:

horse-racing/jrdb/docs/RaceReviewDB_NextWatch_Backtest_Input_Contract_v0_1.md

Key decisions:

- RaceReviewDB CURRENT is the primary source for source-race features, horse
  identity and Phase 1 next-start outcomes.
- canonical SED is the sidecar for abnormal-result eligibility, race-type
  filtering, final popularity and final win odds.
- source/target identity is race_horse_key with horse_id continuity.
- next-start resolution is the first later RaceReviewDB start for the same
  horse_id.
- 2026-05 through 2026-09-22 has 44 observed PACI/SED date pairs.
- realized payout/ROI source is not yet contracted; Turn 7 must audit it before
  return-based conclusions.

## Turn 2 - Build candidate feature dataset

Goal:

Build leakage-safe source-race observations for Discovery + Holdout.

Tasks:

- extract eligible 2026-05-01 through 2026-09-22 horse-starts
- compute raw RaceReviewDB feature set
- compute within-horse historical features using only earlier starts
- assign Discovery / Holdout period
- persist candidate_signals Parquet
- audit duplicate source keys, missing horse IDs, date bounds and row counts

No next-start outcome scoring yet.

Completion:

CANDIDATE_SIGNAL_FACT_READY

## Turn 3 - Resolve next starts and outcomes

Goal:

Map every eligible source horse-start to the immediately following JRA start.

Tasks:

- deterministic horse_id + chronological next-start mapping
- ensure target_next_date > source_date
- derive Phase 1 outcomes
- persist next_start_results and joined backtest fact
- audit one-to-one mapping, missing-next-start population and sample rows

No rule search yet.

Completion:

NEXT_START_FACT_READY

## Turn 4 - Single-signal Discovery screening

Goal:

Measure each signal family independently on 2026-05 through 2026-07 only.

Tasks:

- establish overall and major population baselines
- evaluate stable buckets for time, closing, position, pace, trouble and
  within-horse improvement signals
- calculate N and outcome lifts
- reject clearly non-informative signals
- produce compact single-signal report/table

Do not look at Holdout while selecting thresholds.

Completion:

DISCOVERY_SINGLE_SIGNAL_READY

## Turn 5 - Interpretable combination Discovery

Goal:

Test only justified 2-condition and limited 3-condition combinations.

Tasks:

- generate candidate rule IDs
- enforce minimum sample guards
- compare with baselines
- record rejected and surviving rules
- freeze exact candidate definitions for Holdout before reading Holdout outcomes

Completion:

CANDIDATE_RULES_FROZEN

## Turn 6 - Holdout validation

Goal:

Evaluate frozen candidate rules on 2026-08-01 through 2026-09-22.

Tasks:

- do not alter thresholds
- calculate same metrics as Discovery
- compare direction and magnitude
- mark ACCEPTED_A / ACCEPTED_S / REJECTED / INSUFFICIENT_SAMPLE
- preserve all results, including failures

Completion:

HOLDOUT_VALIDATED

## Turn 7 - Phase 2 market-value audit

Goal:

If popularity/odds/result payout sources are available, test whether accepted
ability signals retain betting-market value.

Tasks:

- join next-start popularity/odds/payout
- audit missingness
- evaluate popularity-adjusted performance
- calculate win/place return where source quality supports it
- keep ability classification separate from betting value

If reliable market data is unavailable, mark this turn BLOCKED without changing
Phase 1 conclusions.

Completion:

MARKET_VALUE_AUDITED or MARKET_VALUE_BLOCKED

## Turn 8 - Rule contract and operationalization

Goal:

Turn validated rules into a reproducible Next-Watch contract.

Tasks:

- write next_watch_rules_v0_1.json
- write final backtest report
- implement deterministic selector if justified
- add tests for rule boundaries and leakage
- document how a completed race day can output S/A candidates after
  RaceReviewDB update

Completion:

NEXT_WATCH_V0_1_OPERATIONAL

## 19. Timeout / recovery policy

For this Chat thread:

1. Prefer local deterministic computation after one bounded source download.
2. Persist intermediate Parquet instead of rebuilding from scratch each turn.
3. Do not run broad condition search and source acquisition in the same turn.
4. Do not mix Git changes and a long historical calculation unless the change is
   needed to execute that exact turn.
5. Every large transformation must first run on a small sample or schema-only
   check before full execution.
6. Use row-count/key/hash audits at each durable checkpoint.
7. If a turn fails after producing a valid prior checkpoint, resume from that
   checkpoint rather than restarting earlier turns.
8. Never silently promote a partial computation to the next turn.

This plan is the canonical v0.1 design until an explicit versioned update
supersedes it.


## 20. Turn 2 execution checkpoint

Status:

CANDIDATE_SIGNAL_FACT_READY

Execution date:

2026-09-25

Successful workflow:

- run_id: 36108597763
- Issue: #1346
- result: PASS

Source:

- RaceReviewDB generation:
  jrdb_race_review_v0_1_incremental_g36094708797
- requested source period: 2026-05-01 through 2026-09-22
- actual first source date: 2026-05-02
- actual last source date: 2026-09-22

Population:

- candidate rows: 18,707
- distinct source race_horse_key: 18,707
- distinct horses: 8,002
- Discovery rows: 11,648
- Holdout rows: 7,059
- duplicate source keys: 0
- empty horse_id rows: 0
- invalid finish/time rows: 0
- jump rows: 0
- history_date_leak rows: 0

Feature contract:

- raw RaceReviewDB horse-performance fields are retained
- race-level Review/context fields are joined by race_key
- performance_signal is defined as
  -horse_adjusted_delta_per_1000m, so higher is better
- within-horse history uses only preceding rows ordered by
  horse_id / race_date / race_key / horse_no
- derived self-comparison fields include prior 3/5-start performance means,
  prior 5-start best, last3F relative history, closing-gain history,
  days since previous start, and recent-best indicators
- Discovery/Holdout labels are persisted, but no next-start outcomes are
  present in this artifact

Expected missingness is preserved as NULL, never coerced to neutral values.

Observed null counts:

- performance_signal: 0
- last3f_speed_percentile: 0
- closing_gain_sec: 17,333
- prior3_performance_mean: 1,795
- prior5_performance_mean: 1,795
- prior3_last3f_pct_mean: 1,795
- prior5_closing_gain_mean: 14,409

The high closing_gain missingness means closing-gain rules must be evaluated on
their available-evidence population and must not treat NULL as zero.

Checkpoint artifact:

- Drive folder next_watch:
  1TPjuy73X9mObzxAiMOawBspqoNdnjtXg
- Drive folder next_watch/v0_1:
  1u10flcW396mrwmBf-kdYMBSAuCFMo_Qm
- artifact ZIP:
  RaceReviewDB_NextWatch_Turn2_g36108597763.zip
- Drive file ID:
  1rd9KRoFmJYJcRlRyblprP997n9TdJOLi
- contained candidate Parquet:
  next_watch_candidate_signals.parquet
- contained audit:
  candidate_signals_audit.json
- Parquet size:
  1,894,808 bytes
- Parquet SHA256:
  204f6e15f391f213f8369a0b32dda9d2884e2f486bb2047e0744626fd095dde4

Failed/superseded Turn-2 requests:

- #1343: no target workflow run due initial invalid workflow YAML; closed
  not_planned
- #1344: DuckDB COPY target parameter incompatibility; closed not_planned
- #1345: candidate build succeeded, audit failed on DuckDB 1.1 boolean SUM;
  closed not_planned
- #1346: successful retry; closed completed

Next turn:

Turn 3 - resolve immediate next JRA starts and Phase-1 outcomes from this
checkpoint without rebuilding Turn 2.


## 21. Turn 3 execution checkpoint

Status:

NEXT_START_FACT_READY

Execution date:

2026-09-25

Successful workflow:

- run_id: 36109088127
- Issue: #1350
- result: PASS

Input:

- Turn2 checkpoint Drive file ID:
  1rd9KRoFmJYJcRlRyblprP997n9TdJOLi
- RaceReviewDB CURRENT generation:
  jrdb_race_review_v0_1_incremental_g36094708797
- observation horizon:
  2026-09-22

Resolution contract:

- one row per Turn2 source race_horse_key
- immediate later JRA start is selected by the same stable horse_id
- target ordering is deterministic by race_date / race_key / horse_no
- next_date must be strictly greater than source_date
- source features are not rebuilt or modified
- NO_NEXT_START_BY_HORIZON remains censored, not a failure
- jump next starts are retained as RESOLVED_JUMP and excluded from flat Phase-1
  outcome metrics
- invalid next results are retained as RESOLVED_INVALID_RESULT and excluded
  from Phase-1 outcome metrics

Population:

- Turn2 source rows: 18,707
- Turn3 outcome rows: 18,707
- distinct source keys: 18,707
- joined backtest fact rows: 18,707
- resolved flat valid: 10,685
- resolved jump: 33
- resolved invalid: 78
- no next start by 2026-09-22 horizon: 7,911
- Phase-1 eligible rows: 10,685
- minimum observed days to next start: 6
- maximum observed days to next start: 141
- hard errors: 0

By evaluation period:

- Discovery source rows: 11,648
- Discovery Phase-1 eligible: 8,619
- Holdout source rows: 7,059
- Holdout Phase-1 eligible: 2,066

Right-censoring warning:

The 2026-08-01 through 2026-09-22 Holdout source window is not yet fully
mature at an observation horizon of 2026-09-22. In particular, late-August and
September source starts have had limited or zero time to produce a subsequent
JRA start.

Therefore Turn 6 must not interpret "a next start happened by 2026-09-22" as a
predictive success criterion, and must not compare only observed Holdout rows
without a maturity policy. Before Holdout validation, freeze a censoring policy
such as a minimum follow-up window / mature-source cutoff, or extend the
outcome horizon with later RaceReviewDB data. Discovery rule search remains
separate and may proceed without consulting Holdout outcomes.

Checkpoint artifact:

- Drive folder:
  race_review/v0_1/next_watch/v0_1
- Drive file:
  RaceReviewDB_NextWatch_Turn3_g36109088127.zip
- Drive file ID:
  1LXlUZ4dhCmoRSDPyJZcAhF-SpHvGroMg
- contained outcome Parquet:
  next_watch_next_start_results.parquet
- contained joined fact:
  next_watch_backtest_fact.parquet
- contained audit:
  next_start_audit.json

Object hashes:

- next_watch_next_start_results.parquet
  SHA256:
  32ecbbb92723ec095ccce4718748906523df0e15f85c5defb8ae5257d6ec43c3
- next_watch_backtest_fact.parquet
  SHA256:
  fe46db0770465734722253e7e4fc004e11e22fc10960966cb6567de4b5c983fb

Next turn:

Turn 4 - Discovery single-signal screening using only Discovery rows and
Phase-1 eligible next-start outcomes. Holdout outcomes remain outside threshold
selection.


## 22. Turn 4 execution checkpoint

Status:

DISCOVERY_SINGLE_SIGNAL_READY

Execution date:

2026-09-25

Successful workflow:

- run_id: 36109590220
- Issue: #1356
- result: PASS

Input:

- Turn3 checkpoint Drive file ID:
  1LXlUZ4dhCmoRSDPyJZcAhF-SpHvGroMg
- Discovery Phase-1 eligible rows:
  8,619
- Holdout outcomes:
  not used for signal screening or threshold selection

Discovery baseline:

- win rate:
  7.70%
- top3 rate:
  23.33%
- top5 rate:
  38.48%
- average next finish:
  7.34
- median next finish:
  7
- average finish improvement:
  -0.37

Screened signal families:

- source finish band
- performance_signal quintile
- last3f_speed_percentile band
- overall position gain
- late position gain
- trouble score
- late-break score
- performance vs prior 3 starts
- last3F percentile vs prior 3 starts
- recent-5-start performance-best flag
- pace shape
- race pace code
- fourth-corner frontness
- closing_gain_sec on available-evidence rows only

Descriptive findings, Discovery only:

- source finish 1-3 is the strongest bucket:
  N=2,126, next top3=41.96%, lift=+18.62 percentage points.
  This is expected persistence of already-good performance and is not by itself
  a useful hidden-value Next-Watch rule.
- performance_signal top quintile:
  N=1,723, next top3=39.00%, lift=+15.67 pp.
- last3F percentile 90-100:
  N=1,458, next top3=34.22%, lift=+10.89 pp.
- last3F percentile 80-90:
  N=1,015, next top3=31.33%, lift=+8.00 pp.
- fourth-corner FRONT:
  N=2,873, next top3=30.70%, lift=+7.37 pp.
- last3F percentile improvement vs prior 3 starts, +10 to +20 points:
  N=868, next top3=30.07%, lift=+6.74 pp.
- overall position gain POS_STRONG:
  N=1,053, next top3=29.44%, lift=+6.11 pp.
- performance vs prior-3, +0.5 to +1.0:
  N=1,291, next top3=26.88%, lift=+3.55 pp.

Closing-gain evidence:

- only 795 Discovery Phase-1 rows have closing_gain_sec
- strong observed buckets exist, but this is a restricted evidence population
- closing_gain must not be interpreted as an all-horse signal and NULL must
  never be coerced to zero

Trouble evidence:

- jrdb_trouble_score >= 2:
  N=33, next top3=36.36%, lift=+13.03 pp
- the sample is too small to promote; keep as exploratory only

Turn-5 search policy refinement:

The strongest single bucket is source finish 1-3, which mainly confirms that
already-good horses remain good. The project goal is to detect horses whose
next-run value is not obvious from finishing position alone.

Therefore Turn 5 should preserve two complementary tracks:

1. persistence track:
   evaluate whether high performance / closing / positional signals add value
   beyond already-good source finish

2. hidden-value defeat track:
   explicitly test source finish >= 4 (and selected >= 6 definitions) combined
   with strong performance, last3F, position dynamics, pace/trip opposition,
   trouble evidence, or within-horse improvement

Candidate rules must be compared against the appropriate source-finish baseline,
not only the all-horse baseline. This avoids simply rediscovering that horses
finishing 1-3 are more likely to run well next time.

Checkpoint artifact:

- Drive file:
  RaceReviewDB_NextWatch_Turn4_g36109590220.zip
- Drive file ID:
  1x7JFIm9p0yCX4Hw7JqCQFcbNBhyGkwxZ
- contained result:
  next_watch_single_signal_discovery.parquet
- contained audit:
  single_signal_audit.json
- result SHA256:
  2ae8c27dabc3e25655a7d15775c89c66c2abcd6dba35ab190630e7e1e71d5e22

Workflow note:

The newly-created standalone Turn4 workflow registered after a short delay.
A temporary Turn4 job was also added to the already-registered Turn3 workflow,
causing duplicate execution with identical results. The temporary route was
removed afterward. The standalone Turn4 workflow is the retained route.

Superseded requests:

- #1354: no target run during workflow registration delay; closed not_planned
- #1355: no target run during registration delay; closed not_planned
- #1356: successful Turn4 request; closed completed

Next turn:

Turn 5 - interpretable Discovery combinations, with source-finish-conditioned
baselines and explicit hidden-value defeat rules. Freeze candidate definitions
before any Holdout evaluation.


## 23. Turn 5 execution checkpoint

Status:

CANDIDATE_RULES_FROZEN

Execution date:

2026-09-25

Successful workflow:

- run_id: 36110362625
- Issue: #1358
- result: PASS

Input:

- Turn3 checkpoint Drive file ID:
  1LXlUZ4dhCmoRSDPyJZcAhF-SpHvGroMg
- Discovery rows:
  8,619
- Holdout consulted:
  false

Matched Discovery baselines:

- ALL:
  N=8,619, top3=23.33%, top5=38.48%
- FINISH_GE4:
  N=6,493, top3=17.23%, top5=31.36%
- FINISH_GE6:
  N=4,983, top3=14.33%, top5=26.85%
- FINISH_LE3:
  N=2,126, top3=41.96%, top5=60.25%

Frozen thresholds:

- performance_signal_q80:
  -0.09305555555555287
- performance_signal_q90:
  0.16777149321267684
- last3f_pct_strong:
  80
- last3f_pct_elite:
  90
- position_gain_strong:
  0.25
- last3f_vs_prior3_improvement:
  10
- performance_vs_prior3_improvement:
  0.5
- trouble_score_strong:
  2

Promotion guardrails used for Holdout-candidate freezing:

- minimum Discovery N:
  30
- primary:
  matched-baseline top3 lift >= 5 percentage points
  AND matched-baseline top5 lift >= 3 percentage points
- secondary:
  matched-baseline top3 lift >= 4 percentage points
  AND average finish improvement better than matched baseline

Tested rules:

18

Frozen Holdout candidates:

11

Hidden-value candidates:

- HV01:
  4着以下 + performance_signal 上位20%
  N=763
  top3=27.65%
  matched baseline=17.23%
  lift=+10.42 pp

- HV02:
  6着以下 + performance_signal 上位20%
  N=400
  top3=24.50%
  matched baseline=14.33%
  lift=+10.17 pp
  average finish improvement=+0.86

- HV03:
  4着以下 + 上がり速度percentile 90以上
  N=647
  top3=22.87%
  matched baseline=17.23%
  lift=+5.64 pp

- HV05:
  4着以下 + performance上位20% + 上がり80以上
  N=257
  top3=31.91%
  matched baseline=17.23%
  lift=+14.67 pp
  top5=49.81%
  top5 lift=+18.45 pp

- HV06:
  6着以下 + performance上位20% + 上がり80以上
  N=100
  top3=28.00%
  matched baseline=14.33%
  lift=+13.67 pp
  top5=40.00%
  top5 lift=+13.15 pp
  average finish improvement=+0.63

- HV07:
  4着以下 + 強い位置取り改善 + 上がり80以上
  N=315
  top3=22.86%
  matched baseline=17.23%
  lift=+5.62 pp

- HV11:
  4着以下 + performance上位20% + 自身過去3走比改善
  N=469
  top3=22.81%
  matched baseline=17.23%
  lift=+5.58 pp

- HV12:
  6着以下 + performance上位20% + 自身過去3走比改善
  N=253
  top3=21.34%
  matched baseline=14.33%
  lift=+7.02 pp
  average finish improvement=+0.66

- HV13:
  4着以下 + performance上位10% + 上がり90以上
  N=63
  top3=25.40%
  matched baseline=17.23%
  lift=+8.16 pp

Persistence candidates:

- P01:
  1-3着 + performance上位20%
  N=961
  top3=47.97%
  matched baseline=41.96%
  lift=+6.01 pp

- P03:
  1-3着 + performance上位20% + 上がり80以上
  N=606
  top3=48.35%
  matched baseline=41.96%
  lift=+6.39 pp

Rejected / exploratory examples:

- HV15:
  4着以下 + JRDB強い不利 + 上がり80以上
  N=8
  top3=50.00%
  matched-baseline lift=+32.77 pp
  status=INSUFFICIENT_SAMPLE

- HV14:
  6着以下 + performance上位10% + 上がり90以上
  N=20
  top3=25.00%
  matched-baseline lift=+10.67 pp
  status=INSUFFICIENT_SAMPLE

Interpretation:

Discovery provides a real hidden-value signal candidate rather than merely
rediscovering source finishing position. In particular, strong RaceReviewDB
performance among horses finishing 6th or worse remains materially above the
same 6th-or-worse population baseline, and combining performance with strong
last-3F increases the concentration further.

These findings are Discovery-only. They are not accepted S/A rules until
Holdout validation passes without threshold changes.

Frozen rule contract:

- next_watch_candidate_rules_frozen.json
- rule_version:
  next-watch-rules-discovery-v0.1
- holdout_consulted:
  false

Checkpoint artifact:

- Drive file:
  RaceReviewDB_NextWatch_Turn5_g36110362625.zip
- Drive file ID:
  1AzhPgqr8GXei4opzbI8gD7nb4-5qZ3Zr
- contained files:
  next_watch_rule_discovery.parquet
  next_watch_candidate_rules_frozen.json
  turn5_audit.json

Hashes:

- discovery rule result:
  c760e8069440cf77bd6bc99458c31c399a37de6ce4ff5af5a50f498b3b15d649
- frozen rule contract:
  07ca97658fcbfc8d0e7a5f0c8da17e3da49cc90523918606bd2a99ba1e862e4a

Next turn:

Turn 6 - Holdout validation.

Before evaluating rule performance, Turn 6 must first enforce the right-censoring
policy documented in Turn 3. Frozen conditions and thresholds above must not be
changed based on Holdout outcomes.


## 24. Turn 6 maturity gate result

Status:

HOLDOUT_VALIDATION_BLOCKED_MATURITY

Execution date:

2026-09-25

Observed formal Holdout gate:

- Turn3 observation horizon:
  2026-09-22
- Holdout start:
  2026-08-01
- maturity rule:
  Discovery-only 90th percentile of observed days_to_next_start
- Discovery q90:
  77 days
- Discovery q95:
  91 days
- q90 mature-source cutoff at the current horizon:
  2026-07-07
- formally mature Holdout rows:
  0

Interpretation:

No 2026 Holdout source row is mature under the pre-committed q90 policy yet.
Therefore the frozen 11 Turn-5 candidate rules must not be graded as S/A from
the currently observed 2026-08 through 2026-09 next-start subset.

Using only horses that have already returned by 2026-09-22 would condition the
evaluation on quick return and create the exact right-censoring / selection bias
the Turn-3 gate was designed to prevent.

The result is not rule failure. It is an unavailable formal Holdout.

Holdout outcomes were not used to retune any Turn-5 threshold.

Earliest formal q90 readiness:

- Holdout first source date:
  2026-08-01
- q90 maturity requirement:
  77 days
- minimum observation horizon:
  2026-10-17

The formal Turn-6 Holdout validation must be rerun after RaceReviewDB CURRENT
contains completed results through at least 2026-10-17 (or the next available
completed JRA date after that point).

Frozen assets remain unchanged:

- Turn-5 rules Drive ID:
  1AzhPgqr8GXei4opzbI8gD7nb4-5qZ3Zr
- rule_version:
  next-watch-rules-discovery-v0.1
- frozen rule count:
  11

Execution evidence:

- workflow run:
  36111295006
- generated audit initially reported zero mature Holdout rows; this semantic
  result is recorded here as BLOCKED_MATURITY rather than a successful
  validation.

Next action:

Do not proceed to formal S/A promotion or market-value validation from the
censored 2026 Holdout. Preserve the frozen rules and rerun Turn 6 when the
minimum observation horizon is available.


## 25. Turn 6 Historical OOS validation checkpoint

Status:

HISTORICAL_OOS_VALIDATED

Execution date:

2026-09-25

Rationale:

The original forward Holdout (2026-08 onward) remains immature under the
Discovery-only q90 next-start maturity policy. Formal validation therefore
moved to historical out-of-sample data that fully predates the 2026 Discovery
window. The frozen Turn-5 rule contract was applied unchanged.

Historical OOS source:

- source period:
  2024-01-01 through 2025-12-31
- source rows:
  91,597
- distinct source keys:
  91,597
- valid flat next-start outcomes:
  81,038
- nonfuture next-start rows:
  0
- thresholds reoptimized:
  false
- frozen rules:
  11

Validation blocks:

- 2024H1:
  source 23,949 / eligible 21,485
- 2024H2:
  source 21,488 / eligible 18,820
- 2025H1:
  source 23,686 / eligible 21,223
- 2025H2:
  source 22,474 / eligible 19,510

Historical grading policy:

- each block requires at least N=20
- HISTORICAL_S_SUPPORTED:
  all 4 blocks valid,
  at least 3 blocks retain positive top3/top5 matched-baseline direction,
  full-period top3 lift >= 5 percentage points,
  full-period top5 lift >= 3 percentage points
- HISTORICAL_A_SUPPORTED:
  at least 3 positive blocks,
  full-period top3 lift >= 3 percentage points,
  full-period top5 lift >= 0

Results:

- HISTORICAL_S_SUPPORTED:
  9 hidden-value rules
- HISTORICAL_A_SUPPORTED:
  2 persistence rules
- rejected:
  0
- insufficient sample:
  0

All 11 frozen rules retained positive top3 and nonnegative top5 lift versus
their matched source-finish baseline in all four historical blocks.

Hidden-value rules:

- HV01:
  4着以下 + performance_signal 上位20%
  historical N=5,967
  full top3 lift=+11.70 pp
  full top5 lift=+15.62 pp
  block top3 lift range=+11.17 to +12.77 pp
  status=HISTORICAL_S_SUPPORTED

- HV02:
  6着以下 + performance_signal 上位20%
  historical N=3,137
  full top3 lift=+7.77 pp
  full top5 lift=+11.10 pp
  block top3 lift range=+6.65 to +8.36 pp
  status=HISTORICAL_S_SUPPORTED

- HV03:
  4着以下 + 上がり速度percentile 90以上
  historical N=5,319
  full top3 lift=+5.43 pp
  full top5 lift=+9.40 pp
  block top3 lift range=+4.40 to +6.35 pp
  status=HISTORICAL_S_SUPPORTED

- HV05:
  4着以下 + performance上位20% + 上がり80以上
  historical N=1,725
  full top3 lift=+12.37 pp
  full top5 lift=+17.29 pp
  block top3 lift range=+10.25 to +15.37 pp
  status=HISTORICAL_S_SUPPORTED

- HV06:
  6着以下 + performance上位20% + 上がり80以上
  historical N=698
  full top3 lift=+6.96 pp
  full top5 lift=+10.33 pp
  block top3 lift range=+2.31 to +10.55 pp
  status=HISTORICAL_S_SUPPORTED

- HV07:
  4着以下 + 強い位置取り改善 + 上がり80以上
  historical N=3,037
  full top3 lift=+8.21 pp
  full top5 lift=+13.21 pp
  block top3 lift range=+6.78 to +10.46 pp
  status=HISTORICAL_S_SUPPORTED

- HV11:
  4着以下 + performance上位20% + 自身過去3走比改善
  historical N=3,304
  full top3 lift=+9.07 pp
  full top5 lift=+12.18 pp
  block top3 lift range=+8.25 to +10.35 pp
  status=HISTORICAL_S_SUPPORTED

- HV12:
  6着以下 + performance上位20% + 自身過去3走比改善
  historical N=1,764
  full top3 lift=+5.36 pp
  full top5 lift=+8.22 pp
  block top3 lift range=+3.70 to +6.26 pp
  status=HISTORICAL_S_SUPPORTED

- HV13:
  4着以下 + performance上位10% + 上がり90以上
  historical N=405
  full top3 lift=+16.27 pp
  full top5 lift=+19.98 pp
  block top3 lift range=+10.53 to +18.65 pp
  status=HISTORICAL_S_SUPPORTED

Persistence rules:

- P01:
  1-3着 + performance上位20%
  historical N=8,745
  full top3 lift=+3.33 pp
  full top5 lift=+3.32 pp
  status=HISTORICAL_A_SUPPORTED

- P03:
  1-3着 + performance上位20% + 上がり80以上
  historical N=5,911
  full top3 lift=+4.92 pp
  full top5 lift=+5.22 pp
  status=HISTORICAL_A_SUPPORTED

Interpretation:

The 2026 Discovery result is not confined to that period. The principal
hidden-value rules reproduce across four independent 2024-2025 half-year
blocks using the exact numeric thresholds frozen from 2026 Discovery.

The strongest practical candidates are not necessarily the highest raw lift.
For operational S/A design, balance strength, support and simplicity:

- HV05:
  strong combined performance + last3F, large N and stable lift
- HV01:
  simplest high-support hidden-value rule
- HV02:
  stricter defeated-horse version with large support
- HV11:
  adds within-horse improvement and remains stable
- HV13:
  strongest lift but smaller N; useful as a high-conviction subtype rather than
  the sole S definition

Forward 2026-08+ validation remains reserved as an additional prospective test
once mature; it is no longer a blocker for historical OOS conclusions.

Checkpoint artifact:

- workflow run:
  36112649509
- Drive file:
  RaceReviewDB_NextWatch_Historical_OOS_g36112649509.zip
- Drive file ID:
  1tzhV7Pp0NxuwTTvQyOYxxrWYke6ckZEU
- contained files:
  next_watch_historical_oos_fact.parquet
  next_watch_historical_oos_validation.parquet
  historical_oos_audit.json
- fact SHA256:
  38fd09adac64e1c6c82df684d923a4704e1a365f39df0a7e4528dbc51b13c969
- validation SHA256:
  fdad5dcb30ae674742f300309625d3f1c0f828bf97429c69bd30c46ae811477c

Issue history:

- #1374:
  initial request before workflow registration, closed not_planned
- #1375:
  first successful Historical OOS run, closed completed
- #1378:
  block-metric audit rerun with unchanged frozen rules, closed completed

Next turn:

Turn 7 - market-value audit.

The ability-prediction signal is now historically supported. The next question
is whether next-start popularity / odds already price that signal. Market-value
analysis must remain separate from the ability classification.


## 25. Operationalization checkpoint

Status:

NEXT_WATCH_V0_1_OPERATIONAL

Execution date:

2026-09-25

Operational interface:

- request a completed JRA source date
- run the canonical selector
- return S/A next-start attention horses
- allow zero candidates
- do not force list length

Canonical selector:

- horse-racing/jrdb/src/jrdb_next_watch_select.py

Operational contract:

- horse-racing/jrdb/docs/RaceReviewDB_NextWatch_Operation_v0_1.md

Standard grading:

- S:
  HV05/HV13 match OR at least two hidden-value frozen-rule matches
- A:
  at least one hidden-value frozen-rule match and not S
- persistence-only P01/P03:
  excluded from standard S/A

Smoke test:

- source date:
  2026-09-22
- run:
  36115281667
- source starts:
  147
- S:
  4
- A:
  10
- result:
  PASS
- Drive artifact:
  16bm8KNyDewqaakzpwkbrNUZUPuDUqf5B

The normal chat request is:

"xx/xxの次走注目馬をお願いします"

The assistant resolves the source date, executes the selector, and returns the
S/A list with concise matched-rule reasons.

The intended role is an additive evidence layer for RaceNote / RL rather than a
standalone profitability system.
