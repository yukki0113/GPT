# JRDB Newspaper module

Status: BASE POC IMPLEMENTED / REAL-DATA POC IN PROGRESS

このディレクトリは、JRDB PWA向け「自分用競馬新聞」の日次生成・外部source merge・配布契約を独立管理するためのmodule boundaryです。

## Design source of truth

- `../docs/JRDB_PWA_Newspaper_Design_v0_1.md`
- `../schema/jrdb_pwa_newspaper_race_schema_v0_1.json`
- `../schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json`
- `../docs/JRDB_Newspaper_Neutral_Dependency_Inventory_v0_1.md`

## Architecture boundary

NewspaperはRaceNoteの派生consumerではありません。

禁止する依存:

```text
RaceNote v1.0 bundle -> Newspaper base
racenote_jrdb.py -> Newspaper base
racenote_history_engine.py -> Newspaper history
その他 racenote_* の内部ロジック -> Newspaper JRDB base/history
```

基本構造は次です。

```text
JRDB Raw / PACI
  -> neutral JRDB layer
     - src/jrdb_raw.py
     - src/jrdb_raw_history.py
     - 必要に応じて新設するneutral history/access modules
       -> RaceNote adapter
       -> Newspaper adapter
```

RaceNote内にNewspaperでも必要な汎用処理が見つかった場合は、その処理をそのままNewspaperからimportしません。まずJRDB汎用moduleへ抽出し、RaceNote側もその汎用moduleを使うようにしてから双方で共有します。

RaceNoteの予想結果・短評そのものは外部addonとして `addons.racenote_prediction` へmerge可能です。これはJRDB Base/history生成への依存とは別責務です。

## Implemented Base PoC

`../src/jrdb_newspaper_build.py` はCommon Readerから直接、1レース1JSONのNewspaper Baseを生成します。

```text
PACI
  BAC/KYI/CHA/CYB/UKC -> race/basic/jrdb
  KYI previous 1-5 + ZED/ZKB -> detailed history
  optional Analysis Lite -> compact older history up to total 8
  -> Newspaper race bundle v0.1
```

実装済みの境界:

- `racenote_*` をimportしない
- target/future historyをfail-closed
- BAC declared field sizeとKYI頭数を一致検証
- horse number一意性を検証
- history sequenceと`history_date < target_date`を検証
- Eval / RaceNote prediction / keibailuka / independent indexは未取得時null/PENDING
- Edgeは未merge時空配列
- unresolved previous linkは履歴生成失敗と同一視せず、`source_status.jrdb_history` のcoverage metadataで明示

Synthetic regressionは `.github/workflows/jrdb_common_reader_tests.yml` に組み込み済みです。2026-09-09 run `34305173081` はsuccess。

## UI order

```text
馬情報 -> 印群 -> 過去走 -> Edge
```

1頭1行を基本とし、スマホ横スクロールを前提にします。

## Planned routine request

将来の専用Workスレッドでは、ユーザーが原則として日付だけ指定できる運用を目標とします。

```text
09/12の競馬新聞用データを生成してください。
```

同じ依頼を再実行可能とし、初回はJRDB Baseを生成、後続実行ではその時点で取得可能なEval / RaceNote prediction / keibailuka / Edge / independent indexを安全にmergeします。

外部sourceが未取得でもJRDB Base生成を妨げず、未取得slotはnull/PENDINGで保持します。

## Source responsibilities

- JRDB Raw / PACI fixed-width parse: `../src/jrdb_raw.py`
- historical Raw access: `../src/jrdb_raw_history.py`
- Newspaper Base builder: `../src/jrdb_newspaper_build.py`
- JRDB current race / runner base: BAC / KYI / CHA / CYB / UKC等のpre-race dataをneutral readerから投影
- history: Newspaper専用projectionをneutral JRDB history/access層の上に実装する
- Eval: `addons.eval`
- RaceNote prediction: `addons.racenote_prediction` + race-level RaceNote note
- keibailuka: `addons.keibailuka`
- independent index: `addons.my_index`
- Edge Registry: `edge_matches`

RaceNote v1.0、Eval、Edge Registry等の既存source truthはこのmoduleへ移さない。

## Storage / delivery target

日次生成物はGit管理外。

候補:

```text
Drive canonical
  -> publish workflow
  -> GitHub Pages data
  -> PWA
  -> OPFS offline copy
```

Gitはcode / schema / docsのみを正本管理します。

## Implementation status

実装済み:

- neutral dependency inventory
- Newspaper JRDB Base builder synthetic PoC
- detailed previous 1-5 history projection
- optional Analysis compact history to total 8
- race bundle schema alignment
- schema / as-of / headcount / architecture regression tests

未実装:

- real-data 札幌記念PoCの完了監査
- merge engine
- daily manifest builder
- Drive save
- publish workflow
- PWA newspaper page
- OPFS newspaper sync

最初のreal-data PoCは `2026-08-16 札幌11R 札幌記念`。RaceNote bundleを入力には使わず、PACI/Common Readerを正本経路として検証します。
