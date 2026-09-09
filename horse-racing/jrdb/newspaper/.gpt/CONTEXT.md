# JRDB Newspaper project context

## Status
REAL-DATA POC ACTIVE. PACI-only 札幌記念 PoC is PASS; Analysis-backed 5+3 PoC is the current validation step. Merger / publisher / PWA page are not implemented yet.

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
- real-data PoC auditor: `../../src/audit_jrdb_newspaper_poc.py`
- Newspaper design: `../../docs/JRDB_PWA_Newspaper_Design_v0_1.md`
- Neutral dependency inventory: `../../docs/JRDB_Newspaper_Neutral_Dependency_Inventory_v0_1.md`
- 5+3 acceptance: `../../docs/JRDB_Newspaper_PoC_20260816_Sapporo11_5plus3_20260909.md`
- Race bundle schema: `../../schema/jrdb_pwa_newspaper_race_schema_v0_1.json`
- Daily manifest draft schema: `../../schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json`
- Issue request contract: `REQUEST_CONTRACT.md`
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

## Base/history implementation

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

## PACI-only real-data PoC result

Target: `2026-08-16 札幌11R 札幌記念`, race key `01261811`.

PASS:

- 16 horses exact
- detailed previous history = 80/80 resolved = 5 per horse
- unresolved = 0
- chronology violations = 0
- duplicate history identities = 0
- forbidden RaceNote imports = 0
- addons all null / Edge empty
- core current field nulls = 0 for horse_name / sire / BMS / running style / IDM / total index / training index

アドマイヤテラの2025-11-30 ジャパンCは `abnormal_code=3` で、ZKB race commentは「スタート直後躓き態勢崩し鞍上が落馬、中止」。last3f / IDM等のnullは競走中止レコードに対応し、parser failureではない。

## Active 5+3 PoC

同じ札幌記念へ共有Analysis Liteを接続する。

```text
PACI detailed 1-5
  + Analysis compact 6-8
  = bundle maximum 8
```

Rules:

- PACI detailed history order/source layerを変更しない
- Analysisはoldest detailed runよりさらに古い `race_date` だけを取得
- target race/resultは補完対象外
- compact rowは詳細欠損をparser error扱いしない
- Analysis file/size/SHA/quick_check/row count/date spanをauditへ残す
- detailed/compact null distributionsを分離する

## Routine target
将来のWork運用では、ユーザーの通常依頼を次の形まで簡略化する。

```text
MM/DDの競馬新聞用データを生成してください。
```

実行はhybrid / idempotentとする。

- PACIがあればJRDB Baseを生成する
- Analysis Liteが利用可能ならolder compact historyへ使用できる
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

## Issue entrypoint for current PoC

Current real-data PoC uses `[JRDB_RAW_FETCH_REQUEST]` with optional `newspaper_poc`. Exact contract is `REQUEST_CONTRACT.md`. Root `.gpt/ISSUE_REQUEST_CONTRACTS.md` preflight/retry rules apply.

## Distribution
日次生成JSONはGitへ入れない。Driveを保存正本候補とし、PWA配布面はGitHub Pages data + manifest、端末側はOPFSを第一候補とする。

## Deferred
- live/final odds
- 当日最終馬体重
- 勝負服画像
- 10走以上
- Edge status表示policy
- 独自指数計算
