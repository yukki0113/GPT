# Dynamic Drive manifests for Data Storage

Status: implementation v1 — tests and live Actions acceptance must be checked before declaring production use.

## Purpose

Run daily updates through the canonical Data Storage fallback without:
- daily Git commits of changed source file IDs or checksums;
- uploading PACI/Parquet bytes to public GitHub Issues or Git blobs;
- generating a separate RSA key for the normal link-shared Drive route;
- rewriting DuckDB SQL.

Immutable sources remain on existing public_drive_inputs. Dynamic sources use
dynamic_public_drive_inputs in the **same** [DATA_STORAGE_FALLBACK] Issue.

## Source registry / GPT orchestration

Stable registry: tools/data-storage/config/drive_source_registry.json.
It defines:
- jrdb.paci.daily: registered PACI folder, exact PACIYYMMDD.zip for date YYYY-MM-DD.
- jrdb.analysis.current: registered Analysis folder, exact CURRENT archive filename.

The registry NEVER contains the daily source file ID. Each GPT run:

1. Uses the **connected Google Drive** native connector to list only the configured folders.
2. Selects the unique file with exact expected filename and matching parent.
3. Saves connector metadata as a before snapshot: id, name/title, size, parent_ids,
   modified_time, mime_type, optional revision/version.
4. Uses native Drive fetch(download_raw_file=true) to materialize the original bytes
   locally; records its actual local path. Never use a markdown attachment filename
   as an assumed local path.
5. Reads metadata once more, before the Issue is opened.
6. Assembles a local JSON object of connector observations, mapped by logical source
   names (see below). For an update during the snapshot phase, rediscover/re-download
   ONCE; if still unstable, stop with SOURCE_CHANGED.
7. Runs the stdlib-only builder to verify the exact file, bytes, size and metadata,
   and to generate one request JSON.
8. Calls the connected GitHub create_issue action with the request JSON as body,
   and title starting [DATA_STORAGE_FALLBACK]. This avoids requiring GH_TOKEN in
   the GPT container. The Issue MUST be created by the authorized yukki0113 identity.
9. Watches the resulting Actions job, obtains the audit and output artifact, and
   continues the user's original analysis, including specific race SQL.
   
The builder does not itself call Drive or GitHub: authentication stays within the
native connectors. A local file alone never proves the correct Drive revision;
both metadata observations are mandatory.

## GPT-side observation JSON

    {
      "sources": {
        "jrdb.paci.daily": {
          "candidates": [
            {
              "id": "<drive_file_id>",
              "name": "PACI261024.zip",
              "size": "489353",
              "parent_ids": ["<registered_paci_folder_id>"],
              "modified_time": "<actual_drive_timestamp>",
              "mime_type": "application/zip"
            }
          ],
          "metadata_after": {
            "id": "<same_id>", "name": "PACI261024.zip",
            "size": "489353", "parent_ids": ["<same_folder_id>"],
            "modified_time": "<same_timestamp>", "mime_type": "application/zip"
          },
          "download_path": "/mnt/data/PACI261024.zip"
        },
        "jrdb.analysis.current": {
          "candidates": [{"id": "<actual_id>", "name": "jrdb_analysis_v1_4_canonical_current.tar.xz",
                          "size": "<actual_size>", "parent_ids": ["<actual_folder>"],
                          "modified_time": "<actual_timestamp>"}],
          "metadata_after": {"id": "<actual_id>", "name": "jrdb_analysis_v1_4_canonical_current.tar.xz",
                             "size": "<actual_size>", "parent_ids": ["<actual_folder>"],
                             "modified_time": "<actual_timestamp>"},
          "download_path": "/mnt/data/<connector-materialized-basename>"
        }
      }
    }

Example command (after the connector creates snapshot.json and files):

    python tools/data-storage/scripts/build_dynamic_drive_request.py \
      --registry tools/data-storage/config/drive_source_registry.json \
      --snapshots /mnt/data/source_snapshot.json \
      --template tools/data-storage/config/dynamic_drive_analysis_query_template.json \
      --date 2026-10-24 \
      --output /mnt/data/drive_request_20261024.json

The output contains dynamic_public_drive_inputs, source_fingerprints and
date-scoped request_id. The sample SQL intentionally performs a historical-year
count only: actual predictions require an appropriate reviewed SQL step.

## Fallback contract (compatible with prior workflows)

New optional request field: dynamic_public_drive_inputs. Up to 8 groups, 32 files
in total and cumulative expected size <= 1 GiB. Schema for each group:

    {
      "label": "paci",
      "artifacts": [{
        "artifact_id": "paci_20261024",
        "file_id": "<actual_id>",
        "destination": "PACI261024.zip",
        "expected_name": "PACI261024.zip",
        "expected_size": 489353,
        "sha256": "<actual_verified_64_hex_sha256>"
      }]
    }

Required fields are exact. Unknown fields, path traversal, duplicate IDs, duplicate
labels across fixed/dynamic/artifact/encrypted inputs, zero sizes and non-hex hashes
are rejected before any transfer. Existing {public_drive:LABEL} placeholders apply
to BOTH fixed and dynamic sources. No shell entrypoint is introduced.

At Actions execution, the runner serializes each inline group as a temporary
schema_version=1, transport=public_google_drive JSON manifest and calls the
UNCHANGED tools/gpt_io/public_drive/fetch.py. This validates anonymous download,
content size and SHA. The same Data Storage DuckDB entrypoints run afterward.
Only receipts, manifests' provenance hashes, execution audits and query results
are published as Actions artifacts, not the source PACI/Parquet bytes.

## Failure modes

- SOURCE_NOT_FOUND: no exact named file in registered Drive folder.
- SOURCE_AMBIGUOUS: multiple matches; never select arbitrarily.
- SOURCE_CHANGED: before/after metadata or materialized byte size differs.
- INVALID_MANIFEST: unexpected/missing fields, duplicate source, untrusted path,
  invalid SHA or exceeded limits.
- PUBLIC_FETCH_FAILED: anonymous download/verification failed in Actions.
  The canonical fetch helper rejects SHA mismatches; no stale-file substitute.
- STEP_FAILED: canonical query did not complete; do not invent results.

No Drive permission changes are made or requested as part of this contract.
The user's established folder-wide link-sharing policy remains unchanged.

## Acceptance

- Offline: pytest tests/test_dynamic_public_drive_inputs.py and
  tests/test_build_dynamic_drive_request.py.
- Compatibility: existing static, Actions artifact and optional encrypted staged
  input tests remain green.
- E2E: owner-created Issue with real file IDs and actual SHA-256, Actions source
  checksummed PASS, DuckDB query output artifact obtained and inspected.
- Subsequent daily date change requires only connector discovery + one Issue
  (no daily Git commits or dedicated encryption key).
