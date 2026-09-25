# RaceReviewDB Next-Watch Backtest Plan v0.1

Status: PLANNED
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
