# JRDB GPT workflow

Last reviewed: 2026-09-13

## Thread restart bootstrap

会話量上限・スレッド分割・担当変更後は、作業開始前に次を確認する。

1. repository root `.gpt/GITHUB_OPERATION_POLICY.md`
2. repository root `.gpt/README.md`
3. `horse-racing/jrdb/README.md`
4. `.gpt/HANDOFF.md`
5. `.gpt/CONTEXT.md`
6. `.gpt/WORKFLOW.md`（この文書）
7. latest `main` HEAD
8. 対象subsystemのcurrent guide / contract / audit / source / focused tests

RaceNote作業では追加で `docs/racenote/README.md` と `docs/racenote/FORECAST_GEN0_PLAN.md` を読む。旧決定論的予想系を扱う場合だけ `docs/racenote/legacy/README.md` も確認する。

過去handoff、古いIssue本文、日付付きaudit、固定SHAを単独でcurrent truthとしない。latest source + current guide/contractを優先する。

## Standard preflight

1. `README.md` / HANDOFF / CONTEXTを確認。
2. 対象Pythonと対応README・schema/reference/contractを確認。
3. 2026 Raw（PACI / SED / HJC）を扱う場合は、`docs/JRDB_2026_Raw_Drive_Reference.md` を確認し、Google Drive上の既存Rawを最優先でresolveする。Drive inventoryを確認せずupstream全日付取得を開始しない。
4. 既存仕様を壊さない範囲で改修。
5. 可能な範囲で実行テスト / 回帰確認。
6. 生成物・秘密情報・Rawデータが差分に入っていないことを確認。
7. entrypoint / default / contract / subsystem boundary / current-vs-legacy boundaryが変わる場合、README / CONTEXT / HANDOFF / dedicated docsの更新要否を同時確認。
8. Gitへcommitし、以後Git版を正本とする。

## GitHub routing standard — 2026-09-10

JRDBをChatGPTから扱う場合、処理開始時に「GitHub Actions実行環境が本当に必要か」を判定し、次の4経路を標準とする。Issue駆動を既定経路にはしない。

### A. Read / Audit

GitHub repository/file/commit/issue/workflow/run/artifact metadata、コード検索、main内容、差分、SHA、RESULT状態などの確認はGitHubのread/search/fetch機能から直接行う。確認だけのためにIssueを作成しない。

### B. Git Change

source/test/docs/config等のUTF-8テキスト変更は、原則としてGitHubのcreate/update/delete機能で最新mainへ直接remote commitする。

変更前に次を確認する。

1. 最新main
2. 対象pathの存在
3. 現在内容 / blob SHA
4. 必要差分

変更後は対象fileをreadbackし、必要なfocused test / regressionをCまたは既存CIで確認する。`[gpt-git-update]` Issueは標準経路としない。

複数fileを連続更新する間にmainが進んだ場合は、次のwrite前にlatest mainと対象blobを再確認し、他commitを上書きしない。

### C. Pure Deterministic Execution

Secrets、Actions固有権限、Actions artifact chain、長時間・大容量runner、immutable freeze、正式監査runを必要としない決定的処理はChat実行環境のPython / shellで直接行う。

例:

- focused unit test / regression test
- 既取得artifactやSQLite/JSON/CSVの集計・監査
- SHA-256 / schema / row-count / integrity確認
- WATCH理由分解等のaudit-only処理
- 固定入力に対する変換・JOIN・レポート生成
- fixed fixture / frozen inputに対するRaceNote / Edge / Newspaperのdeterministic validation

同一処理を「Issueを投げるためだけ」にActionsへ送らない。

### D. Actions-Native Execution

以下はIssue / GitHub Actions経路を維持する。

- `JRDB_USER` / `JRDB_PASSWORD` 等のSecretsを使うJRDB取得・再構築
- upstream Actions artifactを正式入力としてchainする処理
- Full 2010-2025等の長時間・大容量build
- immutable freeze / publication / release等、GitHub runを不変証跡として必要とする処理
- 正式な監査run・再現性証跡としてrun ID / artifact / workflow RESULTを残す必要がある処理
- GitHub-hosted環境そのものを検証対象とする処理

Dを使う場合のみ、下記「Issue駆動Actionsのpreflight」を適用する。

### Google Drive routing — do not use Actions Drive bridge

JRDBのRaw / Analysis / Fact Lite / research asset等をGoogle Driveへ保存・取得する場合も、repository rootのDrive routing decisionを優先する。

