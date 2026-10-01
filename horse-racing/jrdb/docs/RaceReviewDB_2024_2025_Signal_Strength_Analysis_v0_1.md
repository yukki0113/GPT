# RaceReviewDB 2024–2025 Signal Strength / Monotonicity Analysis v0.1

- Status: research candidate strength map; no rule promotion
- Source period: 2024-01-01 through 2025-12-31
- Evaluation: existing source-to-next-start OOS mapping and settled SED market enrichment (mapped target starts through 2026-09-27)
- Input: `analysis/oos/rrdb_2024_2025_signal_oos_fact_with_market.parquet`
- Generated: 2026-10-01

## 1. Executive summary

2024–2025の固定OOSに対し、既存factとsource→target対応を再利用し、事前固定したstrength bandで次走能力の単調性を調べた。最も説明しやすい傾向は、FRONTの勝ち馬差が小さくなるほど次走top3が増える傾向（ただし勝ち馬差0以下で逆転）と、REARの上がり速度percentileが高い帯でtop3が高くなる傾向である。TIME_CLASSはclass gap・上位クラス基準差とも最大帯で反転し、連続的なstrength gradeとしては単調でない。

| Signal / axis | 結果 | 解釈 |
|---|---|---|
| TIME_CLASS class gap | `NON_MONOTONIC` | +1.0～+2.0未満はnext top3 43.3–44.8%だが、+2以上は36.9%。 |
| TIME_CLASS next-class margin | `NON_MONOTONIC` | 0.30–0.60秒帯が45.2%で最大。0.60秒以上は低下し、1秒以上は23.6%。 |
| FRONT winner gap | `NON_MONOTONIC`（端の≤0を含む） | >0.80秒の20.3%から0.01–0.20秒の46.8%まで上昇する一方、≤0は30.8%。 |
| FRONT cumulative thresholds | 0.80→0.50→0.30秒は概ね上向き、0.20秒は低下 | top3は34.7→36.5→36.7→35.5%。matched liftは+10.9→+11.1→+6.4→+0.5pt。 |
| FRONT pace strength | `FLAT` | pace 70–79 / 80–89 / 90–100のtop3は28.6 / 28.3 / 27.1%。 |
| REAR last3f percentile | `MOSTLY_MONOTONIC` | 80–89.9: 18.3%、90–94.9: 21.7%、98–100: 30.1%。95–97.9は該当行なし。 |
| REAR winner gap within last3f≥90 | `MOSTLY_MONOTONIC` | gap >0.80から≤0.20へtop3は19.7→36.9%。matched liftの上昇は完全単調ではない。 |
| HV01 / HV02 performance strength | `MOSTLY_MONOTONIC` | いずれもQ90–Q95で一度下がり、Q95以上で上昇。 |

分類は記述的な帯域比較であり、統計的な採用判定ではない。`N<30`は単調性の結論から除外した。市場ROIは参考診断であり、ROIだけでsignalを棄却しない。

## 2. Data and audit

| Check | Result |
|---|---:|
| Existing OOS fact rows / columns | 81,767 / 100 |
| Strength fact rows / columns | 81,767 / 132 |
| Duplicate `source_race_horse_key` | 0 |
| Target date ≤ source date | 0 |
| Source/target `horse_id` mismatch | 0 |
| Unclassified target finish | 0 (target finish 0 / abnormal: 569; excluded from ability denominator) |
| Valid settled market rows | 81,198 |
| Frozen signal positive N (TIME_CLASS_PLUS1 / FRONT_SURVIVE_GAP05 / FRONT_SURVIVE_OR / REAR_HIGH_LAST3F90 / HV01 / HV02 / POSITION_RECOVERY) | 386 / 4,612 / 7,760 / 1,610 / 6,014 / 3,165 / 10,216 |
| Class-margin observations / missing | 50,110 / 31,657 |
| Future next-class reference dates | 0 |

The input fact was not modified, and no source→target mapping was regenerated. Ability rates use mapped target rows with `target_finish > 0`; 569 target rows coded 0 are retained in the fact but excluded from ability denominators. Market metrics use valid settled-market rows with classified target finish.

