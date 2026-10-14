# JRDB SRB Race Lap Phase 3 Research — 2026 YTD

Status: RESEARCH / NOT PROMOTED  
Study date: 2026-10-14  
Target period: 2026-01-04 through 2026-10-12

## 1. Purpose

Phase 3 evaluates whether race-level SRB lap data adds useful information for
analysis and prediction beyond existing SED fields.

No production RaceNote score, Edge score, or prediction gate is changed by this
study.

## 2. Source and coverage

Canonical source used in this run:

- Google Drive `00_raw/SED`
- ordinary `SEDYYMMDD.zip`
- `SEDYYMMDD.txt` + bundled `SRBYYMMDD.txt`

Locally materialized in this study:

- 87 race-date ZIPs
- 2,730 races
- 37,686 horse-result rows
- 2,636 races with populated SRB lap arrays
- 94 races without SRB lap arrays

All 94 no-lap races were obstacle-surface records in this sample. No flat-race
lap-count mismatch was found: every populated SRB record matched
`ceil(distance_m / 200)`.

The locally materialized set spans 2026-01-04 through 2026-10-12.

Phase 3B re-fetched the previously missing 2026-09-06, 2026-09-12 and
2026-09-13 SED archives from JRDB and verified their SRB members. The three
dates add 84 races, 1,121 horse-result rows and 81 populated flat-race lap
arrays; the remaining three no-lap rows are obstacle races. The research
coverage is therefore complete for the identified JRA race dates through
2026-10-12.

## 3. SRB fields evaluated

Primary lap-derived features:

- first 3F leader time, only where the first segment is a full 200m
- last 3F leader time
- late-minus-early 3F delta
- lap standard deviation
- lap range
- fastest 200m lap
- largest adjacent acceleration
- largest adjacent deceleration
- last-lap minus best-lap fade
- last-3-segment slope
- fastest segment position
- official SRB pace-up remaining-furlong field when populated

Horse-relative context was also tested by combining the prior race SRB values
with SED horse-level values such as:

- prior finish / popularity / odds / IDM
- individual first 3F and last 3F
- 4th-corner position
- SED front / late / pace / race-pace indices
- prior race distance / surface / field size

## 4. Coarse SED pace vs SRB lap shape

For races with a full first 200m and an SED race pace code, mean
`last3F - first3F` was:

| SED race pace | n | mean delta |
|---|---:|---:|
| H | 781 | +1.38 s |
| M | 678 | +0.47 s |
| S | 474 | -1.01 s |

Positive means the final 3F was slower than the opening 3F; negative means a
late-acceleration shape.

The SRB early/late delta correlates with the SED race pace index at about
`r = 0.553`. This confirms meaningful overlap: SRB should not be treated as a
new independent "pace vote" and added on top of SED pace score.

However, the H/M/S groups overlap materially:

| code | P10 | P25 | median | P75 | P90 |
|---|---:|---:|---:|---:|---:|
| H | -0.60 | +0.30 | +1.30 | +2.40 | +3.30 |
| M | -1.70 | -0.70 | +0.40 | +1.60 | +2.60 |
| S | -3.57 | -2.40 | -1.00 | +0.30 | +1.40 |

Therefore the code is a useful coarse summary, but not a complete description
of lap structure.

## 5. Surface-level characterization

Across populated SRB races:

| surface | races | mean late-minus-early | mean lap SD | mean last-vs-best fade |
|---|---:|---:|---:|---:|
| turf (1) | 1,295 | -0.494 s | 0.517 s | 0.778 s |
| dirt (2) | 1,260 | +1.672 s | 0.585 s | 1.572 s |

The 2026 sample therefore shows a strong structural difference:

- turf is more often late-accelerating;
- dirt is more often early-loaded with larger terminal fade.

This is exactly why absolute lap thresholds should not be shared blindly across
surface and distance. Any future feature must be normalized by race context.

Representative distance groups with at least 20 races:

- turf 1200m: mean late-minus-early +0.98s
- turf 1600m: -0.81s
- turf 1800m: -1.12s
- turf 2400m: -1.56s
- dirt 1200m: +2.46s
- dirt 1400m: +1.96s
- dirt 1600m: +1.63s
- dirt 1800m: +1.13s

