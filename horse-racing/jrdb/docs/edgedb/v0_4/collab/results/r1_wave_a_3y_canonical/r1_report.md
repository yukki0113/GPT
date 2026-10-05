# Canonical R1 Wave A 3y and R3 family decision

Status: CANONICAL_R1_ACCEPTED

Source commit: 9aba7103f944ea419189c104be4e48485b819d0d
Frozen inputs: Feature Mart 82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6; Stage B catalog cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba
Window: 2022-12-28 through 2025-12-28 inclusive
DuckDB C2A and C2B merge were run from canonical repository entrypoints. Production impact: NONE.

## PR #1800 aggregate sanity comparison

Canonical C1/C2A: 68,685 / 17,807; parent links 52,171; unique parent requests 14,129; total requests 30,733.
PR #1800 is a provisional reference; differences downstream of C1 are not treated as errors without examining canonical DuckDB output.

## Family decisions

Rates use that family’s C2 shortlist as denominator. No composite score was used.

### PEDIGREE_CROSS

Decision: `EXTEND_FROZEN_FAMILY_TO_5Y`
The largest non-jackpot incremental pool merits a frozen 5y stability check; the 3y result does not authorize depth-4 execution.

C1 41,012; C2 11,963; incremental 266 (2.22%); mixed 68 (0.57%); jackpot-dependent 11629 (97.21%); other 0.
Incremental depths D2/D3: 30 / 236; child support min/median 16 / 50; support distribution `{"count": 266, "max": 683, "median": 50, "min": 16, "p10": 23, "p90": 161}`; recent support medians 365d/730d 21 / 38; parent ROI delta min/median -117.20689655172414 / 89.26233893208628; recent direction counts 365d {'win_positive': 209, 'place_positive': 184}, 730d {'win_positive': 231, 'place_positive': 223}; temporal flags: `{"730D_DIRECTION_CONTRADICTS_FULL_3Y": 2304, "NO_RECENT_365D_SUPPORT": 53, "TOP3_EXCLUSION_REMOVES_BOTH_LANES": 11629, "VALUE_CONFINED_TO_ONE_YEAR": 153}`.

Representative conditions and child/immediate-parent metrics are in `r1_summary.json` and the <=100-row `shortlist.csv`. These are research examples, not betting recommendations.

### PEDIGREE_TRANSITION_CROSS

Decision: `KEEP_3Y_OBSERVE_ONLY`
Some incremental evidence exists, but the smaller pool and temporal/support uncertainty do not yet justify expansion.

C1 18,531; C2 4,204; incremental 81 (1.93%); mixed 17 (0.40%); jackpot-dependent 4106 (97.67%); other 0.
Incremental depths D2/D3: 2 / 79; child support min/median 11 / 32; support distribution `{"count": 81, "max": 277, "median": 32, "min": 11, "p10": 15, "p90": 85}`; recent support medians 365d/730d 11 / 24; parent ROI delta min/median -157.36363636363637 / 139.09774436090228; recent direction counts 365d {'win_positive': 61, 'place_positive': 67}, 730d {'win_positive': 73, 'place_positive': 71}; temporal flags: `{"730D_DIRECTION_CONTRADICTS_FULL_3Y": 786, "NO_RECENT_365D_SUPPORT": 13, "TOP3_EXCLUSION_REMOVES_BOTH_LANES": 4106, "VALUE_CONFINED_TO_ONE_YEAR": 72}`.

Representative conditions and child/immediate-parent metrics are in `r1_summary.json` and the <=100-row `shortlist.csv`. These are research examples, not betting recommendations.

### TRANSITION_CROSS

Decision: `STOP_FAMILY_EXPANSION`
The family is dominated by jackpot-dependent candidates and has too few non-jackpot incremental cases to justify further search.

C1 9,142; C2 1,640; incremental 20 (1.22%); mixed 5 (0.30%); jackpot-dependent 1615 (98.48%); other 0.
Incremental depths D2/D3: 0 / 20; child support min/median 47 / 112; support distribution `{"count": 20, "max": 561, "median": 112, "min": 47, "p10": 48, "p90": 521}`; recent support medians 365d/730d 39 / 69; parent ROI delta min/median -81.74501424501423 / 78.9371030735269; recent direction counts 365d {'win_positive': 15, 'place_positive': 10}, 730d {'win_positive': 18, 'place_positive': 13}; temporal flags: `{"730D_DIRECTION_CONTRADICTS_FULL_3Y": 312, "TOP3_EXCLUSION_REMOVES_BOTH_LANES": 1615, "VALUE_CONFINED_TO_ONE_YEAR": 1}`.

Representative conditions and child/immediate-parent metrics are in `r1_summary.json` and the <=100-row `shortlist.csv`. These are research examples, not betting recommendations.

## Disposition and scope

PR #1800 remains provisional and should be closed/superseded after the canonical replacement result is reviewed. PR #1801 is blocked-only documentation and should be closed as superseded. No 5-year or depth-4 execution, threshold tuning, market conditioning, SHADOW publication, or production serving change was performed.
