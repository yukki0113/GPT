# 20261005_006 — PEDIGREE_CROSS frozen 5y extension

- Status: **BLOCKED — pre-evaluation guard**
- Production impact: **NONE**
- Decision scope: no 5y result or family-expansion recommendation is made.

## Required route and local preflight

Repository data-storage instructions were read:

- `tools/data-storage/README.md`
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`
- `.gpt/GITHUB_OPERATION_POLICY.md`

At the repository snapshot, `PYTHONPATH=tools/data-storage .venv-data-storage/bin/python -m data_storage check-deps` returned `DEPENDENCY_MISSING` for DuckDB and PyArrow (Python 3.12.14). One install attempt from `tools/data-storage/requirements.txt` failed because the managed environment could not connect to `proxy:8080` (Operation not permitted). The required post-install check still returned `DEPENDENCY_MISSING`.

The local checkout was dirty (uncommitted C1/C2B/planner/workflow changes and untracked task files), so it was not used for evaluation.

## Frozen source and upstream availability

- Required source commit: `9aba7103f944ea419189c104be4e48485b819d0d`.
- Frozen Feature Mart artifact: run `36116777782`, artifact `jrdb-edge-feature-mart-parquet-36116777782`, artifact ID `10856365234`, archive digest `sha256:19d713da2e6ebf57965de98952fbf18d79f9ddfd5c1996833af3267b1a53f725`.
- Frozen Stage B catalog artifact: run `36262821119`, artifact `jrdb-edge-v04-stage-b-36262821119`, artifact ID `10912552938`, archive digest `sha256:5e71e15aba78228404441790bf9a67e7cd461bed542bc510ee6e8744de20805d`.
- Canonical 3y baseline: fallback run `37321021557`, artifact `data-storage-fallback-37321021557`, artifact ID `11349722900`, archive digest `sha256:ceadecafe0e1b78ce6c3f370439c446cc39017943b510f175e81fbe67bd43269`.

All three artifacts were listed as available and unexpired. These are archive digests, not the required extracted Parquet SHA-256 values. The Feature Mart and catalog contents were not extracted or rehashed in this blocked preflight.

## Failed guard

The pinned repository planner at the required source commit accepts lane and depth filters, but no family filter. Its shared preflight selector also accepts only lane and depth. The C1 evaluator accepts a template Parquet and shard plan but has no family-selection argument. Therefore the existing canonical path cannot build and audit the frozen `family == PEDIGREE_CROSS` template identity set while retaining verifiable provenance to the full pinned Stage B catalog.

Running the existing Wave A fallback runner with a 5y window would also evaluate other families, which is explicitly prohibited. No C1/C2 evaluation was started. No `[DATA_STORAGE_FALLBACK]` issue was created, because there is no valid family-only request to submit.

Required before rerun: add and review a deterministic family-subset selection/planning path that (a) reads the immutable Stage B catalog, (b) selects only the existing `PEDIGREE_CROSS` label within the three allowed lanes and depths 2–3, (c) records selected count, lane/depth counts, sorted template-ID SHA-256 and plan SHA-256, and (d) preserves the original catalog SHA as source provenance. Then rerun this task from that reviewed commit via the documented fallback.

## Run and output record

- Fallback Issue/run/artifact/digest: **not created**; preflight guard failed before execution.
- Python/DuckDB/PyArrow execution versions: Python `3.12.14`; DuckDB and PyArrow unavailable locally; Actions versions not applicable because no run was started.
- Input file hashes/row counts, family template-set hash, shard-plan hash, stage audits/counts, exact C2B request/result integrity and 3y-to-5y metrics: **not produced**.
- Decision: **BLOCKED, no acceptance decision**.
- PR status: this result is being submitted in a new PR; no PR is merged automatically.

## Scope

No non-`PEDIGREE_CROSS` family, depth 4+, threshold/support change, market conditioning, SHADOW publication, production integration or production-serving change was run or made.