# JRDB Feature Audit — Stage B Report

Date: 2026-10-05
Instruction: `20261005_JRDB_FEATURE_AUDIT_STAGE_B_INSTRUCTION.md`
Window: **2023-01-01 through 2025-12-31 only**
Decision: **PROCEED_STAGE_C**
Repository baseline: `1af38fcd` (Stage B instruction commit)

## Executive findings

The three-year sample is large enough to discuss Reader information priority and redundancy in Stage C. The direct JRDB pre-race indices show clear, repeated raw outcome separation, but several high-separation fields substantially track the final market and/or each other. No fixed weights or production Reader changes follow from this audit.

| Evidence family | Three-year observation | Market / overlap interpretation | Research label |
|---|---|---|---|
| IDM, total, information indices | Q1 vs Q5 win-rate gap: 17.83, 19.46, 19.77 percentage points; zero ordered-bucket violations in each year | Rank versus final popularity Spearman: IDM -0.696, total -0.775, information -0.765; IDM/total within-race percentile Spearman 0.952 | STRONG_STABLE; MARKET_PRICED; REDUNDANT_CANDIDATE |
| Jockey index / expected top-two rate | Q1 vs Q5 gaps: 20.25 / 20.53 points; year-by-year direction repeats | Nearly the same ranking (Spearman 0.989, top-1 Jaccard 0.959); final-popularity correlations -0.833 / -0.840 | STRONG_STABLE; MARKET_PRICED; REDUNDANT_CANDIDATE |
| KYI training index | Q1 vs Q5 gap 20.14 points and zero violations in 2023, 2024, 2025 | Final-popularity correlation -0.821; distinct from CYB training index (within-race percentile Spearman 0.159) | STRONG_STABLE; MARKET_PRICED |
| Pace late index | Q1 vs Q5 gap 10.28 points, zero violations in each year | Final-popularity correlation -0.389; Q1 still separates in broad popularity bands, though less strongly at 10+ | MODERATE_STABLE |
| CHA last clock index / CYB condition index | Q1 vs Q5 gaps 5.61 / 6.66 points, zero violations in each year | Smaller raw separation; less market alignment than the leading KYI composites | MODERATE_STABLE |
| CHA total clock index / CYB training index | Identical observed values and coverage on 136,601 valid-result entries | Perfect within-race Spearman and top-1/top-3 overlap | REDUNDANT_CANDIDATE |
| Start index, late-break rate, CHA front/middle clock indices | Combined Q1 vs Q5 gaps 2.96, 2.21, 0.85, 1.15 points | Smaller and less clean bucket relationships; late-break and CHA front/middle have combined violations | WEAK_OR_UNSTABLE |
| CYB training grade | No values in the three-year source population | No outcome comparison is possible | INSUFFICIENT_COVERAGE |

All Q1/Q5 figures are descriptive **within-race** quintile views, not optimized thresholds or causal estimates. Tied values may place multiple runners in a rank/flag; bucket counts are in the machine tables. Each of the leading Q1 groups still has negative win ROI at final payout levels (for example IDM -19.90%, pace late -22.27%, KYI training -22.37%). Strong raw separation is not a betting system.

## Sources, preflight, and cohort

The pipeline uses frozen annual Raw ZIPs for BAC, KYI, CHA, CYB, and SED for 2023/2024/2025. All 15 Drive file identities, byte sizes, and locally computed SHA-256 hashes are recorded in `source_manifest.json`; the frozen inventory is `config/jrdb_frozen_raw_inventory_20260918.json`. The common `jrdb_raw.Parser` supplies fixed-width fields. Annual member names establish target date, BAC gives race context, KYI gives target runners, and CHA/CYB join on `race_horse_key`. SED is joined separately by `race_key + horse_no` and the blood registration number must match. CHA workout dates are checked to be no later than the target race date. No SED value enters a feature column.

| Year | KYI entries | KYI races | SED matches | BAC race coverage |
|---|---:|---:|---:|---:|
| 2023 | 47,672 | 3,456 | 47,672 | 3,456 |
| 2024 | 47,181 | 3,454 | 47,181 | 3,454 |
| 2025 | 47,884 | 3,455 | 47,884 | 3,402 |
| **Total** | **142,737** | **10,365** | **142,737** | **10,312** |

BAC is absent for 53 races / 735 entries in late 2025; these entries retain their KYI and outcome metrics, while conditional views requiring BAC context exclude them. Among 142,737 joined entries, 1,214 have abnormal/no valid finish, leaving **141,523 valid-result entries**. Final popularity is present for all valid-result entries; no winner is missing a win payout. A small number of top-three finishers (270) have no place payout, which can occur under shorter-field place-payment rules; the payout denominator still includes every selected runner.

