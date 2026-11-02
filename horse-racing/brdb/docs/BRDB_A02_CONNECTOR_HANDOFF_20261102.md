# A02 — BRDB CURRENTの週次追従（既存Driveコネクタ運用）

更新日: 2026-11-02
対象: BRDBのCURRENT resolverとローカルcacheのみ。ほかの競馬DB、PWA、共通Driveモジュール、Drive共有設定は対象外。

## 決定済みの輸送方針

- 通常の認証付きDrive取得: 接続済み **Google Driveネイティブコネクタ → GPT実行環境 → GitHub正本のBRDB Python**。
- サービスアカウント、Drive REST API、OAuth secretの新設をしない。
- 公開 `gdown` は通常CURRENTには用いない（既存のimmutable公開ファイルの固定SHA取得のみ例外）。
- Driveのフォルダ・ファイル・共有権限・台帳は変更しない。共有権限は既存のユーザー確定ルールを正本とする。
- 前回PR #2328のAPI-only実装はPR #2330で完全に撤回済み。

## 今回の実装

`src/brdb_current.py` の通常入口は固定Git SHAによる自動取得を行わず、
`--current-zip` と `--connector-receipt` の両方を必須とする。
`src/brdb_current_connector.py` は受け取った実物だけを検証する純粋なローカル処理であり、
Google Driveへアクセスしない。

### 取得・受け渡し手順（GPT/Work）

1. コネクタで正規フォルダ `1WhcWthqKlTvVrbK3-gkiPZW70yr9e6Bv` を列挙。
   `BloodReviewDB_CURRENT.zip` **完全一致が1件**であることを確認。
   リストが途中で省略された場合は一意とみなさない。代替候補の推測・最終更新日時だけの自動選択は禁止。
2. 対象ファイルのmetadataを取得し、ID、正規親フォルダ、ファイル名、size、更新日時、mimeTypeを照合。
3. コネクタから**当該ファイルの実物**をGPTのローカル作業領域へmaterializeする。
   取得後のmetadata/一覧も確認し、取得中にファイルID・サイズ・更新日時・名前や候補数が変わっていれば停止。
4. 同じ実行でローカルの `connector_receipt.json` に取得元情報を保存する（テンプレートは下記）。
   `observed_at_utc` は今回の確認時刻。過去のreceiptを使い回さない。
5. GitHub正本の `src/brdb_current.py` をローカル実行する。ReaderがPASSした場合だけ、新しい状態を採用。
   成功時のprovenanceにはfile ID、remote modified time、ZIP SHA-256、generation_idを残す。

```bash
python horse-racing/brdb/src/brdb_current.py \
  --cache-root /path/to/local-brdb-cache \
  --current-zip /path/to/BloodReviewDB_CURRENT.zip \
  --connector-receipt /path/to/connector_receipt.json
```

### source receipt v1

```json
{
  "schema_version": 1,
  "transport": "native_google_drive_connector",
  "folder_id": "1WhcWthqKlTvVrbK3-gkiPZW70yr9e6Bv",
  "candidate_count": 1,
  "file_id": "1fvqJgMMf1KUNL0Zr_GVnUAC6FyU8rMVz",
  "file_name": "BloodReviewDB_CURRENT.zip",
  "source_size_bytes": 6923691,
  "source_modified_time": "2026-10-22T00:00:13.522Z",
  "observed_at_utc": "2026-11-02T12:00:00Z"
}
```

この値は**項目例**であり、毎回コネクタ実測値に差し替える。
`candidate_count=1` は、取得前後の正規フォルダ確認を行った結果としてのみ記録する。
`observed_at_utc` が実行時点から1時間超古い場合は拒否する。コネクタが取得したZIPの内容SHAはPython自身が計算する（remoteがSHAを返すと仮定しない）。

### キャッシュ

- 受領した実物のSHA-256と、receiptのID・更新時刻・サイズを照合した後、同一の受入済み内容ならcache HIT。
- 同一IDで内容が変わった場合、新IDに置き換わった場合、同一内容の再公開でも再検証が必要な場合は再取得分を検証する。
- ZIP展開のパストラバーサル/重複を拒否し、`BloodReviewReader` のcurrent/manifest/Parquet整合性検証を維持。
- 同じgeneration IDに異なるcurrent/manifest/必須ファイルを登録する行為は拒否。
- 受入前に異常を検知したらcacheの前世代を保持するが、今回の呼出しでは失敗し、古い世代をCURRENTとして返さない。
- 転送元が以前より古い更新時刻に後退した場合は受け入れない。
- cache更新時は専用lockで直列化し、検証後のみstateをatomic更新する。

**注意:** Python自身にはネイティブDriveコネクタの呼出し能力がないため、ZIP・receiptの取得/生成はChatGPT/Work側のオーケストレーション責務。
モジュール単体を定期起動してもDriveの最新情報は取得できない。週次更新はこの既存のGPTオペレーションに組み込む。

## 不変の過去再現モード

以前の `config/public_drive/brdb_current_v0_1.json` の固定SHA/IDは削除・変更しない。
過去世代を再現する場合だけ、明示的に次を利用する。

```bash
python horse-racing/brdb/src/brdb_current.py \
  --cache-root /path/to/immutable-cache \
  --transport-manifest horse-racing/brdb/config/public_drive/brdb_current_v0_1.json
```

この固定manifestを週次CURRENT用に使い回さない。

## テスト/受入

- `tests/test_brdb_current.py`: 固定SHA再現と旧cache保護。
- `tests/test_brdb_current_connector.py`: 同ID更新、新ID切替、cache HIT、破損、古いreceipt、世代ID衝突、一意性、前世代への後退、並列ロック。
- `.github/workflows/brdb_a02_connector_handoff_regression.yml`: GitHub上でオフライン・mock入力に対するBRDB限定のCIのみ。
- 実データの受入検証では、GPTコネクタで取得した実ZIPを渡して検証し、source SHA・generationを記録する。

### 他システムへの影響境界

- `tools/gpt_io/gdrive/`、`tools/gpt_io/public_drive/`など**共通Drive実装は変更しない**。
- Driveファイル本体、権限、台帳、RRDB/Analysis、PWA/Pages、RaceNoteの動作は変更しない。
- 固定SHAの過去検証と、最新版の通常CURRENTを混同しない。
