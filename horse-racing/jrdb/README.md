# JRDB project

中央競馬予想で使用するJRDB系の取得・解析・RaceNote・EdgeDB・競馬新聞/PWA・研究資産を管理する現行プロジェクトです。

このREADMEは **入口と全体像** を担当します。スレッド移動や会話量上限後の再開では、READMEだけで作業を始めず、下記の引継ぎ順を使ってください。

## Thread restart / handoff

新しいChat / WorkスレッドでJRDB作業を再開する場合は、原則として次の順に確認します。

1. `README.md` — 全体像・思想・主要module
2. `.gpt/HANDOFF.md` — 現在の運用default・禁止事項・再開チェックリスト
3. `.gpt/CONTEXT.md` — データ正本・subsystem別の永続context
4. `.gpt/WORKFLOW.md` — GitHub / Actions / deterministic executionの経路選択
5. 対象subsystemのcurrent docs / contract / audit / source module
6. **必ず最新 `main` を再確認**してから変更する

古い引継ぎ文書、過去audit、過去Issue、固定SHAは履歴証跡です。現在仕様の判定は、最新main上のsource + current contract + current operational documentを優先します。

## Documentation map

| 役割 | 正本 |
| --- | --- |
| プロジェクト入口 | `README.md` |
| スレッド引継ぎ・現在default | `.gpt/HANDOFF.md` |
| 永続domain context | `.gpt/CONTEXT.md` |
| 実行経路・Git運用 | `.gpt/WORKFLOW.md` |
| JRDB Raw固定長解釈 | `src/jrdb_raw.py` + `docs/JRDB_Common_Raw_Reader_v0_1.md` |
| RaceNote正式仕様 | `docs/README_racenote_v1.md` / `docs/README_racenote_request.md` |
| RaceNote現行開発方針 | `docs/racenote/README.md` |
| RaceNote Forecast Gen0研究計画 | `docs/racenote/FORECAST_GEN0_PLAN.md` |
| RaceNote旧予想系境界 | `docs/racenote/legacy/README.md` |
| EdgeDB v0.2 serving | `docs/JRDB_Edge_Suggestive_Serving_Contract_v0_2.md` |
| EdgeDB STANDARD activation | `docs/JRDB_Edge_v0_2_STANDARD_Activation_Audit_20260911.md` |
| RaceNoteコメント表示 | `docs/RaceNote_Presentation_Comment_Contract_v0_2.md` |
| 開催後Analysis/Mart更新 | `docs/README_post_race_analysis_mart_refresh.md` |
| PWA / 条件別集計 / Newspaper表示運用 | `pwa/.gpt/HANDOFF.md` + `pwa/README.md` |

## Source of truth

正本は用途ごとに分離します。

- **code / schema / contract / docs**: GitHub `main` の `horse-racing/jrdb/`
- **JRDB Raw ZIP / PACI**: データ原典・再構築source
- **Analysis Lite / Stats Mart / large Canonical / research DB**: Google Drive上の検証済み共有artifact
- **RaceNote Archive**: immutable GitHub Release asset + release metadata
- **秘密情報**: Secrets / 環境変数。Gitへ保存しない

Gitへ大容量データを正本として持ち込まず、逆にコード仕様をDriveだけへ逃がしません。

## Core design principles

### 1. Raw interpretation is centralized

JRDB固定長データのbyte offset、decode、canonical key解釈は `src/jrdb_raw.py` を正本とします。

```text
JRDB Raw / PACI
  -> jrdb_raw.py
     -> consumer adapter
        -> RaceNote / Analysis / Eval / Edge / PWA
```

consumerが独自byte sliceを増殖させないことを原則とします。新fieldが必要ならCommon Readerへ追加し、characterization / regressionを通してから利用します。

### 2. Prediction-time data is pre-race only

開催前の予想、Edge matching、RaceNote predictionでは対象レース結果や後日情報を混入させません。過去日再現では `as_of_exclusive = target_date` を守ります。

### 3. Data delivery and prediction are separated

RaceNote / EdgeDB / Newspaper adapterは観測事実・検証済みevidence・provenanceを運びます。consumer側で同じ条件を再計算したり、表示層で印やEdgeを作り直したりしません。

### 4. Audit fields and reader language are separated

内部code、閾値、Edge ID、raw conditionは監査可能な形で保持します。一方、競馬新聞の通常表示や短評は読者向けの自然な競馬用語へ翻訳します。

### 5. Historical evidence is not automatically an additive score

Performance / Value、CONFIRMED / SUGGESTIVE、重複Edgeを安易に数値加算しません。数値統合は別途calibration / TRUE_FORWARD contractが成立した場合だけ行います。

## Stable identity / joins

主要joinは文字列identityを壊さないことを優先します。

