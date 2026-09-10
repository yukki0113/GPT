# JRDB Training Research Base v0.1

## Status and purpose

`JRDB Training Research Base v0.1` is the reusable SQLite research layer for
same-horse workout comparison, trainer-specific patterns, rest/training-process
patterns, and later comparison with JRDB processed workout evaluations.

It is not an Ability model, a production Edge formula, or a Value layer.

Canonical artifact filename:

```text
jrdb_training_research_2010_2025_v0_1.sqlite
```

The local file is a cache. The accepted frozen artifact is stored under the Google
Drive JRDB research/mart area and registered as `jrdb://training-research/v0.1` in
the external live Store manifest. Git retains source, schema, tests, build/audit
contracts, reports, and publication provenance; the SQLite binary is never committed.

## Source and chronology

```text
annual JRDB Raw 2010-2025
  -> Common JRDB Reader (fixed-width authority)
  -> Index Base neutral materialization
  -> Official RunPerf v0.1 (T1|EXPANDING|RAW)
  -> Training Research Base v0.1
```

The training builder does not parse Raw offsets. It projects the audited Index Base,
whose CHA/CYB/KYI/SED rows come from `src/jrdb_raw.py` through
`src/jrdb_index_base_adapter.py`.

Time split is fixed:

- 2010–2012: `WARMUP`
- 2013–2023: `DEVELOPMENT`
- 2024–2025: `HOLDOUT`

The holdout rows include outcome storage for later Controller-authorized evaluation.
Current predictive analysis must not read, aggregate, rank, correlate, compare, or
summarize those outcome columns. `analyze_jrdb_training_stage1b.py` enforces this by
selecting only 2010–2023 and asserting the maximum selected year is 2023.

## Schema boundary

`training_runner` is one row per `race_key + horse_no`. It includes:

- race and horse identity;
- race context and rest/rotation context;
- raw-derived CHA workout facts and separate JRDB CHA indices;
- raw-derived CYB pattern facts and separate JRDB CYB processed evaluations;
- KYI processed training fields retained only for later comparison;
- result and Official RunPerf labels;
- row-level member/hash provenance plus build/schema/Git provenance.

Odds, popularity and payouts are excluded. A later Value layer may join market data
without contaminating this explanatory research base.

The schema also exposes `v_training_development` and a deliberately outcome-free
`v_training_holdout_locked`.

## Index policy

The compact index set supports the expected recurring access paths:

- horse chronology;
- horse + CHA course + furlong chronology;
- trainer chronology and trainer + course chronology;
- year scans;
- rest/rotation exploration;
- CYB course-use exploration.

The audit captures `EXPLAIN QUERY PLAN` for the primary comparable-workout lookup.
Additional indices require measured query benefit and file-size review.

## Build and audit

Full construction is Actions-Native because it requires JRDB credentials, all 16 Raw
years, a long-running RunPerf chain, immutable artifacts, and a formal run record.

Issue prefix:

```text
[JRDB_TRAINING_RESEARCH] <request_id>
```

The workflow performs:

1. focused Common Reader/Index Base and holdout-lock tests;
2. annual Raw fetch for BAC/KYI/CHA/CYB/SED/UKC, 2010–2025;
3. Index Base build and audit;
4. Official RunPerf v0.1 build and audit;
5. Training Research Base build;
6. Raw/SQLite/chronology/provenance/coverage/market audit;
7. Stage 1b development-only evidence generation;
8. separate SQLite and report artifact upload.

`training_research_build_audit.json` includes Raw ZIP integrity, fixed-record-length
errors, duplicate business keys, identity joins, missing identity, future training
dates, chronology, Official RunPerf provenance, CHA/CYB/trainer/rest coverage,
year/split counts, nonfinite values, market contamination, indices, and the holdout
policy marker.

## Stage 1b frozen analysis contract

Feature:

```text
same horse_id
+ same CHA course_code
+ same furlong_count
+ strictly prior race dates
```

For current final segment time `x` among `n` prior comparable times:

```text
self_percentile = (
  count(prior_time > x) + 0.5 * count(prior_time == x)
) / n
```

Higher is faster. Transparent companions are prior median minus current time and
previous comparable time minus current time.

Outcome:

```text
current Official RunPerf v0.1
- median(strictly-prior scored Official RunPerf for the same horse)
```

The baseline requires at least three prior scored RunPerf rows. The primary result
requires at least three prior comparable workouts; thresholds 2, 3, 4, 5, 6, 8 and
10 are all reported. The report includes fixed self-percentile quintiles, fastest
20% versus slowest 20%, Spearman associations, standardized effect size, same-horse
paired comparison, sample sizes, and 2013–2023 annual stability.

JRDB workout/finish indices, KYI training score, odds, popularity and payouts are not
Stage 1b predictors. No automated result can authorize Production adoption.

## Stage 2 readiness

The same central row supports trainer × course/type/rest/effort/pair-work/volume and
one-week-ago-to-final-workout exploration without rebuilding Raw. Stage 2 still needs
a Controller-frozen multiple-testing, minimum-sample, temporal-validation and
shrinkage policy before pattern mining begins.

