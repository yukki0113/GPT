# JRDB / Kenshow_Labo PWA

`horse-racing/jrdb/pwa/` は、JRDB系の配布済みデータをブラウザで閲覧・集計する **consumer / presentation layer** の正本です。

このPWAは、JRDB Raw・Analysis・Eval・Edge・RaceNoteの条件や判定を再実装する場所ではありません。上流で確定・監査されたデータを受け取り、ブラウザで安全に同期・保存・表示することを責務とします。

スレッド移動や会話量上限後にPWA保守を再開する場合は、まず `.gpt/HANDOFF.md` を確認してください。

## Core principles

1. **PWAはconsumerであり、研究ロジックを再計算しない**
   - EvalのH1/H2等の条件判定、WATCH/MATCHの意味付けはEval側の責務。
   - Edge条件のmatching / serving判定はEdge側の責務。
   - RaceNote予想や印の決定はRaceNote prediction側の責務。
2. **配布物と正本を分離する**
   - Analysis / Stats Mart / Fact Lite等の大容量正本はGit管理外。
   - GitHub Release / Pages上のSQLite・JSONはconsumer向け配布キャッシュ。
3. **manifest / SHA / schemaを見て同期する**
   - READMEへ動的なFile ID、最新SHA、最新データ世代を固定しない。
   - 現在値はRelease asset / manifest / Newspaper current pointerから毎回確認する。
4. **fail-safeで切り替える**
   - 新データ取得・検証に失敗した場合、利用可能な既存ローカルデータを壊さない。
5. **UI変更でデータ意味論を変えない**
   - 色、リンク、モーダル等は表示上の affordance であり、推奨・確度・買い判断をPWA側で付加しない。

## Main surfaces

| 画面 | 主データ | 位置づけ |
| --- | --- | --- |
| `fact-lite.html` 条件別集計 | **Fact Lite** | 通常の自由条件集計の主DB |
| `newspaper.html` 競馬新聞 | **Newspaper current day package** | 当日新聞の閲覧・addon表示 |
| Stats Mart | Stats Mart SQLite | 重い集計・将来拡張用の補助データ |

通常の「条件別集計」を最新開催まで進めるために必要なのは、開催後に更新したAnalysisから **Fact Liteを再生成・検証・配布すること**です。Stats Mart更新は分析資産として重要ですが、通常の条件別集計PWA更新の必須条件ではありません。

## Module map

### 条件別集計

- `fact-lite.html` — UI shell
- `fact-lite.js` — Fact Lite同期・query・表示の基礎
- `fact-lite-v3.js` — Fact Lite v0.3互換層 / WIN5 filter
- `fact-lite-sort.js` — 集計結果sort
- `fact-lite-duckdb.js` — Parquet直読PoC/検証資産。現在の条件別集計ページではloadしない
- `../src/build_jrdb_pwa_fact_lite.py` — Analysis -> Fact Lite builder
- `../schema/jrdb_pwa_fact_lite_schema_v0_3.sql` — current schema
- `../docs/README_build_jrdb_pwa_fact_lite.md` — build / validation contract

### 競馬新聞

- `newspaper.html` — UI shell / shared dialog
- `newspaper-day.js` — current day package取得・切替
- `newspaper-v4.js` 以降 — 新聞表の段階的な表示互換・override
- `newspaper-v6.js` — RaceNoteコメント等の既存dialog利用
- `newspaper-v7.js` — 特注メモ表示
- `newspaper-v8.js` — source status表示拡張
- `newspaper-v9.js` / `newspaper-v9.css` — Eval分析コメントリンク・modal表示
- `newspaper-v10.js` — 独自指数（Training Edge）表示とsource status
- `../src/jrdb_newspaper_merge_external.py` — Eval / RaceNote / keibailuka merge
- `../src/jrdb_newspaper_merge_edge.py` — Edge merge
- `../src/jrdb_newspaper_edge_adapter.py` — Edge reader-facing display boundary
- `../newspaper/.gpt/HANDOFF.md` — Newspaper専用の引継ぎ正本

