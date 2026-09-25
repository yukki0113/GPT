# RaceNote Gen0.3 two-day blind rehearsal review

Date: 2026-09-25
Target days:
- 2026-07-25
- 2026-07-26

Venues:
- 中京
- 新潟
- 札幌

Total races: 72

## 1. Rehearsal contract

Both days were processed with the same unchanged rehearsal author profile:

`DayRehearsal-v0.1`

For both days the complete sequence was:

```text
daily RaceNote
→ 36/36 Prepare
→ Synthesis
→ Pairwise
→ Scenario
→ Forecast
→ Freeze
──────── result firewall boundary ────────
→ result open
→ full-day audit
```

No result from the target day was opened before all 36 Forecasts had passed Freeze.

### 2026-07-25
- Prepare run: `36122714800`
- Author/Freeze run: `36144321824`
- frozen_at: `2026-09-25T23:00:00+09:00`
- 36/36 PASS

### 2026-07-26
- Prepare run: `36145885805`
- Author/Freeze run: `36146023728`
- frozen_at: `2026-09-25T23:20:00+09:00`
- 36/36 PASS

## 2. Day-by-day comparison

| metric | 2026-07-25 | 2026-07-26 |
|---|---:|---:|
| races | 36 | 36 |
| axis wins | 8 (22.2%) | 3 (8.3%) |
| axis top2 | 12 (33.3%) | 5 (13.9%) |
| axis top3 | 17 (47.2%) | 12 (33.3%) |
| winner mean forecast rank | 4.89 | 5.19 |
| winner median forecast rank | 4 | 4 |
| winner in forecast top3 | 16 (44.4%) | 15 (41.7%) |
| winner in forecast top5 | 23 (63.9%) | 22 (61.1%) |
| mean top3 overlap | 1.17 | 0.92 |
| mean actual podium in forecast top5 | 1.69 | 1.61 |
| mean top5 overlap | 2.69 | 2.61 |
| mean Spearman | +0.202 | +0.187 |
| median Spearman | +0.254 | +0.220 |
| mean absolute rank error | 3.56 | 3.59 |

The axis metrics moved sharply between days, while winner candidate-set metrics and full-order rank correlation were much more stable.

## 3. 72-race aggregate

Axis:
- wins: 11 / 72 = 15.3%
- top2: 17 / 72 = 23.6%
- top3: 29 / 72 = 40.3%

Winner location:
- mean frozen forecast rank: 5.04
- median frozen forecast rank: 4
- winner in forecast top3: 31 / 72 = 43.1%
- winner in forecast top5: 45 / 72 = 62.5%

Candidate-set coverage:
- mean forecast-top3 vs actual-top3 overlap: 1.04 / 3
- top3 overlap distribution:
  - 0/3: 12 races
  - 1/3: 47 races
  - 2/3: 11 races
  - 3/3: 2 races
- mean actual podium horses inside forecast top5: 1.65 / 3
- mean forecast-top5 vs actual-top5 overlap: 2.65 / 5

Full-order:
- mean Spearman: +0.194
- median Spearman: +0.242
- mean absolute rank error: 3.58

## 4. Evidence coverage across 72 races

Distribution:
- FULL_TOP_LANE_EVIDENCE: 33
- PARTIAL_TOP_LANE_EVIDENCE: 31
- INSUFFICIENT: 7
- ABILITY_FALLBACK_ONLY: 1

### FULL_TOP_LANE_EVIDENCE — 33 races
- axis win rate: 18.2%
- axis top3 rate: 36.4%
- winner mean forecast rank: 4.82
- winner in forecast top3: 48.5%
- winner in forecast top5: 60.6%
- mean top3 overlap: 0.91
- mean Spearman: +0.194
- mean absolute rank error: 3.66

### PARTIAL_TOP_LANE_EVIDENCE — 31 races
- axis win rate: 12.9%
- axis top3 rate: 41.9%
- winner mean forecast rank: 4.94
- winner in forecast top3: 41.9%
- winner in forecast top5: 67.7%
- mean top3 overlap: 1.10
- mean Spearman: +0.210
- mean absolute rank error: 3.64

### INSUFFICIENT — 7 races
Small sample.
- axis win rate: 14.3%
- winner mean forecast rank: 6.57
- winner in forecast top5: 42.9%
- mean Spearman: +0.120

### ABILITY_FALLBACK_ONLY — 1 race
No inference from one sample.

