# RaceNote Gen0.3 2026-07-25 one-day blind rehearsal review

Date: 2026-09-25
Target day: 2026-07-25
Venues: 札幌 / 新潟 / 中京
Race count: 36

## 1. Rehearsal contract

The whole day was processed under the result firewall.

Flow:

```text
daily RaceNote source
→ 36/36 Gen0.3 Prepare
→ day rehearsal Synthesis
→ Pairwise
→ Scenario
→ Forecast
→ Freeze
──────── result firewall boundary ────────
→ result open
→ 36-race audit
```

Freeze completed before any 2026-07-25 target result was opened.

Day author profile:
`DayRehearsal-v0.1`

This profile is rehearsal-only. It is not promoted to the normal single-race GPT authoring path.

Frozen artifact:
- run: `36144321824`
- artifact: `racenote-gen0-3-day-author-36144321824`
- frozen_at: `2026-09-25T23:00:00+09:00`
- race_count: 36
- Freeze validation: 36/36 PASS

## 2. Evidence coverage

Pre-freeze field evidence distribution:

- FULL_TOP_LANE_EVIDENCE: 15
- PARTIAL_TOP_LANE_EVIDENCE: 16
- ABILITY_FALLBACK_ONLY: 1
- INSUFFICIENT: 4

31/36 races therefore contained at least some directional Data Trend and/or RaceReview evidence.

This is materially different from the earlier single-race cohort, which was heavily weighted toward ABILITY_FALLBACK_ONLY cases.

## 3. Result sources

Post-freeze result audit used:
- 2026-07-25/26 JRA result/refund CSV for podium cross-check
- JRDB SED backfill for full finishing order

Four runners had non-normal SED status. Full-rank metrics exclude runners without a positive SED finishing rank for that race.

## 4. Day-level metrics

Axis / ◎:
- wins: 8 / 36 = 22.2%
- top2: 12 / 36 = 33.3%
- top3: 17 / 36 = 47.2%

Winner location in frozen order:
- mean forecast rank: 4.89
- median forecast rank: 4
- winner in forecast top3: 16 / 36 = 44.4%
- winner in forecast top5: 23 / 36 = 63.9%

Candidate-set coverage:
- mean forecast-top3 vs actual-top3 overlap: 1.17 / 3
- top3 overlap distribution:
  - 0/3: 4 races
  - 1/3: 24 races
  - 2/3: 6 races
  - 3/3: 2 races
- mean number of actual podium horses inside forecast top5: 1.69 / 3
- mean forecast-top5 vs actual-top5 overlap: 2.69 / 5

Full-order metrics:
- mean Spearman: +0.202
- median Spearman: +0.254
- mean absolute rank error: 3.56

Axis actual-rank distribution:
- 1st: 8
- 2nd: 4
- 3rd: 5
- 4th: 6
- 5th: 2
- 6th: 1
- 7th: 3
- 8th: 3
- 9th: 1
- 10th: 1
- 12th: 1
- 15th: 1

## 5. Evidence-status split

### FULL_TOP_LANE_EVIDENCE — 15 races
- axis win rate: 33.3%
- axis top3 rate: 53.3%
- winner mean forecast rank: 4.47
- winner in forecast top3: 53.3%
- winner in forecast top5: 60.0%
- mean top3 overlap: 1.00
- mean actual podium in forecast top5: 1.40
- mean Spearman: +0.213
- mean absolute rank error: 3.58

### PARTIAL_TOP_LANE_EVIDENCE — 16 races
- axis win rate: 12.5%
- axis top3 rate: 37.5%
- winner mean forecast rank: 4.75
- winner in forecast top3: 43.8%
- winner in forecast top5: 68.8%
- mean top3 overlap: 1.31
- mean actual podium in forecast top5: 1.94
- mean Spearman: +0.217
- mean absolute rank error: 3.62

### ABILITY_FALLBACK_ONLY — 1 race
Single sample only; no inference.
- axis win: 0
- winner forecast rank: 5
- mean Spearman: +0.233

### INSUFFICIENT — 4 races
Very small sample; no stable inference.
- axis win rate: 25.0%
- winner mean forecast rank: 7.0
- mean Spearman: +0.093

