# Kenshow_Labo PWA handoff

この文書は、会話量上限・Chat/Workスレッド移動・担当交代後に `horse-racing/jrdb/pwa/` の保守を再開するための **durable handoff** です。

ここには変わりやすいDrive File ID、current SHA、current run IDを固定しません。再開時はこの文書で思想と入口を復元し、動的な現在状態は必ずlatest `main` / current Release / manifest / workflow runから取得してください。

## Start here

新しいスレッドでは次の順で確認します。

1. `horse-racing/jrdb/pwa/.gpt/HANDOFF.md` — この文書
2. `horse-racing/jrdb/pwa/README.md` — architecture / module map / consumer semantics
3. `horse-racing/jrdb/pwa/SYNC_PROVIDER.md` — data Release / browser sync / OPFS
4. `horse-racing/jrdb/pwa/DEPLOYMENT_TRIGGER.md` — deploy trigger / completion
5. 対象subsystemの正本
   - 条件別集計: `horse-racing/jrdb/docs/README_build_jrdb_pwa_fact_lite.md`
   - 競馬新聞: `horse-racing/jrdb/newspaper/.gpt/HANDOFF.md`
   - Eval分析コメント: `horse-racing/eval/docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md`
   - Edge: current Edge serving / consumer contract
6. latest `main` の対象source / workflow / tests
7. current Release / manifest / Newspaper current pointer / relevant Pages run

推奨の再開指示:

> `horse-racing/jrdb/pwa/.gpt/HANDOFF.md` と参照先のGit正本を確認し、Kenshow_Labo PWA保守スレッドとして継続してください。

## Mission

PWAの責務は **上流で確定・監査されたデータを安全に同期し、スマホ/ブラウザで読みやすく表示・集計すること** です。

PWAで行わないこと:

- Eval条件、H1/H2、WATCH/MATCHの再判定
- Edge matcher / serving条件の再実装
- RaceNote predictionの再計算
- 欠損sourceのfuzzy join / 推測補完
- historical ROIやEdge strength等を表示層で加算して新しい評価を作る
- UI上の色やリンクを独自の買い推奨へ変換する

## Current surfaces and authority

### 条件別集計

主DBは **Fact Lite** です。

- builder: `horse-racing/jrdb/src/build_jrdb_pwa_fact_lite.py`
- schema: `horse-racing/jrdb/schema/jrdb_pwa_fact_lite_schema_v0_3.sql`
- build contract: `horse-racing/jrdb/docs/README_build_jrdb_pwa_fact_lite.md`
- browser compatibility: `fact-lite-v3.js`
- current Release tag: `jrdb-pwa-fact-lite-current`

Stats Martは補助データです。通常の条件別集計を最新開催へ進める必須工程は、更新済みAnalysisからFact Liteを再生成・検証・配布することです。

### 競馬新聞

NewspaperはJRDB-first day packageのconsumerです。

- Newspaper専用運用: `../newspaper/.gpt/HANDOFF.md`
- external merge: `../src/jrdb_newspaper_merge_external.py`
- Edge merge: `../src/jrdb_newspaper_merge_edge.py`
- Edge display boundary: `../src/jrdb_newspaper_edge_adapter.py`
- current Release tag: `jrdb-newspaper-current`

PWA側は既存day packageの意味を変更せず表示します。

### Stats Mart

- current Release tag: `jrdb-stats-mart-current`
- heavier aggregate / future extension用の補助channel
- normal Fact Lite画面の主DBではない

## Fact Lite v0.3 invariants

条件別集計browserの正式contractは **SQLite + sql.js + OPFS**。AnalysisはParquet正本を維持し、そこからFact Lite SQLiteを生成・配布する。Parquet/DuckDB-Wasm直読は再読み込み負荷・ローカルcache安定性の観点から通常運用には採用しない。Fact Lite Parquetが検証資産として残っていてもbrowserは参照しない。

current schemaはv0.3。PWAは旧v0.2のread compatibilityを維持します。

WIN5:

- source field: `win5_leg_no`
- non-WIN5 = `NULL`
- WIN5 legs = `1..5`
- checkbox default = OFF
- ON = `win5_leg_no IS NOT NULL`
- capability/columnなし = checkbox disabled
- PWAで日付・レース番号からWIN5を推測しない

Fact Liteの検索・集計条件を追加する場合、できるだけupstream fact/schemaへ明示的に持たせ、browserだけに隠れた派生条件を増やさないことを優先します。

## Eval analysis comment invariants

Eval分析コメントはEval研究側が確定します。

Newspaper JSONの概念:

```json
{
  "addons": {
    "eval": {
      "eval": 52,
      "analysis": {
        "status": "WATCH",
        "codes": ["H1_PRE"],
        "title": "...",
        "comment": "...",
        "version": "...",
        "asof": "..."
      }
    }
  }
}
```

PWA表示rule:

- `analysis.comment` null/empty -> 通常Eval値
- non-empty -> Eval値そのものをtap/click可能にする
- 別アイコン・別詳細列を増やさない
- link styleはイルカ列と同じ青字 + 下線
- 既存 `newspaper-detail-dialog` を共用
- codes/status/version/asofを表示してよいが、意味を再解釈しない
- WATCH = 条件成立/買い推奨ではない
- MATCH = 的中保証ではない