## 5. Scenario robustness across 72 races

Distribution:
- ROBUST: 61
- CONDITIONAL: 11

### ROBUST — 61 races
- axis win rate: 13.1%
- axis top3 rate: 41.0%
- winner mean forecast rank: 5.13
- winner in forecast top5: 60.7%
- mean Spearman: +0.194

### CONDITIONAL — 11 races
- axis win rate: 27.3%
- axis top3 rate: 36.4%
- winner mean forecast rank: 4.55
- winner in forecast top5: 72.7%
- mean Spearman: +0.197

The day split is important:
- on 2026-07-25, CONDITIONAL happened to perform very strongly;
- on 2026-07-26, CONDITIONAL produced zero axis wins and much weaker ordering.

Therefore the two-day rehearsal reinforces:
`scenario_axis_robustness != forecast confidence`

Neither ROBUST nor CONDITIONAL should currently promote/suppress marks or probabilities.

## 6. What replicated across both days

The following behavior was comparatively stable:

### 6.1 Winner candidate-set placement
Winner median forecast rank was 4 on both days.

Winner-in-top5 rate:
- 63.9% on 07-25
- 61.1% on 07-26
- 62.5% across 72 races

This is much more stable than axis win rate.

### 6.2 Weak positive full-order information
Mean Spearman:
- +0.202 on 07-25
- +0.187 on 07-26
- +0.194 across 72 races

Mean absolute rank error:
- 3.56
- 3.59
- 3.58 combined

The near-identical day-level values suggest the rehearsal profile carries a small but repeatable amount of full-field ordering information.

### 6.3 Exact podium ordering is not the current strength
Only 2 of 72 races had exact 3/3 forecast-top3 / actual-top3 set overlap.

Most races were 1/3 overlap:
- 47 / 72

This again favors evaluation of candidate-set quality separately from exact-order quality.

## 7. What did NOT replicate

### 7.1 Axis hit rate
Axis wins:
- 22.2% on 07-25
- 8.3% on 07-26

This is too unstable to treat the current rank-1 choice as a calibrated confidence output.

### 7.2 Scenario status performance
The apparent strength of CONDITIONAL on the first day disappeared on the second day.

Scenario status remains descriptive sensitivity metadata only.

### 7.3 FULL evidence superiority
FULL_TOP_LANE_EVIDENCE did not dominate PARTIAL consistently.

Across 72 races:
- FULL had better axis win rate;
- PARTIAL had better winner-top5 rate, top3 overlap, and Spearman.

Thus:
`field_evidence_summary.status != forecast quality score`

It describes coverage, not guaranteed discrimination quality.

## 8. Interpretation of DayRehearsal-v0.1

The two-day result suggests the deterministic rehearsal author profile is not random:
- winner median rank repeatedly lands around 4;
- winner top5 coverage is repeatedly around 60%+;
- full-order Spearman repeatedly lands around +0.19 to +0.20.

But it is not a strong rank-1 selector:
- axis performance varies materially by day;
- podium ordering remains weak.

The main separation should remain:

```text
candidate-set quality
!= single-axis confidence
!= exact-order quality
!= evidence coverage
!= scenario robustness
```

## 9. Engineering decision after 72 blind races

Keep unchanged:
- result firewall
- General Evidence
- field_evidence_summary
- Synthesis
- Pairwise
- SLOW / MEDIUM / FAST scenario audit
- semantic Freeze
- day-level batch Prepare
- day-level batch Author / Freeze
- DayRehearsal-v0.1 for further controlled rehearsal only

Do NOT yet change from these 72 races:
- Ability weighting
- pace-pressure threshold formula
- marks based on ROBUST/CONDITIONAL
- automatic confidence promotion
- FULL/PARTIAL status weighting
- venue-specific ranking rules

## 10. Next research target

The 72-race sample is now large enough to stop asking only:
`does the pipeline run?`

The next useful analysis is:
`where does rank-1 selection lose information while top5 candidate selection remains useful?`

Specifically, compare the frozen rank-1 horse against:
- frozen ranks 2-5,
- the actual winner,
- Data Trend direction,
- RaceReview direction,
- Ability gap,
- pairwise decisive lane,
- position variability,
- scenario sensitivity.

The next design change, if supported, should target the transition from:
`useful candidate cluster → forced single axis`

rather than globally rewriting the evidence or pace model.