既存の `newspaper-vN.js/css` は後方互換を維持するためのlayerです。理由なく大規模統合・全面書換えせず、現在のoverride順と回帰テストを確認して最小差分で変更します。

### 共通

- `service-worker.js` — static app shell cache。`/data/` はcache対象外
- `manifest.webmanifest` — PWA manifest
- `style.css` — 共通UI
- `SYNC_PROVIDER.md` — データ配布・browser同期
- `DEPLOYMENT_TRIGGER.md` — Pages deployの入口と完了判定

## Fact Lite current contract

current schemaは **v0.3** です。PWAは旧v0.2も読める後方互換を維持しますが、新機能は実データのschema / capabilityを確認して有効化します。

v0.3の主要追加は `fact_stats_entry.win5_leg_no` です。

- WIN5対象外: `NULL`
- WIN5対象: `1..5`
- UIの「WIN5対象レースのみ」はdefault OFF
- ON時の条件は `win5_leg_no IS NOT NULL`
- v0.2等でcolumn / capabilityがない場合はcheckboxを無効化
- PWA側でWIN5対象レースを日付・レース番号から推測しない

Fact Liteは1出走1行を保持する配布用SQLiteです。年/月/場/芝ダ障害/距離/馬場/クラス/レース名/最低出走数/WIN5等をブラウザ内のsql.jsで絞り込み、種牡馬・騎手・枠・脚質・年齢・性別・人気・前走距離・前走クラス等を集計します。上流のAnalysis正本はParquetのまま維持し、Fact Lite SQLiteはそこから再生成可能なconsumer向け配布cacheとして扱います。

レース名は配布時のBAC lookupを利用します。前走距離・前走クラスをAnalysis内で解決できない場合は推測せず不明扱いです。

## Newspaper display contracts

### Eval analysis comment

Eval研究側が条件判定・注目馬選定・`status / codes / title / comment / version / asof` を確定します。Newspaper mergerはexact joinで透過的に `addons.eval.analysis` へ格納し、PWAは受け取った情報を表示するだけです。

PWAの現在動作:

- `analysis.comment` がnull / 空: Eval値を従来どおり通常表示
- comment非空: **Eval値そのものだけ**をリンク化
- linkはイルカ列と同じ青字 + 下線
- 既存 `newspaper-detail-dialog` を共用
- title / comment / codes / status / version / asofを表示
- PWAにH1/H2条件式を持たない
- WATCHを買い推奨へ変換しない
- MATCHを的中保証として扱わない

旧日次JSONや旧Eval CSV由来の `analysis` なしデータも正常表示します。

### 独自指数 / Training Edge

PWAは上流で算出済みの独自指数を **再計算せずそのまま表示**します。canonicalな馬単位JSONは次を使用します。

```json
{
  "addons": {
    "my_index": {
      "training_edge_index": 80.9
    }
  }
}
```

表示rule:

- preferred field: `addons.my_index.training_edge_index`
- 旧互換: `display_value / index / score / value`
- `addons.my_index` 自体が無い（source未取込）: `—`
- `training_edge_index` が明示的にnull / 空（source取込済みだが指数なし）: **空欄**
- `training_edge_index` が明示されている場合、nullでも旧互換fieldへfallbackしない
- 数値はPWAの通常指数表示と同じ1桁小数表示
- 日次manifestは `source_status.my_index.state` を使用し、`READY` のとき概要欄を `指数○` とする
- PWA側で順位化、標準化、percentile、加重、他指数との合成を行わない

元CSVの標準列は `date, venue_code, race_no, horse_no, training_edge_index`。CSVからNewspaper day packageへのexact join・source_status・auditはNewspaper生成側の責務であり、PWAは完成JSONだけをconsumerとして扱います。

### Edge / 特注メモ

PWA / NewspaperはEdge matcher / serving結果をconsumerとして表示します。PWA側でEdge条件を再match・再評価せず、reader-facing translationとaudit情報の表示境界を守ります。

