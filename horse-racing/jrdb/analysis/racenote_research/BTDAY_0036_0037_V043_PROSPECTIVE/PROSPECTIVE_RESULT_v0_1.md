# RaceNote v0.4.3 Prospective Validation — BTDAY-0036 / 0037

Date of review: 2026-10-03

## Population

Formal prospective cohort:
- BTDAY-0036: 2026-06-27 / 36R
- BTDAY-0037: 2026-07-18 / 36R
- total: 72R

Logic:
- `RaceNote-Human-Context-Reader-0.4.3-candidate`
- RRDB: `rrdb-recommendation-signals-v0.3`

Both days:
- `FROZEN_CLEAN_BLIND`
- result_opened=false at Freeze
- validator v0.4.3 PASS
- five unique marks / axis consistency PASS
- target-day market stripped before Forecast

Excluded:
- BTDAY-0038: INVALIDATED_MARKET_EXPOSURE
- BTDAY-0039: EXCLUDED_INPUT_BINDING_VIOLATION

0039 is not part of any formal aggregate in this report.

## Forecast performance

| metric | 0036 | 0037 | combined |
|---|---:|---:|---:|
| races | 36 | 36 | 72 |
| ◎ wins | 14 (38.9%) | 11 (30.6%) | 25 (34.7%) |
| ◎ top2 | 20 (55.6%) | 19 (52.8%) | 39 (54.2%) |
| ◎ top3 | 24 (66.7%) | 25 (69.4%) | 49 (68.1%) |
| winner in five | 32 (88.9%) | 29 (80.6%) | 61 (84.7%) |
| all Top3 in five | 14 (38.9%) | 12 (33.3%) | 26 (36.1%) |

## Betting performance

100 yen per ticket.

| bet | 0036 ROI | 0037 ROI | combined ROI | combined hits |
|---|---:|---:|---:|---:|
| ◎ win | 97.2% | 82.8% | 90.0% | 25 |
| ◎○ quinella | 10.8% | 137.8% | 74.3% | 12 |
| ◎▲ quinella | 127.5% | 41.9% | 84.7% | 8 |
| ◎→○ exacta | 15.8% | 114.7% | 65.3% | 6 |
| ◎→▲ exacta | 144.7% | 62.2% | 103.5% | 5 |
| ◎-key trio 6 | 63.1% | 81.3% | 72.2% | 24 |
| ◎ first-fixed trifecta 12 | 62.4% | 104.3% | 83.4% | 13 |
| five-horse trio box 10 | 63.5% | 53.9% | 58.7% | 26 |

The two days show substantial lane variance:
- 0036 favored the ◎▲ lane.
- 0037 favored the ◎○ lane.
- pooled ◎→▲ exacta ROI is above 100%, but this is only 72R and 5 hits.

## Mechanical Hierarchy diagnostic

Winner was inside the selected five but not ◎:
- 0036: 18R
- 0037: 18R
- combined: 36/72 = 50.0%

Winner role among these 36:
- ○: 12
- ▲: 13
- △1: 7
- △2: 4

Because ▲ is an independent single-shot role, ▲ wins should not automatically be counted as hierarchy errors.

Excluding ▲ wins:
- ordinary mainline/support winner above ◎: 23/72 = 31.9%

For the v0.4.2 BTDAY-0023〜0032 baseline:
- mechanical hierarchy cases: 153/336 = 45.5%
- ▲ winner cases: 26
- non-▲ hierarchy cases: 127/336 = 37.8%

Thus the prospective v0.4.3 cohort has a lower non-▲ hierarchy-miss rate (31.9% vs 37.8%).
This is supportive of the hierarchy-consistency hypothesis, but it is not same-day A/B evidence.

## Coverage diagnostic

v0.4.3 prospective:
- coverage failure races: 46/72 = 63.9%
- missed Top3 horses: 61
- missed winners: 11
- missed seconds: 23
- missed thirds: 27
- all Top3 in five: 26/72 = 36.1%

v0.4.2 BTDAY-0023〜0032 baseline:
- coverage failure races: 251/336 = 74.7%
- missed Top3 horses: 325
- missed winners: 82
- missed seconds: 112
- missed thirds: 131
- all Top3 in five: 83/336 = 24.7%

The largest apparent improvement is winner coverage:
- v0.4.2 baseline winner miss: 82/336 = 24.4%
- v0.4.3 prospective winner miss: 11/72 = 15.3%

Second- and third-place miss rates improved only modestly.
Therefore the early gain appears stronger in selecting the winning candidate set than in completely closing podium coverage.

## Baseline comparison — primary Forecast metrics

v0.4.2 baseline BTDAY-0023〜0032 (336R):
- ◎ win: 101/336 = 30.1%
- ◎ top2: 166/336 = 49.4%
- ◎ top3: 213/336 = 63.4%
- winner in five: 254/336 = 75.6%
- all Top3 in five: 83/336 = 24.7%

v0.4.3 prospective BTDAY-0036〜0037 (72R):
- ◎ win: 34.7%
- ◎ top2: 54.2%
- ◎ top3: 68.1%
- winner in five: 84.7%
- all Top3 in five: 36.1%

All five primary Forecast metrics currently point in the favorable direction for v0.4.3.
However, the cohorts are on different dates and the prospective sample is still only 72R.

## Critical implementation diagnostic

Every one of the 72 frozen v0.4.3 records contains a `consistency_pass` audit.

Observed activation counts:
- hierarchy_changed: 0/72
- single_shot_promoted: 0/72
- coverage_changed: 0/72
- coverage_challenger non-null: 0/72

All records are effectively recorded as:
`UNCHANGED_AFTER_INDEPENDENT_REVIEW`.

This means the current prospective result cannot yet demonstrate that the three explicit v0.4.3 correction gates themselves improved the Forecast.

Possible interpretations:
1. the gates are correctly conservative and no race crossed them;
2. the model internalized the v0.4.3 principles before the provisional mark stage, so no post-pass change was necessary;
3. the operational implementation is not exposing a meaningful provisional-vs-final difference, making the change-attribution audit uninformative.

The third possibility must remain open until more BTDAYs or a stronger trace contract is observed.

## Current interpretation

Positive:
- ◎ performance is above the 0.4.2 baseline on all main hit-rate metrics.
- winner-in-five improvement is large enough to watch closely.
- full Top3 coverage is also materially higher.
- ▲ remains useful as an independent lane; 13 selected-five winners came from ▲.
- ◎→▲ exacta recovered to 103.5% in the first 72R.

Caution:
- only two clean prospective days / 72R.
- different-day cohort comparison is not causal A/B.
- the explicit v0.4.3 change gates fired zero times.
- betting ROI remains volatile between days.

## Decision

Keep `RaceNote-Human-Context-Reader-0.4.3-candidate` as the active prospective candidate.

Do not promote it to a finalized logic version yet.

Next clean target:
- add at least one more clean BTDAY to exceed roughly 100R;
- preserve the current v0.4.3 contract unchanged;
- inspect whether any consistency-pass changes actually fire;
- continue comparing primary Forecast quality before optimizing betting lanes.
