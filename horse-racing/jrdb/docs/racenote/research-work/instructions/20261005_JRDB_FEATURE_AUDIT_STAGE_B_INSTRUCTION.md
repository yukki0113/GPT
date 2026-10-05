# JRDB Feature Audit — Stage B Instruction

Status: **READY FOR EXECUTION**  
Date: 2026-10-05  
Research lane: RaceNote 0.5.x candidate research  
Active prediction cohort: v0.4.6 unchanged  
Depends on: Stage A audit ACCEPT_WITH_NOTES

## Objective

Measure the practical predictive behavior of current-race JRDB pre-race indices and ordinal evaluations over the recent three-year window.

Primary question:

> Which JRDB-provided fields show stable, monotonic and practically useful relationships with race outcomes, and which appear weak, redundant or mostly market-priced?

This is an audit, not a new forecasting model.

Do not modify the active Reader or prediction logic.

## Historical window

Analyze only:

**2023-01-01 through 2025-12-31**

Do not extend to 2021-2025 in this stage.

A five-year extension requires a separate Stage B2 instruction after audit.

Do not use 2026 BTDAY outcomes for feature selection.

## Primary feature scope

Start from the accepted Stage A inventory, but expand grouped conceptual rows into stable scalar/ordinal leaf features.

Priority families:

### Ability / composite

- IDM
- total index
- information index
- jockey index
- stable index
- longshot index
- jockey expected top-two rate

### Pace / position

Expand independently:

- front index
- pace index
- late index
- position index
- corresponding ranks
- projected mid-race order/margin/lane
- projected last-3F order/margin/lane
- projected finish order/margin/lane
- start index
- late-break rate
- running style where meaningful as categorical context

### Suitability / class

Evaluate as ordinal/categorical where semantics are established:

- JRDB class
- distance fit
- surface fit
- heavy-track fit
- race-condition-relevant JRDB categories

Do not invent numeric ordering for categories whose official order is unknown.

### Training / condition

Keep distinct sources separate:

- KYI training index
- training arrow
- improvement code
- stable evaluation
- CHA workout clock indices
- CHA workout context where an ordered interpretation is known
- CYB training index
- CYB condition index
- farm rank / farm-index rank

Do not collapse KYI / CHA / CYB training information into one synthetic score.

### JRDB marks

Analyze each mark dimension separately as categorical/ordinal evidence.

Do not treat "has any JRDB mark" as one composite unless explicitly reported as a secondary diagnostic.

## Deferred from primary Stage B

Do not include these in the main feature ranking:

- free-text comments;
- horse/jockey/trainer names as identity features;
- RaceNote historical_profile;
- race_trends;
- pedigree_context;
- older_runs as a container;
- recent_runs as a container;
- field.context;
- optional PACI fields with unresolved lineage.

They may be noted for later research, but do not let them expand this stage.

## Step 0 — source and coverage preflight

Before expensive aggregation, establish how each scalar candidate can be reconstructed historically for 2023-2025.

For every feature report:

- canonical source;
- exact leaf field;
- rows available;
- races covered;
- horses covered;
- missing percentage;
- first/last covered date;
- year-by-year coverage;
- whether the value is truly pre-race for the target race.

Fail closed on uncertain target-race leakage.

Do not silently impute missing values.

Do not substitute another field because names look similar.

If a source family is unavailable for a material share of the three years, retain it in the coverage report but exclude it from comparative ranking unless the report clearly labels the reduced sample.

## Outcome / market evaluation source

Use canonical historical result data for:

- finish;
- win payout;
- place payout;
- final win odds;
- final win popularity.

These are evaluation/control variables only.

They must never be joined back as feature inputs.

Join using stable race/horse identity keys.

## Scalar feature transformations

For continuous numeric features, produce at least:

1. raw-value distribution and missingness;
2. within-race rank;
3. within-race percentile where practical;
4. top-1 / top-3 / top-5 flags;
5. gap from race median;
6. gap from second-best for race leader where meaningful.

For provider-supplied rank fields, analyze the supplied rank directly and compare it with rank reconstructed from its numeric counterpart where both exist.

For ordinal/categorical features, use provider semantics without inventing unsupported numeric distances.

## Core outcome metrics

For each analyzable feature/view report:

- sample size;
- race count;
- win rate;
- top-2 rate;
- top-3 rate;
- win ROI;
- place ROI.

Use consistent betting-denominator semantics and document them.

For rank/bucket views, include counts for every bucket. Do not suppress weak buckets.

## Monotonicity

For ordered numeric/rank features, determine whether stronger values correspond consistently to better outcomes.

At minimum provide:

- ordered bucket outcome table;
- monotonic direction;
- number of monotonic violations;
- a simple monotonicity score or rank-correlation statistic;
- year-by-year version of the same direction.

Do not declare a feature "strong" from one extreme bucket alone.

## Year-to-year stability