Partial-first-segment distances such as 1150m / 1500m / 1700m / 1900m /
2100m were intentionally excluded from direct opening-3F comparison because
SRB does not subdivide the first partial segment.

## 6. Optional SRB field completeness

The lap arrays themselves remained populated for flat races through the latest
2026-10-12 file in this study.

By contrast, the following optional SRB fields were populated for 2,220 races
and then became uniformly blank from 2026-08-29 onward in the materialized
files:

- pace-up remaining furlongs
- track-bias fields
- race comment

This pattern is operationally important. It may reflect upstream publication
timing or the version of SED captured by the current daily acquisition, but
this study does not establish the cause.

Before depending on these optional fields in production, compare a same-date
SED fetched immediately post-race with a later upstream copy after the JRDB
update window.

## 7. Forward predictive experiment

A chronological exploratory test was performed on horse runs having a prior
observed 2026 run.

Dataset:

- 26,054 current-run observations with a prior 2026 run
- train: through 2026-07-31, 19,011 observations
- test: 2026-08-01 through 2026-10-12, 7,043 observations

Baseline prior-run features included SED result / popularity / odds / IDM,
front-late-pace indices, race pace index, individual first/last 3F, corner
position and race conditions.

The augmented model added SRB lap-shape and horse-relative interaction features.

### 7.1 Next-run top-3 classification

XGBoost exploratory model:

| model | ROC AUC | log loss | Brier |
|---|---:|---:|---:|
| SED baseline | 0.73654 | 0.47104 | 0.15330 |
| SED + SRB context | 0.73551 | 0.47174 | 0.15353 |

Result: no improvement. Direct promotion of SRB numeric features into the main
prediction score is not supported by this 2026-only test.

### 7.2 "Beat popularity" exploratory classification

Exploratory target only: `finish < final popularity`. This is not ROI, not a
betting strategy, and not a production value label.

| model | ROC AUC | log loss | Brier |
|---|---:|---:|---:|
| SED baseline | 0.68094 | 0.63611 | 0.22303 |
| SED + SRB context | 0.68135 | 0.63555 | 0.22280 |

Result: a very small improvement appears in market-relative overperformance,
but the effect is too small and too weakly validated to promote.

## 8. Phase 3 interpretation

### Supported

SRB adds useful descriptive dimensions that coarse SED pace fields do not fully
represent:

1. where the race accelerated;
2. whether the race was smooth or highly variable;
3. how large the strongest acceleration/deceleration was;
4. whether the final segment materially faded from the race's best speed;
5. whether a horse's own final 3F / position gain occurred in a favorable or
   adverse race flow.

These are suitable as structured evidence for Race Structure / Scenario /
post-race reading.

### Not supported

The 2026 study does not support:

- adding SRB features as an independent additive score;
- double-counting SRB early/late pace on top of SED race pace index/code;
- interpreting race-level leader sectionals as individual horse sectionals;
- promoting any SRB feature to a production gate based on 2026 alone.

## 9. Recommended candidate evidence contract

For a historical race, retain these neutral race-shape facts:

- `lap_shape.early_late_delta_sec`
- `lap_shape.lap_std_sec`
- `lap_shape.fastest_lap_sec`
- `lap_shape.fastest_segment_no`
- `lap_shape.max_accel_sec`
- `lap_shape.max_decel_sec`
- `lap_shape.last_vs_best_sec`
- `lap_shape.last3_slope_sec`
- `lap_shape.pace_up_remaining_f` when present
- provenance and coverage flags

For each horse's historical run, derive interpretation above that neutral layer:

- front runner under front-loaded pressure;
- closer in a strongly late-accelerating race;
- position gain despite an unfavorable flow;
- strong individual last 3F relative to the race-level final 3F;
- apparent good/bad finish supported by unusual lap volatility.

These should initially be evidence objects / prose support, not score
components.

## 10. Next recommendation

Phase 3 result: **RESEARCH-POSITIVE FOR CONTEXT, NOT FOR DIRECT SCORING**.

Recommended next step is a Phase 3B / integration design:

1. retain the Phase 3B resolution of the three September race dates in the canonical Raw operation;
2. adopt a late-finalization policy for optional SRB enrichment after the JRDB Monday update window;
3. extend the same lap-shape extraction into historical years if SRB is present
   in annual SED archives;
4. define RaceNote-compatible structured evidence;
5. run a larger true-forward evaluation before any production promotion.
