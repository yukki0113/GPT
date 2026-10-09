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
| historical BTDAY専用入口 → `SESSION_SEALED` | PASS、24レース・356頭 |
| historical専用入口とgolden Warehouse経路の `normal_view` | PASS、24/24 |
| 既存v0.5.2の2026 Freeze/Verify回帰 | PASS、既存BTDAY-0059 fixture |
| historical BTDAY `save → freeze → verify` | PASS、構造用Decision Core fixtureで24/24、`FROZEN_CLEAN_BLIND` |

`metadata.generated_at` は実行ごとに異なる。Reader View の生の `source_semantic_sha256` はこの時刻を含むため、独立実行の生ハッシュは24/24で異なった。既存 DAY PREP の `evidence_semantic_sha256()` はこの実行メタデータとローカルの照会テレメトリを除外する。この正規化後は24/24で一致した。予想モデルが実際に読む最終 `normal_view` の意味ハッシュは24/24で一致した。生ハッシュの差異を隠さず、正規化後のsource semanticsと実際の `normal_view` の一致を受入判定に用いる。

## 最終ゲート

PR #1908 の [Actions run 37895352821](https://github.com/yukki0113/GPT/actions/runs/37895352821) がRaceReviewDBを取得し、全経路を実行して成功した。機械可読な[同値性レポート](RACENOTE_HISTORICAL_WAREHOUSE_V052_EQUIVALENCE_20251228.json)の `status=PASS`、`mismatch_count=0` を確認した。historical BTDAY 入口はこのPASSレポートと同じaccepted Warehouse generationを要求する。

[Actions run 37896203389](https://github.com/yukki0113/GPT/actions/runs/37896203389) は新しいhistorical入口を同日のaccepted Warehouseで実行し、`SESSION_SEALED` とblindフラグを確認した。入口から生成した `normal_view` はgolden Warehouse経路と24/24で一致した。同runの既存v0.5.2テストは、2026 BTDAY fixture の Freeze/Verify を通した。

[Actions run 37896362096](https://github.com/yukki0113/GPT/actions/runs/37896362096) はhistorical入力に対し、構造用Decision Core fixtureで既存の `save → freeze → verify` を実行し、24/24 の `FROZEN_CLEAN_BLIND` を確認した。このfixtureは判断内容の妥当性を示す予想ではなく、契約とblind境界の回帰検証用である。

## データ境界

`WarehouseRaceNoteReader` は BAC/KYI/CHA/CYB と、KYI が指す過去の ZED/ZKB のみを `BundleBuilder` に渡す。対象日の SED/HJC は読まない。Analysis と RRDB は既存の as-of 検証を通し、forecast_prep は対象日 market を剥がす。受入ゲートは対象日以降の `recent_runs`、市場情報、結果監査の失敗を拒否する。

## 既知の範囲

実データのgolden dayは2025年の1日のみ。2010年の一部で前年2009年の結果キーが必要な場合、accepted Warehouseのcoverage外として既存Readerがfail-closedする。`racenote_request.py` の明示的Raw boundary fallbackは別の監査/rollback手順であり、このhistorical BTDAY入口は自動的に切り替えない。