## Distribution channels

大容量データはGitへcommitしません。current配布tagは固定名で、asset内容を世代更新します。

| channel | Release tag | Pages path |
| --- | --- | --- |
| Stats Mart | `jrdb-stats-mart-current` | `/data/` |
| Fact Lite | `jrdb-pwa-fact-lite-current` | `/data/fact-lite/` |
| Newspaper | `jrdb-newspaper-current` | `/data/newspaper/current/` |

**full-site Pages artifactの組み立て正本は `.github/workflows/jrdb_pwa_pages.yml` (`JRDB PWA Pages`)** です。このworkflowはstatic PWAと3系統のcurrent Releaseを集約して配布します。

データ別publisher:

- Stats Mart: `.github/workflows/jrdb_pwa_publish_data.yml`
- Fact Lite: `.github/workflows/jrdb_pwa_fact_lite_publish.yml`
- Newspaper: Newspaper Current Publish workflow

詳細と既知のpartial-deploy注意点は `SYNC_PROVIDER.md` / `DEPLOYMENT_TRIGGER.md` を参照してください。

## Browser sync / offline

PWAはオンライン時にPages上のmanifestを確認し、ローカルmetadataと比較して必要な場合だけ新版を取得します。

SQLite系の基本:

```text
remote manifest
  -> download incoming
  -> size / SHA-256 / schema / table / integrity validation
  -> incoming -> previous/current
  -> OPFS current.sqlite
```

検証失敗時はcurrentを維持します。Service Workerはstatic app shellをcacheしますが、`/data/` はcacheしません。Fact Lite SQLiteはOPFSの `current.sqlite` に保存し、再読み込み・オフライン時はローカルDBを先に復元します。

Fact Liteの本番readerは `./data/fact-lite/manifest.json` を確認し、配布SQLiteのsize / SHA-256 / schema / required tables / `PRAGMA integrity_check` を通過した場合だけOPFSの `incoming.sqlite → previous.sqlite / current.sqlite` を切り替えます。Analysis ParquetやFact Lite Parquetをブラウザから直接読むことは現在の本番contractではありません。

## Deployment completion

PWA変更・データ更新を「完了」とする際は、commitやRelease更新だけで判断しません。

最低限:

1. latest `main` の対象sourceを確認
2. 必要なtest / validationを通す
3. current Release / manifestが想定世代か確認
4. **`JRDB PWA Pages` がfull-site artifactを成功deployしたことを確認**
5. 必要に応じてiPhone実機でlayout / tap / offline / syncを確認

コード更新経路・データpublisherごとのtrigger差は `DEPLOYMENT_TRIGGER.md` を正本とします。

## Data policy

- JRDB Raw、Analysis、Stats Mart、Fact Lite等の生成正本はGit管理外
- source / schema / contract / workflow / PWA codeはGitHub `main`
- Release / Pages artifactは配布cacheであり研究正本ではない
- Drive File ID、current SHA、current data version等の動的値をREADMEへ固定しない

## Thread restart / handoff

新しいChat / Workへ移る場合は次の順で読みます。

1. `pwa/.gpt/HANDOFF.md`
2. `pwa/README.md`
3. `pwa/SYNC_PROVIDER.md`
4. `pwa/DEPLOYMENT_TRIGGER.md`
5. 対象consumerの正本
   - 条件別集計: `../docs/README_build_jrdb_pwa_fact_lite.md`
   - 競馬新聞: `../newspaper/.gpt/HANDOFF.md`
6. latest `main` / current Release / manifest / Pages runを再確認

再開時の推奨文:

> `horse-racing/jrdb/pwa/.gpt/HANDOFF.md` と参照先のGit正本を確認し、Kenshow_Labo PWA保守スレッドとして継続してください。

過去の固定SHA、File ID、Issue番号、run IDは履歴証跡としてのみ扱い、現在値を推測しません。
