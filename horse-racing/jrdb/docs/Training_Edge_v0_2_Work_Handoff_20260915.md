# Training Edge v0.2 — Workスレッド運用引き継ぎ

Date: 2026-09-15

## 1. 目的

この文書は、Training Edge v0.2 の**日次生成・運用検証・新聞/PWA受け渡し**を、研究スレッドから専用Workスレッドへ切り出すための引き継ぎ正本とする。

研究スレッド側で確定済みの科学仕様・モデル・calibration・runtime fingerprintは変更しない。Workスレッドは、確定済み仕様を毎開催日に再現可能な形で実行し、CSV/auditを残す運用担当とする。

## 2. 現在状態

- `TRAINING_EDGE_V0_2_SPEC = FROZEN`
- `2026_OOT_STATUS = OPENED_AND_CONSUMED`
- `POST_OOT_RETUNING = PROHIBITED`
- `DAILY_FORWARD_IMPLEMENTATION = READY`
- `RUNTIME_FINGERPRINT = FROZEN_AND_ENFORCED`
- `DAILY_RUNTIME_TESTS = PASS`
- `FIRST_LIVE_FORWARD_DAY = NOT_YET_RUN`

2024-2025および2026-09-13までのデータは、fresh holdoutとして再利用しない。

## 3. 参照すべき正本

### 科学仕様

- `horse-racing/jrdb/docs/Training_Edge_v0_2_Freeze_20260915.md`
- `horse-racing/jrdb/docs/Training_Edge_v0_2_OOT_Input_Route_Addendum_20260915.md`
- `horse-racing/jrdb/config/training_edge_v0_2_calibration.json`
- `horse-racing/jrdb/src/training_edge_v0_2_core.py`

### 日次運用

- `horse-racing/jrdb/docs/Training_Edge_v0_2_Daily_Forward_Implementation_20260915.md`
- `.github/workflows/jrdb_training_edge_v02_daily_issue.yml`
- `horse-racing/jrdb/src/score_training_edge_v0_2_daily.py`
- `horse-racing/jrdb/config/training_edge_v0_2_runtime_fingerprint.json`

### runtime freeze evidence

- Issue `#975`
- run `34933935199`
- eligible 2013-2025 fit rows `256701`
- semantic SHA-256 `4c59926f41cb213a924285743ffa5c923c5f08b2c0a1fa7b042cd633aa1c5d33`
- C prediction SHA-256 `7a30ceb98e2f3bbad281f1aae88611cf51d503ef12eca4d0f639ca859becbe87`
- CAB prediction SHA-256 `33d483132623ef8fd714e439702ad000dd3854be4674dc8c053137b9ff3ef250`

### daily implementation test evidence

- Issue `#977`
- run `34941126889`
- Python `3.12.14`
- NumPy `2.5.3`
- pandas `3.0.5`
- SciPy `1.18.1`
- scikit-learn `1.9.1`
- `11 passed`

## 4. Workスレッドの担当範囲

Workスレッドは次を担当する。

1. 対象日のPACI/SED状態確認
2. 正式日次経路の起動
3. 2010-2025履歴 + 2026既決着履歴の再構築
4. frozen scientific asset確認
5. runtime fingerprint確認
6. Training Edge v0.2 の対象日score生成
7. `独自指数_YYYYMMDD.csv` とaudit JSONの監査
8. 新聞/PWA担当への受け渡し
9. 開催後、必要に応じて結果と指数の記録・監査
10. run ID、Issue、artifact、SHA等の実行証跡を残す

Workスレッドは、以下を行わない。

- v0.2特徴量の追加・削除
- Ridge alpha変更
- calibration再計算
- 2026結果を見た閾値・表示変換の変更
- odds/popularityのEdgeへの混入
- 既知結果を使った再調整

これらが必要になった場合は、別versionの研究課題として研究スレッドへ戻す。

## 5. 正式な日次前向き経路

正式なライブ前向き実行は、**対象日PACIが存在し、対象日SEDがまだ存在しない状態**でのみ行う。

標準経路:

