# JRDB Feature Audit — Stage B Report

Date: 2026-10-05  
Source: normalized from the user-supplied Stage B artifact bundle  
Window: **2023-01-01 through 2025-12-31 only**  
Decision: **PROCEED_STAGE_C**  
Repository baseline used by supplied run: `1af38fcd`

## Executive summary

The three-year sample is large enough to discuss Reader information priority
and redundancy without extending to five years.

Cohort:

- 10,365 races;
- 142,737 runner entries;
- 141,523 valid-result entries;
- 73 scalar feature leaves;
- 2023 / 2024 / 2025 preserved separately.

The direct JRDB pre-race indices show clear repeated outcome separation, but
several high-separation fields substantially track final popularity and/or each
other. No fixed weights or production Reader changes follow from this audit.

## Headline findings

| Evidence family | Three-year observation | Interpretation |
|---|---|---|
| IDM / total / information | strongest-vs-weakest quintile win-rate gaps about 17.83 / 19.46 / 19.77 pp | strong and stable, but highly market-aligned and mutually overlapping |
| jockey index / expected top-two rate | about 20.25 / 20.53 pp gaps | extremely redundant; Spearman about 0.989 |
| KYI training index | about 20.14 pp gap | strong/stable but strongly market-aligned |
| pace late index | about 10.28 pp gap | moderate stable signal with less market alignment |
| CHA last clock / CYB condition | about 5.61 / 6.66 pp gaps | smaller but distinct contextual signal |
| CHA total clock / CYB training | identical observed ordering across common sample | direct redundancy candidate |
| start / late-break / CHA front-middle | small or less clean separation | weak/contextual rather than headline |
| CYB training grade | no usable values | insufficient coverage |

The strongest quintiles still have negative final-payout ROI. These findings
describe information quality, not a standalone betting system.

## Source / leakage boundary

The supplied pipeline used frozen annual BAC / KYI / CHA / CYB / SED archives
for 2023-2025.

BAC/KYI/CHA/CYB form the pre-race feature surface.

SED is joined separately by stable race/horse identity and is used only for:

- finish;
- win/place payouts;
- final popularity/odds control.

No SED value populates feature columns.

2026 BTDAY outcomes are not used.

## Coverage

Annual runner counts:

| Year | Entries |
|---|---:|
| 2023 | 47,672 |
| 2024 | 47,181 |
| 2025 | 47,884 |
| Total | 142,737 |

Main ability/composite indices, KYI training index and JRDB marks have broad
three-year coverage.

Notable reduced coverage:

- pace family: about 2.99% missing;
- CHA total clock / CYB training: about 3.48% missing;
- start index: about 13.82% missing;
- late-break rate: about 10.37% missing;
- distance fit: about 32.18% missing;
- turf fit: about 31.66% missing;
- dirt fit: about 40.29% missing;
- CYB one-week-ago index: about 25.03% missing;
- CYB training grade: 100% missing.

Reduced-coverage suitability fields should not become general all-runner
headline rankings.

## Year stability

Representative strongest-quintile win rates remain stable:

| Feature | 2023 | 2024 | 2025 | Combined |
|---|---:|---:|---:|---:|
| IDM | 19.12% | 19.50% | 19.51% | 19.38% |
| total index | 20.43% | 20.84% | 20.62% | 20.63% |
| information index | 20.59% | 21.00% | 20.39% | 20.66% |
| jockey index | 20.96% | 21.45% | 20.61% | 21.00% |
| KYI training index | 21.03% | 21.60% | 20.83% | 21.15% |
| pace late index | 13.74% | 13.99% | 13.13% | 13.62% |
| CHA last clock index | 10.39% | 10.18% | 10.50% | 10.36% |
| CYB condition index | 10.90% | 11.25% | 10.59% | 10.91% |

The principal candidate families therefore are not ambiguous for lack of
three-year sample.

## Market relationship

The leading provider composites strongly align with final popularity.

Examples of within-race feature rank vs final popularity correlation reported by
the supplied audit:

- IDM: about -0.696;
- total index: about -0.775;
- information index: about -0.765;
- jockey index: about -0.833;
- jockey expected top-two rate: about -0.840;
- KYI training index: about -0.821;
- pace late index: about -0.389.

Broad popularity-stratum analysis still shows some within-band separation, but
does not establish fully price-independent predictive value.

## Redundancy

Important observed overlap:

- CHA total clock index vs CYB training index:
  Spearman 1.000, top-1 and top-3 Jaccard 1.000;
- jockey index vs expected top-two rate:
  Spearman about 0.989;
- IDM vs total index:
  Spearman about 0.952;
- pace numeric indices vs corresponding provider ranks:
  near-identical ordering;
- projected order vs projected margin:
  very high overlap.

This is the main actionable result for Stage C: future Reader design should
avoid presenting deterministic or near-deterministic duplicates as independent
confirmations.

## Recommendation

**PROCEED_STAGE_C**

Do not extend to 2021-2025. The three-year sample is already large and stable
enough for an information-architecture decision.

Stage C should focus on:

- primary vs secondary evidence presentation;
- collapsing duplicate representations;
- preserving distinct pace / training / condition context;
- reducing cognitive duplication without introducing fixed weights.

The active v0.4.6 Reader and prediction logic remain unchanged.

## Provenance

Exact supplied-bundle checksums are recorded in:

`results/stage_b_2023_2025/ARTIFACT_MANIFEST.md`

Independent acceptance audit:

`audits/20261005_JRDB_FEATURE_AUDIT_STAGE_B_AUDIT.md`
