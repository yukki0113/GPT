# JRDB GPT workflow

## Public Drive read-only Historical input (2026-10-09)

For accepted 2010–2025 Historical v0.5.2 work, the verified unauthenticated
transport boundary is `tools/gpt_io/public_drive/fetch.py`. For the current
accepted 2025 Warehouse generation, use the reviewed manifest
`config/public_drive/racenote_historical_golden_20251228_v1.json`.
The manifest pins public file IDs, filenames, sizes and SHA-256 values. The
shared helper downloads read-only and validates integrity before local
promotion; downstream work must continue through the existing Warehouse /
RaceNote readers.

Do not add direct `gdown` URLs to JRDB workflows or silently use authenticated
Drive access on failure. Do not write back to Drive from Actions. 2026 daily
PACI remains unchanged. See `tools/gpt_io/DRIVE_ROUTING_DECISION_v0_2.md`.

The BTDAY lottery state
`config/racenote_backtest_day_pool_2026.json` is legacy-named but now unified:
it contains remaining 2026 PACI rows and 109 actual 2025 race days from
`BAC_2025.zip` as `source_mode=historical_warehouse`,
`selection_cycle=1`. A normal unfiltered pick may select either source.
After every pick, branch on the selected row's `source_mode`; never fabricate
a `paci_file_id` for a Historical row. Historical preparation must first
materialize the reviewed public bundle through the shared helper, then call
`src/racenote_v052_from_historical_warehouse.py`.


## RaceNote v0.5.2 source routing — 2026-10-09

- 2026: continue using the existing PACI daily ZIP entrypoint.
- 2010–2025: require the committed Raw/Warehouse equivalence report `PASS`
  for the same accepted Warehouse generation, then use
  `src/racenote_v052_from_historical_warehouse.py` to create DAY PREP,
  market-blind forecast_prep and a sealed v0.5.2 session.
- Use the same v0.5.2 authoring, Decision Core, `save`, `freeze`, and `verify`
  commands for either source. Never open target results or final market before
  Freeze/Verify. Preserve `as_of_exclusive=target_date`.
- Historical picker inventory must record source reference and selection cycle;
  do not clear first-cycle usage to replay a date.
- Detailed commands and gate: `docs/racenote/RACENOTE_V052_SINGLE_DAY_RUNBOOK_v0_1.md`.

Last reviewed: 2026-10-09

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
3. Parquet / DuckDBを扱う場合は、repository共通 `tools/data-storage/` をresolveし、既存 `.venv-data-storage` + `check-deps` を先に確認する。依存が現在のPythonへ入っていないだけでは停止せず、必要なら `tools/data-storage/requirements.txt` からbootstrapする。
4. 2026 Raw（PACI / SED / HJC）を扱う場合は、`docs/JRDB_2026_Raw_Drive_Reference.md` を確認し、Google Drive上の既存Rawを最優先でresolveする。Drive inventoryを確認せずupstream全日付取得を開始しない。
5. 既存仕様を壊さない範囲で改修。
6. 可能な範囲で実行テスト / 回帰確認。
7. 生成物・秘密情報・Rawデータが差分に入っていないことを確認。
8. entrypoint / default / contract / subsystem boundary / current-vs-legacy boundaryが変わる場合、README / CONTEXT / HANDOFF / dedicated docsの更新要否を同時確認。
9. Gitへcommitし、以後Git版を正本とする。

## Current daily Raw acquisition — 2026-10-01

Routine 2026 acquisition requests use the canonical contract:

`docs/JRDB_Daily_Raw_Acquisition_Operation_v0_1.md`

User-facing commands:

- `mmddの開催前取得をお願いします`
  - target-date PACI
  - identify the actual race dates in the immediately preceding JRA race week
  - check canonical Drive SKB inventory first
  - fetch/upload only missing SKB for those preceding-week race dates
  - do not fetch target-date SED/HJC as part of this command
- `mmdd〜mmddの開催後取得をお願いします`
  - fetch/upload SED and HJC for each requested race date
  - do not request SKB
  - do not request PACI

SKB is a delayed-recovery family in routine daily operation. A same-week `NOT_FOUND` for SKB is not by itself an error and must not trigger repeated blind retries. Missing SKB is recovered during the next pre-race acquisition after a Drive inventory check.

