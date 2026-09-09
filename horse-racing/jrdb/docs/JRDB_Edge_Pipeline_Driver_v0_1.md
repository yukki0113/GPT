# JRDB Edge Pipeline Driver v0.1

Status: **IMPLEMENTED FOR PHASE1 SHADOW PIPELINE**  
Date: 2026-09-09

## Purpose

`src/run_jrdb_edge_registry_pipeline.py` is the thin orchestration layer for the JRDB Edge Registry build.
It does **not** reimplement Feature Mart, Discovery, temporal validation, statistical guard, reporting, or publication-manifest domain logic.
Those remain owned by the existing CLI modules.

The driver owns only:

- request validation;
- deterministic stage sequencing;
- fail-fast stage stop;
- `failure_class` / `failed_step` / `retryable` assignment;
- final machine-readable `workflow_result.json`;
- invocation of the fail-closed publication manifest builder.

## Stage order

```text
fetch_raw
→ index_build
→ index_audit
→ feature_mart
→ discovery
→ registry
→ statistical_guard
→ summary
→ publication_manifest
```

`--skip-fetch` is available for controlled runs where the Raw root is already populated.
The driver does not silently continue after a non-zero stage exit.

## Request contract

Required CLI identity:

```text
request_id
from_year / to_year        # 2010..2025
registry_version
issue_number
run_id
head_sha                   # 40-hex Git SHA
template_version           # optional on CLI; loaded from candidate-template config if omitted
work_dir
```

Archive hashing remains opt-in with `--hash-archives`, matching the existing V2 workflow default.

## Failure taxonomy

| Stage/type | failure_class | retryable |
| --- | --- | --- |
| request validation | `REQUEST_INVALID` | false |
| JRDB Raw fetch | `EXTERNAL_TRANSIENT` | true |
| index/feature/discovery/registry/summary execution | `IMPLEMENTATION_ERROR` | false |
| index audit/statistical guard/publication manifest validation | `DOMAIN_VALIDATION_FAILED` | false |

This taxonomy is intentionally coarse in v0.1. The RESULT preserves the concrete `failed_step`, exit code and error code so a later workflow layer can refine external/auth failures without changing Edge statistical semantics.

## RESULT

The driver writes:

```text
<work_dir>/report/workflow_result.json
```

with at least:

```text
schema_version
status
request
artifact_name
exit_codes
failed_step
failure_class
error_code
retryable
message
publication_manifest
```

Success requires every stage to exit zero **and** `out/manifest.json` to exist.
A successful manifest subprocess with a missing output file is converted to `IMPLEMENTATION_ERROR / MANIFEST_OUTPUT_MISSING`.

## Publication

The last stage invokes `build_jrdb_edge_publication_manifest.py` against `out/`.
The template version is sourced from `config/jrdb_edge_candidate_templates_v0_1.json` unless explicitly supplied.
This connects the already-frozen publication manifest contract to the pipeline driver without duplicating manifest validation logic.

## Tests

`tests/test_run_jrdb_edge_registry_pipeline.py` covers five driver-level contracts:

1. invalid request rejection before stage execution;
2. success path and exact stage order through manifest;
3. implementation failure stops downstream stages;
4. statistical-guard failure is fail-closed domain validation;
5. fetch failure is classified retryable external transient.

Workflow YAML should remain a transport shell: parse GitHub event context, run regression tests, invoke this driver, upload `out/` + `report/`, comment RESULT, and close only on `status=success`.
