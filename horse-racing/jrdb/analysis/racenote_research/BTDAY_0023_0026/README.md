# RaceNote Research Population — BTDAY-0023〜0026

## Purpose
RaceNote Human-Context Reader v0.4.2 candidate の BTDAY-0023〜0026、計144Rを、①Hierarchy、②Coverage、③Race Selector discovery の共通研究母集団へ再編したもの。

## Files
- `forecast_population.jsonl`
  - 結果を含まない事前Forecast側の正規化ビュー。
  - 元Forecast全文は複製せず `source_ref` からBTDAY原本へ戻れる。
  - marks / reader_facing_reason / mark_reason / race_model / single_shot_case / RRDB evidence / semantic hash / prediction hash を保持。
- `outcome_BTDAY_0023.jsonl` 〜 `outcome_BTDAY_0026.jsonl`
  - SED/HJCから再構成したコンパクト結果。
  - Top3、最終人気・単勝オッズ、実際の勝ち組合せ払戻を保持。
- `research_population.jsonl`
  - ForecastとOutcomeを `selection_id + venue + race_no` でJOINした研究用1レース1行正本。
  - ①Hierarchy / ②Coverage の機械ラベルと、研究対象馬券の100円単位精算を保持。
  - ③Selectorラベルは意図的に未付与。

## Selector leakage guard
`research_labels.selector_discovery` は全144Rで以下の状態から開始する。

- `label_status = UNLABELED_PRE_RESULT_REVIEW_REQUIRED`
- `axis_confidence = null`
- `five_horse_convergence = null`
- `chaos_level = null`
- `single_shot_value = null`
- `label_source = FORECAST_ONLY`
- `result_visible_to_labeler = false`

③のラベル付け時はForecast側情報だけを読む。Outcome / settlement を見ながらラベルを決めてはいけない。

## Mechanical labels

### Hierarchy
- `winner_in_five`: 勝ち馬が◎○▲△1△2のいずれか
- `main_won`: ◎が勝利
- `hierarchy_failure`: 勝ち馬は5頭内だが◎ではない

### Coverage
- `all_top3_in_five`: 1〜3着すべてが5頭内
- `coverage_failure`: Top3に1頭以上の無印馬
- `coverage_miss_count`: Top3の無印頭数
- `missed_top3`: 漏れた好走馬

## Settlement units
すべて100円単位。
- ◎単勝: 100円/R
- ◎○馬連: 100円/R
- ◎▲馬連: 100円/R
- ◎→○馬単: 100円/R
- ◎→▲馬単: 100円/R
- ◎軸3連複: 6点 = 600円/R
- ◎1着固定3連単: 12点 = 1,200円/R
- 5頭3連複BOX: 10点 = 1,000円/R（candidate-set qualityの補助指標）

## Validation snapshot
| Set | R | ◎勝 | ◎Top2 | ◎Top3 | 勝ち馬5頭内 | Top3全頭5頭内 |
|---|---:|---:|---:|---:|---:|---:|
| 0023 | 36 | 12 | 15 | 16 | 27 | 6 |
| 0024 | 36 | 12 | 19 | 25 | 27 | 15 |
| 0025 | 36 | 7 | 17 | 20 | 28 | 6 |
| 0026 | 36 | 15 | 20 | 23 | 28 | 7 |
| Total | 144 | 46 | 71 | 84 | 110 | 34 |

0023のTop3全頭5頭内は、旧メモの7/36ではなく、原ForecastとSED/HJCを再JOINした本母集団では6/36。その他の主要な0023精算値（◎単勝、◎○/◎▲、3連系）は旧集計と一致した。

## Git size policy
この母集団はJSONL/Markdownのみ。xlsx / parquet / zip / JRDB Raw複製は置かない。
新しい研究軸は列を巨大化させず、必要なら別JSONLでannotationを追加し、原Forecastを重複保存しない。


## Selector discovery labels v0.1

`selector_labels_discovery_v0_1.jsonl` に144Rの③用ラベルを保存した。

### ラベル
- `axis_confidence`: ◎信頼度
- `five_horse_convergence`: 5頭収束度
- `chaos_level`: 波乱度
- `single_shot_value`: ▲妙味度

各軸は `HIGH / MID / LOW`。

### blindness
23〜26は分析者が結果を既知のため、厳密なblindではない。
全行に `label_blindness = PSEUDO_BLIND_RESULT_KNOWN_TO_ANALYST` を保持する。

ラベル付け工程では outcome / settlement / final market を参照せず、
Forecastと `reader_stripped` の事前情報だけを利用した。

### full-field calibration
文章表現の世代差を自信度と誤認しないため、Reader文章の強い言い回しだけで判定しない。

全頭の事前情報から、IDM・総合指数・調教指数・直近着順・RRDB recommendation signalを
レース内相対値へ正規化した補助比較を作り、以下をラベル判断の校正材料にした。

- ◎の全頭相対順位と選択5頭内の差
- 選択5頭が全頭相対Top6を何頭占有するか
- 最上位無印候補と選択上位馬の差
- 全頭上位6頭の評価spread
- ▲の全頭相対順位、RRDB signal、独立した展開・条件シナリオ

この補助比較自体を新しいForecastロジックとは扱わない。
Race Selector仮説発見のためのanalysis-side annotationである。

### 144R label distribution

| axis | HIGH | MID | LOW |
|---|---:|---:|---:|
| ◎信頼度 | 48 | 79 | 17 |
| 5頭収束度 | 107 | 20 | 17 |
| 波乱度 | 19 | 80 | 45 |
| ▲妙味度 | 92 | 47 | 5 |

次工程で初めてOutcome / settlementとJOINし、ラベル別の成績・ROI・組合せ効果を確認する。


## Hierarchy ◎ vs ○ review v0.1

- `HIERARCHY_MAIN_VS_SECOND_REVIEW_v0_1.md`: ○逆転23RをFreeze時点の材料へ戻って再評価した研究レビュー。
- `hierarchy_main_vs_second_annotations_v0_1.jsonl`: 23Rのassessment / cause_codes / rationaleを1R1行で保持。

結果だけで序列を学習しないため、`REVERSAL_WARRANTED / NARROW_GAP / PRE_RACE_JUSTIFIED` を区別する。