For both commands:

1. check canonical Drive inventory before upstream fetch;
2. authenticated JRDB fetch remains Actions-native;
3. download the Actions artifact into GPT runtime;
4. validate ZIP/readability/member presence/size/SHA;
5. publish through the native Google Drive connector only;
6. re-list Drive and verify exact filename + size before reporting success.

Do not use the retired Actions-to-Drive bridge.

## Completed-race Result Query — mandatory Drive bridge

For requests asking for completed JRA results, payouts, hit settlement, ROI inputs, or in-the-money outcomes, use JRDB first.  RaceNote has two post-Freeze routes: JRDB SED/HJC when those target-date files already exist, and a public-Web速報 fallback only while they are still unavailable.

### Post-Freeze RaceNote result / settlement routing

1. Confirm the relevant Forecast records are already frozen and the pre-result Guard passed.
2. Check the canonical Drive inventory for target-date `SEDyymmdd.zip` and `HJCyymmdd.zip`.
3. If **both exist**, use the deterministic JRDB route:
   - materialize both files through the native Drive connector;
   - run `src/racenote_daily_result_from_jrdb.py --date YYYY-MM-DD --sed ... --hjc ...`;
   - SED supplies finishers, HJC supplies all eight payout types;
   - SED win/place payout fields are cross-validated against HJC;
   - Web result acquisition is unnecessary.
4. If target-date SED/HJC is **not yet available** (normally race-day速報), use `src/racenote_daily_result_fetch.py --date YYYY-MM-DD`.
   - v0.1 uses Sponichi Keiba Web as a replaceable public-Web source;
   - unfinished/incompletely posted races stay `pending`; abnormal/dead-heat shapes fail closed as `review_required`.
5. Run `src/racenote_daily_settlement.py --forecast ... --results ...`.
   - all tickets are 100 yen fixed;
   - it reports ◎ win/place, ◎-○/▲ quinella and exacta, ◎-all-marks trio flow, and ◎-1st-fixed trifecta flow ROI/top payouts.
6. Detailed RaceReview remains the canonical JRDB SED/HJC post-race review path.

Canonical guide: `docs/racenote/SAME_DAY_RESULT_SETTLEMENT_v0_1.md`.

Hard boundary:
- never open the target-date public result page before the Forecast Freeze/Guard;
- do not use same-day Web results as a RaceNote/Forecast input;
- do not replace weekday JRDB SED/HJC detailed review with this速報 route.

The generic completed-race path below remains the default for historical/post-race result queries and for any date whose JRDB result assets are already available.

Standard execution:

1. Read `docs/README_jrdb_result_query.md`.
2. Run `src/jrdb_result_query_runner.py --date ... --plan` to obtain the exact required SED/HJC Drive paths.
3. Use the **native Google Drive connector** to locate and materialize those files into the plan's local paths.
4. Execute `src/jrdb_result_query_runner.py --date ... [--venue ...] [--race ...]`.
5. If the query returns `success` / `review_required`, use JRDB as the result source.
6. If a required Drive object cannot be found after an actual Drive inventory check, report the JRDB gap. External Web may be used only when the user needs a fallback fact and the JRDB source is genuinely absent/outside coverage.

Important:
- Raw ZIPs are intentionally excluded from Git. "Raw is not in the repository" is an expected state, not a failure.
- Do not use GitHub repository search to decide whether SED/HJC data exists.
- Do not ask the user to provide local paths when the connected Project Drive contains the source.
- Do not add a direct Drive client/gdown/API transport to GitHub Actions for this flow; transport remains GPT/native-connector -> runtime.
- 2026+ uses daily `SEDyymmdd.zip` + `HJCyymmdd.zip`; <=2025 runner plans annual `SED_YYYY.zip` + `HJC_YYYY.zip`, which the query engine filters to the requested date.

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

#### Parquet / DuckDB execution preflight

JRDBでParquet / DuckDBを読む・集計する・validationする処理では、`tools/data-storage/` をrepository共通の汎用CRUD / Data Storage基盤として扱う。

