# Boat racing Git migration status

Updated: 2026-09-13
Status: COMPLETE

## Gitへ移行済み

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

### GitHub Actions

- `.github/workflows/boatrace_racelist_manual.yml`
- `.github/workflows/boatrace_racelist_issue.yml`
- `.github/workflows/boatrace_pre_race_manual.yml`
- `.github/workflows/boatrace_pre_race_issue.yml`
- `.github/workflows/boatrace_results_manual.yml`
- `.github/workflows/boatrace_results_chat.yml`

## 移行状態

競艇取得運用に必要なPython本体、README、GPT向け運用資料、定型作業手順、ForwardTrial予想・結果取込・分析実装、Python依存関係、GitHub Actions実行経路はGitへ移行済み。

今後は `yukki0113/GPT` の `main` ブランチ配下 `boat-racing/` と `.github/workflows/` を正本として参照する。
過去の添付ZIPやWorkスレッド内の一時作業領域は、Git正本の代わりとして使用しない。

会話量上限やスレッド引越し時は `boat-racing/.gpt/HANDOFF.md` を再開入口とする。変動する日次状態や累計値を会話メモリだけで復元せず、Google Drive、ネイティブGoogle Sheets、GitHub Issue / Actionsの正本から再取得する。

作業開始時は、少なくとも以下を確認する。

1. `boat-racing/README.md`
2. `boat-racing/.gpt/CONTEXT.md`
3. `boat-racing/.gpt/HANDOFF.md`
4. `boat-racing/.gpt/WORKFLOW.md`
5. `boat-racing/.gpt/MIGRATION_STATUS.md`
6. 対象作業の `docs/` と `src/` の対応ファイル
7. D. Actions-Native Executionを使用する場合だけ対応するIssue起動Workflow

## Python依存関係

取得ツール全体では `boat-racing/requirements.txt` を使用する。
直前情報取得を単独で扱う場合は `boat-racing/requirements_直前情報取得.txt` も使用できる。

現在の取得ツールで必要な主な外部パッケージ:

- `requests`
- `beautifulsoup4`
- `lxml`

## GitHub運用経路 2026-09-10

GitHub作業は毎回、次の4系統へ分類する。

- A. Read / Audit: repository / file / commit / issue / workflow / artifact / SHA / run状態の確認。ChatからGitHub read/searchで直接実施し、Issue不要。
- B. Git Change: source / test / docs / config / workflow等のUTF-8テキスト変更。latest main、path、現内容を確認してGitHub direct create/update/deleteでremote commitを作成し、Issue不要。
- C. Pure Deterministic Execution: Git正本moduleと必要入力をChat側で取得でき、secret・特殊runner・Actions監査証跡が不要で計算量が許容範囲ならGPTローカル実行を優先する。artifact回収後のJSON/CSV検査、SHA計算、差分比較も原則C。
- D. Actions-Native Execution: Secrets、認証付き外部取得、artifact chain、長時間・大容量処理、特殊runner、immutable freeze、監査run、または正本moduleをChatローカルで同一条件実行できない場合に限定してIssue -> GitHub Actionsを使用する。

「GitHubにmoduleがある」ことだけを理由にIssue / Actionsを使わない。

## 取得系のActions-Native経路

BOAT RACE公式サイトへの取得系処理も、正本PythonをChatローカルで同一条件実行でき、必要な公式入力を取得できる場合はCを優先する。

ChatローカルのPython実行環境からBOAT RACE公式サイトへ通信できず、正本fetcherを再現できない場合はDとし、次のIssue起動Workflowを使用する。

- 出走表取得: `.github/workflows/boatrace_racelist_issue.yml`
- 直前情報取得: `.github/workflows/boatrace_pre_race_issue.yml`
- 結果取得・予想照合: `.github/workflows/boatrace_results_chat.yml`

直前情報取得のIssue prefixは `[BOATRACE_PRE_RACE_REQUEST]`。Issue本文はraw JSONとし、`date` / `venue` / `race` / `format` を対象workflow/parserと照合してから1回だけ発行する。

Issue発行前はlatest main、request contract、必須キー、upstream dependency、artifact / SHA / dates / IDs等の実値を必要範囲で完全検証する。失敗時はRESULT、artifact、failed step / logを確認し、同一requestのblind rerunを行わない。

成果物はartifactへ保存し、Issueコメントの機械可読RESULTから `status` / `run_id` / `artifact_name` / exit code / validation をChat側で取得する。処理終了後はRequest IssueをCloseする。

`workflow_dispatch` のmanual Workflowは人手での補助経路として残すが、ChatがDを選択した場合はIssue起動を優先する。

## 日次成果物と外部正本

Git対象外の日次資産は、Google Drive / Google Sheets側を正本とする。

- Google Drive `data`: Folder ID `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
  - `racecards` / `predictions` / `prediction-rationales` / `sales-selection` / `results`
- Google Drive `analysis`: Folder ID `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`
- Google Sheets `競艇note販売運用台帳`: Spreadsheet ID `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`

結果取得工程は結果CSV・取得ログの生成と監査までとし、Google Sheets台帳記帳・ForwardTrial分析更新は別工程とする。

## Git対象外

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

## 運用上の注意

- ソース参照・改修時は、まずGitの `main` 最新状態を確認する。
- 公式サイト側の構造変更により改修が必要な場合は、既存出力互換性を維持する。
- 改修時はPythonと対応READMEを同時に更新する。
- Workflow変更時も正本PythonのCLI互換性を確認する。
- Git更新のためだけにIssueを作成しない。
- IssueはD. Actions-Native Executionの実行要求に限定する。
- Issue本文をshellへ直接展開せず、JSON解析・型検証後に引数listとして実行する。
- 可能な限り実日付または保存済みfixtureで回帰確認する。
- 日次成果物、ログ、キャッシュ、台帳はcommitしない。
- 新しいスレッドで過去会話がないと再開できない情報が判明した場合は、会話メモリだけに残さず `HANDOFF.md` または対象docsへ戻す。
