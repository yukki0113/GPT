# Drive to GPT to GitHub Actions bridge

Status: implementation candidate, pending one-time secret provisioning and live E2E.
Scope: shared Data Storage fallback for local files fetched by GPT from native Google Drive.

## Architecture

1. GPT downloads PACI/Analysis ZIP or Parquet artifacts from connected Google Drive into its filesystem. Check expected file size and SHA-256 against canonical evidence when available.
2. Run scripts/drive_gpt_actions_bridge.py. It encrypts each local input with a fresh AES-256-GCM key and wraps the key using an RSA-3072 public key (OAEP-SHA256).
3. The client uploads ONLY CIPHERTEXT to GitHub Git Blobs and opens an authorized DATA_STORAGE_FALLBACK Issue with blob SHA, checksum, nonce and wrapped key metadata.
4. Existing Actions fallback retrieves the ciphertext under the repository token, decrypts only inside the ephemeral runner using the RSA private key from GitHub Actions Secret DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM, verifies checksum and size, and puts input files under /tmp/data-storage-fallback/inputs/LABEL/.
5. Existing fallback runs reviewed repository entrypoints with the normal input:LABEL placeholder and publishes output/audit artifacts. Plaintext input files are excluded from published artifacts.

GitHub repository yukki0113/GPT is PUBLIC. The Git blobs are encrypted but may persist; there is no assured deletion or expiry. No raw JRDB bytes, secret private keys, or plaintext access URLs belong in Issues, Git trees, or logs.

## One-time setup

Prerequisite: authorized GitHub Actions Secrets operator and GitHub token with Contents write and Issues write. The GPT-side runtime needs Python cryptography, but it does not need duckdb/pyarrow.

    python -m pip install 'cryptography>=42,<47'
    python tools/data-storage/scripts/drive_gpt_actions_bridge.py keygen \
      --private-key-out /secure/data-storage-bridge-private.pem \
      --public-key-out /secure/data-storage-bridge-public.pem

Set the repository Actions secret DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM to the entire private PEM (BEGIN/END lines included):

    gh secret set DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM \
      --repo yukki0113/GPT < /secure/data-storage-bridge-private.pem

Store the public PEM as a reviewed configuration accessible to GPT-side Python. Do NOT commit the private PEM. Rotate both halves together; encrypted pending jobs from an old key cannot decrypt under a replacement secret.

Python upload client requires GH_TOKEN or GITHUB_TOKEN in environment, which is NOT automatically exposed by a connected ChatGPT GitHub connector. Provide a separate authorized scoped credential to the runtime. The current Issue workflow requires the authenticated Issue author to be yukki0113; an integration bot Issue will not trigger the job.

## Reusable execution

For the 2026-10-24 data, after native Drive downloads and byte preflight:

    python tools/data-storage/scripts/drive_gpt_actions_bridge.py submit \
      --repo yukki0113/GPT \
      --public-key /secure/data-storage-bridge-public.pem \
      --request-json tools/data-storage/config/drive_gpt_actions_example.json \
      --request-id jrdb-artemis-analysis-20261024 \
      --input paci=/mnt/data/PACI261024.zip \
      --input analysis=/mnt/data/jrdb_analysis_v1_4_canonical_current.tar.xz.tar

The client returns Issue URL. Wait for Actions to complete, inspect DATA_STORAGE_FALLBACK_RESULT and download data-storage-fallback-RUN_ID. Check fallback-audit.json status PASS, staged input integrity PASS and all step exit codes zero. Do not trust an Issue-created response as execution success.

The example request expands the Analysis archive safely and queries a historical year count with canonical DuckDB. It is a TRANSPORT SMOKE, NOT an Artemis Stakes race forecast. The scientific SQL for each race must be specified in a reviewed query step.

## Contract and limits

Optional staged_inputs: an array of at most 8 encrypted input envelopes in the existing fallback Issue JSON. Each item contains label, filename, blob_sha, wrapped_key_b64, nonce_b64, plaintext_sha256, ciphertext_sha256, size_bytes. Labels cannot collide with input_artifacts or public_drive_inputs. The generic input:LABEL placeholder resolves a staged input or downloaded Actions artifact.

The client limits input size to 32 MiB per file and uses only validated local regular files with safe basenames. Inputs over the limit must use a separate reviewed artifact route. It does not pass authenticated private Drive links to GitHub. The stage is not transactional: an API failure may leave orphaned ENCRYPTED Git blobs; no Issue is created when upload fails.

Decryption fails closed if the secret is missing or incorrect, blob integrity mismatches, size/hash mismatches, or labels/paths fail validation. The GitHub public repository ciphertext is NOT guaranteed to expire. Do not stage content whose licensing or security terms prohibit encrypted public-repo object storage.

Use only the existing Python data_storage query engine for Parquet; do not reimplement DuckDB or relax as-of exclusions. Native Drive owns the original download, and Actions never accesses private Drive or writes to it.

## Testing and verification

    PYTHONPATH=tools/data-storage python -m pytest \
      tools/data-storage/tests/test_fallback_runner.py \
      tools/data-storage/tests/test_drive_gpt_actions_bridge.py -q

Offline tests cover encryption/decryption, invalid metadata, corruption rejection, absent secret, path safety and request labels. A production-ready claim additionally requires a real staged upload, owner-created Issue, Actions secret, completed artifact and verified SQL output.
