# A02 — BRDB operational CURRENTの動的解決とキャッシュ無効化

更新日: 2026-11-02
監査参照: `GIT_WEEKLY_ASSET_GENERATION_AUDIT_20261102.md` / A02

## 変更対象と残す資産

- 通常CURRENT入口: `src/brdb_current.py` → `src/brdb_current_live.py`。
- canonical Drive folder: `1WhcWthqKlTvVrbK3-gkiPZW70yr9e6Bv`
- exact name: `BloodReviewDB_CURRENT.zip`
- 過去再現の不変な旧世代: `config/public_drive/brdb_current_v0_1.json`（`eeca93556584a5b8`）。Git側固定SHAは過去の受入済み世代の証跡として維持する。
- Reader: `brdb_pedigree_reader.py`（current/manifest/全必須オブジェクトSHA/親関係を検証）をそのまま使用。

## 通常モード (dynamic)

```bash
export GPT_GDRIVE_SERVICE_ACCOUNT_JSON='<service account JSON>'
python horse-racing/brdb/src/brdb_current.py --cache-root /path/to/brdb-cache
```

注: 公開 `gdown` 取得だけではDriveの最新revisionやfolder内重複を保証できないため、**通常モードは認証済みGoogle Drive APIが必要**。サービスアカウントにcanonical folderへの読み取り権限を付与すること。これがない実行環境では古いキャッシュを返さず失敗する。

処理:

1. 指定folder配下で完全一致名を、Drive APIの全ページで照会する。候補0件・2件以上は停止。
2. 取得したIDのmetadataを再読し、親folder・名前・mimeType・version・modifiedTime・size・MD5を照合する。
3. このfingerprintが前回受入状態と完全一致し、既存Readerも検証できればcache HIT。返却前にもリモートfingerprintを再照会する。
4. fingerprintに差があればstagingへZIPを取得し、size・MD5・SHA-256を計算、取得後とReader validation後の両方でリモートが不変であることを検査。
5. 新世代の `current.json`、manifest、Parquetの整合性をReaderで検証し、`generations/<generation_id>` を受入。既存generation IDとの内容衝突は停止。
6. 検証が完了してからlocal stateをatomic replace。失敗時は以前の受入cache/stateを維持するが、**古い世代をCURRENTとして返さない**。

### 同一IDの週次更新

同じDriveファイルIDに新しい内容が上書きされるとmodifiedTime/version/MD5が変わり、古いcacheはMISSとなる。新しい実物からSHAを計算し、Reader検証に成功したものだけ受け入れる。Git固定manifestは変更不要。

### 同名での新ID切替

公開folderに新IDのCURRENTが1つだけ存在するなら新IDへ追従する。新旧が同時に同名で残れば、曖昧性を検出して停止。旧IDのファイルを別名にする、または正規運用の承認を経て削除・整理すること。推測で最新modifiedTimeのファイルを選ばない。

## 過去再現モード

```bash
python horse-racing/brdb/src/brdb_current.py \
  --cache-root /path/to/immutable-replay-cache \
  --transport-manifest horse-racing/brdb/config/public_drive/brdb_current_v0_1.json
```

SHA・サイズ・ID固定の従来モードをそのまま使用する（別cacheディレクトリ推奨）。このモードは週次CURRENTへ追従する設計ではない。

## 回帰・検証

- `tests/test_brdb_current.py`: pinned replayと失敗時cache保護。
- `tests/test_brdb_current_live.py`: warm/cold、同一ID更新、ID変更、重複・不存在、更新中変更、ダウンロード破損、世代ID内容衝突、metadata不足、認証不能。
- `.github/workflows/brdb_a02_current_resolver_regression.yml`: 上記の決定的・非通信テストをPRで実行。

実Drive上では2026-11-02時点、canonical folderに同名CURRENTは1件、ID `1fvqJgMMf1KUNL0Zr_GVnUAC6FyU8rMVz`、サイズ `6,923,691` bytesだった。
テストは疑似Drive APIを使うため、実サービスアカウントの共有権限・認証環境の運用確認とは区別する。

## 別途必要な権限是正

Drive metadataでCURRENTの権限に `anyone: writer` が残る。
動的取得では以前の固定SHA gateがないため、運用開始前に**Viewerへ変更**し、owner/運用者以外が上書きできないことを確認する。権限変更はこのPRに含まれない。
誤った更新でも内部manifestがPASSなら自動で信頼しうる点を認識し、運用権限と更新後の受入監査が必要。

## A02受入境界

技術的な最新版discovery・キャッシュinvalidationsは上記テストで検証する。環境認証とDrive権限是正が揃って初めて本番利用可とする。BRDB blood scoring / Newspaper / PWA公開は行わない。
