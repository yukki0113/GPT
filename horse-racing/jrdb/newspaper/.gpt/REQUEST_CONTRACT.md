# JRDB Newspaper Issue request contract

## Current real-data PoC entrypoint

Newspaperの実データPoCは、既存のJRDB Raw fetch Issue経路へ `newspaper_poc` を付加して実行する。

Title prefix:

```text
[JRDB_RAW_FETCH_REQUEST]
```

Body is raw JSON.

Required base fields:

```json
{
  "date": "YYYYMMDD",
  "kinds": ["PACI"]
}
```

Optional Newspaper PoC block:

```json
{
  "newspaper_poc": {
    "venue_code": "01",
    "race_no": 11,
    "expected_paci_sha256": "<optional 64 hex>",
    "analysis_url": "<optional Google Drive URL>"
  }
}
```

Constraints:

- `newspaper_poc` requires `PACI` in `kinds`.
- `venue_code`: `01..10`.
- `race_no`: integer `1..12`.
- `expected_paci_sha256`: optional. Supplied when a known PACI snapshot is being reproduced; mismatch fails closed.
- `analysis_url`: optional Google Drive URL. When supplied, the workflow downloads and validates SQLite, and the builder may supplement detailed PACI history to a maximum of 8 runs with `compact_older_history` rows.
- Analysis supplement still obeys Newspaper as-of policy and only selects rows older than the oldest already-resolved detailed run.

Success marker:

```text
JRDB_RAW_FETCH_RESULT
```

Success requires top-level `status=success`. When `newspaper_poc` is requested, additionally require:

- `newspaper_poc.audit_status=PASS`
- exact target race identity
- `chronology.violations=0`
- `chronology.duplicate_history_identities=0`
- `architecture.forbidden_racenote_imports=[]`

Failure marker is the workflow failure comment containing the Actions run URL. Retry follows root `.gpt/ISSUE_REQUEST_CONTRACTS.md`: inspect the failed step first, rebuild the request from latest `main`, and do not blindly rerun an unchanged failed request.
