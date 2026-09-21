# RaceNote Historical Warehouse Operation v1

## Routing contract

- Historical rebuilds for 2010–2025 use the accepted dedicated JRDB Warehouse current pointer `GPT/horse-racing/10_warehouse/jrdb/v1/current.json` and its immutable generation manifest.
- The required relations are BAC, KYI, CHA, CYB, ZED, and ZKB. The Warehouse reader feeds the existing `racenote_jrdb.BundleBuilder`; it does not change RaceNote schema or semantics.
- Requests for 2026 and later remain on the existing PACI/Raw route. Warehouse coverage is fail-closed outside 2010–2025.
- Raw is retained for formal audit, rollback, and the explicit 2010 pre-coverage previous-result boundary only. It must never be a silent historical fallback.

## Invocation contract

`racenote_request.py` requires `--warehouse-current` plus verified local immutable `--warehouse-asset-root FAMILY=PATH` values for BAC/KYI/CHA/CYB/ZED/ZKB. The current file must be the accepted dedicated JRDB pointer and must agree with its final manifest.

## Boundary fallback

A 2010 target may cite results before 2010. The reader stops with a boundary error; a caller may proceed only by explicitly supplying `--raw-dir`. The output provenance records `pre_2010_previous_result_boundary`. No other Warehouse read failure may downgrade to Raw.

## Audit gate

Use `audit_jrdb_racenote_raw_vs_warehouse.py` against frozen Raw and verified immutable assets before modifying reader logic. Compare logical bundles under Archive's semantic hash rule (only `metadata.generated_at` is excluded), plus rows, keys, schema, NULL/blank semantics, all logical values, joins, deterministic reread, and idempotence.
