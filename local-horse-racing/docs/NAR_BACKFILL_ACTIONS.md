# NAR historical monthly backfill (Actions-native)

## Why this uses Actions

Long multi-month retrieval from the external NAR download endpoint is treated as **D. Actions-Native Execution** under the repository-wide GitHub operation policy. The workflow preserves a run ID, artifact and manifest for later audit and Drive intake.

## Issue contract

Title prefix:

```text
[NAR_BACKFILL_REQUEST]
```

Body:

```text
request_id: <unique id>
kind: race|odds
start_ym: YYYY-MM
end_ym: YYYY-MM
delay_seconds: <float, default 1.0, minimum 0.5>
```

Required fields are `request_id`, `kind`, `start_ym` and `end_ym`.

## Artifact contract

The workflow uploads one artifact named:

```text
nar-<kind>-<start_ym>-<end_ym>-<request_id>
```

Contents:

```text
raw/                 # original ZIP responses, unchanged
audit/manifest.json  # per-month SHA-256, size, validation and download result
run.log
```

Artifact retention is 7 days.

## Success result

The Issue receives `NAR_BACKFILL_RESULT` followed by JSON containing at least:

- `status`
- `request_id`
- `kind`
- `start_ym`
- `end_ym`
- `requested_months`
- `successful_months`
- `download_failures`
- `validation_warnings`
- `total_bytes`
- `run_id`
- `artifact_name`
- `artifact_retention_days`
- `source_commit`

`success` means every requested month produced a readable ZIP and passed the current strict schema guard.
`success_with_validation_warnings` means every requested month produced a readable ZIP, but one or more historical files differed from the current strict schema guard. Raw ZIPs are still preserved for audit.
`partial_failure` means at least one requested month could not be acquired as a readable ZIP.

The workflow closes the Issue only for the two success states. Partial failures remain open for diagnosis.

## Drive intake

This workflow does **not** write to Google Drive. After the run is audited, accepted raw race ZIPs are stored under `/GPT/NAR/00_raw/race/` and accepted raw odds ZIPs under `/GPT/NAR/00_raw/odds/`. The artifact manifest is the intake audit source.