- production-standard: connected native Google Drive connector / native tools
- frozen / prohibited for normal operation: `[gpt-gdrive-request]` / `.github/workflows/gpt_gdrive_request_issue.yml` / `tools/gpt_io/gdrive/`
- GitHub Actions artifactをDriveへ保存する場合は、GitHub connectorでartifactを取得し、native Google Drive connectorへ渡す。
- Actions artifact -> Driveの搬送だけを理由にDrive bridge Issueを作らない。
- repositoryにworkflowが残っていても、それはcompatibility / future implementation assetであり、current operational permissionではない。
- `GPT_GDRIVE_ACTIONS_BRIDGE_ENABLED` やService Account Secretを有効化・設定しない。

正本: repository root `tools/gpt_io/DRIVE_ROUTING_DECISION_v0_1.md`。

### Edge Registry / EdgeDBでの標準適用

- Registry/source/docs/configの参照、Issue/run/artifact/SHA確認: **A**
- Edge Registry / v0.2 matcher / current facts / publicationのPython/test/docs/config修正: **B**
- 既存Registry artifactに対するWATCH/statistical audit、focused tests: **C**
- fixed current facts / matcher / newspaper adapterの決定的回帰: **C**
- 2025-only real-data smoke build（Raw取得を含む）: **D** — JRDB Secrets + artifact監査
- Full 2010-2025 Registry rebuild: **D** — Secrets + 長時間/大容量 + publication artifact
- PACI等の認証取得を伴うofficial current matching / artifact chain: **D**

Current operational boundary:

- ordinary `run_jrdb_edge_match_current_v0_2.py` defaultは `STANDARD`
- low-level `jrdb_edge_matcher_v0_2.py` defaultは意図的に `CONFIRMED_ONLY`
- SUGGESTIVEはRegistry ACTIVEへ昇格させない
- Performance / Valueを混ぜない
- consumerでEdge条件を再実装しない

詳細は `docs/JRDB_Edge_Suggestive_Serving_Contract_v0_2.md` を優先する。

#### Edge storage execution rule

- Feature Mart canonicalはParquet。通常のfull Registry buildでは `prepare_jrdb_edge_feature_mart_duckdb.py` でDuckDB execution workspaceを1回作成し、そのworkspaceをdiscovery / validation / HUMAN calibration / statistical guardで共有する。
- `jrdb_edge_feature_mart_parquet.materialize_current_sqlite()` を通常workflowから呼ばない。Feature Mart SQLiteはlegacy reproductionだけ。
- Feature Mart再生成は `build_jrdb_edge_feature_mart_v0_2.py --output-engine duckdb` → `build_jrdb_edge_feature_mart_parquet_generation.py --workspace ...` を標準とする。
- Registryはmutable build中のみtransient SQLiteを許容する。v0.2 full build成功時は同じrunでRegistry Parquet candidateも生成し、長期保存/current sourceはParquetとする。
- Registry canonical readは `jrdb_edge_registry_parquet.connect_current()` を使用する。ParquetからSQLiteへ戻す通常経路は禁止。SQLite再materializeは明示的なlegacy reproductionのみ。
- Edge scientific semantics、v0.2 STANDARD、v0.3 SHADOW、TRUE_FORWARD境界はstorage実装変更と同時に変更しない。


### RaceNote Forecast Gen0での標準適用

Current prediction researchは **RaceNote Forecast Gen0**。作業開始時に `docs/racenote/README.md` と `docs/racenote/FORECAST_GEN0_PLAN.md` を確認する。

- current forecast方針、prediction record、self-audit guidance、docs/schema/testのUTF-8変更: **B**
- validated Reader View / frozen fixture等の既取得pre-race入力だけを使う比較、prediction-record validation、hash / leakage / freeze-format検証: 正式run証跡が不要なら **C**
- JRDB Secretsを使うsource取得、正式なimmutable pre-result freeze、Actions artifact chain、formal TRUE_FORWARD evidenceを必要とする実行: **D**
- Gen0の一回の研究・レビューをIssue/Actionsへ送ること自体を目的化しない。要件がA/B/Cで満たせるならDへ送らない。

Current Gen0 boundary:

- RaceNote authoritative bundle / Reader Viewはfacts / evidence / provenanceでありprediction modelではない
- GPTがRaceNote全体を横比較してforecastする
- fixed weight / single score / single gateをcurrent defaultにしない
- result acquisitionはprediction freezeより後
- 改善は原則として約50R等のまとまりでreading error / overvaluation / undervaluation / uncertaintyを監査する
- EdgeDBを使う場合もPerformance / Value、CONFIRMED / SUGGESTIVE、overlapを区別し、単一Edgeで機械的に軸を決めない
- Eval / keibailuka等のexternal sourceをRaceNote-only Gen0へ暗黙に混ぜない

