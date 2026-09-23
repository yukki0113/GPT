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

## Controlled operational E2E

`racenote_request_issue.yml` accepts an explicit `warehouse_audit` request object for a controlled Historical E2E.  The normal Archive-first request policy is unchanged.  In this one audit mode only, the workflow:

1. receives the dedicated current, final manifest, and request-scoped immutable object URLs from the existing Drive acquisition layer;
2. verifies current/manifest SHA-256 and every object size/SHA-256 before supplying local asset roots to RaceNote;
3. explicitly bypasses Archive and requires `used_backend=historical_warehouse`;
4. writes `historical_warehouse_e2e_audit.json` using `audit_racenote_historical_warehouse_e2e.py`.

No Drive identifier or Warehouse URL is persisted in Git.  A 2011–2025 failure is fail-closed and must not silently downgrade to Raw.  The audit runner verifies full-day bundle/runner identity, required joins, `as_of_exclusive`, prior-run dates, and (when a comparison run is supplied) semantic deterministic rebuilds.  A foreign-based entrant may have an explicitly documented `foreign_based_entry_no_jra_history` profile gap; this is not silently treated as a JRA-history failure.