Every headline finding must show:

- 2023
- 2024
- 2025
- 2023-2025 combined

Flag features where the combined result hides inconsistent yearly direction.

A feature should not be recommended as foundational if one year reverses direction without a plausible sample explanation.

## Market independence

A high raw win rate is insufficient.

Evaluate whether a feature adds separation inside broad final-popularity groups.

At minimum use practical popularity strata such as:

- 1-3
- 4-6
- 7-9
- 10+

Adjust bins only if sample sizes require it; document any change.

For each important feature, compare outcome rates within popularity strata.

Also report whether within-race feature rank is strongly correlated with final popularity.

Do not optimize a predictive model against final odds/popularity.

The purpose is descriptive market-independence audit only.

## Redundancy

For numeric features with sufficient common coverage, measure pairwise overlap using appropriate descriptive statistics:

- Spearman correlation;
- top-1 overlap;
- top-3 overlap.

Highlight likely redundancy groups, especially:

- IDM / total / information indices;
- jockey index / expected top-two rate;
- pace numeric values / supplied ranks;
- KYI / CHA / CYB training measures;
- index values / corresponding JRDB marks.

Do not drop anything automatically.

## Broad conditional slices

Keep conditional analysis deliberately coarse.

Required where sample size is adequate:

- turf / dirt / obstacle;
- sprint / mile / middle / staying distance bands;
- new/maiden vs allowance vs open/graded;
- field-size bands.

Do not explode immediately into venue x exact-distance x class combinations.

If a feature looks condition-specific, record the finding for later Stage C rather than recursively mining smaller slices.

## Evidence tiers in the report

Stage B may assign descriptive research labels only:

- STRONG_STABLE
- MODERATE_STABLE
- CONDITIONAL
- MARKET_PRICED
- REDUNDANT_CANDIDATE
- WEAK_OR_UNSTABLE
- INSUFFICIENT_COVERAGE

These labels are report summaries, not active Reader behavior.

Do not create KEEP/HIDE production recommendations yet; those belong to Stage C.

## Statistical restraint

Do not perform exhaustive threshold optimization.

Do not search hundreds of cut-points and report only the best one.

Prefer predeclared ranks, quantiles and broad buckets.

Where many features are compared, clearly distinguish exploratory observations from robust repeated patterns.

The purpose is to understand the data, not maximize in-sample ROI.

## Required artifacts

Create a reproducible Stage B analysis pipeline and machine-readable results.

Preferred outputs:

- scalar feature catalog derived from Stage A;
- coverage report;
- overall feature metric table;
- year-by-year metric table;
- market-stratified metric table;
- redundancy matrix / pair table;
- broad conditional-slice table;
- Markdown Stage B report.

Store large analytical tables in an efficient machine-readable format appropriate for the repository; do not paste huge tables into Markdown.

The Markdown report belongs in:

`docs/racenote/research-work/reports/`

Use a dated name matching the research-work convention.

## Report requirements

The Stage B report must clearly answer:

1. Which fields have sufficient 2023-2025 coverage?
2. Which show the cleanest monotonic outcome relationship?
3. Which are stable across all three years?
4. Which appear mostly explained by market popularity?
5. Which overlap strongly with other fields?
6. Which appear useful only under broad conditions?
7. Which are weak or unstable despite sounding intuitively useful?
8. Is the three-year evidence sufficient for Stage C, or is Stage B2 (2021-2025) genuinely needed?

Include a concise table of the most important findings, but preserve all machine-readable outputs for audit.

## Stop / extension rule

At the end of Stage B, choose exactly one recommendation:

### PROCEED_STAGE_C

Three years provide enough stable evidence to discuss Reader prioritization/redundancy.

### REQUEST_STAGE_B2

Only when important candidate features remain genuinely ambiguous because of coverage/sample instability that two extra years could reasonably resolve.

### NO_FIXED_HIERARCHY_SIGNAL

Three-year sample is already substantial and no stable practical priority emerges. In this case, do not automatically request more years merely to search for significance.

The audit thread will decide whether Stage B2 is warranted.

## Non-goals

Do not:

- edit active v0.4.6 Reader exposure;
- edit v0.4.6 prediction prompts/logic;
- create a new weighted score;
- train a prediction model;
- optimize thresholds for ROI;
- use 2026 clean-blind results;
- automatically expand to five years;
- infer official JRDB formulas that are not documented.

## Acceptance criteria

Stage B is acceptable only if:

- analysis is reproducible;
- input features are strictly pre-race;
- scalar leaves are evaluated independently;
- coverage is explicit;
- 2023/2024/2025 are shown separately;
- market independence is evaluated without using market as a predictor;
- redundancy is quantified;
- broad conditional slices are controlled;
- no active v0.4.6 behavior changes;
- the final report makes a clear Stage C / Stage B2 / no-fixed-hierarchy recommendation.
