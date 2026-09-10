# JRDB Newspaper Actions request contract

この文書は **Actions-Native Execution (D) のみ** を扱います。通常のread/audit、Git更新、取得済み入力に対するNewspaper build/mergeはIssueを使いません。標準経路は `.gpt/WORKFLOW.md` を参照してください。

## 1. Standard daily operation

通常の日次Newspaper生成は次の分離を標準とします。

```text
official PACI acquisition if needed  -> D / Actions
obtained PACI + Analysis             -> C / GPT local build
Eval / RaceNote / keibailuka merge   -> C / GPT local merge
schema / SHA / day-package           -> C / GPT local validation/build
PWA source change                    -> B / direct Git commit
Pages deployment                     -> D / push-triggered Pages Actions
```

PACIが添付・Library・既存artifact等から取得済みなら、Newspaper生成のためのIssueは作りません。

## 2. JRDB official data acquisition

JRDB Secretsを使う公式取得はActions-Nativeです。

Title prefix:

```text
[JRDB_RAW_FETCH_REQUEST]
```

基本body:

```json
{
  "date": "YYYYMMDD",
  "kinds": ["PACI"]
}
```

Success marker:

```text
JRDB_RAW_FETCH_RESULT
```

Issue作成前にroot `.gpt/ISSUE_REQUEST_CONTRACTS.md` と対象workflow parserを確認し、upstream/SHA/artifact条件を満たしてから1回だけ発行します。

## 3. Legacy / explicit hosted Newspaper PoC

既存JRDB Raw fetch workflowの `newspaper_poc` blockは、GitHub-hosted環境でのreal-data PoC監査を明示的に必要とするときだけ使用できます。通常の日次生成には使いません。

```json
{
  "date": "YYYYMMDD",
  "kinds": ["PACI"],
  "newspaper_poc": {
    "venue_code": "01",
    "race_no": 11,
    "expected_paci_sha256": "<optional 64 hex>",
    "analysis_url": "<optional Google Drive URL>"
  }
}
```

Hosted PoCを使う場合は `newspaper_poc.audit_status=PASS`、target identity、chronology/duplicate、architecture boundaryを監査します。

## 4. Full-day Issue workflow

`.github/workflows/jrdb_newspaper_day_issue.yml` / `[JRDB_NEWSPAPER_DAY_REQUEST]` は、Secretを使ったPACI取得から日次artifact生成までをActions上で一括固定したい場合の **fallback / audit route** とします。

通常の日次Workでは、PACI取得後にGPTローカルで `jrdb_newspaper_day_build.py` を実行するため、このIssueは使いません。

Request body:

```json
{
  "date": "YYYYMMDD",
  "analysis_url": "<optional Google Drive URL>",
  "revision": 1
}
```

このrouteを選ぶ条件:

- Actions artifact自体を正式な監査証跡として残す必要がある
- GitHub-hosted runnerで一括再現することが要件
- Chat側で必要入力を取得できず、Actions環境での取得が必要

上記以外ではCを優先します。

## 5. Retry rule

Actions Issueが失敗した場合はfailed step / logs / latest main / upstream RESULTを確認し、原因を修正してから必要なら新requestとして再発行します。同一requestのblind rerun、推測SHA、未確認artifact名は使用しません。
