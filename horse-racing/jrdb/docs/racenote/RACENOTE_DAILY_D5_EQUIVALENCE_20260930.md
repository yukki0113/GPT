# RaceNote Daily Build D5 Equivalence Audit — 2026-09-30

Status: **PASS / PRODUCTION DAY-LEVEL CUTOVER APPROVED**

## Purpose

Validate that the consolidated day-level RaceNote builder preserves the
semantics of the existing one-race production enrichment path before making
`src/build_racenote_daily.py` the normal full-day production entrypoint.

No Forecast logic was changed by this audit.

## Validation target

- target date: `2026-05-23`
- reason: already-used / research-ineligible day
- venues: 京都 / 新潟 / 東京
- races: 36
- horses: 549

Fixed sources:

- Analysis generation: `analysis-v1_4-canonical-20260928-01`
- RRDB generation: `jrdb_race_review_v0_1_incremental_g36094708797`
- Next-Watch rules: `next-watch-rules-discovery-v0.1`
- PACI: `PACI260523.zip`

## Compared paths

Old path, race by race:

```text
PACI base RaceNote
  -> racenote_history_enrichment.enrich_production()
  -> racenote_rrdb_enrichment.enrich_bundle()
  -> Reader View round-trip
```

New path:

```text
PACI parsed once
  -> all base RaceNotes
  -> enrich_production_many()
  -> enrich_bundles()
  -> Reader Views
  -> validation / package
```

## Migration equality rule

The migration semantic hash intentionally excludes only execution-only metadata
that necessarily differs between independent executions:

- `metadata.generated_at`
- local Analysis `path`
- local Analysis `manifest_path`
- Analysis `query_count`
- Analysis `parquet_scan_count`

All evidence and provenance semantics remain hash-significant.

Reader View is required to pass semantic round-trip independently for both old
and new bundles. Its full `source_semantic_sha256` is not required to match
between independent executions because that hash includes the execution-only
metadata above. Evidence-semantic equality is checked separately.

## Audit iterations

### Initial infrastructure attempt

Issue #1603 / run `36645037205` stopped before comparison because the workflow
did not expose the GitHub token under the `GH_TOKEN` environment name expected
by the GitHub CLI. This was an execution harness failure, not a semantic result.

### Main source regression discovered

The first real-data run exposed a pre-existing indentation regression in
`racenote_history_engine.py` in the `target_entry_not_found` branch.
The engine could not import, so neither the one-race nor daily path could
execute.

The source regression was fixed on main in commit:

`e8750228d654921fb2e5d1ce08df5f1dc6c01971`

### D5 gate v0.1

Issue #1609 / run `36645741020`.

Observed for all 36 races:

- race identity: equal
- horse identity: equal
- evidence semantic hash: equal
- P1/P2: equal
- RRDB: equal

The run was marked FAIL only because audit v0.1 additionally required the full
Reader source hash to match old-vs-new. That condition was stricter than the
frozen migration contract because the Reader source hash includes expected
execution-only metadata differences.

### Corrected D5 gate v0.2

Issue #1610 / run `36646155701`.

Result:

- status: PASS
- cutover_eligible: true
- race identity: PASS
- horse identity all: PASS
- evidence semantic equality all: PASS
- P1/P2 all: PASS
- RRDB all: PASS
- Reader View round-trip all: PASS

### Final confirmation after main source fix

Issue #1611 / run `36646513226`.

This run executed from main after commit `e875022...`, so the audit harness
did not need to repair the History Engine source at runtime.

Result:

- status: **PASS**
- cutover_eligible: **true**
- 36 / 36 races PASS
- 549 horses covered
- all six D5 gates PASS

## Cutover decision

D5 acceptance is satisfied.

Standard full-day RaceNote generation is now:

```text
src/build_racenote_daily.py
  -> BASE
  -> HISTORY / Trend / P1 / P2
  -> RRDB
  -> Reader View
  -> validation
  -> package
```

The existing one-race path is retained for explicit single-race operation,
audit and rollback. It is no longer the normal full-day production path.

Forecast logic remains unchanged at
`RaceNote-Human-Context-Reader-0.3.2`.
