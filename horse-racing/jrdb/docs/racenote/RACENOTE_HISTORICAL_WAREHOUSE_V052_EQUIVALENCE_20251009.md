# Historical Warehouse → v0.5.2 同値性監査（2026-10-09）

## 範囲

- 対象は 2010〜2025 のみ。2026 は既存 PACI 経路を維持する。
- Golden day: **2025-12-28**。中山・阪神の 24 レース、356 頭。
- A: annual Raw（BAC/KYI/CHA/CYB 2025、ZED/ZKB 2024・2025）から既存の `build_paci_equivalent()` を使用。
- B: accepted Warehouse `jrdb_normalized_warehouse_v1_2010_2025_g20260921` を既存の `WarehouseRaceNoteReader` で使用。
- A/B は同じ `racenote_jrdb.BundleBuilder`、Analysis current、RaceReviewDB、DAY PREP、forecast_prep、v0.5.2 Reader/session を使用する。

## 確認済み

| 判定 | 結果 |
| --- | --- |
| race roster | PASS、24/24 |
| horse roster | PASS、356/356 |
| BAC/KYI/CHA/CYB/ZED/ZKB 件数 | PASS、24/356/356/356/3158/3158 |
| RaceNote base evidence semantic hash | PASS、24/24 |
| 共通 Analysis 履歴補強後の evidence semantic hash | PASS、24/24 |
| 履歴補強段階の v0.5.2 `normal_view` semantic hash | PASS、24/24 |
| 最終 RRDB を含む DAY PREP、forecast_prep、`SESSION_SEALED` | PASS、両経路24/24 |
| 最終 `normal_view` semantic hash | PASS、24/24 |
| Reader manifest model identity | PASS |
| 生の `source_semantic_sha256` | 不一致（実行メタデータを含む） |
| execution-only metadataを除いたsource semantics | PASS、24/24 |
| market/result blind firewall | PASS、両経路 |

`metadata.generated_at` は実行ごとに異なる。Reader View の生の `source_semantic_sha256` はこの時刻を含むため、独立実行の生ハッシュは24/24で異なった。既存 DAY PREP の `evidence_semantic_sha256()` はこの実行メタデータとローカルの照会テレメトリを除外する。この正規化後は24/24で一致した。予想モデルが実際に読む最終 `normal_view` の意味ハッシュは24/24で一致した。生ハッシュの差異を隠さず、正規化後のsource semanticsと実際の `normal_view` の一致を受入判定に用いる。

## 最終ゲート

PR #1908 の [Actions run 37895352821](https://github.com/yukki0113/GPT/actions/runs/37895352821) がRaceReviewDBを取得し、全経路を実行して成功した。機械可読な[同値性レポート](RACENOTE_HISTORICAL_WAREHOUSE_V052_EQUIVALENCE_20251228.json)の `status=PASS`、`mismatch_count=0` を確認した。historical BTDAY 入口はこのPASSレポートと同じaccepted Warehouse generationを要求する。

## データ境界

`WarehouseRaceNoteReader` は BAC/KYI/CHA/CYB と、KYI が指す過去の ZED/ZKB のみを `BundleBuilder` に渡す。対象日の SED/HJC は読まない。Analysis と RRDB は既存の as-of 検証を通し、forecast_prep は対象日 market を剥がす。受入ゲートは対象日以降の `recent_runs`、市場情報、結果監査の失敗を拒否する。
