# JRDB Edge v0.3 Stage-B2 Statistical Gate Design v0.1

Status: **DRAFT / SHADOW ONLY**  
Date: 2026-09-25  
Production comparator: EdgeDB v0.2 STANDARD  
Upstream: Stage-B1 run `35955430737` / artifact `jrdb-edge-v03-incremental-shadow-35955430737`

## 1. Purpose

Stage-B1 established parent-relative raw metrics for the initial semantic hierarchy without applying a promotion threshold.

Stage-B2 must answer a different question:

> Is the child-vs-parent-complement effect statistically and temporally stable enough to be considered incremental evidence, without being explained by small comparison samples, one period, or one exceptional return?

The first B2 implementation is deliberately split into **B2a diagnostics** and a later **B2b gate freeze**.

B2a computes all diagnostics required to design the gate. It does **not** promote any Edge, build a v0.3 serving catalog, or modify v0.2 STANDARD.

## 2. Stage-B1 facts carried forward

Stage-B1 evaluated 844 currently served Performance edges across the target templates.

- `CONTEXT_ONLY`: 58
- `INSUFFICIENT`: 51
- `RAW_INCREMENTAL_METRIC`: 735

Among the 735 raw incremental rows:

- Performance direction same as current v0.2: 639
- genuinely opposite: 95
- neutral: 1

Parent-complement sample distribution:

- `<20`: 38
- `20-49`: 41
- `50-99`: 53
- `100+`: 603

This distribution is evidence that sample adequacy must be handled explicitly, but it is **not** by itself a reason to freeze a minimum-n threshold before the other diagnostics are observed.

## 3. B2a contract

### 3.1 Reproducibility first

For every B1 `RAW_INCREMENTAL_METRIC` row, B2a rebuilds calendar-year child and parent aggregates from the same immutable Warehouse generation.

The year slices must re-sum to the B1:

- child `n`
- child place hits
- child payout sum
- parent `n`
- parent place hits
- parent payout sum
- parent-complement values

Any mismatch is a hard failure.

### 3.2 Performance bootstrap CI

Performance effect remains:

`child place-rate - parent-complement place-rate`

B2a uses a deterministic **year-stratified nonparametric Bernoulli bootstrap**.

For a fixed year with `n` runners and `h` place hits, resampling the original binary outcomes with replacement is equivalent to drawing:

`Binomial(n, h / n)`

Therefore B2a can reproduce runner-level Bernoulli bootstrap behavior from sufficient statistics without materializing hundreds of thousands of runner outcomes into Python arrays.

Initial diagnostic settings:

- 2,000 bootstrap replicates
- 95% percentile CI
- deterministic seed derived from `edge_id`

These are computation settings, not serving thresholds.

### 3.3 Multiple testing

For each child vs parent-complement pair, B2a calculates a two-sided pooled two-proportion z-test p-value for Performance.

Benjamini-Hochberg q-values are then produced at two levels:

1. global across all Stage-B2a child hypotheses;
2. template-local, for diagnostics only.

No q cutoff is frozen in B2a.

The global q-value is the default candidate for future promotion control because the serving system exposes hypotheses from multiple templates together.

### 3.4 Temporal stability sensitivity

A single hard yearly minimum is not chosen in advance.

B2a reports temporal direction stability under a sensitivity grid where both child and parent-complement must have at least:

- 1 runner/year
- 5 runners/year
- 10 runners/year
- 20 runners/year

For every grid point it records:

- eligible years
- same-direction years
- opposite-direction years
- neutral years
- sign consistency
- recent-four-eligible-year sign consistency

B2b will choose the stability rule after the observed distributions are inspected.

### 3.5 Value channel remains separate

B2a does not convert Performance significance into Value evidence.

For Value it calculates descriptive, fail-closed diagnostics:

- yearly parent-relative place-ROI direction stability;
- maximum single place payout;
- maximum single payout share of child total returns;
- maximum calendar-year share of child total returns.

A Value inferential promotion gate is explicitly deferred until the return distribution behavior is inspected. This prevents a nominally high ROI driven by one exceptional payout from being promoted automatically.

## 4. B2a output

New artifact content:

- `statistical_edges.jsonl`
- `summary.json`
- B1 `summary.json`
- request/provenance
- Warehouse current reference
- materialization audit JSONs

Each `statistical_edges.jsonl` row preserves:

- Edge identity and semantic hierarchy
- current v0.2 Performance/Value signals
- B1 parent-relative metrics
- Performance p/q/bootstrap/temporal diagnostics
- Value temporal/concentration diagnostics

All rows remain `METRICS_READY`; there is no B2a promotion class.

## 5. B2b gate-freeze questions

After B2a distribution inspection, B2b must freeze explicit policy for:

1. minimum child/complement sample adequacy;
2. bootstrap CI requirement;
3. global FDR q threshold;
4. minimum temporal coverage;
5. sign-consistency requirement;
6. recent-period reversal handling;
7. return concentration ceiling or fail-closed rule;
8. Value inferential test / multiple-testing method.

The policy must be frozen before Stage-C shadow serving or target-result-aware replay tuning.

## 6. Production protection

Throughout Stage-B2:

- EdgeDB v0.2 STANDARD remains production.
- v0.3 remains `SHADOW_ONLY`.
- `edge_serving_catalog_v0_2.jsonl` is not overwritten.
- Newspaper / RaceNote production routes are unchanged.
- no arbitrary Performance + Value score is introduced.
- same semantic parent/child evidence is not added together.
