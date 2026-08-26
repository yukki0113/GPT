# RaceNote Request Issue E2E test — 2025-08-24 新潟11R

## Purpose

`src/racenote_request.py` と `[RACENOTE_REQUEST]` Issue → GitHub Actions → artifact 経路について、過去レースをGPTから1件取得する実運用相当のE2E確認を行う。

Target:
- date: 2025-08-24
- venue: 新潟
- race: 11R 新潟2歳ステークス

## Request route

```text
GPT
  -> current Analysis / matching Stats MartをDriveから解決
  -> historical Raw annual ZIPをDriveから解決
  -> [RACENOTE_REQUEST] Issue
  -> GitHub Actions
  -> Drive download
  -> racenote_request.py
  -> historical PACI-equivalent reconstruction
  -> racenote_jrdb.py
  -> Analysis / Stats Mart as-of enrichment
  -> RaceNote ZIP artifact
  -> RACENOTE_RESULT comment
  -> Issue close
```

Historical requests prefer pre-positioned Raw cache supplied from external storage. JRDB annual download is only a fallback for missing packs. This avoids requiring JRDB credentials for ordinary past-date requests when canonical Raw is already available in Drive.

## Successful run

Issue: #44

Request ID:
`chat-20260826-20250824-niigata11-test3`

GitHub Actions run:
`32925267055`

Result:
- task_exit_code: 0
- collect_exit_code: 0
- workflow conclusion: success
- artifact generated
- machine-readable result comment generated
- Issue automatically closed

## Artifact verification

Outer artifact contains:
- `RaceNote_20250824_新潟_11R.zip`
- `resolved_request.json`

RaceNote ZIP contains:
- `request_manifest.json`
- `race_bundle_20250824_新潟11R.json`

Bundle verification:
- race: 2025-08-24 新潟11R 新潟2歳ステークス
- horses: 10
- `recent_runs` counts: `[1,2,2,1,1,4,2,1,1,3]`
- `older_runs`: all 0
- latest historical run date: 2025-08-10
- `as_of_exclusive`: 2025-08-24
- frame stats: 1–8 available

Historical reconstruction manifest:
- BAC: 1
- KYI: 10
- CHA: 10
- CYB: 10
- ZED: 18
- ZKB: 18
- previous result keys: 18
- previous result years: 2025

The result agrees with the independent Raw/as-of audit for this race.

## Earlier test findings fixed during E2E

1. `gdown 6.1.0` no longer accepts the old `--fuzzy` option. Workflow was corrected to pass Drive URLs directly.
2. Repository `JRDB_USER` / `JRDB_PASSWORD` secrets were not configured. Historical requests were therefore redesigned to accept GPT-resolved Drive Raw URLs as an internal request field and use them as a pre-positioned cache. Current/future PACI fetch still requires JRDB authentication unless another authenticated execution route is added.

## Architectural conclusion

The user-facing request contract can remain stable:

```text
date
optional venue
optional race
```

Temporal routing and scope routing are independent. Backend evolution does not require changing the user/GPT contract.

Current plan:
- current/future -> PACI
- past -> Drive/Archive-prepositioned historical source, Raw fallback
- future production improvement -> RaceNote Archive backend for high-volume historical retrieval

Raw remains an audit/rebuild source rather than the intended high-volume query layer.