### Next-class standard reconstruction

`next_higher_class_standard_sec` is not present in the input. It was reconstructed from the preceding race-review history for the same venue, surface, and next-higher declared class, using historical winner time and subtracting the historical race's day/track adjustment when available. Scope priority was: prior 7 days exact distance, prior 14 days exact distance, then prior 14 days within ±200m. Every selected source race was strictly earlier than its OOS source date; the source actual time was adjusted by its own day/track adjustment for a like-for-like margin. The resulting `next_class_margin_sec = next_higher_class_standard_sec - source_time_adjusted_sec`; positive means faster than the reconstructed reference. Missing references remain null, not zero. This local reconstruction is a proxy and has 61.3% coverage; margin results should be read with that limit.

HV strength bands reuse frozen `performance_signal_q80=-0.0930555556` and `performance_signal_q90=0.1677714932`. The Q95 split was fixed from the 2022–2023 pre-OOS performance-signal distribution (`0.3612475482`), not selected using 2024–2025 outcomes. The source performance signal recomputation exactly matched the existing field.

## 3. TIME_CLASS

### Class-gap axis

| Historical class gap | N | Next win | Next top3 | Next top5 | Mean finish | Matched top3 lift | Median popularity | Median odds | Place ROI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| <+1.0 | 12,715 | 7.5% | 21.4% | 36.0% | 7.66 | -0.7pt | 8 | 26.70 | 73.2% |
| +1.0–<+1.5 | 194 | 20.1% | 43.3% | 58.2% | 5.20 | +9.0pt | 3 | 5.25 | 77.2% |
| +1.5–<+2.0 | 87 | 21.8% | 44.8% | 69.0% | 4.55 | +5.4pt | 2 | 4.80 | 77.5% |
| ≥+2.0 | 103 | 17.5% | 36.9% | 56.3% | 5.85 | -0.7pt | 3 | 6.20 | 76.9% |

### Margin to next-class reference

| Margin | N | Next top3 | Next top5 | Matched top3 lift | Median popularity | Median odds | Place ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| <0 | 6,551 | 21.4% | 35.7% | -0.7pt | 8 | 27.70 | 72.7% |
| 0–<0.30 sec | 139 | 38.8% | 50.4% | +12.9pt | 4 | 8.80 | 99.6% |
| 0.30–<0.60 sec | 104 | 45.2% | 59.6% | +17.3pt | 3 | 7.00 | 95.9% |
| 0.60–<1.00 sec | 75 | 32.0% | 54.7% | +4.6pt | 4 | 8.20 | 70.4% |
| ≥1.00 sec | 686 | 23.6% | 38.9% | -1.4pt | 7 | 22.25 | 65.6% |

**回答:** class gapとnext-class marginの両方で、最上位帯まで強くなるほど次走能力が改善する単調性は確認できない。class gapは+1.0〜+2.0未満で高いが+2.0以上で反転。marginは0.30–0.60秒帯が最良で、1秒以上では崩れる。marginは説明可能な物理量だが、基準再構築の欠損と上位帯の逆転があり、今回の結果だけでは安定した連続gradeとして採用できない。人気・オッズも帯域間で大きく変わる。

## 4. FRONT_SURVIVE

固定exposure `pace_balance_percentile >= 70` and `corner4_frontness >= 0.60` を使用した。

| Winner gap | N | Next top3 | Next top5 | Matched top3 lift | Median popularity | Place ROI |
|---|---:|---:|---:|---:|---:|---:|
| >0.80 sec | 5,299 | 20.3% | 34.3% | +0.2pt | 8 | 81.0% |
| 0.51–0.80 sec | 1,478 | 29.2% | 45.9% | +5.9pt | 5 | 87.5% |
| 0.31–0.50 sec | 1,318 | 36.1% | 54.1% | +11.3pt | 4 | 75.6% |
| 0.21–0.30 sec | 855 | 40.0% | 57.7% | +10.1pt | 3 | 79.1% |
| 0.01–0.20 sec | 705 | 46.8% | 61.3% | +10.8pt | 2 | 78.0% |
| ≤0 sec | 1,699 | 30.8% | 48.9% | -8.2pt | 4 | 68.7% |

