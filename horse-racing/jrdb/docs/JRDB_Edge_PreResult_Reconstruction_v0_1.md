# JRDB Edge Pre-Result Reconstruction v0.1

Status: **BACKTEST SUPPORT / RESULT-FREE MATCHING ONLY**
Established: 2026-09-09

## Purpose

Historical 2026+ RaceNote blind tests sometimes need Edge matching after the race date has passed, while the prediction freeze must still be made before HJC/SED/result acquisition.

`TRUE_FORWARD` cannot be reconstructed after post time, and `RECONSTRUCTED_BACKFILL` acquires SED. Therefore this route exists only to reproduce the **pre-result matching stage** with the canonical EdgeDB runner.

It does not settle races and does not claim TRUE_FORWARD status.

## Issue contract

Title prefix:

```text
[JRDB_EDGE_PRERESULT_RECONSTRUCT] <request_id>
```

Workflow:

```text
.github/workflows/jrdb_edge_preresult_reconstruct_issue.yml
```

Required JSON body:

- `dates`: sorted `YYYYMMDD` list
- `analysis_url`: leakage-safe Analysis Lite Drive URL
- `analysis_sha256`: exact uncompressed Analysis SQLite SHA-256
- `registry_run_id`: successful published Registry run ID
- `registry_artifact_name`: exact Registry artifact name
- `registry_sha256`: exact `edge_registry_active.jsonl` SHA-256
- `sources`: object keyed exactly by dates; each value requires `paci_sha256`

No SED/HJC/result/settlement input is accepted.

## Execution

For each date:

1. fetch exact PACI and verify SHA-256;
2. download and verify the exact published ACTIVE Registry;
3. download and verify Analysis Lite;
4. invoke the canonical `src/run_jrdb_edge_match_current.py` with `ACTIVE` only;
5. preserve `edge_matches.jsonl`, `current_facts.jsonl`, exact PACI and hashes.

Output mode:

```text
evaluation_mode = PRE_RESULT_RECONSTRUCTION
result_data_used = false
```

Success marker:

```text
JRDB_EDGE_PRERESULT_RECONSTRUCT_RESULT
```

This is acceptable as a prediction-freeze input for historical blind tests because it reconstructs only information available before the target race. It is not part of the TRUE_FORWARD performance ledger.

## Retry

Root `.gpt/ISSUE_REQUEST_CONTRACTS.md` applies. Do not blindly rerun a failed request; inspect the failed step and rebuild from current main/upstream RESULT. Use a new request_id for retries.