## 6. Scenario robustness split

ROBUST:
- 31 races
- axis win rate: 16.1%
- axis top3 rate: 45.2%
- winner mean forecast rank: 5.35
- winner in forecast top3: 38.7%
- winner in forecast top5: 58.1%
- mean Spearman: +0.166

CONDITIONAL:
- 5 races
- axis win rate: 60.0%
- axis top3 rate: 60.0%
- winner mean forecast rank: 2.0
- winner in forecast top3: 80.0%
- winner in forecast top5: 100%
- mean Spearman: +0.429

The CONDITIONAL sample is only five races and must not be interpreted as evidence that CONDITIONAL is superior.

The important conclusion remains:
`scenario_axis_robustness != forecast confidence`

ROBUST only means the authored axis survives the modeled SLOW/MEDIUM/FAST scenario family.

## 7. Venue split

中京:
- axis wins: 4 / 12
- winner mean forecast rank: 3.58
- winner in forecast top5: 83.3%
- mean Spearman: +0.211

新潟:
- axis wins: 1 / 12
- winner mean forecast rank: 6.00
- winner in forecast top5: 58.3%
- mean Spearman: +0.158

札幌:
- axis wins: 3 / 12
- winner mean forecast rank: 5.08
- winner in forecast top5: 50.0%
- mean Spearman: +0.238

These venue differences are descriptive only. One day is far too small to create venue-specific rules.

## 8. Main findings

### 8.1 Day-scale operation is technically viable

The pipeline successfully processed:
- 36 RaceNote bundles
- one RaceReviewDB download
- 36 Prepare stages
- 36 Synthesis validations
- 36 Pairwise validations
- 36 Scenario validations
- 36 Forecast validations
- 36 Freeze audits

A day no longer requires 36 separate manual Issue chains.

### 8.2 Evidence availability alone does not solve ranking

31/36 races had directional top-lane evidence, but mean Spearman was only +0.202 and the winner median forecast rank was 4.

FULL_TOP_LANE_EVIDENCE was better than PARTIAL in axis win rate, but not consistently better in candidate-set coverage or Spearman.

Therefore:
`more evidence coverage != automatically better ordering`

Coverage is necessary context, not a quality score.

### 8.3 Candidate-set quality is stronger than exact-order quality

The winner was in the frozen top5 in 23/36 races, while exact axis wins were 8/36.

This supports continuing to track:
`candidate-set quality != single-axis confidence != full-order quality`

These must remain separate evaluation dimensions.

### 8.4 Robustness still must remain orthogonal

The one-day cohort reinforces the five-race conclusion that ROBUST must not upgrade the axis automatically.

No mark or probability rule should be changed from robustness alone.

## 9. Important limitation of this rehearsal

`DayRehearsal-v0.1` used one deterministic qualitative author profile for all 36 races.

It preserved the existing lane priority:
`DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR`

but it necessarily compressed GPT's race-by-race semantic reading into a consistent rehearsal authoring rule.

Therefore this run measures two things together:
1. Gen0.3 evidence/contract behavior at day scale
2. the quality of the rehearsal author profile

It must not be treated as a pure estimate of the eventual production GPT forecast accuracy.

## 10. Current engineering decision

Keep:
- Gen0.3 firewall
- General Evidence
- field_evidence_summary
- All-Runner Synthesis
- Pairwise
- SLOW/MEDIUM/FAST Scenario
- Freeze / semantic hash
- separate evidence coverage and scenario robustness labels
- day-level batch Prepare infrastructure

Do NOT yet change:
- Ability weighting
- pace-pressure thresholds
- mark suppression/promotion
- ROBUST/CONDITIONAL definitions
- venue-specific rules
- automatic confidence promotion
- ranking formula based on this one day

Next useful step:
Run a second full blind day using the same `DayRehearsal-v0.1` profile without changing it.

A second day is needed to distinguish:
- repeatable behavior
from
- 2026-07-25 day-specific variance.

Only after at least a second unchanged day should we decide whether the next change belongs in:
- evidence interpretation,
- Pairwise authoring,
- scenario modeling,
- or confidence/mark semantics.
