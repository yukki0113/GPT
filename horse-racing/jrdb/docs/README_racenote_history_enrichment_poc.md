# RaceNote Analysis / Stats Mart enrichment PoC

既存のRaceNote v0.2.x 1レースJSONを変更せず、後段でJRDB Analysis Lite v1.2とStats Mart v1.1を付加して情報量を比較するPoCです。

## 目的

札幌記念など1レースを対象に、次の2案を同時生成して比較します。

- 8走案: PACI `recent_runs` 最大5走 + Analysis `older_runs` 最大3走
- 10走案: PACI `recent_runs` 最大5走 + Analysis `older_runs` 最大5走

両案共通で以下を追加します。

- `historical_profile`: Analysis由来のcareer / same_surface / same_distance / distance_ranges / same_venue
- `horses[].stats.sire`: Stats Mart由来の同場・同芝ダ・完全一致距離 + 距離レンジの種牡馬傾向
- `horses[].stats.jockey`: 同条件の騎手傾向
- `race.race_trends.frame`: 同条件の枠傾向

集計値は `starts / wins / top3 / win_rate / top3_rate` に絞り、払戻率は初期PoCでは付加しません。

## 距離レンジ

完全一致距離の統計は残したまま、対象距離に対応する `distance_ranges` を追加します。

初期仕様は以下です。

```text
1000–1400
1400–1800
1800–2400
2500+
```

境界は競走馬の適性が連続的であることを考慮し、1400mと1800mだけ意図的に重複させます。

- 1400m: `1000–1400` と `1400–1800` の両方
- 1800m: `1400–1800` と `1800–2400` の両方
- 2400m: `1800–2400` のみ
- 2500m以上: `2500+`

2400mは中距離側だけに含め、長距離は2500mからとします。

カテゴリ名（短距離・マイル・中距離・長距離）はJSONの判定値として固定せず、`min_m` / `max_m` の数値範囲を正本とします。

例: 1400m戦

```json
"distance_ranges": [
  {
    "min_m": 1000,
    "max_m": 1400,
    "starts": 12,
    "wins": 2,
    "top3": 5,
    "win_rate": 16.7,
    "top3_rate": 41.7
  },
  {
    "min_m": 1400,
    "max_m": 1800,
    "starts": 9,
    "wins": 1,
    "top3": 3,
    "win_rate": 11.1,
    "top3_rate": 33.3
  }
]
```

`2500+` は `max_m: null` として表現します。

## as-of安全性

過去レースを再現する場合、現在のStats Martの当年集計をそのまま使うと対象日より後の結果が混入する可能性があります。

そのため本PoCは、対象年を含む5暦年を基本窓とし、

- 対象年より前の年: Stats Martを利用
- 対象年: Analysis Liteを `race_date < target_date` でその場集計

として結合します。

例: 2026-08-16札幌記念なら、2022-2025はMart、2026は2026-08-15までのAnalysisだけを利用します。

またStats Martの `track_condition_code` は事前予想時点で未確定なので、初期PoCでは馬場状態を跨いだ `all_conditions` 集計とします。

## 実行

```bash
python src/racenote_history_enrichment_poc.py \
  --bundle ./race_bundle_20260816_札幌11R.json \
  --analysis ./jrdb_analysis_2016_2026YTD_20260823_v1_2.sqlite \
  --mart ./jrdb_stats_mart_2016_2026YTD_20260823_v1_1.sqlite \
  --output-dir ./racenote_history_poc
```

## 出力

- `*_enriched_8runs_poc.json`
- `*_enriched_10runs_poc.json`
- `*_enrichment_comparison_poc.json`

比較JSONには各案の文字数、UTF-8 bytes、現行bundleからの増分、馬ごとの`older_runs`件数、警告件数、距離レンジ仕様を出します。

## older_runsの切り方

PACIの詳細5走とAnalysis側で二重掲載しないため、PACI `recent_runs` に含まれる最古日より前のAnalysis履歴だけを `older_runs` 候補にします。

Analysis側の表示項目はコンパクトに、日付・場・R・芝ダ・距離・実馬場・グレード・脚質・調教指数・着順・異常・最終単勝オッズ・人気に限定します。

## PoC判定

札幌記念16頭および条件の異なる複数レースで実行後、少なくとも以下を比較します。

1. 8走案 / 10走案のファイルサイズ・文字量差
2. 6走目以降が予想判断に実質的な追加材料を与えるか
3. sire / jockey / frameのMart傾向が読みやすく、過剰にJSONを肥大化させていないか
4. `starts` が小さい統計をGPTが過大評価しない構造になっているか
5. 完全一致距離が疎な条件で `distance_ranges` が有効な補助情報になるか
6. 1400m / 1800mの重複境界が過剰な重複情報にならないか
7. 対象日以降のデータ混入がないか

本PoCで採用形を決めてから、本番 `racenote_jrdb.py` またはpipelineへの統合を検討します。