Stage A's 41 conceptual groups were expanded into **73 stable leaves**: 47 KYI, 12 CHA, 14 CYB. The catalog labels 54 as primary candidate leaves and 19 as context-only leaves (for example raw workout clocks/course and training-course counts). Every leaf has a Stage A parent, exact parser leaf, source record, Reader path, type, and declared direction if meaningful. Code-valued JRDB class, distance fit, lane, and provider marks are kept categorical when a numeric distance is unsupported. KYI code `0` for running style or distance fit is treated as null, matching the RaceNote normalizer. Blank/zero/unmarked JRDB marks are recorded as `NONE` for the mark-specific analysis; this represents no mark, not a missing source row.

### Coverage conclusions

- Main ability/composite indices, KYI training index, and all seven mark dimensions have full source coverage in all three years. The pace indices/ranks/projected-position family has **138,476 / 142,737** values (2.99% missing), covering 9,991 races.
- CHA total clock index and CYB training index each have **137,768** source values (3.48% missing); condition index has **142,629** (0.08% missing). Their year-level coverage is in `coverage.csv.gz`.
- Start index is 13.82% missing and late-break rate 10.37% missing. Running style is 10.20% missing after the normalized zero-code rule.
- Distance fit is 32.18% missing, turf fit 31.66%, dirt fit 40.29%, and CYB one-week-ago index 25.03%. Treat comparisons for these as reduced-sample, condition-sensitive descriptions. The dirt-fit and distance-fit populations are not suitable for a general all-runner ranking.
- CYB training grade is **100% missing**. It is retained in the catalog and coverage output, and excluded from outcome claims.

The coverage report lists rows available, missing percentage, races, distinct horses, first/last date, and 2023/2024/2025 separately for every scalar leaf. No missing values are silently filled or substituted.

## Transformations and outcome metrics

For numeric leaves, the output includes raw min/P05/P25/median/P75/P95/max; rank within each target race; within-race percentile and five ordered buckets; top-1/top-3/top-5 membership; raw difference from race median; and the leader's gap to second place. Provider pace ranks also have their own 1, 2, 3, 4, 5, 6+ outcome buckets and an explicit comparison with the numeric-index-derived rank. Ties use minimum rank; the first quintile therefore need not contain exactly 20% of runners.

Every overall and yearly metric row reports sample size, race count, win/top-two/top-three rate, and win/place ROI. ROI is net return per **¥100 equal stake on every selected runner**: `100 × (sum of JRDB SED payout / (100 × selected runners) - 1)` percent. Blank loser payouts are zero returns; no missing winner win payout was encountered. The result population excludes cancellation/exclusion/nonfinish/disqualification rows with no valid placing. Final odds, final popularity, finish and payouts are evaluation/control fields only.

The five-bucket monotonicity table records every bucket, direction, adjacent violation count, and Spearman score of ordered bucket win rates, plus year-specific versions. Among 32 ordered numeric leaves, 29 have zero combined-bucket violations. This high fraction does not mean 29 independent discoveries: several are deterministic or very close transformations of the same provider estimate.

## Year stability, market, and redundancy

| Feature (Q1 win rate) | 2023 | 2024 | 2025 | 2023–25 |
|---|---:|---:|---:|---:|
| IDM | 19.12% | 19.50% | 19.51% | 19.38% |
| Total index | 20.43% | 20.84% | 20.62% | 20.63% |
| Information index | 20.59% | 21.00% | 20.39% | 20.66% |
| Jockey index | 20.96% | 21.45% | 20.61% | 21.00% |
| KYI training index | 21.03% | 21.60% | 20.83% | 21.15% |
| Pace late index | 13.74% | 13.99% | 13.13% | 13.62% |
| CHA last clock index | 10.39% | 10.18% | 10.50% | 10.36% |
| CYB condition index | 10.90% | 11.25% | 10.59% | 10.91% |

These headline features retain the same strongest-to-weakest quintile direction in all three years. The full yearly tables include weak buckets and ROI, rather than showing only extremes. The weak examples above also have positive Q1–Q5 gaps in every year, but front/middle CHA clock indices and late-break rate have violations within the five-bucket sequence. Their practical separation is much smaller.

Market analysis uses final popularity groups **1–3, 4–6, 7–9, 10+**. Within the 1–3 group, IDM Q1 wins 25.42% versus 16.85% for Q2–Q5 (19,733 versus 11,243 observations). Pace late is 25.20% versus 20.01% (12,891 versus 17,004), and CYB condition index is 24.45% versus 21.18% (10,673 versus 20,301). The gap shrinks in the 10+ group: pace late 1.06% versus 0.81%. These are broad popularity bands, so residual differences between popularity rank 1 and rank 3 remain possible. The table describes market association and within-band separation; it does not establish price-independent predictive value. Popularity is never a model input.

