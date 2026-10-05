# Codex Local-First -> Actions Fallback Contract

Status: ACTIVE  
Scope: repository-wide Parquet / DuckDB deterministic execution  
Canonical tool: `tools/data-storage/`

## Purpose

Codex, ChatGPT, Work, and project-specific agents must not reimplement Parquet/DuckDB logic merely because their current managed runtime cannot import `duckdb` or `pyarrow`.

The standard route is:

```text
Parquet / DuckDB task
  -> local repository data-storage preflight
  -> local execution when dependencies are usable
  -> one documented repair attempt when dependencies are missing
  -> if repair is blocked by the managed runtime/network policy:
       GitHub Actions data-storage fallback
  -> inspect RESULT + artifact
  -> continue research / implementation from the canonical result
```

A managed-runtime package restriction is an **execution-route constraint**, not permission to silently replace the scientific implementation.

## 1. Local-first preflight

From repository root:

```bash
if [ ! -x .venv-data-storage/bin/python ]; then
  python -m venv .venv-data-storage
fi

PYTHONPATH=tools/data-storage \
  .venv-data-storage/bin/python -m data_storage check-deps
```

If `check-deps` reports `DEPENDENCY_MISSING`, make one normal repository repair attempt:

```bash
.venv-data-storage/bin/python -m pip install -r tools/data-storage/requirements.txt

PYTHONPATH=tools/data-storage \
  .venv-data-storage/bin/python -m data_storage check-deps
```

If the repair succeeds, continue locally.

If dependency installation itself is blocked by the managed environment, proxy, or network policy, do **not**:

- declare Parquet/DuckDB unsupported by the repository;
- rewrite DuckDB SQL in PyArrow/pandas merely to bypass the environment;
- vendor ad-hoc wheels into project directories;
- change scientific thresholds or semantics;
- repeatedly retry the same blocked package download.

Use the Actions fallback below.

## 2. When Actions fallback is allowed

Use the fallback when all of the following are true:

- the operation is deterministic;
- the canonical implementation already exists in the repository or is part of the reviewed change;
- the local managed runtime cannot satisfy the pinned data-storage dependencies;
- required inputs are available from the checkout and/or immutable GitHub Actions artifacts;
- no Google Drive transport is required inside Actions;
- the task does not require arbitrary interactive shell work.

If an input exists only as an ephemeral local file, first resolve a reproducible source. Do not upload opaque local state just to make the fallback run.

## 3. Fallback workflow

Workflow:

`.github/workflows/data_storage_fallback_issue.yml`

Trigger by opening an Issue whose title begins:

```text
[DATA_STORAGE_FALLBACK]
```

The Issue body must be a single JSON object.

The workflow:

1. validates the request before checkout;
2. checks out the exact requested ref;
3. installs `tools/data-storage/requirements.txt`;
4. runs `data_storage check-deps`;
5. downloads declared upstream Actions artifacts;
6. executes one or more repository Python entrypoints with `subprocess` argument arrays, never through arbitrary shell;
7. records source/input/request provenance;
8. uploads the output directory plus audit/stdout/stderr;
9. comments the Issue with the run/artifact status;
10. closes the request Issue. Failed requests are not left open.

## 4. Request contract

Example:

```json
{
  "request_id": "edgedb-v04-c2a-equivalence-20261005",
  "source_ref": "main",
  "input_artifacts": [
    {
      "label": "c1",
      "run_id": 123456789,
      "artifact_name": "jrdb-edge-v04-stage-c1-123456789"
    }
  ],
  "steps": [
    {
      "name": "canonical-c2a",
      "entrypoint": "horse-racing/jrdb/src/prepare_jrdb_edge_v04_stage_c2.py",
      "args": [
        "--c1-parquet",
        "{input:c1}/research_candidates.parquet",
        "--output-dir",
        "{output}"
      ]
    }
  ]
}
```

### Required top-level fields

- `steps`: non-empty JSON array, maximum 20.

### Optional top-level fields