### RaceNote legacy prediction / presentationでの標準適用

次はhistorical reproducibility / benchmark用legacy prediction logicとして扱う。

- v0.2 control baseline
- v1.1-P gated prediction
- `src/racenote_edge_prediction_policy.py`
- `src/run_racenote_v11p_true_forward_day.py`
- v1.1-P TRUE_FORWARD freeze / workflow
- v1.1-P frozen marksを入力とするpresentation

旧資産の参照・監査: **A**。互換性を保つsource/docs/test修正: **B**。既取得freezeを使う再現・差分監査: **C**。旧formal runの再生成にSecrets / immutable run evidenceが必要なら **D**。

LegacyからGen0へ再利用してよいのは、pre-race guard、as-of validation、source identity、hash、immutable freeze、result-after-freeze、prediction/presentation immutable check等の**検証インフラ**。次の旧decision ruleはcurrent Gen0へ暗黙に持ち込まない。

- top5固定候補
- Good差 `<= 0.04`
- stronger Edge polarityによる機械的な◎昇格
- v1.1-P順位の無条件継承

詳細は `docs/racenote/legacy/README.md`。`src/racenote_prediction_presentation_v0_2.py` と `docs/RaceNote_Presentation_Comment_Contract_v0_2.md` は既存consumer / historical v1.1-P freezeの表示互換として扱い、Gen0 prediction policyの根拠にしない。

### Newspaper / PWAでの標準適用

- Newspaper / PWA source、schema、contract、current publish metadataの確認: **A**
- reader-facing wording、adapter、merge、schema/docs/testのUTF-8修正: **B**
- fixed fixtureでのmerge、join、reader-language regression: **C**
- JRDB Secretsを使うsource取得を含む正式day package生成、immutable publication chain: **D**

責務境界:

- NewspaperはEdge matcher outputをconsumeし、Edge条件を再計算しない
- `jrdb_newspaper_edge_adapter.py` はdisplay boundaryでありmatching semanticsを変更しない
- internal code / raw condition / Edge IDはaudit可能に保持し、ordinary reader-facing proseでは必要に応じて翻訳する
- PWA / Newspaperのdelivery都合でForecast policyを決めない。forecastは先にfreezeし、consumerは安定したoutput contractを表示する
- 表示だけの修正でEdge threshold / eligibility / Registry status / prediction markを変えない

既存v1.1-P frozen predictionを表示する場合のreader wordingは `docs/RaceNote_Presentation_Comment_Contract_v0_2.md` を参照する。

### Post-race Analysis / Mart / Fact Liteでの標準適用

- current Analysis/Mart/Fact Liteの世代、schema、manifest、Drive/Git publication状態確認: **A**
- updater / builder / validator / docs / workflowのテキスト修正: **B**
- 既取得PACI/SED/Analysisを使う差分生成・validation・row count・integrity確認: 条件がCを満たす場合 **C**
- JRDB認証取得、formal artifact chain、Release/Pages publicationを伴う開催後正式更新: **D**

開催後は `Analysis update -> canonical save/validation -> Stats Mart refresh -> Fact Lite regenerate/validate/publish -> condition-summary PWA update` を一つの運用世代として扱う。Analysisだけを更新して後続PWAを旧世代に残さない。

### Ability / Debut Ability指数開発での標準適用

- Controller disposition、protocol、source、issue/run/artifact、main HEAD、SHA、既存監査結果の確認: **A**
- Ability / Debut Abilityのsource/test/docs/schema/config/workflow修正、protocol freeze文書の反映: **B**
- compile、focused pytest、fixture回帰、固定済み入力に対する決定的な集計・比較・SHA/整合性確認: **C**
- 既取得済みartifact/SQLite/JSON/CSVだけを入力とする追加metric、差分比較、診断レポート: **C**。正式run証跡が不要なら再度Actionsを起動しない。
- `jrdb_debut_ability_smoke_issue.yml` 相当のcompile + focused regressionは通常 **C** とし、smokeだけのためにIssueを作成しない。GitHub-hosted runner環境自体の検証が目的の場合のみ **D** を許可する。
- `JRDB_USER` / `JRDB_PASSWORD` でRawを取得して2010-2023/2025を再構築するAbility/Debut snapshot audit・coverage: **D** — Secrets + 長時間/大容量 +正式監査artifact。
- 2010-2023 Ability/Debut predictive comparison: **D** — 長時間・大容量のwalk-forward/model gridであり、Controller選択前のcanonical comparison evidenceとしてrun ID / artifactを固定する。
- 2024-2025 temporal holdout/confirmation: **D** — locked holdoutのimmutable confirmation evidenceとしてActions履歴を必要とする。
- canonical model/snapshotの正式再監査、再現性freeze、publication/releaseに相当するrun: **D**。

