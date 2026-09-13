# Boat racing Git migration status

Updated: 2026-09-13
Status: COMPLETE

## 1. Gitへ移行済みの運用正本

### Project / GPT operation

- `boat-racing/README.md`
- `boat-racing/.gpt/CONTEXT.md`
- `boat-racing/.gpt/HANDOFF.md`
- `boat-racing/.gpt/WORKFLOW.md`
- `boat-racing/.gpt/MIGRATION_STATUS.md`
- `boat-racing/requirements.txt`
- `boat-racing/requirements_直前情報取得.txt`

### Core docs

- `boat-racing/docs/README_出走表取得.md`
- `boat-racing/docs/README_直前情報取得.md`
- `boat-racing/docs/README_公式結果取得.md`
- `boat-racing/docs/出走表取得依頼_定型作業.txt`
- `boat-racing/docs/直前情報取得依頼_定型作業.txt`
- `boat-racing/docs/直前情報取得_GitHubActions運用.md`
- `boat-racing/docs/直前情報取得_GitHubIssue運用.md`
- `boat-racing/docs/結果照合取得依頼_定型作業.txt`
- `boat-racing/docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`
- `boat-racing/docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
- `boat-racing/docs/競艇note販売運用台帳_日次結果取込再発防止手順.md`
- `boat-racing/docs/競艇note販売運用台帳_ForwardTrial専用分析台帳.md`
- `boat-racing/docs/ForwardTrial_Chat日次台帳記帳運用.md`
- `boat-racing/docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md`
- `boat-racing/docs/司令塔Chat_台帳正本運用連携.txt`
- `boat-racing/docs/競艇_会場特性マスタ_Ver0.1.md`
- `boat-racing/docs/競艇_会場特性×Ver1.2.1_336R検証_Ver0.1.md`

### Python modules

- `boat-racing/src/fetch_boatrace_racelist_with_meta.py`
- `boat-racing/src/fetch_boatrace_racelist.py`
- `boat-racing/src/fetch_boatrace_event_meta.py`
- `boat-racing/src/enrich_boatrace_racelist_metadata.py`
- `boat-racing/src/fetch_boatrace_pre_race_info.py`
- `boat-racing/src/forward_trial_predict.py`
- `boat-racing/src/fetch_boatrace_results.py`
- `boat-racing/src/ledger_daily_result_import.py`
- `boat-racing/src/forward_trial_analysis_import.py`
- `boat-racing/src/forward_trial_chat_ledger.py`

### GitHub Actions — 現役取得経路

- `.github/workflows/boatrace_racelist_manual.yml`
- `.github/workflows/boatrace_racelist_issue.yml`
- `.github/workflows/boatrace_pre_race_manual.yml`
- `.github/workflows/boatrace_pre_race_issue.yml`
- `.github/workflows/boatrace_results_manual.yml`
- `.github/workflows/boatrace_results_chat.yml`

## 2. 廃止済みの台帳記帳経路

Googleサービスアカウント / `GPT_GDRIVE_SERVICE_ACCOUNT_JSON` を使ってGitHub ActionsからGoogle Drive / Sheetsへ書き込む台帳記帳経路は廃止済み。

以下を現行正本として扱わない。

- 旧 `run_forward_trial_chat_import.py`
- 旧 `boatrace_ledger_import_issue.yml`
- `[BOATRACE_LEDGER_IMPORT]` Issueを使う日次台帳記帳
- 旧Issue RESULT / artifactを完了判定の必須条件とする運用

日次台帳記帳の現行標準は、Work / 接続済みGoogle Drive・Google Sheetsと、Git正本の `forward_trial_analysis_import.py` / `forward_trial_chat_ledger.py` を組み合わせる直結経路である。

## 3. 移行状態

競艇取得・予想・結果・台帳・分析・司令室運用に必要なPython本体、README、GPT向け運用資料、定型作業手順、ForwardTrial実装、Python依存関係、必要な取得系GitHub ActionsはGitへ移行済み。

今後は `yukki0113/GPT` の `main` 配下 `boat-racing/` と、必要な取得系 `.github/workflows/` を正本として参照する。

過去の添付ZIP、Workスレッド内の一時作業領域、会話メモリだけをGit正本の代わりに使用しない。

## 4. スレッド引越し

会話量上限やスレッド移動時は `boat-racing/.gpt/HANDOFF.md` を再開入口とする。

作業開始時は原則として以下を確認する。

1. latest `main`
2. `boat-racing/README.md`
3. `boat-racing/.gpt/CONTEXT.md`
4. `boat-racing/.gpt/HANDOFF.md`
5. `boat-racing/.gpt/WORKFLOW.md`
6. 対象作業の `docs/` / `src/`
7. D. Actions-Native Executionを使用する場合だけ対象workflow

司令室・会場選別・仕様研究では `ForwardTrial_司令室運用・会場選別・Shadow検証.md` も読む。

変動する日次状態や累計値はGit文書へ固定せず、Google Drive / Google Sheets / 必要な場合のみGitHub Actionsの正本から再取得する。

## 5. Python依存関係

取得ツール全体では `boat-racing/requirements.txt` を使用する。
直前情報取得を単独で扱う場合は `boat-racing/requirements_直前情報取得.txt` も使用できる。

主な外部パッケージ:

- `requests`
- `beautifulsoup4`
- `lxml`

## 6. GitHub運用経路

2026-09-10以降、GitHub作業は毎回次の4系統へ分類する。

- A. Read / Audit
- B. Git Change
- C. Pure Deterministic Execution
- D. Actions-Native Execution

Read/AuditとGitテキスト変更のためだけにIssueを作らない。

BOAT RACE公式サイトへの取得系処理は、正本PythonをChatローカルで同一条件実行できる場合はCを優先し、不可能な場合にのみDを使う。

現役D経路:

- 出走表取得: `.github/workflows/boatrace_racelist_issue.yml`
- 直前情報取得: `.github/workflows/boatrace_pre_race_issue.yml`
- 結果取得・予想照合: `.github/workflows/boatrace_results_chat.yml`

Issue発行前はlatest main、request contract、workflow/parser、必須キー、upstream実値を検証し、失敗時にblind rerunしない。

## 7. 日次成果物と外部正本

Git対象外の日次資産はGoogle Drive / Google Sheetsを正本とする。

- Google Drive `data`: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
  - `racecards` / `predictions` / `prediction-rationales` / `sales-selection` / `results`
- Google Drive `analysis`: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`
- Google Sheets `競艇note販売運用台帳`: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`

結果取得工程は結果CSV・取得ログの生成と監査までとし、Google Sheets台帳記帳・ForwardTrial分析更新は別工程とする。

台帳記帳はstable-key upsert + Atomic Aggregate Set全再生成 + `FT2_集計監査` read-backを1論理作業として完結させる。

## 8. Git対象外

以下は引き続きGit管理対象外とする。

- 日次CSV / JSON
- HTMLキャッシュ
- 実行ログ
- Actionsの日次artifact内容
- `resolved_request.json`
- `validation_report.json`
- `run_status.txt`
- Excel運用台帳
- 予想・結果の運用成果物

これらはGit正本のソース・仕様の代わりとして参照しない。

## 9. 継続保守

- ソース参照・改修時は最新 `main` を確認する。
- 公式サイト変更時も既存出力互換性を維持する。
- Python改修時は対応README / docs / testsへの影響を確認する。
- workflow変更時は正本PythonのCLI互換性を確認する。
- 可能な限り実日付または保存済みfixtureで回帰確認する。
- 日次成果物、ログ、キャッシュ、台帳はcommitしない。
- 新しいスレッドで過去会話がないと再開できない情報が判明した場合は、会話メモリだけに残さず `HANDOFF.md` または対象docsへ戻す。
