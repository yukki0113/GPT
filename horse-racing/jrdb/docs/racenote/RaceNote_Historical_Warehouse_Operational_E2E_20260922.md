# RaceNote Historical Warehouse Operational E2E — 2026-09-22

## Verdict

`PASS`

`HISTORICAL_WAREHOUSE_OPERATIONAL_CUTOVER=PASS`

`RACENOTE_RESEARCH_RESTART=GO`

This document originally recorded the pre-full-day operational audit. The
remaining blockers were subsequently resolved by the 2018-12-02 full-day
operational E2E recorded in
`RaceNote_Operational_E2E_20181202_20260923.md`.

The active enrichment route is Analysis canonical only. Stats Mart is a frozen
legacy cache and is no longer required by RaceNote.

## Executed controlled integration

- Warehouse generation: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- Target date: `2018-12-02` (2010 boundary excluded)
- Base backend: `historical_warehouse`, explicitly Archive-bypassed
- Races / runners: 36 / 501
- RaceNote schema: `1.0`
- Reconstruction: BAC 36, KYI/CHA/CYB 501; required CHA/CYB joins 501/501; ZED/ZKB previous-result joins 1787/1787.
- Previous-result years: 2017 and 2018; no 2010 boundary fallback.
- Enrichment: Analysis canonical executed for every bundle; rolling horse/sire/jockey/frame statistics are calculated directly from Analysis with `race_date < target_date`; 0 enrichment warnings.
- Leakage audit: `as_of_exclusive=2018-12-02` for all bundles and applicable profiles; prior-run dates were all before target; no future leakage detected.
- Explicitly documented exception: 1 foreign-based entrant has `foreign_based_entry_no_jra_history` and no JRA Analysis profile; this is source coverage metadata, not an unreported join failure.
- Determinism: two independently generated full-day bundle sets produced identical semantic hashes after excluding only `metadata.generated_at`.

The exact run output is transient; the controlled audit is reproducible through `racenote_request_issue.yml` using its `warehouse_audit` request contract and `audit_racenote_historical_warehouse_e2e.py`.

## Implementation changes

- `src/racenote_request.py`: audit-only Archive bypass; normal Archive-first routing remains unchanged.
- `src/materialize_racenote_warehouse_assets.py`: request-scoped Drive materialization with accepted current/manifest and immutable object SHA/size checks.
- `src/audit_racenote_historical_warehouse_e2e.py`: fail-closed full-day Warehouse RaceNote audit and semantic rerun comparison.
- `.github/workflows/racenote_request_issue.yml`: accepts the controlled Warehouse contract, materializes verified assets, injects Warehouse roots, and asserts `used_backend` before publishing its artifact.
- `.github/workflows/jrdb_racenote_warehouse_tests.yml` and `tests/test_jrdb_racenote_warehouse_reader.py`: Reader/current/manifest resolution, semantic reconstruction, previous-result join, 2010 boundary detection, missing asset fail-fast, and materializer verification.

## Verification

- Warehouse adapter + Reader + materializer unit tests: 14 passed.
- Forecast Gen0 validation/guard/presentation tests: 17 passed.
- Newspaper external RaceNote exact-merge compatibility tests: 23 passed.
- Controlled full-day RaceNote Warehouse audit: PASS (36 races / 501 runners / deterministic rebuild PASS).

## Resolved blockers

1. Actual GPT structured decisions were produced for all 36 INDEPENDENT request
   artifacts and passed producer, validator, freeze/hash, and source-runner
   completeness guard.
2. Stats Mart was removed from the active dependency chain. The same rolling
   statistics are calculated directly from canonical Analysis under the
   as-of-safe `race_date < target_date` rule.
3. The complete day package passed strict race/runner identity checks for all
   36 races / 501 runners and the Newspaper/PWA handoff audit.

Final evidence:

- GitHub Actions run: `35847351773`
- head: `9822c674731c26cc2d3c08cc385b78ce23c7bbda`
- final artifact digest:
  `sha256:cf22326fdd6ed79946503729e553041a809a7602f35e17dc77a5ec7f74b3aa52`

## Technical debt not blocking the verified Warehouse-to-RaceNote route

- `FULL_MONTH_ARCHIVE_AUDIT`
- `2010_BOUNDARY_FULL_AUDIT`
- 2010–2025 Archive backfill and promotion to publishable Archive

These remain Archive-program work.  They do not invalidate the accepted Warehouse generation or this 2018 controlled Warehouse reconstruction; and do not block the completed historical cutover or research restart.

## Rollback

- Remove `warehouse_audit` from the Issue request to retain normal Archive-first behavior.
- Do not modify the JRDB Warehouse current pointer or immutable assets.
- For documented 2010 previous-result boundary work only, use the explicit Raw fallback already defined by `racenote_request.py`; 2011–2025 Warehouse failures remain fail-closed.

## Commit

Implementation commit SHA: `3f2915f7bdb0044192b8c30bebe913888a848925`.
