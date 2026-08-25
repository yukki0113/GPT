# 直前情報取得 GitHub Issue運用

## 目的

ChatからGitHub Actionsの `workflow_dispatch` を直接起動できない場合があるため、直前情報取得の標準実行経路を GitHub Issue 起動方式へ切り替える。

Issueを実行要求、GitHub Actionsを実行基盤、Issueコメントを制御結果、artifactを成果物返却として扱う。

取得ロジック自体はGit正本の `boat-racing/src/fetch_boatrace_pre_race_info.py` をそのまま使用し、Actions専用ロジックへ分岐させない。

## 正本

Repository: `yukki0113/GPT`
Branch: `main`

使用資産:

- `boat-racing/src/fetch_boatrace_pre_race_info.py`
- `boat-racing/requirements.txt`
- `boat-racing/docs/README_直前情報取得.md`
- `boat-racing/docs/直前情報取得依頼_定型作業.txt`
- `.github/workflows/boatrace_pre_race_issue.yml`

従来の `.github/workflows/boatrace_pre_race_manual.yml` は手動実行用の補助経路として残す。

## Issue request

### タイトル

```text
[BOATRACE_PRE_RACE_REQUEST] <request_id>
```

`request_id` は `[A-Za-z0-9._-]{1,80}` を満たす一意な値とする。

例:

```text
[BOATRACE_PRE_RACE_REQUEST] 20260825-mikuni-4R-001
```

### 本文

Issue本文は raw JSON とする。

```json
{
  "date": "20260825",
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
  "request_id": "20260825-mikuni-4R-001",
  "status": "success",
  "run_id": 1234567890,
  "artifact_name": "boatrace-pre-race-20260825-mikuni-4R-001-1234567890",
  "task_exit_code": "0",
  "validation_exit_code": "0",
  "validation": {},
  "output_files": []
}
```

`status` は `success` / `partial` / `failure` を使用する。

## Chat側の標準運用

今後のChat側は原則として次の順で処理する。

1. Git mainのREADME / CONTEXT / WORKFLOW / 対象Python / Issue Workflowを確認
2. request_idを生成
3. raw JSON本文でGitHub Issueを作成
4. IssueのRESULTコメントを確認
5. `run_id` / `artifact_name` を取得
6. Actions artifactを回収
7. `validation_report.json` と実成果物を再確認
8. 成果物をユーザーへ返却

Issue経路が利用できる限り、Chatから `workflow_dispatch` を直接起動することを前提としない。
