# JRDB PWA Sync Provider

## Purpose

Kenshow_Labo PWAはGoogle Driveの可変File IDをブラウザへ直接持たせず、**GitHub Release + GitHub Pages上の固定配布経路**からconsumer用データを同期します。

大容量SQLite / day packageの研究・生成正本はGit管理外とし、GitHub Release / Pages artifactは **配布cache** として扱います。

PWAは上流データの意味を再計算せず、manifest / SHA / schema / audit済み内容をconsumerとして利用します。

## Distribution channels

| channel | current Release tag | Pages path | browser role |
| --- | --- | --- | --- |
| Stats Mart | `jrdb-stats-mart-current` | `./data/` | 補助集計DB |
| Fact Lite | `jrdb-pwa-fact-lite-current` | `./data/fact-lite/` | 条件別集計の主DB |
| Newspaper | `jrdb-newspaper-current` | `./data/newspaper/current/` | 当日競馬新聞 |

Release tag名は固定ですが、assetのdata version / SHA / sizeは世代更新されます。README等に現在値を固定せず、実行時にmanifest / release metadataを確認します。

## Publish flows

### Stats Mart

```text
validated Stats Mart on Google Drive
  -> [JRDB_PWA_DATA_PUBLISH] request
  -> .github/workflows/jrdb_pwa_publish_data.yml
  -> size / SHA-256 / required tables / integrity validation
  -> jrdb-stats-mart-current Release
```

### Fact Lite

```text
updated / validated Analysis on Google Drive
  -> [JRDB_PWA_FACT_LITE_PUBLISH] request
  -> .github/workflows/jrdb_pwa_fact_lite_publish.yml
  -> Analysis download
  -> BAC race-name lookup
  -> build_jrdb_pwa_fact_lite.py
  -> Fact Lite v0.3 validation
  -> jrdb-pwa-fact-lite-current Release
```

Fact Lite v0.3 publisherは少なくとも `win5_leg_no`、schema version、row count、race-name lookup、previous-distance / previous-class、WIN5 rows、SHA、size、SQLite integrityを検証します。

上流のAnalysisはParquet正本を維持し、publisherはcurrent manifestに列挙されたpartitionだけからFact Lite SQLiteを再生成します。browser deliveryの正式経路は `jrdb-pwa-fact-lite-current` の単一SQLite + manifestです。Parquet / DuckDB-Wasm資産を同値監査・開発検証として保持することはありますが、browser Release、Pages staging、通常runtimeには含めません。

### Newspaper

```text
verified immutable day-package revision
  -> Newspaper current pointer
  -> Newspaper Current Publish
  -> jrdb-newspaper-current Release
```

Newspaperの日次生成・revision・source mergeは `../newspaper/.gpt/HANDOFF.md` と同subsystemのcontractを正本とします。

## Full-site Pages assembly

**full-site Pages artifactの組み立て正本は `.github/workflows/jrdb_pwa_pages.yml` (`JRDB PWA Pages`) です。**

このworkflowは次を同一artifactへ集約します。

```text
horse-racing/jrdb/pwa/ static shell
+ sql.js / wasm
+ jrdb-stats-mart-current
+ jrdb-pwa-fact-lite-current
+ jrdb-newspaper-current
= GitHub Pages full-site artifact
```

したがって、consumer全体の配布完了判定は「個別Releaseが更新された」だけではなく、**そのcurrent Release群を含む `JRDB PWA Pages` の成功**まで確認します。

Fact Lite publisherはReleaseのみを更新し、Pagesをpartial deployしません。successful `JRDB PWA Fact Lite Publish` は`workflow_run`でfull `JRDB PWA Pages` を起動します。Stats Martは旧思想の補助資産として既存経路を維持しますが、条件別集計の更新完了はFact Lite SQLite Releaseとfull-site Pagesの両方の成功で判定します。

## Browser flow: SQLite channels

ブラウザはPages上のmanifestを確認し、ローカルmetadataのSHA-256と比較します。

基本動作:

- 同一SHA-256: 再downloadしない
- 新版: 配布SQLiteをdownload
- download後: size / SHA-256 / schema / required tables / `PRAGMA integrity_check` 等を検証
- 検証成功: incoming -> previous/current の順で安全に切替
- 検証失敗: 利用中currentを維持

Fact LiteはOPFSへ保存し、起動時にローカルcurrentを復元したうえでオンラインなら最新版確認を行います。schema / capabilityを実データから確認し、未対応機能を推測で有効化しません。

## Newspaper browser flow

Newspaperはcurrent配布metadataとday packageを取得し、日付・revision・SHA等を確認したうえで端末保存/表示します。

Newspaper JSON内部のEval / RaceNote / keibailuka / Edge等について、PWAはsource側の条件を再評価しません。たとえばEval分析コメントは `addons.eval.analysis.comment` の有無のみを表示gateとして使用します。

## Service Worker boundary

Service WorkerはHTML / JS / CSS / manifest / sql.js等の **static app shell** をcacheします。

`/data/` はService Worker cache対象外です。データ世代の切替をapp shell cacheに委ねず、manifest / SHA / OPFS等のdata sync mechanismで管理します。

したがって:

- static更新: Service Worker cache version / asset query versionを必要に応じて更新
- data更新: Release / manifest / Pages data pathで同期

を分離します。

## Failure policy

- Drive取得失敗: Releaseを更新しない
- size / SHA不一致: Release / currentを更新しない
- schema / integrity不正: 配布対象にしない
- browser download / validation失敗: 既存currentを維持
- optional Newspaper addon欠損: Newspaper側の日次contractに従いsource stateを明示し、PWA側で推測補完しない
- full-site Pages再構成未確認: consumer全体のdeploy完了とは扱わない

## Source-of-truth rule

現在の配布世代を確認するときは、次を優先します。

1. latest `main` のworkflow / code
2. current Release asset / manifest
3. Newspaper current pointer / release metadata
4. successful `JRDB PWA Pages` run
5. 過去README記載の固定値・Issue・run IDは履歴証跡

Drive File ID、current SHA、current size、current data versionは世代更新されるため、この文書には固定しません。