Redundancy is quantified on common runner observations with **within-race percentile Spearman** and top-1/top-3 Jaccard overlap. Examples: IDM versus total index 0.952; jockey index versus expected top-two rate 0.989; pace-front numeric versus supplied rank 0.999; projected finish order versus projected finish margin 0.992; CHA total clock index versus CYB training index 1.000. In contrast, KYI training index versus CYB training index is only 0.159, so the shared word “training” does not make them equivalent. Provider pace rank exact-match rates to reconstructed numeric rank range from 87.98% (late) to 93.72% (front), while rank Spearman remains 0.985–0.998. JRDB marks are also close to rank labels: code `1` for total/IDM/training marks corresponds to numeric top rank in the observed sample. The mark-to-index table retains all mark codes and `NONE`, not a single “has mark” score.

## Broad conditional view

The table covers turf/dirt/obstacle, sprint/mile/middle/staying distance, new/maiden versus allowance versus open/graded, and field-size bands, with 2023/2024/2025 and combined views. A slice is labeled size-adequate only with at least 200 Q1 entries and 100 races. BAC-missing races are absent from these context slices.

For pace late index, the combined Q1 versus Q2–Q5 win-rate gap is **10.32 points in new/maiden** and **6.28 in allowance**; by distance it is **6.47 in sprint**, **7.76 in mile**, and **9.23 in middle**. This is a `CONDITIONAL` research observation, not a tuned rule: class and distance change field size, market mix and available pace ranks. The full table should be used to check those interactions before any Stage C recommendation. Strong ability/composite Q1 advantages appear in both turf and dirt and across the broad class bands; the raw rates do not justify a narrower venue/distance search.

## Limitations and decision

- The audit is descriptive and compares many correlated leaves. It does not claim significance from the largest in-sample bucket, optimize thresholds, fit a model, or use any 2026 BTDAY outcome.
- Provider formulas and some categorical orderings are not inferred. JRDB class and suitability categories remain categorical. The 2023–2025 source coverage is broad enough for the principal numeric families, but some categories are reduced-sample and CYB training grade is unavailable.
- Final-popularity grouping cannot prove incremental value against the full betting market; it is an explanatory control. Negative Q1 ROI is a practical reminder.
- The 53 BAC-missing races limit context slices, not the KYI/SED stable-key outcome join. CHA total clock and CYB training index equality is an observed three-year identity, not an asserted provider formula.

**Recommendation: PROCEED_STAGE_C.** Three years show stable raw relationships and enough evidence to examine overlap and Reader presentation priority. The strongest apparent signals are also heavily market-aligned and correlated with each other, so Stage C should discuss information priority without producing a fixed score. The sample is not inconclusive for lack of observations; a Stage B2 extension is not requested. The active v0.4.6 Reader and prediction logic remain untouched.

## Artifacts and reproduction

Pipeline: `horse-racing/jrdb/tools/run_racenote_feature_audit_stage_b.py`
Machine outputs: `horse-racing/jrdb/docs/racenote/research-work/results/stage_b_2023_2025/`

Files: `scalar_feature_catalog.json`, `source_manifest.json`, `source_coverage.json`, `cohort.json`, `outcome_quality.json`, and gzip CSV tables `coverage`, `raw_distributions`, `numeric_transform_summary`, `overall_metrics`, `yearly_metrics`, `monotonicity`, `market_strata`, `provider_rank_comparison`, `redundancy_pairs`, `mark_index_overlap`, `conditional_slices`. The gzip files use fixed timestamp metadata for deterministic regeneration. Annual Raw ZIP bytes are local analysis inputs and are excluded from Git.

Run, after placing the 15 annual ZIPs named `KIND_YYYY.zip` in a local directory:

```powershell
python horse-racing/jrdb/tools/run_racenote_feature_audit_stage_b.py --raw-root <annual-zip-directory> --preflight-only
python horse-racing/jrdb/tools/run_racenote_feature_audit_stage_b.py --raw-root <annual-zip-directory>
```

Input file sizes must match the frozen Drive inventory. The pipeline checks canonical member names, target dates, year-coded race keys, unique business keys, KYI/SED horse identity, CHA workout dates, and outcome-label invariance. It writes the coverage report before outcome aggregations. A full rerun produced byte-identical outputs: the SHA-256 over each of the 16 files' names and bytes in sorted order was `ed209ff20b8a2266a661f86687a69dee6c39f755e5cdfaab479a774fad406201` on both runs. Baseline commit: `1af38fcd`.
