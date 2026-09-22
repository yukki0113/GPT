# RaceNote Historical Warehouse Operation v1

## Routing contract

- Historical rebuilds for 2010–2025 use the accepted dedicated JRDB Warehouse current pointer `GPT/horse-racing/10_warehouse/jrdb/v1/current.json` and its immutable generation manifest.
- The required relations are BAC, KYI, CHA, CYB, ZED, and ZKB. The Warehouse reader feeds the existing `racenote_jrdb.BundleBuilder`; it does not change RaceNote schema or semantics.
- Requests for 2026 and later remain on the existing PACI/Raw route. Warehouse coverage is fail-closed outside 2010–2025.
- Raw is retained for formal audit, rollback, and the explicit 2010 pre-coverage previous-result boundary only. It must never be a silent historical fallback.

## Invocation contract

`racenote_request.py` requires `--warehouse-current` plus verified local immutable `--warehouse-asset-root FAMILY=PATH` values for BAC/KYI/CHA/CYB/ZED/ZKB. The current file must be the accepted dedicated JRDB pointer and must agree with its final manifest.

## Archive / backfill contract (Phase 2)

- New Historical Archive shards and `backfill_racenote_archive_year.py` use `build_racenote_archive_month_from_warehouse.py`; the existing Archive schema, `full_month`/`publishable` checks, full scan, Release naming and immutable existing shards are unchanged.
- A backfill supplies the accepted `--warehouse-current` and six materialized immutable `--warehouse-asset-root FAMILY=PATH` roots.  The builder records Warehouse asset SHA-256 values in its source manifest and does not create, copy or update Warehouse Parquet.
- Existing publishable Release shards continue to be resolver-validated and skipped.  The legacy annual Raw builders remain available only for rollback, audit, dual-read, 2010 boundary input and legacy immutable reproduction.
- The Warehouse Archive builder rejects 2026+; daily PACI/Raw Archive handling and all current-day orchestration are unchanged.

## Boundary fallback

A 2010 target may cite results before 2010. The caller must explicitly supply `--boundary-raw-dir`; only the matched pre-2010 ZED/ZKB rows are parsed and included alongside Warehouse target rows. The source manifest records every boundary file SHA-256, result-key count and raw-row count. No other Warehouse read failure may downgrade to Raw.

## Audit gate

Use `audit_racenote_archive_raw_vs_warehouse.py` against frozen Raw and verified immutable assets before a production Archive cutover. Compare full-month archive schema, race identities/counts, every bundle semantic SHA, source provenance, full scan and independent repeated Warehouse-build determinism. The required representative months are 2018, 2025 and a 2010 boundary month.
