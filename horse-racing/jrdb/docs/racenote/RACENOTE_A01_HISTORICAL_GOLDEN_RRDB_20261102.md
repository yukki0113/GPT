# A01 — historical golden RRDBのimmutable snapshot固定（2026-11-02）

## 問題
`racenote_historical_golden_20251228_v1.json` の `golden_20` は、以前は毎週上書きする
`RaceReviewDB_CURRENT.zip` のDriveファイルID `1UwNfrupMTHRPhkzULPvClGre4MWz2TFg` と、
2026-10-10時点の固定SHA/サイズを同時に持っていた。CURRENTが正しく週次更新されても、過去の検証CIが停止する。

## 修正
`golden_20` の `file_id` だけを、RRDB snapshotsフォルダの保管済みgenerationへ変更する。

- Drive snapshot: `RaceReviewDB_jrdb_race_review_v0_1_incremental_g38052055588.zip`
- file ID: `1qP-LQwELUTZsEPBxCAVoIO8e-rphchLC`
- size: `47410583`
- SHA-256: `a46eb35f2525cada2ae42ec4e0f2d783e5cb7ed24db5eb2d9b7c07e2322099f9`
- internal `current.json` generation: `jrdb_race_review_v0_1_incremental_g38052055588`
- manifest validation status: `PASS`; period_to: `2026-10-04`
- consumer destination: `rrdb.zip` (変更なし)

2026-11-02にDriveから実物を再取得し、サイズ・SHA・ZIP CRC・内部generationを確認した。既存のgolden固定SHAと完全一致するため、**golden入力データは変更されない**。

## 利用経路
- `.github/workflows/racenote_historical_v052_equivalence.yml`
- `.github/workflows/racenote_btday_v052_prepare.yml`
- `horse-racing/jrdb/config/public_drive/racenote_historical_golden_20251228_v1.json` を使うv0.5.2/v0.5.3等のhistorical手順

両workflowは既存の `tools/gpt_io/public_drive/fetch.py` を使うため、`golden_20` を除外していない限り、新IDがそのまま適用される。固定SHA検証を削除しない。別の週次CURRENTをgoldenの入力として自動使用しない。

## 受入・再発防止
- `test_racenote_a01_immutable_golden.py` は、immutable snapshot ID契約とサイズ・SHA固定、同サイズ改変の拒否を確認する。
- `racenote_a01_golden_rrdb_smoke.yml` は、Driveの不変スナップショット実物を取得し、ZIPの世代・validationを確認する。
- GitHub CIで、週次更新によりCURRENTの内容が変わっても、goldenの取得先と検証入力は不変。

## 対象外
- RRDB CURRENT取得系の動的最新性確認、ID変更契約（A05/A06）。
- `racenote_historical_v052_equivalence.yml` の別件テストfixture不一致
  (`rrdb-recommendation-signals-v0.3` vs `v0.4`)。A01のSHA問題とは独立しており、ここではfixtureを書き換えない。
