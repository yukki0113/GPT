# JRDB Newspaper project context

## Status
BASE POC IMPLEMENTED. Synthetic validation is PASS; first real-data PoC is in progress. Merger / publisher / PWA page are not implemented yet.

## Goal
スマホ中心の自分用競馬新聞を、JRDB Base + optional external addonsのハイブリッド日次bundleとして生成・配布する。

UI meaning order:

```text
馬情報 -> 印群 -> 過去走 -> Edge
```

## Source of truth
- JRDB fixed-width parse: `../../src/jrdb_raw.py`
- JRDB historical Raw access: `../../src/jrdb_raw_history.py`
- Newspaper Base builder: `../../src/jrdb_newspaper_build.py`
- Newspaper design: `../../docs/JRDB_PWA_Newspaper_Design_v0_1.md`
- Neutral dependency inventory: `../../docs/JRDB_Newspaper_Neutral_Dependency_Inventory_v0_1.md`
- Race bundle schema: `../../schema/jrdb_pwa_newspaper_race_schema_v0_1.json`
- Daily manifest draft schema: `../../schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json`
- RaceNote source truth remains RaceNote v1.0. Newspaper does not replace or mutate it.
- Edge source truth remains JRDB Edge Registry.
- Eval / keibailuka / independent index remain separate source systems.

## Hard architecture rule
NewspaperのJRDB Base/historyはRaceNote実装に依存させない。

禁止:

```text
RaceNote v1.0 bundle -> Newspaper base/history
racenote_jrdb.py -> Newspaper base
racenote_history_engine.py -> Newspaper history
その他 racenote_* moduleの内部処理 -> Newspaper JRDB base/history
```

採用する依存方向:

```text
JRDB Raw / PACI
  -> neutral JRDB modules
       -> RaceNote adapter
       -> Newspaper adapter
```

RaceNote内部にのみ存在する処理が実質的に汎用で、Newspaperでも必要な場合は:

1. その責務をneutral JRDB moduleとして抽出する。
2. RaceNote側をneutral module利用へリファクタする。
3. Newspaperも同じneutral moduleを利用する。

RaceNote固有moduleをNewspaperから直接importして近道しない。

RaceNoteの**予想結果・印・短評そのもの**は外部sourceとして `addons.racenote_prediction` へmergeしてよい。これはBase/history生成依存とは明確に分離する。

## Base PoC implementation

`src/jrdb_newspaper_build.py` はPACIをCommon Readerで直接読み、Newspaper race bundle v0.1へ投影する。

- BAC -> race header
- KYI -> current runner, JRDB marks/indices, previous 1-5 links
- CHA/CYB -> workout/training
- UKC -> pedigree/profile as-of target date
- ZED/ZKB -> detailed previous history
- optional Analysis Lite -> compact older history, total max 8

Base builderは `racenote_*` をimportしない。architecture testでこれを固定する。

History source readinessは `READY/PENDING/NOT_APPLICABLE/ERROR` のsource stateと、別のcoverage metadataで表す。未解決previous linkがある場合も架空補完せず:

- `coverage_complete`
- `expected_count`
- `resolved_count`
- `unresolved_count`
- `supplemental_count`

を保持する。

Synthetic regressionは `tests/test_jrdb_newspaper_build.py`。Common Reader CI run `34305173081`（2026-09-09）はsuccess。

## Routine target
将来のWork運用では、ユーザーの通常依頼を次の形まで簡略化する。

```text
MM/DDの競馬新聞用データを生成してください。
```

実行はhybrid / idempotentとする。

- PACIがあればJRDB Baseを生成する
- external addonが利用可能ならmergeする
- unavailable addonはPENDING/nullのまま保持する
- 同じ日付への再実行で新たに利用可能になったaddonだけを安全に反映する

## Merge ownership
- JRDB: race / basic / jrdb / history
- Eval: addons.eval
- RaceNote prediction: addons.racenote_prediction and owned race note fields
- keibailuka: addons.keibailuka
- independent index: addons.my_index
- Edge matcher: edge_matches

各consumerは他source namespaceを上書きしない。

## Identity
External default join:

```text
date + venue_code + race_no + horse_no
```

JRDB内ではrace_key / race_horse_key / horse_idも保持する。
馬名推測joinを標準化しない。

## History
Newspaperの履歴要件はNewspaper自身のcontractとして定義する。

- 最大8走をbundle内に保持
- 初期画面は3走
- target dateより前の履歴だけを利用
- PACI/KYIが明示するprevious linksとneutral JRDB sourceを利用
- detailed previous 1-5はZED/ZKB exact result key join
- 5走を超える補完はoptional Analysis Lite compact queryで可能
- RaceNote enrichmentを直接呼ばない
- coverageが不完全な場合はmetadataで明示し、完全履歴と推測しない

既存RaceNoteで得られた5+3 / 8走の知見は設計参考にはできるが、実装依存・契約依存にはしない。

## First real-data PoC

`2026-08-16 札幌11R 札幌記念` を対象とする。

- RaceNote bundleは入力に使わない
- PACI/Common Reader経路でBaseを生成する
- target race resultを混入させない
- JSON bytes / 16頭 identity / history count/source layer / null distributionを監査する
- 必要ならAnalysis Liteで6-8走目を補う

## Distribution
日次生成JSONはGitへ入れない。Driveを保存正本候補とし、PWA配布面はGitHub Pages data + manifest、端末側はOPFSを第一候補とする。

## Deferred
- live/final odds
- 当日最終馬体重
- 勝負服画像
- 10走以上
- Edge status表示policy
- 独自指数計算
