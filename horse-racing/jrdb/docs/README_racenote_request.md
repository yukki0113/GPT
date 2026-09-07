# RaceNote Request Router

RaceNote生成を「過去データ取得」「当日取得」「未来取得」に分けず、1つのリクエスト契約で扱うための入口です。

## Design goal

ユーザー/GPTからは次だけを指定します。

- `date` — 対象日
- `venue` — 任意。未指定なら全開催
- `race` — 任意。指定時は `venue` 必須

例:

```text
明日8/27のRaceNoteを作成してください。
2025/08/24のデータを取得してください。
2025/08/24 新潟11RのRaceNoteを取得してください。
```

RaceNote Request Routerが日付と対象範囲を正規化し、データ取得方法を内部で選択します。

## Enrichment artifact resolution

RaceNoteのAnalysis Lite / Stats Martは2つの互換経路で解決します。

- `--analysis` と `--mart` を両方明示した場合: 従来どおりそのSQLiteを利用
- どちらかが未指定の場合: `--store-manifest` または `JRDB_STORE_MANIFEST` から `src/jrdb_store.py` を使って不足artifactをresolve
  - Analysis: `jrdb://analysis/current`
  - Stats Mart: `jrdb://stats/current`

Store ResolverはDrive live manifestのsize/SHA-256を検証し、ローカル実体をcontent-addressed cacheとしてmaterializeします。ConsumerはDrive File IDや恒久ローカルpathを保持しません。

現行GitHub Actionsの `[RACENOTE_REQUEST]` workflowは後方互換のためIssueで指定されたAnalysis/Mart URLをdownloadし、Routerへ明示pathとして渡します。Store bridgeはRouterの追加機能であり、既存Actions経路を壊しません。

Store設計は `docs/JRDB_Store_Resolver_v0_1.md` を正本とします。

## Temporal routing

日付判定と対象範囲判定を分離します。

```text
target_date < today  -> past
target_date = today  -> current
target_date > today  -> future
```

対象範囲は独立して以下です。

```text
venueなし             -> all
venueあり / raceなし  -> venue
venueあり / raceあり  -> race
```

### current / future

```text
JRDB PACI
 -> racenote_jrdb.py
 -> Analysis Lite enrichment
 -> Stats Mart enrichment
 -> selected bundles
 -> ZIP
```

### past

過去日は **publishableなRaceNote Archiveをpreferred base backend** とします。

```text
publishable full-month RaceNote Archive
 -> base RaceNote v0.2 restore
 -> Analysis Lite (race_date < target_date)
 -> Stats Mart as-of aggregation
 -> selected bundles
 -> final RaceNote v1.0 ZIP
```

Archiveはbase v0.2だけを保存するdelivery cacheです。final v1.0はrequest時点のproduction enrichmentで毎回生成します。

Archiveを解決できない、対象月が未整備、validationで拒否された、または対象scopeが存在しない場合は、従来のsafe fallbackを維持します。

2026年以降の過去日:

```text
2026+ historical date
 -> JRDB daily PACI
 -> racenote_jrdb.py
 -> Analysis Lite (race_date < target_date)
 -> Stats Mart as-of aggregation
 -> selected bundles
 -> ZIP
```

2025年以前:

```text
<=2025 historical date
 -> annual Raw
 -> target-date BAC/KYI/CHA/CYBだけ抽出
 -> KYI prev1-5が明示するSED/SKBだけ抽出
 -> PACI-equivalent ZIPを再構成
 -> racenote_jrdb.py
 -> Analysis Lite (race_date < target_date)
 -> Stats Mart as-of aggregation
 -> selected bundles
 -> ZIP
```

Raw fallbackはArchive未整備期間・Archive validation失敗時の互換経路であり、Raw/Core自体は引き続き監査・再生成用のsource of truthです。

## RaceNote Archive distribution / resolution

大容量Archive SQLiteはGit treeへcommitしません。

固定命名:

```text
jrdb_racenote_archive_YYYYMM_v1_0.sqlite
```

現在の配布実装では、immutableなGitHub Release assetとして配置します。

Release tag:

```text
jrdb-racenote-archive-YYYYMM-v1.0
```

同じReleaseへ次のvalidation/reproducibility metadataも配置します。

- `racenote_archive_manifest.json`
- `archive_validation.json`
- `month_build_summary.json`
- `expected_race_index.json`
- `source_manifest.json`

`src/resolve_racenote_archive_release.py` は対象月のRelease候補をversion降順で探索し、SQLite実体をダウンロードした後に次を検証します。

- SQLite `integrity_check`
- Archive schema version / base schema version
- `target_month`
- `coverage_mode = full_month`
- `publication_status = publishable`
- `provenance_status = complete`
- `expected_race_count == actual race_count`
- `expected_index_sha256` が存在すること

tag名だけでは採用せず、SQLite metadataを最終判定根拠にします。

通常の `[RACENOTE_REQUEST]` workflowは過去日についてresolverを自動実行し、解決できた場合だけ `racenote_request.py --archive <local-path>` を渡します。resolverが `not_found` / `error` の場合もrequestは停止せず、Raw/PACI fallbackへ進みます。

月次Archiveをpublishする検証済み経路:

```text
[RACENOTE_ARCHIVE_PUBLISH] <request_id>
 -> Analysis Liteからauthoritative monthly race identityを生成
 -> annual Rawからfull-month base v0.2を再構築
 -> identity exact match
 -> 360/360等のfull scan validation
 -> publishable確認
 -> immutable GitHub Release asset
```

