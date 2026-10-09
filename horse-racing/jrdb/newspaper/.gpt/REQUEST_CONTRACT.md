# JRDB Newspaper Actions request contract

この文書は **Actions-Native Execution (D) のみ** を扱います。通常のread/audit、Git更新、取得済み入力に対するNewspaper build/mergeはIssueを使いません。標準経路は `.gpt/WORKFLOW.md` を参照してください。

## 1. Standard daily operation

2026-10-09以降、**公開PWAまで更新する日次Newspaper運用**では、既存の正式workflowを優先します。PACI取得済みでも、canonical Analysis / STANDARD EdgeDB / EdgeDB v0.5 / day artifactを同一監査chainで固定する必要があるためです。

```text
official PACI acquisition if needed
  -> JRDB Raw Fetch / Actions
verified PACI artifact
  -> JRDB Newspaper Day Build via Issue
  -> canonical Analysis resolve
  -> STANDARD EdgeDB
  -> EdgeDB v0.5 addon
  -> audited day artifact
external late addons / deterministic checks
  -> existing canonical merge modules
Drive canonical + publish/current.json
  -> JRDB Newspaper Current Publish
  -> JRDB PWA Pages
  -> public verification
```

C / Pure Deterministic Executionは、取得済み入力に対する単体build・merge・診断・回帰確認には引き続き利用できます。ただし、正式日次PWA公開で既存Actions artifact chainが正本になっている工程を、Chat側の独自Pythonへ置き換えません。

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

## 4. Full-day daily Newspaper workflow

正本workflow:

```text
.github/workflows/jrdb_newspaper_day_issue.yml
workflow name: JRDB Newspaper Day Build via Issue
title prefix: [JRDB_NEWSPAPER_DAY_REQUEST]
```

このworkflowは、既に取得済みのJRDB Raw/PACI artifactを入力に、Base生成からcanonical Analysis、STANDARD EdgeDB、EdgeDB v0.5 addon、day artifact出力までを一括で監査します。

Request bodyの現行contract:

```json
{
  "date": "YYYYMMDD",
  "revision": 1,
  "raw_run_id": 123456789,
  "artifact_name": "jrdb-raw-YYYYMMDD",
  "analysis_bundle_drive_file_id": "<canonical Analysis bundle Drive file id>",
  "analysis_generation_id": "<canonical generation id>",
  "analysis_manifest_sha256": "<64 lowercase hex>"
}
```

必須identity:

- `date`: 対象日 `YYYYMMDD`
- `revision`: integer >= 1
- `raw_run_id`: 成功済みJRDB Raw Fetch run
- `artifact_name`: 必ず `jrdb-raw-YYYYMMDD`
- `analysis_bundle_drive_file_id`
- `analysis_generation_id`
- `analysis_manifest_sha256`

Analysis 3項目が欠けるとBaseは作れてもcanonical Analysisを解決できず、Edge系が正常生成されません。日次PWA公開では、原則として3項目を事前解決してからrequestを発行します。

workflow内の正規順序:

```text
PACI artifact verify
-> Newspaper Base / history
-> canonical Analysis bundle download + generation/SHA verify
-> jrdb_edgedb_query.py --profile STANDARD
-> Edge exact merge
-> EdgeDB v0.5 addon
-> audited day artifact
```

EdgeDB v0.5は既存frozen cohort / matcher / addon moduleを使用します。未取得featureを独自推測で補いません。

Success marker:

```text
JRDB_NEWSPAPER_DAY_RESULT
```

Success後はartifactの `audit.json` / `manifest.json` を確認し、少なくともrace count、venue codes、history coverage、completeness、source status、Edge v0.5 join状態を監査します。

## 5. Retry rule

Actions Issueが失敗した場合はfailed step / logs / latest main / upstream RESULTを確認し、原因を修正してから必要なら新requestとして再発行します。同一requestのblind rerun、推測SHA、未確認artifact名は使用しません。
