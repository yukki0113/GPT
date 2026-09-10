# 直前情報取得 GitHub Issue運用

## 目的

この文書は、直前情報取得が D. Actions-Native Execution と判定された場合の正式実行経路を定義する。

GitHubに正本moduleが存在すること自体はIssueを使う理由にしない。正本PythonをChatローカルで同一条件実行でき、必要入力を取得できる場合は C. Pure Deterministic Execution を優先する。

一方、ChatローカルのPython実行環境からBOAT RACE公式サイトへ通信できず、`fetch_boatrace_pre_race_info.py` を同一条件で再現実行できない場合は、GitHub Actions上での外部取得が必要になるため本Issue経路を使用する。

Issueを実行要求、GitHub Actionsを実行基盤、Issueコメントを制御結果、artifactを成果物返却として扱う。取得ロジック自体はGit正本の `boat-racing/src/fetch_boatrace_pre_race_info.py` をそのまま使用し、Actions専用ロジックへ分岐させない。

## GitHub作業の経路

- repository / file / commit / issue / workflow / artifact / SHA / run状態の確認は A. Read / Audit とし、ChatからGitHub read/searchで直接行う。
- source / test / docs / config / workflow等のUTF-8テキスト変更は B. Git Change とし、direct create/update/deleteを使う。Git更新だけを目的としたIssueは作らない。
- artifact回収後のJSON検査、SHA計算、差分比較などは、Actions上の監査run自体が要件でない限り C. Pure Deterministic Execution としてChatローカルで行う。
- 本文書のIssue経路はDの取得本体だけに使用する。

## 正本

Repository: `yukki0113/GPT`
Branch: `main`

使用資産:

- `boat-racing/src/fetch_boatrace_pre_race_info.py`
- `boat-racing/requirements.txt`
- `boat-racing/docs/README_直前情報取得.md`
- `boat-racing/docs/直前情報取得依頼_定型作業.txt`
- `.github/workflows/boatrace_pre_race_issue.yml`

従来の `.github/workflows/boatrace_pre_race_manual.yml` は人手での手動実行用の補助経路として残す。

## Issue発行前Preflight

IssueはD判定後にだけ作成し、発行前に次を確認する。

1. latest `main` を取得する。
2. `.github/workflows/boatrace_pre_race_issue.yml` のrequest parser / contractを確認する。
3. title prefix、request_id、必須キー `date` / `venue` / `race` / `format` と値域を確認する。
4. upstream dependencyがないことを確認し、存在しないrun ID / artifact名 / SHAを推測して付けない。
5. request JSONを機械的にserializeし、Markdown fenceや説明文を混ぜない。
6. 全項目PASS後にIssueを1回だけ発行する。

失敗時はRESULT、artifact、failed step / logを確認し、同じrequestを盲目的にrerunしない。retryが必要なら原因を修正し、必要に応じて新しいrequest_idで新規Issueを作る。

## Issue request

### タイトル

```text
[BOATRACE_PRE_RACE_REQUEST] <request_id>
```

`request_id` は `[A-Za-z0-9._-]{1,80}` を満たす一意な値とする。

例:

```text
[BOATRACE_PRE_RACE_REQUEST] 20260910-mikuni-4R-001
```

### 本文

Issue本文は raw JSON とする。

```json
{
  "date": "20260910",
  "venue": "三国",
  "race": 4,
  "format": "json"
}
```

入力:

- `date`: `YYYYMMDD` または `YYYY-MM-DD`
- `venue`: 会場名または公式会場コード
- `race`: 1〜12
- `format`: `json` または `csv`。通常は `json`

## Workflow

`.github/workflows/boatrace_pre_race_issue.yml`

Issue `opened` を契機に、タイトルが `[BOATRACE_PRE_RACE_REQUEST]` で始まる場合だけ実行する。

処理:

1. `main` をcheckout
2. Python 3.12をセットアップ
3. `boat-racing/requirements.txt` をインストール
4. Issueタイトル・本文JSONを検証
5. `resolved_request.json` を作成
6. Git正本 `fetch_boatrace_pre_race_info.py` をCLI実行
7. 取得結果を独立検証
8. `validation_report.json` を作成
9. `run_status.txt` を作成
10. artifact upload
11. `BOATRACE_PRE_RACE_RESULT` の機械可読JSONをIssueコメント
12. IssueをClose
13. taskまたはvalidation失敗時は最後にWorkflowを失敗扱い

## artifact

基本名:

```text
boatrace-pre-race-<request_id>-<run_id>
```

主な内容:

- `pre_race_result.json` または `pre_race_result.csv`
- `resolved_request.json`
- `validation_report.json`
- `run_status.txt`

日次成果物・artifact内容はGitへcommitしない。

## validation

JSON運用では少なくとも次を検査する。

- `fetch_status == success`
- `racecard_racers` が6艇
- 展示タイムが6艇
- `weather.start_exhibition` が6艇
- 各start_exhibitionに `exhibition_course` / `boat_number` / `start_exhibition_st` が存在
- 気温・水温・天候・風向・風速・波高が存在
- 対象日とRがrequestと一致
- source URLがBOAT RACE公式 `racelist` / `beforeinfo` のみ

失敗時も `failure_kind` / `failure_message`、validation、run statusをartifactとIssueコメントから確認できるようにする。

## RESULTコメント

marker:

```text
BOATRACE_PRE_RACE_RESULT
```

共通形式:

```json
{
  "request_id": "20260910-mikuni-4R-001",
  "status": "success",
  "run_id": 1234567890,
  "artifact_name": "boatrace-pre-race-20260910-mikuni-4R-001-1234567890",
  "task_exit_code": "0",
  "validation_exit_code": "0",
  "validation": {},
  "output_files": []
}
```

`status` は `success` / `partial` / `failure` を使用する。

## Chat側のD経路

直前情報取得がDと判定された場合は次の順で処理する。

1. Git mainのREADME / CONTEXT / WORKFLOW / 対象Python / Issue Workflowを確認
2. Issue発行前Preflightを完了
3. request_idを生成
4. raw JSON本文でGitHub Issueを1回だけ作成
5. IssueのRESULTコメントを確認
6. `run_id` / `artifact_name` を完全一致で取得
7. Actions artifactを回収
8. `validation_report.json` と実成果物をChatローカルで再確認
9. 成果物をユーザーへ返却

D経路ではChatから `workflow_dispatch` を直接起動することを前提としない。