## Future leakage contract

過去レースでは `as_of_exclusive = target_date` を固定します。

- Analysis個体履歴: `race_date < target_date`
- target year Stats: Analysisを `race_date < target_date` で集計
- prior years Stats: Stats Mart年次行を利用
- 対象レース結果、対象日以降の結果は参照しない
- Historical RawではKYIが明示するprev1-5 result keyのみをSED/SKBへJOINする
- Archive内base v0.2も、保存時に`recent_runs`がtarget dateより前であることを検証する

完成済み当年Martをそのまま過去日へ適用しません。

## CLI

### Plan only

```bash
python src/racenote_request.py \
  --date 20250824 \
  --venue 新潟 \
  --race 11 \
  --analysis ./jrdb_analysis.sqlite \
  --mart ./jrdb_stats_mart.sqlite \
  --plan-only
```

### Past race with a resolved Archive

外部artifact探索はRouterの外で行い、Routerにはローカル解決済みSQLiteだけを渡します。

```bash
python src/racenote_request.py \
  --date 20250824 \
  --venue 新潟 \
  --race 11 \
  --analysis ./jrdb_analysis.sqlite \
  --mart ./jrdb_stats_mart.sqlite \
  --archive ./jrdb_racenote_archive_202508_v1_0.sqlite \
  --output ./output
```

`--archive` を省略した場合、またはArchiveがproduction条件を満たさない場合はsafe fallbackを利用します。

### Future / current all races

```bash
python src/racenote_request.py \
  --date 20260827 \
  --analysis ./jrdb_analysis.sqlite \
  --mart ./jrdb_stats_mart.sqlite \
  --output ./output
```

## Output

```text
RaceNote_YYYYMMDD.zip
RaceNote_YYYYMMDD_新潟.zip
RaceNote_YYYYMMDD_新潟_11R.zip
```

ZIP内:

- selected `race_bundle_*.json`
- `request_manifest.json`

`request_manifest.json` の `backend_resolution.used_backend` で実際に利用したbase backendを確認できます。

RaceNote JSONは現行の「PACI詳細 + Analysis履歴 + Stats傾向」を使用します。履歴は詳細recent_runs最大5走 + Analysis older_runs最大3走の8走上限を初期方針とします。

## GPT / GitHub Actions route

Issue prefix:

```text
[RACENOTE_REQUEST] <request_id>
```

Issue bodyはraw JSON:

```json
{
  "date": "20250824",
  "venue": "新潟",
  "race": 11,
  "analysis_url": "<current Analysis Lite Drive URL>",
  "mart_url": "<matching Stats Mart Drive URL>"
}
```

`venue` / `race` は省略可能です。ArchiveのURL・Release tag・Raw URLを通常利用者が指定する必要はありません。

GPTはIssue作成前に現行Analysis/Martを解決します。Drive file IDは再生成で変わり得るためGitへ固定しません。

Workflow:

```text
GPT
 -> current Analysis/Martを解決
 -> [RACENOTE_REQUEST] Issue
 -> GitHub Actions
 -> Analysis/Mart download
 -> pastなら月次Archiveを自動探索・validation
 -> racenote_request.py
      ├ Archive resolved -> racenote_archive
      └ otherwise        -> Raw/PACI fallback
 -> artifact ZIP
 -> machine-readable Issue comment
 -> Issue close
 -> GPTがartifactを回収
```

Issue resultには次も出します。

- `archive_resolution_status`
- `archive_tag`
- `used_backend`

## External data / secrets

GitHub treeへ大容量SQLite、Raw ZIP、認証情報をcommitしません。

Actionsでは以下のRepository Secretsを利用します。

- `JRDB_USER`
- `JRDB_PASSWORD`

秘密値はRepository Settingsの `Secrets and variables -> Actions` でのみ管理します。値そのものを次へ記載・保存しません。

- Git管理ファイル
- Issue本文 / Issueコメント
- workflow input
- artifact
- ChatGPTへの依頼文
- ログ

Workflowは実行時だけ `${{ secrets.JRDB_USER }}` / `${{ secrets.JRDB_PASSWORD }}` を環境変数へ渡します。Actionsログではsecret値が `***` にマスクされることを確認します。

Analysis/MartはIssue requestで渡されたDrive URLから一時取得し、artifactには含めません。RaceNote ArchiveはRelease assetを一時取得し、最終RaceNote artifactにはSQLite自体を含めません。

## Validation status

2025-08 full-month build:

- race dates: 10
- expected races: 360
- generated bundles: 360
- identity match: PASS
- full scan: 360 / 360 PASS
- coverage: `full_month`
- publication: `publishable`
- SQLite: 6,852,608 bytes

2025-08-24 新潟11R real-data Router E2E:

- Archive backend: `racenote_archive`
- fallback backend: `historical_raw_cache_or_fetch`
- final schema: v1.0
- final semantic SHA-256: identical
- semantic match: PASS

通常 `[RACENOTE_REQUEST]` 自動解決試験:

- Archive resolution: `resolved`
- resolved tag: `jrdb-racenote-archive-202508-v1.0`
- used backend: `racenote_archive`
- task / collect: success

詳細は次を参照してください。

- `docs/RaceNote_archive_router_e2e_plan_20250824.md`
- `docs/RaceNote_archive_router_e2e_status.md`
- `docs/RaceNote_multi_race_poc_20260826.md`
