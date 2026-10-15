# Common JRDB race-lap v0.1 implementation audit — 2026-10-15

Base: GitHub main `24d0db3dbffb0c3bbc636448c6ef2581fa36cfd9`.
Runtime: Python 3.12.14, DuckDB 1.1.3; Data Storage dependency check PASS.

## Delivered scope

Added `src/jrdb_race_lap_dataset.py`, `jrdb_race_lap_store.py`,
`jrdb_race_lap_reader.py`, `jrdb_race_lap_contract.py` and
`jrdb_race_lap_shape.py`, plus `schema/race_lap_evidence_schema.json` and three
focused test modules. The legacy RaceNote module imports the moved unchanged
shape function. README/CONTEXT link the common Reader contract; the existing
common-reader CI now includes its compile and pytest checks.

No Raw parser offsets, normalization formulas, RaceNote prediction logic,
RRDB thresholds, warehouse/Analysis current pointers or storage package were
changed. No persistent database was created.

## Focused verification

```bash
python -m pytest -q \
  horse-racing/jrdb/tests/test_jrdb_race_lap_dataset.py \
  horse-racing/jrdb/tests/test_jrdb_race_lap_store.py \
  horse-racing/jrdb/tests/test_jrdb_race_lap_reader.py \
  horse-racing/jrdb/tests/test_jrdb_race_lap.py \
  horse-racing/jrdb/tests/test_racenote_lap_shape_evidence.py
python -m compileall -q horse-racing/jrdb/src
```

Result: **64 passed**, compile PASS; `git diff --check` PASS.
The cases cover full/partial 1700m, 2100m and 1150m sequences, blank/populated
optional context, NO_LAPS, missing SRB, duplicate keys/horse rows, inconsistent
counts/distances, malformed extra members, internal blanks, corrupt physical
columns/JSON/numbers/versions, bound SQL keys, one-query batches, segment
reconstruction, JSON/schema validation, CLI exits and explicit replacement.

## Real canonical SED smoke

The connected native Google Drive connector materialized the existing canonical
`00_raw/SED/SED260829.zip` and `SED260906.zip`; no JRDB acquisition was started.
Inputs were read after the SED refresh, as current snapshots, without combining
older revisions.

- Input archives: 2; race rows: 72; duplicate keys: 0.
- AVAILABLE: 70; NO_LAPS: 2; partial first segment: 11.
- Optional SRB context: 72; dates: 2026-08-29 through 2026-09-06.
- Reader strict JSON serialization and Draft 2020-12 validation: **72/72 PASS**.
- Existing Phase 3B available shape values: **70/70 identical**.
- Reversed input archive order: **byte-identical Parquet and identical audit**.
- ZSTD Parquet: 25,783 bytes.
- SHA-256: `42b18279dab3f77a2c6df3967d82c43d30c4e897dbe228f0114eeef0044c996b`.

Machine-readable evidence:
`JRDB_Race_Lap_Reader_Build_Audit_20261015.json` and
`JRDB_Race_Lap_Reader_Smoke_20261015.json` (including input hashes).
Generated Parquet is a runtime artifact, not a Git-tracked binary. This is a
two-day smoke dataset, not a published full-history generation. No Drive data
or current pointer was written. Rebuild it with the documented builder CLI.

## Existing unrelated failures

The existing common-reader CI unittest command ran **109 tests: 106 passed,
3 errors**, all in `test_racenote_store_resolution`: old SQLite fixtures lack
`broodmare_sire_line_code`, `broodmare_sire_name`, `sire_line_code`.

Existing Phase A CI pytest: **6 passed, 2 failed**:

- `test_running_style_race_trends_are_asof_safe_and_target_independent`:
  fixture lacks `race_condition_code`.
- `test_request_workflow_is_analysis_only`: references missing legacy
  `.github/workflows/racenote_request_issue.yml`.

Both CI command outcomes reproduce unchanged in an isolated worktree at the
base main SHA. They are not repaired by this race-lap task.

An initial test-list invocation used an incorrect working-directory-relative
workflow path, leaving unittest with no explicit module list and triggering
broad discovery. That exploratory run reported 701 tests, 15 failures and
41 errors, including optional pandas dependencies and stale unrelated tests.
The intended CI commands above were then run explicitly. Broad discovery on
the unchanged base reproduces the same 701 / 15 failures / 41 errors.

## Operational limits

Store v0.1 validates the entire snapshot in memory on open. Use immutable input
for its lifetime. Byte determinism was checked within the pinned writer/runtime;
upgrades need separate qualification. Evidence declares the exclusive historical
policy; the consuming prediction layer must enforce source date < target date.
Consumer production integration and full-history publication remain out of scope.