- `race_key`: 場2 + 年2 + 回1 + 日1 + R2。日部分はhexを含むためraw文字列を保持
- `race_horse_key = race_key + horse_no`
- `result_key = blood_registration_no + YYYYMMDD`
- optional source joinは原則LEFT / fail-closedで扱い、欠損を推測補完しない

詳細はJRDBマスタ・固定長・ファイル相関定義とCommon Readerを参照してください。

## Current subsystem map

### Common Raw / Canonical

- `src/jrdb_raw.py` — BAC/KYI/CHA/CYB/SED/SKB/ZED/ZKB/UKC共通Reader
- `src/jrdb_raw_history.py` — annual Raw履歴アクセス
- `src/build_jrdb_canonical.py` — neutral factsのannual SQLite materialization
- `src/jrdb_store.py` — local/CLI向けartifact resolver。GPT標準Drive取得層そのものではない

Canonical SQLiteはRawを置換する正本ではなく、反復・横断アクセス用のmaterializationです。

### Analysis Lite / Stats Mart / post-race

- `src/build_jrdb_analysis_from_raw.py` — production full rebuild
- `src/update_jrdb_analysis_incremental.py` — 対象日単位の差分置換
- `src/build_jrdb_stats_mart.py` — Analysis -> Stats Mart
- `src/refresh_jrdb_stats_mart_year.py` — 対象年partition更新
- `src/build_jrdb_pwa_fact_lite.py` — 条件別集計PWA用Fact Lite

開催後の標準フローは、結果を使ってAnalysisを差分更新し、その更新済みAnalysisを正本保存・検証した後、Stats MartとFact Liteを再生成・検証・配布してconsumerを同一世代へ進めます。Analysisだけ更新してPWAを旧世代に残さないことを運用原則とします。

### RaceNote data layer

- `src/racenote_request.py` — 統一request入口
- `src/racenote_jrdb.py` — PACI -> base RaceNote v0.2
- `src/racenote_history_enrichment.py` / `src/racenote_history_engine.py` — Analysis/Mart履歴enrichment
- `src/racenote_reader_view.py` / `src/racenote_reader_zip.py` — GPT向けcompact view
- `src/racenote_archive.py` / `src/racenote_archive_backend.py` — historical delivery cache
- `src/resolve_racenote_archive_release.py` — compatible archive resolver

GPT-facing正式bundleはRaceNote v1.0。Archiveは高速delivery cacheでありRaw/Coreを置換しません。

RaceNote authoritative bundleはfacts / evidence / provenanceを担当し、予想印・結果を内部へ混ぜません。

### RaceNote Forecast Gen0

現在のRaceNote予想研究の正本方針は `docs/racenote/README.md` と `docs/racenote/FORECAST_GEN0_PLAN.md` です。

RaceNote Forecast Gen0では、RaceNote v1.0 / Reader ViewをGPTが読み、レース条件・能力・適性・展開・調教状態・近走・長期履歴・補助統計・coverageを横比較して予想します。

固定weightや単一の決定論的gateをcurrent defaultにせず、次の順で改善します。

```text
pre-race evidence
  -> GPT comparison / prediction
  -> pre-result self-audit
  -> immutable freeze
  -> result acquisition
  -> post-race reading audit
  -> 約50R単位の改善
```

`docs/RaceNote_Prediction_Handoff_v0_1.md` はGPT prediction layerの原点として引き続き重要です。

旧v0.2 control / v1.1-P gated policyは再現性・比較研究のため保持しますが、現行Gen0の予想ロジックではありません。詳細は `docs/racenote/legacy/README.md` を参照してください。

### EdgeDB v0.2

主要module:

- `src/build_jrdb_edge_feature_mart_v0_2.py`
- `src/jrdb_edge_discovery_v0_2.py`
- `src/build_jrdb_edge_registry_v0_2.py`
- `src/apply_jrdb_edge_statistical_guard_v0_2.py`
- `src/build_jrdb_edge_suggestive_publication_v0_2.py`
- `src/build_jrdb_edge_current_facts_v0_2.py`
- `src/jrdb_edge_matcher_v0_2.py`
- `src/run_jrdb_edge_match_current_v0_2.py`

現在のordinary current-runnerは **STANDARD** がdefaultです。

```text
run_jrdb_edge_match_current_v0_2.py
  -> STANDARD
  -> ACTIVE / CONFIRMED + eligible SUGGESTIVE
```

ただしlow-level `jrdb_edge_matcher_v0_2` のdefaultは意図的に **CONFIRMED_ONLY** のままです。library importだけでserved evidenceが増えないためのfail-safeです。

重要な不変条件:

- ACTIVEのproduction statistical thresholdを緩めない
- SUGGESTIVEをRegistry ACTIVEへ昇格させない。通常は `registry_status=REJECTED` のまま
- Performance evidenceとValue evidenceを別channelとして扱う
- SUGGESTIVEを「統計的に確認済み」と表現しない
- overlapping Edgeのstrength / ROI / lift / q-valueを加算しない
- current matchingはexact-match・pre-race only
- consumer / PWA / NewspaperでEdge条件を再実装しない
- v0.1 matcherはbackward compatibility用として保持し、v0.2仕様を混入させない

