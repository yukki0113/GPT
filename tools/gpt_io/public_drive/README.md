# Public Drive Read-Only Transport v1

This is an **unauthenticated read-only download** adapter, not a Drive API client.
Only repository-reviewed public file IDs in a pinned manifest are eligible.
No upload, edit, sharing, permission management, service-account credential, or OAuth.

## Usage

```bash
python -m pip install gdown
python tools/gpt_io/public_drive/fetch.py \
  --manifest path/to/reviewed_manifest.json \
  --output-root /tmp/materialized \
  --receipt /tmp/fetch_receipt.json
```

Manifest (the SHA below is illustrative, not a valid production artifact):

```json
{
  "schema_version": 1,
  "transport": "public_google_drive",
  "artifacts": [{
    "artifact_id": "example",
    "file_id": "YOUR_PUBLIC_FILE_ID",
    "destination": "raw/BAC/BAC_2025.zip",
    "expected_name": "BAC_2025.zip",
    "expected_size": 12345,
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }]
}
```

`expected_size` is optional; SHA-256 is **mandatory**. Every destination is relative to
`--output-root`; symlink escapes and overwrites of mismatched files are rejected.
The helper downloads to a temporary local file, verifies the content, then renames it.
A local verified file may be reused. It does **not** verify public sharing permissions
via authenticated Drive API; unauthenticated retrieval plus pinned hash is the gate.

Only `gdown.download(id=...)` is used; folder discovery and recursive downloads
are out of scope. Do not pass secrets, private asset IDs, or cookie files to the helper.
Review file IDs and public sharing status before committing a manifest. An artifact
being public also means anyone with its ID can retrieve it; do not expose sensitive data.

Transport does not determine A/B/C/D execution routing. Legacy authenticated
`tools/gpt_io/gdrive/` remains discontinued for Actions. See
`tools/gpt_io/DRIVE_ROUTING_DECISION_v0_2.md`.