- `request_id`: audit label.
- `source_ref`: branch, tag, or commit to checkout. Default: `main`.
- `input_artifacts`: zero to 8 upstream Actions artifacts.

### input_artifacts item

Each item requires:

- `label`: unique identifier matching `[A-Za-z0-9_-]{1,40}`;
- `run_id`: positive GitHub Actions run ID;
- `artifact_name`: exact artifact name.

Artifacts are downloaded to:

```text
/tmp/data-storage-fallback/inputs/<label>/
```

### step item

Each step requires:

- `name`: unique human-readable step label;
- `entrypoint`: repository-relative Python file;
- `args`: JSON array of string arguments.

The runner rejects:

- absolute entrypoint paths;
- paths outside the checkout;
- non-`.py` entrypoints;
- missing files;
- duplicate step names;
- non-string arguments;
- arbitrary shell command strings.

## 5. Placeholders

Arguments may use:

- `{repo}` — checked-out repository root;
- `{work}` — shared writable work directory;
- `{output}` — directory uploaded as the result artifact;
- `{input:LABEL}` — downloaded artifact directory for LABEL.

Example:

```json
{
  "name": "query",
  "entrypoint": "some/project/query.py",
  "args": [
    "--input", "{input:warehouse}/facts.parquet",
    "--scratch", "{work}/query",
    "--output", "{output}/result.json"
  ]
}
```

Steps run sequentially and share `{work}` and `{output}`.

## 6. Result contract

The workflow artifact is named:

```text
data-storage-fallback-<workflow_run_id>
```

It contains, when available:

- `output/` — requested durable outputs;
- `fallback-audit.json`;
- `stdout/<NN>-<step>.log`;
- `stderr/<NN>-<step>.log`.

The audit records:

- request ID and request SHA-256;
- source ref and resolved source commit;
- Python, DuckDB, PyArrow versions;
- each upstream artifact run/name/label;
- each entrypoint path and SHA-256;
- expanded argument vector;
- per-step exit status;
- overall PASS/FAIL.

The workflow artifact is an execution artifact, not automatically a production publication.

## 7. Routing boundaries

### Local remains preferred when

- `.venv-data-storage` passes `check-deps`;
- inputs are already local/reproducible;
- resource usage is practical;
- no formal Actions run is otherwise required.

### Actions fallback is preferred when

- the managed local runtime cannot install the pinned dependencies;
- the operation is deterministic and repository-defined;
- upstream inputs already live as Actions artifacts;
- running in Actions avoids semantic reimplementation.

### Use a project-specific Actions workflow instead when

- Secrets are required;
- an existing formal artifact chain is part of the project contract;
- immutable publication/freeze is required;
- the project workflow has domain-specific guards not represented by the generic fallback.

## 8. Google Drive boundary

This fallback does not create a direct GitHub Actions <-> Google Drive bridge.

If a required input is only in connected Google Drive:

1. resolve/materialize it through the native GPT/Drive route;
2. use the project's approved publication/artifact route if Actions execution is genuinely required.

Do not add Drive credentials, `gdown`, or Drive API transport to this generic fallback.

## 9. Codex behavior

When Codex encounters `DEPENDENCY_MISSING` plus an install failure caused by managed-runtime network policy, it should report:

```text
LOCAL_DATA_STORAGE_BLOCKED
reason=<network/proxy/policy>
fallback_candidate=true|false
```

If `fallback_candidate=true`, Codex should prepare or issue a validated `[DATA_STORAGE_FALLBACK]` request rather than substitute a different computation engine.

After the fallback completes, Codex must inspect the run/audit/artifact before using the result.

## 10. Scientific-computation rule

Storage/execution routing must not change scientific semantics.

In particular:

- DuckDB SQL stays DuckDB SQL when DuckDB is the canonical implementation;
- Parquet schemas and hashes remain pinned;
- threshold, as-of, population, parent/child, and leakage rules are unchanged;
- a fallback run is not a justification to reinterpret a research result.
