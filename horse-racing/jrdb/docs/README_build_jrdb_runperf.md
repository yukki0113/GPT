# JRDB RunPerf feature build v0.1

## Purpose

`build_jrdb_runperf_features.py` builds the transparent Phase B candidate-input layer from the Phase A Index Base SQLite.

This stage does **not** choose the final RunPerf formula and does **not** fit Ability / Edge. Its purpose is to generate leakage-safe inputs for comparing B0 / B1 / T0-T3 / JRDB benchmarks during development walk-forward.

## Input / output

Input:

- Phase A `jrdb_index_base.sqlite`

Output:

- `jrdb_runperf.sqlite`

Main files:

- `schema/jrdb_runperf_schema_v0_1.sql`
- `src/build_jrdb_runperf_features.py`
- `src/audit_jrdb_runperf.py`
- `tests/test_build_jrdb_runperf_features.py`
- `tests/test_audit_jrdb_runperf.py`
- `src/compare_jrdb_runperf_candidates.py`
- `tests/test_compare_jrdb_runperf_candidates.py`
- `docs/README_compare_jrdb_runperf_candidates.md`

## Race representative time

v0 candidate:

- normal result means JRDB abnormal code `0` / blank and a positive finish/time
- obstacle (`race_type_code=20`) is excluded from the initial flat-race RunPerf universe
- at least three valid finishers are required
- `RaceRepresentativeTime = median(time of top 3 valid finishers)`
- `winner_time_sec = min(valid time)`

Cancelled, excluded, stopped, disqualified etc. are retained in runner rows with an exclusion status rather than silently deleted.

## Class key v0

JRDB condition codes are grouped using the source condition-group definition:

- `A1/A2/A3 -> 0`
- `04/05 -> 1`
- `08/09/10 -> 2`
- `15/16 -> 3`
- `OP -> 9`

The v0 class key is:

```text
race_type_code × condition_group_code × grade_code
```

This is a transparent initial hypothesis for ExpectedTime normalization, not a final performance claim. Alternative class representations must be compared in development before changing the locked specification.

## ExpectedTime chronology

For target date `D`:

```text
CourseBaseTime(D) = median(previous RaceRepresentativeTime | venue × surface × distance)
ClassAdjustment(D) = median(previous course residual | class_key_v0)
ExpectedTime(D) = CourseBaseTime(D) + ClassAdjustment(D)
```

The important contract is:

```text
history_date < target_date
```

All races on the same calendar date receive their ExpectedTime before **any** result from that date is added to history. Therefore an earlier race on the target day cannot leak into a later race's ExpectedTime.

Candidate history windows are fixed before validation:

- `EXPANDING`
- `ROLLING_2Y`
- `ROLLING_3Y`
- `ROLLING_5Y`

No minimum-history threshold is hard-coded at this stage. Counts and last-history dates are stored so development validation can decide coverage / shrinkage policy without confusing missing history with zero effect.

## DayTrackBias

After every ExpectedTime on a historical date is frozen:

```text
RaceBias = RaceRepresentativeTime - ExpectedTime
DayTrackBiasRaw = median(RaceBias | race_date × venue × surface)
```

DayTrackBias is therefore a `HISTORICAL_RESULT` value. It may be attached to that completed historical run when the run is later used as history for a future target, but it is not a pre-race feature for another race on that same date.

Rather than fixing one shrink coefficient before testing, the builder stores predeclared candidates:

```text
raw
k=2
k=4
k=8

shrunk_bias = raw_bias × n / (n + k)
```

These candidates are compared in development. 2024-2025 remains locked holdout.

## Runner-level candidate inputs

The builder stores:

- actual time
- winner time
- margin seconds
- margin seconds per 1000m
- finish percentile
- carried weight
- race mean carried weight
- relative carried weight
- ExpectedTime
- DayTrackBias candidates
- time residual without bias and with each bias candidate
- JRDB raw score benchmark
- JRDB IDM benchmark

Higher-is-better transparent primitives:

```text
B0 = finish_percentile
B1 = -margin_per_1000m_sec
T0 input = time_residual
J0 = JRDB raw score benchmark
J1 = JRDB IDM benchmark
```

T1/T2/T3 are **models**, not arbitrary hand sums in this builder:

```text
T1 inputs = time_residual + margin
T2 inputs = time_residual + relative carried weight
T3 inputs = time_residual + margin + relative carried weight
```

Their coefficients / normalization are learned and selected by development walk-forward rather than hard-coded here.

## Market isolation

Odds and popularity are intentionally absent from `runner_runperf_features` and `v_runperf_candidate_matrix`.

Market data remains evaluation/Value-layer material and must not enter RunPerf, Ability, or Edge construction.

## Audit gates

`audit_jrdb_runperf.py` checks at minimum:

1. SQLite integrity
2. successful build metadata
3. `history_last_date < race_date` for both course and class histories
4. duplicate primary/business keys
5. nonnegative derived margins
6. B0 percentile range
7. winner margin = 0
8. time-residual arithmetic
9. no odds/popularity columns in the RunPerf feature table
10. coverage by year and baseline method

A synthetic build must pass before a real-history build is accepted.

## Full-history acceptance

The 2010-2025 real-history audit completed successfully in Issue `#283` / Actions run `33450491990` using builder `0.1.0` and schema `0.1`.

Accepted full-history facts:

```text
race observations       55,268
runner observations    781,161
expected-time rows     221,072   (four baseline methods)
RunPerf feature rows 3,124,644   (781,161 × four methods)
day-bias rows            36,762
```

ExpectedTime coverage by baseline method was approximately 95.8%:

```text
EXPANDING   52,952 / 55,268 = 0.958095
ROLLING_2Y  52,932 / 55,268 = 0.957733
ROLLING_3Y  52,950 / 55,268 = 0.958059
ROLLING_5Y  52,950 / 55,268 = 0.958059
```

All RunPerf audit gates passed:

```text
SQLite integrity                 PASS
strict past-only history         PASS
duplicate keys                   0
negative margin violations       0
finish-percentile violations     0
winner-margin violations         0
time-residual arithmetic errors  0
market-named columns             0
```

This accepts the **candidate-input layer**, not a final RunPerf formula. The 2024-2025 rows were built and audited for structural completeness, but are not used by the development candidate comparison.

## Example

```bash
python horse-racing/jrdb/src/build_jrdb_runperf_features.py \
  --index-db /path/jrdb_index_base.sqlite \
  --out /path/jrdb_runperf.sqlite

python horse-racing/jrdb/src/audit_jrdb_runperf.py \
  --db /path/jrdb_runperf.sqlite \
  --out /path/runperf_audit.json
```

## Current validation step

The structural full-history build is accepted. Candidate selection now uses **only 2010-2023** through `compare_jrdb_runperf_candidates.py` to compare:

- history window
- DayTrackBias shrink candidate
- B0 / B1 / T0-T3 / J0 / J1

The complete protocol, adoption gates, and fitted-coefficient as-of rules are defined in `docs/README_compare_jrdb_runperf_candidates.md`.

The 2024-2025 locked holdout remains unopened for candidate selection.
