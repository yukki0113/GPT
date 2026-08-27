# RaceNote v1 production contract

RaceNote v1.0 は、JRDB PACIをGPT向けの1レース1JSONへ変換したbase情報に、Analysis Lite / Stats Martからas-of-safeな履歴・統計を追加した正式な最終bundle仕様です。

## Stable entrypoints

- request router: `src/racenote_request.py`
- PACI base converter: `src/racenote_jrdb.py`
- production enrichment: `src/racenote_history_enrichment.py`
- machine-readable schema: `schema/racenote_bundle_schema_v1_0.json`

`src/racenote_history_enrichment_poc.py` は、8走/10走比較などの検証を行ったPoC engineとして当面残します。通常利用者・GPTはproduction entrypointのみを使用します。

## Version boundary

```text
PACI
  -> racenote_jrdb.py
  -> base RaceNote schema v0.2
  -> racenote_history_enrichment.py
  -> final RaceNote schema v1.0
```

base v0.2 はPACI固定長変換層として維持し、GPT-facingな正式bundleはenrichment後のv1.0とします。

v1.0 bundleでは `metadata.history_enrichment.base_schema_version` に元のbase schema versionを保持します。

## History layers

通常RaceNoteは最大8走を表示します。ただし固定8件でも、キャリア上の完全な直近8走でもありません。

```text
recent_runs
  source: PACI
  role: detailed_recent_history
  max: 5

older_runs
  source: JRDB Analysis Lite
  role: compact_older_history
  max: 3
  selection: strictly older than oldest recent_run
```

`history_coverage.run_layers` に各層のsource / role / observed_count / max_count / completenessを明示します。

海外戦を含むキャリア完全性は推測しません。

## History coverage

`history_coverage.scope = jrdb_jra_history` とし、RaceNote内の履歴がJRDB/JRA履歴範囲であることを明示します。

主なreason:

- `jra_history_observed`
- `no_prior_jra_history_observed`
- `foreign_based_entry_no_jra_history`
- `target_entry_not_found`

海外所属馬でJRA履歴が0の場合、`historical_profile = null` とし、「0戦」と「履歴範囲外」を区別します。

国内所属馬が海外遠征を挟む場合も、海外戦の完全収録は保証しません。

## Distance policy

完全一致距離統計を残した上で、対象距離に該当する距離レンジ統計を追加します。

```text
1000-1400m
1400-1800m
1800-2400m
2500m+
```

1400mと1800mは隣接2レンジに重複所属します。
2400mは1800-2400mだけに所属し、長距離は2500mからとします。

対象:

- horse `historical_profile.distance_ranges`
- sire stats `distance_ranges`
- jockey stats `distance_ranges`
- race-level frame stats `distance_ranges`

exact統計をrange統計へ置換せず、両方を保持します。

## Sample-size policy

startsに基づく説明用の母数帯を付与します。

```text
0       none
1-19    small
20-49   moderate
50+     sufficient
```

`sample_size_band` は統計的有意性を意味しません。率・wins・top3・startsを加工せず保持し、GPTが小母数の100%等を過大評価しにくくする補助情報です。

## As-of policy

過去RaceNoteでは常に、

```text
as_of_exclusive = target_date
```

とします。

- 馬自身の履歴: `race_date < target_date`
- target yearのsire/jockey/frame統計: Analysis Liteから `race_date < target_date` で再計算
- prior completed years: Stats Martから取得

対象レース結果・対象日当日以降の結果を使いません。

## Stats scope

初期production v1.0:

- 5 calendar years including target-year YTD
- track condition: `all_conditions`
- sire / jockey: horse-level
- frame: race-level
- exact distance + target-relevant distance ranges
- payout/return-rate statisticsは含めない

## Missing values

- scalar unknown: `null`
- list with no rows: `[]`
- whole optional component unavailable: `null`
- 推測補完しない

特に海外馬・海外遠征・source欠損について、存在しない履歴を生成しません。

## Compatibility

v1.0はbase v0.2のPACI由来情報を削除せず、enrichment項目を追加します。

既存の `recent_runs` / `older_runs` フィールド名も維持します。意味の明確化は `history_coverage.run_layers` で行います。

## PoC evidence used for promotion

本番昇格判断には以下の異なる条件を含む5レースPoCを使用しました。

- 北九州記念: 芝短距離・ハンデ
- 京都新聞杯: 3歳GII・2200m・浅いキャリア
- マーチS: ダートGIII
- 万葉S: 3000m・少頭数・希少条件
- ジャパンカップ: 古馬GI・海外所属馬

PoCから得た主な修正:

- exact distanceだけでは疎い -> overlapping `distance_ranges`
- 小母数率の誤読 -> `sample_size_band`
- 海外馬0履歴の誤読 -> `history_coverage`
- `recent_runs` を完全な直近N走と誤読 -> `run_layers`
- 履歴量は5詳細 + 3簡略の最大8走を採用

以後の通常RaceNote生成はv1.0を正本仕様とします。