`gap<=0` is shown because the requested fixed bucket includes it; it contains source winners and does not behave like a progressively smaller losing margin. Excluding that endpoint, closer gaps align with better next-run results, but the sequence and matched lift are not perfectly monotone. The cumulative 0.80→0.50→0.30 thresholds retain positive top3 lift; tightening to 0.20 reduces lift to +0.5pt. Therefore 0.20 is not supported as a strictly stronger research band by this test.

Within the same exposure, pace bands 70–79, 80–89, and 90–100 have top3 rates 28.6%, 28.3%, and 27.1% (flat to slightly down). Frontness bands 0.60–0.69, 0.70–0.79, 0.80–0.89, and 0.90–1.00 show top3 rates 24.8%, 27.4%, 28.0%, and 30.3%, with matched lift +2.8, +5.4, +5.9, and +8.3pt. The latter is an observed gradient, not a presumption that the most forward position is always best; consult the gap×frontness table.

## 5. REAR_HIGH_LAST3F

Fixed exposure: `pace_balance_percentile <= 30`, `corner4_frontness <= 0.40`; the primary signal also requires `last3f_speed_percentile >= 90`.

| Last3f percentile | N | Next top3 | Next top5 | Matched top3 lift | Median popularity | Place ROI |
|---|---:|---:|---:|---:|---:|---:|
| 80–89.9 | 990 | 18.3% | 36.2% | -3.1pt | 8 | 64.0% |
| 90–94.9 | 609 | 21.7% | 38.3% | +1.5pt | 7 | 87.3% |
| 95–97.9 | 0 | — | — | — | — | — |
| 98–100 | 986 | 30.1% | 48.9% | +7.2pt | 5 | 72.6% |

No source rows fall in 95–97.9: stored percentile ranks are discrete and jump over this band. The apparent improvement at 98–100 is consistent across all four half-year blocks in top3 lift (-0.6pt in 2024H1, +8.6pt in 2024H2, +6.0pt in 2025H1, +7.9pt in 2025H2), but the missing middle band means this is not a fully observed stepwise curve.

Within last3f≥90, decreasing winner-gap bands >0.80, 0.51–0.80, 0.31–0.50, 0.21–0.30, and ≤0.20 have next top3 rates 19.7%, 23.2%, 30.7%, 34.1%, and 36.9%. Matched lifts are 0.0, +1.6, +4.2, +3.4, and +2.5pt: performance rises as gaps narrow, but the incremental lift flattens after the 0.31–0.50 band. Rear-position buckets do not assume “farther back is stronger”; descriptively, next top3 rises from 10.5% at frontness 0.00–0.10 to 16.4% at 0.31–0.40. Position alone is not a stable strength axis here.

## 6. HV01 / HV02

HV rules are taken unchanged from the frozen candidate contract. Within each signal, Q80–Q90 / Q90–Q95 / ≥Q95 bands use the frozen Q80/Q90 thresholds and pre-OOS Q95 cut described above.

| Signal / performance band | N | Next top3 | Next top5 | Matched top3 lift | Median popularity | Median odds | Place ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| HV01 Q80–Q90 | 3,389 | 27.4% | 44.3% | +9.9pt | 6 | 15.80 | 80.0% |
| HV01 Q90–Q95 | 1,308 | 26.3% | 45.4% | +8.0pt | 6 | 14.20 | 69.0% |
| HV01 ≥Q95 | 1,279 | 31.1% | 48.5% | +12.2pt | 6 | 14.80 | 96.7% |
| HV02 Q80–Q90 | 1,856 | 21.2% | 35.6% | +7.3pt | 7 | 24.65 | 77.6% |
| HV02 Q90–Q95 | 679 | 18.1% | 35.1% | +3.7pt | 7 | 21.60 | 55.3% |
| HV02 ≥Q95 | 610 | 21.8% | 38.5% | +7.4pt | 7 | 23.95 | 98.0% |

