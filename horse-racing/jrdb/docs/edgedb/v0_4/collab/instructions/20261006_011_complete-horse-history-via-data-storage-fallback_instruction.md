# 20261006_011 — Complete Horse History via Shared Data Storage Fallback

Status: TODO  
Date: 2026-10-06  
Supersedes: the BLOCKED completion state recorded in PR #1822 for instruction 010  
Production impact: NONE

## Objective

Complete the only remaining acceptance gate in PR #1822:

- execute `jrdb_horse_history_query.py` against canonical Analysis Parquet;
- use canonical DuckDB through the repository-wide `tools/data-storage` execution route;
- update the existing PR #1822 and result report from BLOCKED to PASS/accepted if successful.

Do not create a second implementation of Parquet/DuckDB logic.

## Mandatory routing rule

The repository-wide route is authoritative:

1. `.venv-data-storage`
2. `PYTHONPATH=tools/data-storage ... -m data_storage check-deps`
3. one normal repair attempt:
   `.venv-data-storage/bin/python -m pip install -r tools/data-storage/requirements.txt`
4. if the managed runtime proxy/network blocks repair:
   - report `LOCAL_DATA_STORAGE_BLOCKED`
   - `fallback_candidate=true`
   - issue a validated `[DATA_STORAGE_FALLBACK]` request
   - inspect the workflow run, `fallback-audit.json`, stdout/stderr, and result artifact
   - continue the task from the canonical result.

A local missing DuckDB/PyArrow installation is NOT a final BLOCKED reason when fallback_candidate=true.

Read and follow:

- `tools/data-storage/README.md`
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`
- `tools/data-storage/scripts/data_storage_fallback_runner.py`
- `.github/workflows/data_storage_fallback_issue.yml`

## Existing PR to update

Use PR #1822.

Do not open a replacement PR unless technically unavoidable.

The existing implementation is the candidate under test:

- `horse-racing/jrdb/src/jrdb_horse_history_query.py`
- `horse-racing/jrdb/src/jrdb_edgedb_query.py`
- `horse-racing/jrdb/config/edgedb/current_manifest.json`

Do not redesign these solely because local dependencies are unavailable.

## Canonical Analysis input discovery

Before fallback execution, resolve the current accepted Analysis Parquet generation and its immutable source identity.

Use repository publication/current-generation metadata and existing accepted Analysis artifact/workflow evidence.

Required record:

- Analysis generation_id
- manifest identity/SHA
- fact partition count
- source workflow run/artifact if used by fallback
- coverage min/max date
- canonical table: `fact_entry_result_lite`

Do not guess a local path.

### Google Drive boundary

The generic Data Storage fallback cannot directly fetch Drive.

If the current Analysis Parquet exists only in Drive, use the existing approved Analysis publication/artifact route to obtain a reproducible GitHub Actions artifact/source. Do not declare the task BLOCKED merely because Drive is not mounted inside Actions.

If no immutable Actions/repository source exists at all, document that specific missing publication chain as the blocker. That is different from "DuckDB/PyArrow unavailable".

## Fallback execution

The fallback request must check out the exact PR #1822 head commit.

Use the generic Data Storage workflow and pinned requirements.

The request should execute repository Python entrypoints only.

At minimum, run:

1. a dependency/version verification;
2. a real `jrdb_horse_history_query.py` query against canonical Analysis Parquet;
3. focused validation of its output.

If a small deterministic helper is needed to assert the query result, add it to the same PR. Do not use arbitrary shell.

## Real query requirement

Use at least one actual `horse_id` known to exist in the canonical Analysis generation.

Do not use only a synthetic fixture.

Verify:

- exact `horse_id` filtering;
- all returned rows belong to that horse;
- chronological sort is correct;
- race identity fields are stable;
- no duplicate `race_key + horse_no`;
- `--from-date` / `--to-date` bounds work on a real Parquet query;
- `--limit` works;
- source provenance reports the canonical Analysis generation;
- the implementation performs one DuckDB predicate scan over the generation partitions, not a raw ZIP loop.

Record the selected test horse only as an audit fixture; do not bake it into production code.

## Dependency evidence

The result report must record:

- Python version
- DuckDB version (expected pinned Data Storage version)
- PyArrow version
- Data Storage requirements source SHA/commit
- fallback workflow run ID
- fallback artifact name/digest
- fallback audit PASS
- source_ref and resolved commit

## Re-run focused tests

After any correction, run:

```
PYTHONPATH=horse-racing/jrdb/src python -m unittest -v \
  horse-racing/jrdb/tests/test_jrdb_edgedb_query.py \
  horse-racing/jrdb/tests/test_jrdb_horse_history_query.py
```

If additional canonical-Parquet tests are added, include them.

Existing required parity must remain:

- STANDARD matcher parity PASS
- v0.4 observe cohort parity PASS
- lifecycle profile visibility PASS
- manifest fail-closed PASS.

## Result report update

Update:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261006_010_unified-edgedb-query-and-horse-history-foundation_result.md`

Replace the current local-dependency BLOCKED conclusion with actual fallback evidence.

Expected final state if successful:

- canonical Analysis Parquet Horse History: PASS
- instruction 010 acceptance gate: PASS
- production consumer migration: NONE
- PR #1822 remains unmerged pending review.

If fallback itself fails, report the concrete failure from the workflow/audit. Do not collapse it into generic "DuckDB unavailable".

## Acceptance criteria

PR #1822 may be accepted only when all are true:

1. local missing dependency route is recorded correctly;
2. Data Storage fallback is actually executed when fallback_candidate=true;
3. fallback audit is PASS;
4. a real canonical Analysis Parquet Horse History query passes;
5. focused unit/parity tests remain PASS;
6. no production RaceNote/PWA migration occurred;
7. result report no longer lists local DuckDB/PyArrow absence as the unresolved blocker.

## Non-goals

- no alternate pandas/PyArrow-only scientific path;
- no duplicated Data Storage utility;
- no persistent DuckDB database;
- no new Edge discovery;
- no production serving switch;
- no consumer migration;
- no raw SED/HJC day-by-day scan for base Horse History.
