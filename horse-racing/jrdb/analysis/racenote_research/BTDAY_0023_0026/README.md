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