Both have a dip in Q90–Q95 and recover in Q95+, so neither is strictly monotone. Lift remains positive in each populated performance band. Across four half-year blocks, HV01 ≥Q95 lift ranges +8.8 to +14.3pt; HV02 ≥Q95 ranges +3.9 to +11.2pt. These are candidate strength gradients only.

For source finish, HV01 N-band rates and median market values are in the summary CSV. As expected, later source finishes (4–5 → 6–9 → 10+) become less popular (median popularity 4 → 7 → 9; median odds 9.60 → 19.90 → 47.50) and next top3 declines (36.1% → 22.0% → 16.2%). This does not establish increased market mispricing: place ROI also declines (86.0% → 77.9% → 73.2%). HV02 uses only finish 6+ by definition.

## 7. Stability and matched comparisons

The summary CSV includes the four source half-year blocks for every primary band and cumulative threshold. In the main FRONT cumulative thresholds, top3 lift is positive in all four blocks through gap≤0.30; at gap≤0.20 it is negative in 2024H1/H2/2025H1 and positive only in 2025H2. REAR gap≤0.50/0.30/0.20 has period variation, including negative lifts in 2024H1; no one half-year should be used to promote a tighter cutoff. TIME_CLASS high-gap bands have block N often below 30, so block rates are descriptive and unstable. HV01 Q95 is directionally positive in each block; HV02 Q95 also positive, with wider variation.

Matched baseline strata preserve the existing OOS dimensions: source finish band, declared class, surface, and distance category. Each band’s matched baseline is the mapped ability-eligible population in strata represented by that band; it is descriptive, not an independent causal effect. Bootstrap intervals in the summary are clustered by target race (300 replicates) where practical. Two-dimensional tables include `conclusion_eligible_N30`; cells under 30 are not interpreted. In the FRONT 2D table all cells have N≥30. REAR has 10 cells below 30 (9 empty), chiefly because of the discrete 95–97.9 band.

Market ROI uses a 100-yen place stake per valid market runner. The summary also shows place ROI differences against the corresponding odds-band and popularity-band matched populations where available. These diagnostics separate ability from market value; ROI below 100% does not reject an ability signal.

## 8. Answers and research recommendation

1. **TIME_CLASS gap:** larger +1 gaps are not consistently better; +2+ reverses versus +1 to +2.
2. **Next-class margin:** 0.30–0.60 sec is strongest in this sample; thresholds ≥0.60 and ≥1.00 do not improve monotonically. The margin axis is more human-readable but less complete and locally reconstructed.
3. **FRONT gap:** excluding the requested ≤0 endpoint, closer gaps generally predict better next top3; strict 0.20 cut does not maintain matched lift. Pace percentile itself does not add a monotone gradient; frontness has a positive observed association within exposure.
4. **REAR strength:** last3f≥98 is promising, but the discrete percentile gap and sample structure prevent a full 90→95→98 stepwise claim. Smaller winner gap within ≥90 improves top3 with diminishing lift.
5. **HV:** top performance band tends to recover above the Q90–Q95 dip; evidence is “mostly” rather than perfectly monotone.
6. **Most explainable candidate display fields:** show measured values directly—`winner_gap_sec` for FRONT, `last3f_speed_percentile` plus `winner_gap_sec` for REAR, `performance_signal` and frozen percentile band for HV. TIME_CLASS may show both `historical_class_gap_numeric` and the reconstructed next-class margin with its scope/coverage; do not convert it into S/A tiers from this work alone.

**Conclusion:** preserve these as a research candidate strength map. No formal S/A, Next-Watch, PWA, newspaper-mark, or frozen-rule changes were made.

## 9. Outputs

- `analysis/oos/rrdb_2024_2025_signal_strength_fact.parquet`
- `analysis/oos/rrdb_2024_2025_signal_strength_summary.csv`
- `analysis/oos/rrdb_2024_2025_signal_strength_monotonicity.csv`
- `analysis/oos/rrdb_2024_2025_front_strength_2d.csv`
- `analysis/oos/rrdb_2024_2025_rear_strength_2d.csv`
- `analysis/oos/rrdb_2024_2025_signal_strength_examples.csv`
- `docs/RaceReviewDB_2024_2025_Signal_Strength_Analysis_v0_1.md`