通常v0.2 consumer inputは `edge_serving_catalog_v0_2.jsonl`。詳細条件はServing Contractを優先します。

### Legacy RaceNote prediction presentation

- `src/racenote_prediction_presentation.py` — base presentation evidence
- `src/racenote_prediction_presentation_v0_2.py` — frozen Edge axis decisionを読者向け説明へ投影

これらは既存consumer / historical v1.1-P freezeを説明する表示資産として保持します。**v1.1-Pの軸決定を現行Gen0へ持ち込む入口ではありません。**

表示層は予想を再計算しません。

`good`等の内部名は通常コメントへ直接出さず、たとえば `基礎総合評価`、`逆転許容圏内`、Edge方向の `プラス / 中立 / マイナス` へ翻訳します。各馬コメントは馬固有の根拠、レース短評はレース全体の選定・◎変更理由を担当します。

JRDBゴール予測など、すでに基礎評価へ含まれるcomponentをEdge後の独立voteとして再加算・再説明しないことも重要です。

### Newspaper / PWA

- `src/jrdb_newspaper_build.py`
- `src/jrdb_newspaper_day_build.py`
- `src/jrdb_newspaper_merge_external.py`
- `src/jrdb_newspaper_merge_edge.py`
- `src/jrdb_newspaper_edge_adapter.py`
- `src/jrdb_newspaper_publish_current.py`

概念フロー:

```text
PACI + Analysis history
  -> Edge Current Facts
  -> Edge Matcher
  -> edge_matches.jsonl
  -> Newspaper merge / adapter
  -> reader-facing special memo / PWA
```

`jrdb_newspaper_edge_adapter.py` は **display boundary** です。matcher結果の意味を変更せず、structured evidenceを人間向け表示へ翻訳します。Raw `display_text` / evidenceはaudit用に保持します。

joinの中心は `race_key / race_horse_key / horse_no`。Newspaper側でEdge条件を再判定しません。

PWA / Newspaperの都合でForecast policyを変更しません。まずfrozen prediction contractを作り、その出力をconsumerが表示します。

PWAの表示・同期・配布・スレッド再開は `pwa/.gpt/HANDOFF.md` を入口とし、Newspaperの日次生成・source mergeは `newspaper/.gpt/HANDOFF.md` を入口とします。

### Eval / training research

- `src/enrich_eval_csv_with_paci.py` — Eval OCR結果の開催前enrichment
- `src/export_jrdb_eval_race_conditions.py`
- `src/export_jrdb_eval_dataset.py`
- `src/export_jrdb_eval_horse_results.py`
- `src/build_jrdb_training_research.py`
- `src/audit_jrdb_training_research.py`
- `src/analyze_jrdb_training_stage1b.py`

Evalや追い切り研究はそれぞれ独立した検証contractを持ち、RaceNote/Edgeへ暗黙にロジックを混入させません。

## GitHub / execution policy

実行経路は `.gpt/WORKFLOW.md` を正本とします。要約すると:

- **A Read / Audit** — repo/file/commit/run/artifact/SHA確認。Issue不要
- **B Git Change** — source/test/docs/configのUTF-8変更をlatest mainへdirect commit
- **C Pure Deterministic Execution** — focused test、既取得artifact集計、hash/integrity、固定入力変換
- **D Actions-Native Execution** — JRDB Secrets、長時間Full build、immutable publication、正式run証跡が必要な処理

Issue駆動を標準に戻しません。Actionsが必要なときだけIssue / workflow契約を使います。

## Change discipline

変更時は次を守ります。

1. latest mainを確認
2. 対象path・現在内容・blob SHAを確認
3. current contractとsourceのどちらが正本かを確認
4. 必要最小限の差分を作る
5. focused test / deterministic auditを優先
6. write後にreadback
7. 仕様・default・入口が変わった場合はREADME / CONTEXT / HANDOFFのどこを更新すべきか確認

Full rebuildは、frozen artifactで目的を満たせる場合に習慣的に再実行しません。

## Historical documents

`docs/` には設計途中・audit・旧version・PoCも残します。これは再現性のためであり、すべてが現行運用を意味するわけではありません。

特にStatusや日付の古い文書を単独でcurrent truthとみなさず、次の優先順で判断します。

```text
latest main source
  + current contract / operational doc
  + current audit
  > historical handoff / old design / old issue
```

RaceNote旧予想系は `docs/racenote/legacy/README.md` で論理分離します。既存import / workflow / historical reproducibilityを壊さないため、現時点では物理移動しません。

旧JRA-VAN版は `horse-racing/legacy/` の凍結資産で、現行JRDB実装とは分離します。
