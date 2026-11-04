# JRDB PWA deployment trigger / completion

## Phase 3 retirement boundary — Issue #2334

EdgeDB/Training Edge専用のworkflow・計算/取込/preview・config・専用テストを通常の実行場所から撤去し、`horse-racing/jrdb/archive/retired-edge-training/README.md` に証跡を集約した。旧ファイルを直接起動・復元しない。RaceNoteの独立した凍結実験adapter、馬コース適性のcanonical utility、RRDBのprevious-start ledgerは現行依存のため保持する。独立JRDB追切/training_indexと廃止Training Edgeを混同しない。

通常NewspaperはPACI-onlyで起動し、Eval/RaceNote/RRDB/イルカ/桃太郎の既存経路を維持する。`jrdb_newspaper_retired_sources.py` と旧データ非伝播テストは恒久保持。Release/Drive/immutable revisionおよびActions履歴は削除しない。全域監査と本番確認の範囲は `horse-racing/jrdb/newspaper/PHASE3_AUDIT.md` を参照。

## Current PACI-only contract (Phase 2 origin; Issue #2329)

通常Newspaperは PACI → Base/history → 監査PASS → 日次artifact → 任意のEval/RaceNote/RRDB/イルカmerge → 個人/桃太郎投影 → Current候補 の経路を使う。EdgeDB STANDARD/v0.5・Training Edge入力を要求・探索・実行しない。日次requestは `date` とPACI取得元のみで起動し、`revision` は省略時1。旧requestのAnalysis追加フィールドは無視する。仕様は `horse-racing/jrdb/newspaper/DAY_REQUEST_V2.md`。

旧Currentを基にした新revisionでは共通の `jrdb_newspaper_retired_sources.py` が廃止sourceを除去し、race SHA/size・manifest・package・auditを再生成する。通常mergeの `--my-index-csv` は廃止。既存immutable revisionやRelease/Drive正本は変更しない。Eval WATCH/MATCH、Eval.analysis、RRDB不利分析、JRDB/履歴、RaceNote、イルカ、桃太郎の予想/コメントは維持する。Fact Lite/Stats Mart/canonical Analysisは独立経路として維持する。

Phase 3（Issue #2334）でEdgeDB/Training Edge専用実行資産はactive領域からarchiveへ移動済み。通常配信はPACI-only。完了判定ではコード監査と本番Current/Pages配信を区別し、最新のRelease・workflow run・公開画面を毎回確認する。過去runや旧PR時点の未完了記述を現在の状態として流用しない。

2026-11-04 T7最終監査は `../newspaper/T7_FINAL_RETIREMENT_AUDIT_20261104.md`。通常運用廃止・本番配信は範囲限定で完了、Drive退避先資産の物理削除はユーザー申告ベースと区別する。

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
- legacy request file: `horse-racing/jrdb/newspaper/publish/current.json`（現在の可変Releaseポインタではない。2026-09-20 r2の古い要求を残している）
- current Release: `jrdb-newspaper-current`

です。

`workflow_run` で `JRDB Newspaper Current Publish`、`JRDB Newspaper Skeleton Publish`、`JRDB Momotaro Newspaper Current Publish`、`JRDB Newspaper Kensho Merge via Issue` など正式publisherのsuccessful completionを受けてPagesを再構成します。通常のPACI-only日次配布では監査済みartifactを基に個人/桃太郎Currentを更新します。Git-tracked `publish/current.json` は古い要求のままなので、**現在の公開ポインタとして使用せず、検証なしでworkflow_dispatchしない**でください。現行の公開入口は日付・revisionの単調前進を要求し、Current書き込みを共通concurrency groupで直列化します。

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

1. PACI-only day build/監査をPASSさせ、Current Publish先のdate/revisionと実物SHAを照合する。
2. `JRDB Newspaper Current Publish` のsuccess後、`JRDB PWA Pages` のartifact組立・Upload・Deployすべてsuccessを確認する。
3. 個人/桃太郎公開画面の対象日・既存addon・旧EdgeDB/Training Edgeの非表示を確認する。
4. Current Release更新だけで「Pages完了」と報告しない。実機未確認ならその旨を残す。

## Do not use stale IDs as current state

過去のrun ID、artifact ID、release asset SHA、Drive File IDは監査履歴です。

現在状態を確認するときは:

- latest `main`
- current release / manifest
- Newspaper current pointer
- latest relevant workflow run

をその都度読みます。

