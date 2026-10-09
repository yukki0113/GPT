# JRDB PWA deployment trigger / completion

この文書はKenshow_Labo PWAの **何がdeployを起動し、どこまで確認したら完了か** を定義します。

GitHub運用の全体方針は `../.gpt/WORKFLOW.md` ではなく、JRDB rootの `.gpt/WORKFLOW.md` を正本とします。PWAのsource/docs変更は原則direct Git change、Secrets・大容量配布・Release連鎖等はActions-Nativeで扱います。

## Full-site deployment authority

full-siteの配布正本workflowは:

- `.github/workflows/jrdb_pwa_pages.yml`
- workflow name: `JRDB PWA Pages`

です。

このworkflowはstatic shellとcurrent data releasesを再収集し、1つのPages artifactへまとめます。

```text
PWA static source
+ Stats Mart current Release
+ Fact Lite current Release
+ Newspaper current Release
+ sql.js / wasm
-> JRDB PWA Pages
-> GitHub Pages
```

個別publisherが成功していても、consumer全体の最終状態はこのfull-site workflowで確認します。

## Current triggers of `JRDB PWA Pages`

latest sourceを正本とし、2026-09時点では次のtriggerがあります。

### 1. push to `main`

対象path:

- `horse-racing/jrdb/pwa/**`
- `.github/workflows/jrdb_pwa_pages.yml`
- `.github/workflows/jrdb_pwa_publish_data.yml`
- `.github/workflows/jrdb_pwa_fact_lite_publish.yml`

PWA code / CSS / HTML / Service Worker / PWA docsをdirect Git updateした場合、通常はこのpush triggerでPagesが再構成されます。

### 2. Newspaper publish completion

正式なNewspaper current publishは:

- workflow: `.github/workflows/jrdb_newspaper_publish_current.yml`
- workflow name: `JRDB Newspaper Current Publish`
- request pointer: `horse-racing/jrdb/newspaper/publish/current.json`
- current Release: `jrdb-newspaper-current`

です。

`workflow_run` で `JRDB Newspaper Current Publish` のsuccessful completionを受けてPagesを再構成します。Newspaper current更新は、検証済みday-packageをDrive canonicalへ保存し、`publish/current.json` を更新してCurrent Publishを完走させた後、full-site Pagesへ自動連携します。

### 3. Fact Lite publish completion

`workflow_run` で `JRDB PWA Fact Lite Publish` のsuccessful completionを受けて再構成します。Fact Lite publisher自身はReleaseだけを更新し、partial Pages deployを行いません。

### 4. `workflow_dispatch`

手動・明示再構成用です。

次の場合に使用します。

- current Releaseは更新済みだがfull-site Pagesが新世代を取り込んでいない
- trigger抑止・経路差で自動runが発生しなかった
- deploy状態を再確認したい

## Data publisher workflows

### Fact Lite

- `.github/workflows/jrdb_pwa_fact_lite_publish.yml`
- request prefix: `[JRDB_PWA_FACT_LITE_PUBLISH]`
- current Release: `jrdb-pwa-fact-lite-current`

Analysisを取得しFact Liteをbuild / validate / Release更新します。

### Stats Mart

- `.github/workflows/jrdb_pwa_publish_data.yml`
- request prefix: `[JRDB_PWA_DATA_PUBLISH]`
- current Release: `jrdb-stats-mart-current`

検証済みStats Martを取得しsize / SHA / required tables / integrityを検証してRelease更新します。

### Newspaper

Newspaper subsystemのcurrent publish workflowを使用します。正本は `../newspaper/.gpt/HANDOFF.md` と `../newspaper/.gpt/WORKFLOW.md` を参照してください。

## Important: Release is not full-site proof

Fact Lite publisherはSQLite Releaseを更新し、`JRDB PWA Pages` がそのsuccessを受けてfull-site artifactを組み立てます。よって **Fact Lite配布更新はRelease successだけで作業を閉じず、downstream full Pages successまで確認**してください。Stats Martは既存の補助channelとして独自運用を維持します。

## GitHub token / trigger caution

GitHub Actionsの `GITHUB_TOKEN` が作ったpush/eventは、recursive workflow起動が抑止されるケースがあります。

旧運用の `[gpt-git-update]` Issueを標準経路とはしませんが、Actions内からsourceを書き換える旧経路や特殊経路を使用した場合は、**「mainへcommitされたからPagesも起動したはず」と仮定しない**ことが重要です。

必ずworkflow runそのものを確認し、必要なら `workflow_dispatch` を使用します。

## Static asset cache rule

PWA shellを変更した場合、Service Worker / query-string cache bustが必要か確認します。

特に:

- JS/CSSを更新したのにHTMLのasset versionが同じ
- Service Workerの`CACHE_NAME`が同じ
- APP_SHELLに新assetを追加していない

場合、iPhone等で旧表示が残る可能性があります。

一方 `/data/` はService Worker cache対象外です。data世代はmanifest / SHA / local storage / OPFS側で管理します。

## Completion checklist

PWA code変更:

1. latest `main` / current sourceを取得
2. 最小差分で変更
3. 関連回帰testを実行
4. asset version / Service Worker cacheを確認
5. main commitを確認
6. `JRDB PWA Pages` run successを確認
7. UI変更がmobile-sensitiveならiPhone表示・tapを確認

Fact Lite / Stats Mart更新:

1. upstream artifactが正本保存・検証済み
2. publisher validation success
3. current Release / manifestが新版へ更新
4. **full `JRDB PWA Pages` を再構成**
5. Pages run success
6. PWA manifest/SHA同期または実機取得を確認

Newspaper更新:

1. PACIからimmutable revisionを生成・audit
2. canonical Analysis / STANDARD EdgeDB / EdgeDB v0.5のsource statusを確認
3. EdgeDB v0.5は `missing_join_count=0` / `extra_join_count=0` を確認し、`PARTIAL` または `READY` を正常表示対象とする
4. Drive canonical保存と `publish/current.json` 更新
5. 正式 `JRDB Newspaper Current Publish` success
6. current Release `jrdb-newspaper-current` のdate/revision確認
7. downstream `JRDB PWA Pages` の以下4 stepがSUCCESS
   - Run PWA focused tests
   - Prepare Pages artifact
   - Upload Pages artifact
   - Deploy to GitHub Pages
8. 公開 `newspaper.html` で対象日、全レース切替、既存addon、Edge列を確認
9. UI変更を伴う場合は360 / 390 / 430pxのスマホ幅も確認

## Do not use stale IDs as current state

過去のrun ID、artifact ID、release asset SHA、Drive File IDは監査履歴です。

現在状態を確認するときは:

- latest `main`
- current release / manifest
- Newspaper current pointer
- latest relevant workflow run

をその都度読みます。


### EdgeDB v0.5 personal republish

EdgeDB v0.5だけを現行個人Newspaperへ再突合する場合は、

- workflow: `.github/workflows/jrdb_newspaper_edge_v05_republish_issue.yml`
- workflow name: `JRDB Newspaper Edge v0.5 Republish via Issue`
- request prefix: `[JRDB_NEWSPAPER_EDGE_V05_REPUBLISH]`

を使用します。

この経路は既存の個人currentを土台に、PACI＋canonical Analysisでv0.5を再照合し、既存RaceNote/RRDB等を保持したままrevisionを1つ進めます。成功後は `JRDB PWA Pages` のfull deployまで確認します。
