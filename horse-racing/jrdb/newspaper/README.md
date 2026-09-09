# JRDB Newspaper module

Status: REAL-DATA DATA CONTRACT VALIDATED / PWA DISPLAY POC NEXT

このディレクトリは、JRDB PWA向け「自分用競馬新聞」の日次生成・外部source merge・配布契約を独立管理するためのmodule boundaryです。

## Design source of truth

- `../docs/JRDB_PWA_Newspaper_Design_v0_1.md`
- `../docs/JRDB_Newspaper_Neutral_Dependency_Inventory_v0_1.md`
- `../docs/JRDB_Newspaper_PoC_20260816_Sapporo11_5plus3_20260909.md`
- `../schema/jrdb_pwa_newspaper_race_schema_v0_1.json`
- `../schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json`
- `.gpt/REQUEST_CONTRACT.md`

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
  KYI previous 1-5 + ZED/ZKB -> detailed_recent_history
  optional Analysis Lite -> compact_older_history up to total 8
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

`../src/audit_jrdb_newspaper_poc.py` はreal-data PoC用監査器で、PACI/Analysis provenance、schema、headcount、history layer、chronology、duplicate、RaceNote import、addon/Edge境界を監査します。

Synthetic regressionは `.github/workflows/jrdb_common_reader_tests.yml` に組み込み済みです。2026-09-09 run `34305173081` はsuccess。

## Real-data validation: 2026-08-16 札幌11R 札幌記念

### PACI-only 5-run PASS

- target: `01261811` / 札幌11R / 札幌記念 / 芝2000m / G2 / 16頭
- 16頭 identity/headcount exact
- detailed history 5走 × 16頭 = 80走
- previous expected/resolved/unresolved = 80 / 80 / 0
- chronology violation = 0
- duplicate history identity = 0
- forbidden `racenote_*` import = 0
- addons null / Edge empty

アドマイヤテラの2025-11-30 ジャパンCは `abnormal_code=3`、ZKBコメントは「スタート直後躓き態勢崩し鞍上が落馬、中止」。time / last3f / IDM等の欠損は競走中止に対応し、parser failureではない。

### Analysis-backed 5+3 PASS

Issue #614 / run `34307352474`。

- 16/16頭が8走
- total history = 128
- detailed = 80
- compact = 48
- Analysis supplemental = 48
- chronology violation = 0
- duplicate = 0
- schema = PASS
- forbidden RaceNote imports = 0
- pretty JSON = 307,691 bytes

Analysis audit:

- 197,492,736 bytes
- SHA-256 `4df011c74b226ad394a171b71c0841872cb94f3418c8e7f85225a31de89e21b2`
- quick_check = ok
- rows = 513,512
- period = 2016-01-05 .. 2026-08-23

Compact 48 runsでは `final_win_odds` が48/48 null。これは現在のAnalysis Lite全体で当該列がnullであるためで、Newspaper側のparser欠損ではない。6-8走目では人気を利用し、単勝オッズは表示必須にしない。

## UI order

```text
馬情報 -> 印群 -> 過去走 -> Edge
```

1頭1行を基本とし、スマホ横スクロールを前提にします。

PWA display PoC policy:

- default: 3走
- toggle: 5走 / 8走
- 1-5 detailedは時計・上がり・IDM・comment詳細へ展開可能
- 6-8 compactはAnalysisに存在するfieldのみ表示
- compactのrace_name欠損時は場/R + grade/classへfallback
- source layer差を内部的に保持し、compactをdetailedと誤表示しない

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
- real-data PoC auditor: `../src/audit_jrdb_newspaper_poc.py`
- JRDB current race / runner base: BAC / KYI / CHA / CYB / UKC等のpre-race dataをneutral readerから投影
- history: Newspaper専用projectionをneutral JRDB history/access層の上に実装する
- Analysis Lite: optional compact older-history source。RaceNote-owned storeではない
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

完了:

- neutral dependency inventory
- Newspaper JRDB Base builder synthetic PoC
- detailed previous 1-5 history projection
- Analysis compact 6-8補完
- race bundle schema alignment
- schema / as-of / headcount / architecture regression
- PACI-only 札幌記念 real-data PoC
- Analysis-backed 5+3 札幌記念 real-data PoC
- existing JRDB Raw fetch Issueへのoptional Newspaper PoC統合

次:

- PWA newspaper display PoC
- 3/5/8 toggle
- sticky 馬番/馬名 + 横スクロールの実機確認

未実装:

- merge engine
- daily manifest builder
- Drive save
- production publish workflow
- OPFS newspaper sync