Controllerの設計判断やfreeze決定そのものを文書へ反映するだけなら **B** でよい。対して、その判断の根拠となるcanonical full-history build / comparison / holdout / audit evidenceを新規生成する場合は **D** とする。

RaceNote、EdgeDB、Eval、Training等のsubsystemは各専用guide/contractを優先し、別subsystemのロジックを暗黙に混在させない。

## Documentation synchronization rule

次の変更は、sourceだけで終わらせずdocumentation impactを確認する。

- operational defaultの変更
- normal entrypointの変更
- source-of-truthの変更
- schema / join identity / leakage boundaryの変更
- Edge evidence semantics / serving profileの変更
- current prediction direction / current-vs-legacy boundaryの変更
- presentation responsibility boundaryの変更
- post-race generation chainの変更

役割分担:

- `README.md`: durable architecture / project entry
- `.gpt/HANDOFF.md`: new-thread bootstrap / current operational defaults
- `.gpt/CONTEXT.md`: persistent domain context
- `.gpt/WORKFLOW.md`: execution routing
- `docs/racenote/README.md`: current RaceNote development direction
- `docs/racenote/FORECAST_GEN0_PLAN.md`: current Forecast research cycle
- `docs/racenote/legacy/README.md`: historical deterministic prediction boundary
- `docs/*Contract*.md`: subsystem-specific normative semantics
- dated audit: verification evidence, not permanent operational default

## Issue駆動Actionsのpreflight

- JRDB / RaceNote系を含むIssue起点Actionsは、Issue作成前にルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` を確認する。
- title prefix、必須body項目、upstream dependency、RESULT markerをworkflow / 対応docsから確認してからIssueを作成する。
- upstream `run_id` / `artifact_name` 等を使う場合、前工程RESULTが `status=success` であることを確認し、値を完全一致で転記する。推測値を使用しない。
- simple `key: value` bodyは `.gpt/tools/gpt_issue_preflight.py --protocol generic --required-key ...` で事前検証できる。
- retry時はfailed stepを確認し、必要に応じて最新 `main` / upstream RESULTからrequestを再構築する。同一requestの盲目的rerunを標準運用にしない。

## GitHubバイナリ正本の取得・更新

- GitHub `main` 上の `.xlsx`、`.sqlite`、`.zip` 等をChat / Workで実ファイルとして扱う必要がある場合、まず直接取得可能なGitHub/connector経路を確認する。
- 認証済み `gh` CLIを実行できる環境ではルート `.gpt/tools/gpt_git_binary_tool.py` を利用できるが、Issueを不要に経由させない。
- GitHub正本を実ファイルとして直接取得できない場合のみ、`[gpt-git-binary-read]` をフォールバックとする。
- Git管理対象バイナリを直接安全に更新できない場合のみ、`[gpt-git-binary-update]` をフォールバックとする。
- GitHub Connectorでバイナリを直接読めないことを理由に、GitHub正本が存在するファイルの再添付をユーザーへ依頼しない。
- 詳細はルート `.gpt/GIT_BINARY_TOOL.md`、`.gpt/GIT_BINARY_READ_ISSUE.md`、`.gpt/GIT_BINARY_UPDATE_ISSUE.md` を参照する。
- readback artifactは搬送用の一時物であり、正本はGitHub `main` 上の対象ファイルとする。


### Historical Analysis input selection — 2026-09-21

- For a **2010–2025 historical backfill or rebuild**, use the dedicated JRDB Warehouse `current.json` and `jrdb_analysis_warehouse_adapter.py`. It is the accepted standard input after the formal dual-read PASS.
- Use historical Raw-direct only for rollback or audit, with the explicit `--allow-historical-raw` switch. Do not silently select it as the normal historical path.
- For **2026 current daily updates**, keep the existing PACI/SED Raw-direct incremental route. PACI daily normalization remains separate scope.
- The Warehouse reader must reject dates outside its accepted 2010–2025 coverage. Do not attempt to satisfy a 2026 request from Warehouse.
- Do not alter the JRDB Warehouse current pointer, historical Warehouse Parquet, or the existing Analysis current pointer as part of this routing choice.

The formal comparison and exact gates are recorded in `docs/JRDB_Analysis_Warehouse_Dual_Read_Audit_20260921.md`; the normative contract is `docs/JRDB_Analysis_Warehouse_Input_Contract_v1.md`.
