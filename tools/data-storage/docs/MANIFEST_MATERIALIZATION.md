# Manifest-driven immutable asset materialization

`data_storage materialize-manifest` is the shared acquisition layer for immutable, content-addressed datasets whose canonical manifest records `relative_path`, `sha256`, and `size_bytes`.

## Standard contract

1. Read the accepted/current manifest.
2. Use manifest folder references or explicit source indexes only to discover file IDs/URLs.
3. Resolve each manifest asset uniquely by relative path.
4. Download each asset individually.
5. Require exact byte size and SHA-256.
6. Rebuild the manifest relative-path tree locally.
7. Emit a machine-readable audit and fail closed on missing, ambiguous, or mismatched assets.

`gdown --folder` bulk download is not a canonical materialization method. `gdown --json` is used only for recursive public-folder discovery; the actual immutable objects are fetched individually.

## Google Drive example

    PYTHONPATH=tools/data-storage \
      python -m data_storage materialize-manifest \
      --manifest /tmp/warehouse/manifest.json \
      --output-root /tmp/warehouse/materialized \
      --cache-dir /tmp/warehouse/cache \
      --audit /tmp/warehouse/materialization_audit.json

If the manifest has a `families` array with `family`, `staging_folder_id`, and `asset_count`, those folder references are used automatically. Additional folders can be supplied with repeated `--folder LABEL=FOLDER_ID`.

Use repeated `--folder-label LABEL` to materialize only selected source folders while still validating each selected folder's declared Parquet asset count.

## Download backends

`--backend auto` first tries the public Google Drive user-content endpoint and then falls back to individual `gdown` download by file ID. Every backend is accepted only when size and SHA-256 match the manifest. `direct` and `gdown` can be selected explicitly for diagnostics.

## Cache

`--cache-dir` stores verified objects by SHA-256. A cached object is reused only after size and SHA-256 are rechecked. A Drive file ID or existing local path is never trusted without content verification.

## Operational rules

- Canonical source is the accepted manifest, not the folder layout.
- Never silently fall back to a different asset.
- Never regenerate an immutable asset merely because acquisition failed.
- Missing assets, ambiguous path resolution, size mismatch, and SHA mismatch are hard failures.
- Consumer-specific code receives the locally reconstructed tree and must not implement its own Drive folder download loop.
- A genuinely missing immutable object is a recovery incident; restore identical bytes from the original artifact/evidence source and rerun the same materializer.
