# A06 — RRDB CURRENT の新しいDriveファイルIDへの安全な切替

更新日: 2026-11-02  
対象: 中央競馬JRDBのRRDB CURRENT取得・参照IDの管理契約。

## 前提と現状

2026-11-02にネイティブDriveコネクタを用いて正規フォルダを直接列挙し、CURRENT実物を読み直した。

| 確認内容 | 実測 |
|---|---|
| canonical folder | `13m2MGibjEHOvBY6LmENQat4PuTZGcdwc` |
| exact filename | `RaceReviewDB_CURRENT.zip` |
| 現行file ID | `1UwNfrupMTHRPhkzULPvClGre4MWz2TFg` |
| modifiedTime | `2026-11-02T07:10:19.372Z` |
| ZIP bytes | `46,987,840` |
| ZIP SHA256 | `cb348cb825aaa5765e58211321cec77de6ba7c92b157778bd1bb1c6f0910ea41` |
| ZIP内部generation | `jrdb_race_review_v0_1_incremental_20261101_01` |
| manifest period_to | `2026-11-01` |
| manifest validation_status | `PASS` |

現時点では運用どおり**同一file IDへの上書き**が続いている。新しいIDへの切替はまだ発生していない。

## 2種類の更新を分ける

### 通常の週次更新（ID維持）

- RRDBの定例運用が同じDrive `file_id` に新しいZIPを反映。
- `src/racenote_fetch_rrdb_current.py` がそのIDを取得し、毎回 **現物SHAを計算**。
- ZIP CRC、安全なメンバー、CURRENTポインタ、世代一致、manifest PASS、期間末日を検証。
- 取得receiptには `file_id`・`sha256`・`generation_id`・`period_to`・`source_contract_sha256` が保存される。
- 古い世代のSHAをGitに固定せず、週次上書きのたびにGitを編集しない。

### 例外: DriveファイルIDの変更

- 自動最新検索、modifiedTimeだけでの選択、以前のIDへの黙ったfallbackを**禁止**。
- GPTに接続済みのネイティブDriveコネクタで、canonical folderを直接列挙し、同名 `RaceReviewDB_CURRENT.zip` が一意か確認。
- 新しいファイルの親フォルダ、正確な名前、ファイルID、サイズ、更新時刻を確認して、実ZIPを取得し世代とmanifestを検証。
- **ファイル本体・共有権限には触れず**、Gitの `config/rrdb_current_source_v1.json` の `file_id`、`source_revision`、`approval_reference`、`approval_verified_at_utc` を変更するPRを作成。レビュー完了後にmerge。
- これにより後続の取得は新IDへ移行する。旧IDを代替取得しない。新IDが利用不能・中途変更・不正ZIPならfail-closed。
- 既存CURRENTと新CURRENTが同時に同名で存在する場合、一意の正本が確定するまでポインタを昇格しない。GPTコネクタが解決した正本以外を推測しない。

更新時にGitで**実データのSHA256を固定しない**。それはimmutable baseline（A01／A03）の役割と異なる。
承認するのは変更するDriveファイルIDとcanonical location。取得した実データのSHAは毎回検証したうえでrun receiptに固定する。

## 実装対象

- `config/rrdb_current_source_v1.json`: Gitの唯一の承認済みCURRENT IDポインタ。
- `src/rrdb_current_source_contract.py`: JSONから承認済みIDを検証して取得（ネットワークなし）。
- `src/racenote_fetch_rrdb_current.py`: 通常の既存公開ファイル取得方式を維持しつつ、上記IDを使用。取得ZIPのCRC／manifest・世代と各SHAを確認し、receiptに出典を残す。
- `src/racenote_racereview_current.py`: **既存のresolver**が持つ固定IDだけを同じ承認済みポインタ参照に変更。既存の認証・Driveブリッジ実装は変更しない（新しいAPI方式は導入しない）。
- `racenote_v056_forward_paci_t1.yml`: A05で指定された `rrdb.file_id` とこのポインタの一致を**ダウンロード前に**確認。取得後は従来のA05 ZIP SHA/coverage gateが検証。
- 他のRRDBを使う共有BTDAYは既存fetch入口のデフォルトID変更へ追従。

```bash
python horse-racing/jrdb/src/racenote_fetch_rrdb_current.py \
  --output /tmp/rrdb-current.zip \
  --receipt /tmp/rrdb-current-receipt.json
```

A05受入と紐づけるFORWARD時は `--expected-file-id` を使用する。
必要に応じて `--expected-sha256` で承認済み実データSHAも照合できる。

## 互換性と失敗時の扱い

- A01のhistorical golden・A03のimmutable manifest（Drive固定ID＋固定SHA）は変更しない。
- 現行file IDに変更がなければ、取得結果・データ世代の意味は従来と同じ。
- ZIP・ID・manifest・世代の不一致はすべて停止。**別IDへ自動fallbackしない**。
- A05専用運用の受入情報が古い場合、T1は新IDへ無断で切り替えず停止して、受入のやり直しを要求する。
- 新規サービスアカウントやDrive REST API、共有権限・共通Driveツール・PWAの変更はしない。
- 現時点で新ID実運用のE2E試験は発生していないため、切替の運用受入は将来の実際のID変更時に判定する。

## テスト

`tests/test_racenote_a06_rrdb_current_id_rotation.py` の決定的テスト:
同一IDで別SHAとなる週次更新、新IDの承認済み差替え、旧IDを拒否、SHA不一致、manifest FAIL、
未承認sourceの拒否、更新途中のポインタ切替拒否、既存resolverのID一致を確認。

専用CIでは読み取り専用公開取得で現在のDrive CURRENTを実測・receipt化して確認する。