関連layer:

- `newspaper-v9.js`
- `newspaper-v9.css`
- `../tests/test_jrdb_newspaper_eval_analysis_pwa.py`

## Independent index / Training Edge invariants

独自指数は上流で算出済みの値をPWAがそのまま表示する。PWA側で指数を再計算・順位化・標準化・合成しない。

canonical horse addon:

```json
{
  "addons": {
    "my_index": {
      "training_edge_index": 80.9
    }
  }
}
```

- preferred value: `addons.my_index.training_edge_index`
- legacy fallback: `display_value / index / score / value`
- `addons.my_index` missing（source未取込） -> `—`
- explicit `training_edge_index: null` / empty（source取込済み・指数なし） -> **空欄**
- `training_edge_index` が明示された場合はnullでもlegacy fallbackへ落とさない
- day manifest source status: `source_status.my_index.state`
- `READY` -> day summary `指数○`
- source CSV standard columns: `date, venue_code, race_no, horse_no, training_edge_index`
- CSV exact join / duplicate detection / audit / source_status creationはNewspaper生成側の責務
- current PWA layer: `newspaper-v10.js`
- focused test: `../tests/test_jrdb_newspaper_my_index_pwa.py`

## Edge display invariants

PWAはEdge outputを表示するconsumerです。

- exact matching / eligibilityはEdge / adapter側
- PWAでconditionsを再評価しない
- reader-facing表示とraw/audit情報を混同しない
- 特注メモ表示のためにEdge strength等を独自scoreへ加算しない

## Layered Newspaper frontend

Newspaper frontendは `newspaper.js` と複数の `newspaper-vN.js/css` overrideで進化しています。

変更時は:

1. `newspaper.html` のload順を確認
2. override対象function / CSS selectorを確認
3. 既存layerを無視して同じfunctionを重複実装しない
4. 最小の新overrideまたは既存current layerへの修正を選ぶ
5. asset query version / Service Worker cacheを更新する必要があるか確認
6. iPhoneの横幅・sticky列・tap領域を壊していないか確認

大規模なfrontend再統合は、専用refactorとして回帰範囲を明示して行います。

## Distribution architecture

配布channel:

```text
Stats Mart Release  : jrdb-stats-mart-current
Fact Lite Release   : jrdb-pwa-fact-lite-current
Newspaper Release   : jrdb-newspaper-current
```

full-site組み立て:

```text
current Releases
+ pwa static shell
+ sql.js / wasm
-> .github/workflows/jrdb_pwa_pages.yml
-> JRDB PWA Pages
-> GitHub Pages
```

full-site Pages workflowが最終的なconsumer配布artifactを作ります。

## Pages completion rule

Fact Lite publisherはSQLite Releaseのみを更新します。successful completionはfull Pagesの`workflow_run` triggerになり、partial Pages deployを行いません。したがってFact Lite更新後は:

```text
Fact Lite SQLite publisher success
-> current Release / manifest確認
-> workflow_runでfull JRDB PWA Pages再構成
-> Pages success確認
```

までを完了条件にします。

この制約は将来refactorされる可能性があるため、再開時は必ずcurrent workflow sourceを確認してください。

## Current data retention

Analysis LiteのDrive正本とFact Lite配布物は、通常**current世代のみ**を保持する。

1. 新Analysisを所定の共有Driveフォルダへuploadする。
2. filename・size・SHA-256・ZIP/SQLite検査を再fetchで確認する。
3. Fact Liteのschema/integrity/SHA検証、current Release更新、full Pages配布を成功させる。
4. この三段階がすべて成功した後だけ、直前のDrive Analysisを削除する。

Fact Lite Releaseはcurrent assetを置換する。旧Fact Liteを別のDrive保管や旧Release assetとして積み増さない。いずれかが失敗した場合は旧currentを維持し、原因を修正してから再公開する。

## Browser/offline invariants

- static app shell: Service Worker cache
- `/data/`: Service Worker cache対象外
- SQLite current: OPFS
- remote manifest / SHAで更新判定
- download後にsize / SHA / schema / integrity等をvalidate
- validation失敗時は既存currentを維持

PWAの見た目が更新されない場合、dataだけでなくHTML asset query versionとService Worker `CACHE_NAME` も確認します。

## Git / change policy

通常のPWA source / docs / test変更:

```text
latest main
-> target path exists / current blob SHA
-> current content
-> minimal diff
-> direct Git update
-> tests
-> Pages deploy確認
```

Issue駆動をsource変更のdefaultにしません。

Actionsが必要なのは、Drive download、Secrets、大容量build、Release publish、Pages artifact等のActions-native処理です。

## Pre-change checklist

- latest mainを確認したか
- 現在の正本contractを読んだか
- PWA側へ上流条件ロジックを持ち込んでいないか
- old JSON / old SQLiteへの後方互換が必要か
- mobile width / sticky / tapに影響しないか
- testsを追加/更新したか
- Service Worker / cache bustが必要か
- data Releaseとfull Pages deployを混同していないか

## Completion checklist

UI/code変更:

- source commit
- relevant test PASS
- full `JRDB PWA Pages` success
- mobile-sensitive変更なら実機確認

Fact Lite / Stats Mart data更新:

- upstream canonical保存・audit
- publisher validation
- current Release更新
- full Pages recomposition
