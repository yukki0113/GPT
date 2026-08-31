# JRDB RunPerf development comparison

## Purpose

`compare_jrdb_runperf_candidates.py` selects the RunPerf family used as the historical one-run performance target for the PWA independent-index project.

RunPerf means **ability actually demonstrated in one completed run**. The comparison therefore does not choose a score merely because it reproduces the same race finish order. It measures whether the completed-run score remains informative at the horse's literal next chronological start.

## Time split

The comparator is intentionally restricted to:

- 2010-2012: warm-up / coefficient history
- 2013-2023: development walk-forward
- 2024-2025: locked holdout, rejected by the comparator

For example:

```text
2013 test <- next-start pairs ending in 2010-2012
2014 test <- next-start pairs ending in 2010-2013
...
2023 test <- next-start pairs ending in 2010-2022
```

T1-T3 coefficients are re-estimated for every test year. A test year's outcomes never enter its own coefficients.

## Pair definition

One evaluation row links a completed run to the **literal next chronological start for the same `horse_id`**.

The pair is evaluated only when the next start has a valid finish percentile. An abnormal next start is not skipped in order to reach a later convenient result.

The score on the previous run may use completed historical-result information such as the completed day's DayTrackBias. It may not use any information from the target next race.

## Candidate families

Benchmarks:

- `B0`: finish percentile
- `B1`: negative margin per 1000m; higher is better
- `J0`: JRDB raw score benchmark
- `J1`: JRDB IDM benchmark

Independent time families:

- `T0`: TimeResidual
- `T1`: TimeResidual + margin
- `T2`: TimeResidual + relative carried weight
- `T3`: TimeResidual + margin + relative carried weight

For T0-T3, all of the following baseline windows are compared:

- `EXPANDING`
- `ROLLING_2Y`
- `ROLLING_3Y`
- `ROLLING_5Y`

Each is crossed with five DayTrackBias forms:

- `NO_BIAS`
- `RAW`
- `K2`
- `K4`
- `K8`

The full standard comparison therefore contains 84 candidates: four B/J benchmarks plus 80 T-family variants.

## T1-T3 coefficient fitting

The coefficients are not fixed by hand.

For each development test year, OLS with an intercept is fitted from prior-year next-start pairs only, using next-start finish percentile as the fitting target. Moore-Penrose inversion is used only to keep the tiny normal equations stable under collinearity.

This fitting is used to estimate how much time, margin and relative carried weight in a completed run reflect persistent demonstrated ability. The coefficient history is saved in the full report.

## Evaluation metrics

Primary comparison uses equal-year averages so one high-volume year cannot dominate.

For each test year the comparator records:

- Spearman correlation with next-start finish percentile
- Spearman correlation with next-start margin score
- their mean as `primary_rank_score`
- Pearson correlation with next-start finish percentile
- coverage
- top-score horse win rate and top-3 rate in target races with at least three candidate horses

A secondary comparable-condition subset is also recorded:

```text
same surface
AND absolute distance change <= 400m
```

The standard ranking key is:

1. mean `primary_rank_score`
2. mean comparable-condition rank score
3. lower year-to-year standard deviation

## Adoption gates

The ranking is evidence, not an automatic promotion rule. A candidate becomes the provisional official RunPerf only after all of the following are reviewed together:

1. **Development rank**: it must be competitive on the equal-year primary score, not merely on one pooled high-volume period.
2. **Year stability**: the direction should be broadly stable across 2013-2023. A tiny mean advantage supported by only a few strong years is not enough.
3. **Coverage**: an apparent gain caused mainly by evaluating a much smaller and easier subset is not accepted without a separate missingness explanation.
4. **Comparable-condition validity**: performance should remain sensible on the same-surface, distance-within-400m subset where next-start condition change is smaller.
5. **Benchmark gap**: B0/B1 and JRDB J0/J1 are retained as references. JRDB may win the benchmark comparison, but that does not silently turn it into an independent core input; provenance and incremental value remain explicit.
6. **Complexity discipline**: when two independent candidates are practically tied, prefer the simpler and more interpretable specification.
7. **Coefficient stability**: for T1-T3, inspect walk-forward coefficient sign and magnitude by year. An unstable coefficient that flips repeatedly is a warning even if mean rank is high.
8. **Holdout discipline**: 2024-2025 remain unopened during this choice. They are used only after the development choice and decision rule have been frozen.

No single numeric cutoff is hard-coded before seeing the development distribution. Any tolerance used to define a practical tie must be derived from year-to-year development variation and documented before the holdout is opened.

## Market isolation

Odds and popularity are not inputs. The RunPerf database is separately audited for market-named columns before comparison.

## Execution

Create an issue such as:

```text
[JRDB_RUNPERF_COMPARE] development-2013-2023-v0.1
```

with body:

```json
{
  "development_start": 2013,
  "development_end": 2023,
  "methods": ["EXPANDING", "ROLLING_2Y", "ROLLING_3Y", "ROLLING_5Y"]
}
```

The workflow performs:

```text
JRDB Raw 2010..development_end
-> Index Base build + audit gate
-> RunPerf feature DB build + audit gate
-> development walk-forward comparison
-> full JSON artifact + compact Issue result
```

The workflow parser and comparator both reject 2024-2025 development requests.