```text
Parquet / DuckDB task
-> tools/data-storage/README.md 確認
-> 既存 .venv-data-storage を確認
-> check-deps PASSならそのまま再利用
-> absent / DEPENDENCY_MISSINGなら requirements からbootstrap
-> check-deps再実行
-> 共通CLI またはJRDB正本module/configを実行
```

`import duckdb` / `import pyarrow` の失敗だけで「この環境では扱えない」と結論しない。依存install自体が失敗・禁止される場合のみ実行不能として報告する。

単純query / validation / conversionは共通CLIを優先し、JRDB固有のscientific semantics、schema、canonical key、current pointer、publication contractはJRDB正本module/configへ委譲する。

### D. Actions-Native Execution

以下はIssue / GitHub Actions経路を維持する。

- `JRDB_USER` / `JRDB_PASSWORD` 等のSecretsを使うJRDB取得・再構築
- upstream Actions artifactを正式入力としてchainする処理
- Full 2010-2025等の長時間・大容量build
- immutable freeze / publication / release等、GitHub runを不変証跡として必要とする処理
- 正式な監査run・再現性証跡としてrun ID / artifact / workflow RESULTを残す必要がある処理
- GitHub-hosted環境そのものを検証対象とする処理

Dを使う場合のみ、下記「Issue駆動Actionsのpreflight」を適用する。

### Google Drive routing — no direct Actions ↔ Drive transport

JRDBのRaw / Analysis / Fact Lite / research asset等をGoogle Driveへ保存・取得する場合も、repository rootのDrive routing decisionを優先する。

- production-standard: **GitHub source / artifact -> GPTが取得 -> GPT runtime -> connected native Google Drive connectorでupload**
- Drive入力の利用: **native Google Drive connector -> GPT runtime -> GitHub正本moduleを取得してGPT側で実行**
- prohibited: GitHub ActionsからDriveを直接read / writeする通常経路全般。旧`[gpt-gdrive-request]`だけでなく、workflow内のad-hoc `gdown` / `drive.google.com` / Google Drive API直接利用も含む。
- narrow exception: accepted RaceNote 2010–2025 Historical v0.5.2 input may use
  `tools/gpt_io/public_drive/fetch.py` with the repository-reviewed,
  SHA-256-pinned manifest `config/public_drive/racenote_historical_golden_20251228_v1.json`.
  This is unauthenticated read-only public transport only; direct URLs,
  authenticated fallback, arbitrary file IDs and Drive writes remain prohibited.
- `.github/workflows/gpt_gdrive_request_issue.yml` は運用廃止・削除済み。`tools/gpt_io/gdrive/` はcurrent operational routeではない。
- GitHub Actions artifactをDriveへ保存する場合は、GPTがGitHub connectorでartifactを取得し、native Google Drive connectorへ渡す。
- Drive transportだけを理由にIssue / Actionsを作らない。
- `GPT_GDRIVE_ACTIONS_BRIDGE_ENABLED` やService Account Secretを有効化・設定しない。
- Drive inputを必要とするE2Eがpure deterministicに実行可能ならCとしてGPTローカル実行へ寄せる。Actions-native要件が別途ある場合も、Drive搬送部分はGPT側で分離する。

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


### RaceNote day-level buildでの標準適用

D5 PASS後のfull-day production entrypointは `src/build_racenote_daily.py`。

- 既取得PACI / Analysis / RRDB / frozen rulesを用いる日次build・validation: **C**
- JRDB Secretsを使うPACI取得やformal immutable auditを同時に必要とする場合: **D**
- full-day requestを1Rずつ別Issueへ分解しない。PACI parse / Analysis open / RRDB resolve / frozen-rule loadはday request内で各1回を標準とする。
- outputは authoritative bundles + Reader Views + manifest + validation report。
- existing one-race pathはsingle-race、audit、rollback用途として保持する。
- daily builder側でHistory / Trend / P1/P2 / RRDB / Forecast意味論を再実装しない。
- D5 evidence: `docs/racenote/RACENOTE_DAILY_D5_EQUIVALENCE_20260930.md`。

### RaceNote Forecast Gen0での標準適用