1. Workスレッドで対象日 `YYYYMMDD` を受ける。
2. Drive上で対象日PACIの存在を確認する。
3. 対象日SEDが存在しないことを確認する。
4. Issue駆動の正式workflow `.github/workflows/jrdb_training_edge_v02_daily_issue.yml` を起動する。
5. 2010-2025 JRDB annual rawを監査済み取得経路から再構築する。
6. 2026はDriveのPACIと、対象日前日までに存在するSEDを使用する。
7. Index Baseを再構築する。
8. Official RunPerfを再構築する。
9. Training Edge v0.2 input projectionを生成する。
10. scorer実行前に frozen runtime fingerprint を照合する。
11. fingerprint一致時のみ対象日scoreを生成する。
12. 出力CSVとauditを監査する。
13. CSV/audit artifactとrun証跡を保存する。
14. 新聞/PWA担当へCSVを渡す。

### fail-closed条件

少なくとも以下ではCSVを正式成果物として出さない。

- 対象日PACIがない
- 対象日SEDが既に存在する
- scientific asset hash不一致
- runtime fingerprint不一致
- 2013-2025 fit population不一致
- key重複
- 必須列欠損
- 出力契約違反

## 6. 新聞/PWA受け渡し契約

ファイル名:

`独自指数_YYYYMMDD.csv`

列:

```csv
date,venue_code,race_no,horse_no,training_edge_index
```

identity key:

`date + venue_code + race_no + horse_no`

`training_edge_index` は frozen development percentile を `0.0-100.0` で表現し、`ROUND_HALF_UP` で小数点1位に丸める。

frozen-history eligibility不足の馬も行自体は残し、指数だけ空欄とする。

新聞/PWA側はidentity joinのみ行い、再計算・再scale・空欄補完・再丸めをしない。

## 7. まず2026-09-13で運用回帰検証する

Workスレッドへ切り出した最初の作業として、**2026-09-13を使った日次経路の回帰検証**を行う。

ただし2026-09-13は既に結果SEDが存在し、2026 OOTにも含まれているため、これはfresh holdoutでもlive forwardでもない。

`0913_REPLAY = RETROSPECTIVE_OPERATIONAL_VALIDATION`

`0913_REPLAY != LIVE_FORWARD`

`0913_REPLAY != NEW_OOT`

### 0913 replayの入力境界

擬似的にレース前状態を再現する。

- 2010-2025: 確定済み履歴を使用
- 2026 PACI: 2026-09-13まで使用
- 2026 SED: **2026-09-12までのみ使用**
- `SED 2026-09-13`: score生成前の入力から明示的に除外
- odds/popularity: 使用しない

つまり、`PACI0913あり / SED0913なし` の状態を再現してscoreを生成する。

### 重要

本番workflowの「target SEDが存在したら停止」というfail-closed条件は変更しない。

0913 replayのために本番guardを緩めてはならない。必要ならWorkスレッド側で**専用のretrospective replay経路**を追加し、本番workflowとは分離する。

### 0913 replayで確認する項目

score生成時点で以下を確認する。

- frozen scientific assetが一致
- runtime fingerprintがPASS
- fit max year = `2025`
- target date = `2026-09-13`
- target result required = `False`
- market fields used = `False`
- target-day全出走馬がCSVに存在
- identity key重複なし
- eligible馬は指数あり
- ineligible馬は行を残して指数空欄
- `training_edge_index` は小数点1位
- raw/unrounded値はaudit側のみ
- CSV/auditのSHAとrun証跡を保存

### 結果SEDの使用

`独自指数_20260913.csv` とauditを固定した後でのみ、SED0913を参照して結果突合してよい。

その結果比較は**運用確認・参考検証**としてのみ扱い、v0.2の再調整には使わない。

## 8. 0913 replay完了後

0913 replayがPASSしたら、Workスレッドの標準作業を次の2種類に分ける。

### A. 開催前

ユーザー指示例:

`0919の独自指数を作成してください。`

Workスレッドは正式live forward経路を実行し、CSV/auditを返す。

### B. 開催後

結果SEDが入った後、必要に応じて指数と結果を突合・蓄積する。

開催後データは将来の新version研究に利用できるが、frozen v0.2自体は変更しない。

## 9. 初回live forwardの定義

初回live forwardは、2026-09-13より後の開催日で、対象日SEDが存在する前に正式workflowを起動し、CSV/auditを固定できた最初の日とする。

0913 replayはこのカウントに含めない。

初回live forward成功後にのみ:

`FIRST_LIVE_FORWARD_DAY = YYYY-MM-DD`

へ更新する。