新規の未使用BTDAYは v0.5.2 single-day baseline で進める。
入口は `docs/racenote/RACENOTE_V052_SINGLE_DAY_RUNBOOK_v0_1.md`、
GitHub-backed TURN 1 は
`.github/workflows/racenote_btday_v052_prepare.yml` とする。
予約row / requestの `source_mode` で分岐し、2026はPACI、
2010–2025はaccepted Historical Warehouseを使う。Historical rowへ
`paci_file_id` を捏造しない。

DAY PREP・market-blind forecast_prep・sealed v0.5.2 session・会場単位の
Decision Core保存・Freeze・Verifyまでを同じpre-result operationとして扱う。
予想の印・境界候補・理由文をスクリプトで補完しない。結果/対象日marketは
全日FreezeとVerify PASSまで開かない。

v0.4.6の `BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md` と
`racenote_btday_v046_*.yml` はhistorical reproduction用であり、
current BTDAY entrypointではない。

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

Current Analysis daily route is v1.4 native Parquet:
`.github/workflows/jrdb_post_race_parquet_refresh_issue.yml` ->
`build_jrdb_analysis_post_race_parquet_native_v1_4.py`.

The Actions request must chain from a prior successful GitHub Actions artifact
using `source_run_id`, `artifact_name` and
`expected_source_generation`. Do not pass a Google Drive file ID to the
workflow and do not add `drive.google.com`, `drive.usercontent.google.com`,
gdown, or Drive API transport to it.

Drive canonical publication is a separate GPT/native connector step:

`candidate PASS -> GPT downloads artifact -> native Drive publish -> Drive round-trip validation -> current.json promotion`.

Normal v1.4 post-race refresh must keep
`native_parquet_update=true` and `full_sqlite_materialization=false`.
The old full-SQLite post-race route is rollback/historical compatibility only.

開催後は `Analysis update -> canonical save/validation -> Fact Lite regenerate/validate/publish -> condition-summary PWA update` を一つの運用世代として扱う。Analysisだけを更新して後続PWAを旧世代に残さない。Stats Martは現行標準chainから外れており、必要時のみlegacy資産として個別に扱う。

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

## RL / RaceLift retirement rule — 2026-10-02

Normative contract:
`docs/RL_Retirement_Contract_20261002.md`

Current status:

```text
RL_RESEARCH_STATUS               = RETIRED
RL_DAILY_INDEX_GENERATION        = STOPPED
RL_INDEX_REQUIRED_BY_PRODUCTION  = FALSE
```

Missing RL / Training Edge output is a normal production state.

For ordinary work:

- do not start or continue RL / Training Edge model development;
- do not schedule or generate daily RL indices;
- do not treat missing RL output as an error;
- do not auto-run Training Research or the RL scorer to satisfy a downstream consumer;
- do not use Historical Raw fallback to recover a missing RL value;
- do not reopen HOLDOUT / OOT / calibration / runtime-freeze work without a new explicit research decision;
- preserve frozen RL assets for reproduction/audit only;
- preserve JRDB Warehouse / Index Base / record-hash compatibility as active shared infrastructure.

When working on Newspaper / RaceNote / EdgeDB / PWA, assume RL is absent unless the task explicitly concerns historical compatibility or reproduction.



## RL retirement T4 operational boundary — 2026-10-02

Do not invoke Training Edge scorers/evaluators or build Training Research during normal production. Retain their code/tests/config and immutable evidence only for explicitly requested historical reproduction or audit. RL absence is the normal production state. The path-level inventory is docs/RL_Retired_Asset_Inventory_20261002.md; shared Warehouse / Index Base / record-hash compatibility and common DuckDB/Parquet tooling remain active.


## RL retirement T5 workflow routing — 2026-10-02

Keep the five active rlt_* workflows enabled: they serve Warehouse audit/materialization and record-hash compatibility. Their historical RL-T names and issue prefixes are retained; do not treat them as RL model/scorer entrypoints. See docs/RL_Retirement_T5_Shared_Infrastructure_Audit_20261002.md.


## RL retirement final operational state — 2026-10-02

RL absence is the normal production state. Do not auto-score, auto-build Training Research, restart HOLDOUT/OOT/calibration, tune a frozen model, or fall back to Historical Raw to recover RL. Final repo-wide audit: docs/RL_Retirement_Final_Report_20261002.md (PASS). Shared JRDB Warehouse / Index Base / record-hash compatibility stays active.
