# RaceNote Request Router

## Current contract

src/racenote_request.py is the unified operational entrypoint.

    RaceNote request
      -> PACI or accepted Historical Warehouse base
      -> JRDB Analysis Parquet current (DuckDB, as-of-exclusive) enrichment
      -> selected RaceNote v1.0 bundles
      -> ZIP / GPT downstream

RaceNote active enrichment uses JRDB Analysis canonical only. Rolling horse, sire, jockey, and frame statistics are calculated from that same Analysis dataset with race_date < target_date.

Historical routing remains:

- 2010–2025: accepted JRDB Historical Warehouse
- 2026 current/future: PACI daily route
- Raw: explicit rollback/audit and documented 2010 previous-result boundary fallback only
- Archive: optional publishable delivery cache; absence does not stop a Warehouse rebuild

Stats Mart is a frozen legacy cache. It remains for old research, builders, schemas, and reproducibility, but is not an active RaceNote dependency.

## CLI

Normal usage passes the verified Analysis Parquet current root:

    python horse-racing/jrdb/src/racenote_request.py \
      --date 20260923 \
      --analysis-root ./jrdb_analysis_parquet \
      --analysis-backend parquet \
      --output ./output_racenote_request

--analysis is a hidden SQLite compatibility option. It is available only with
--analysis-backend sqlite for audit, equivalence, or explicit rollback. Production
does not materialize SQLite and does not automatically fall back to it.
--mart remains a hidden deprecated option and is ignored.

## GitHub Actions request

Workflow: .github/workflows/racenote_request_issue.yml

Issue title:

    [RACENOTE_REQUEST] <request_id>

Issue body:

    {
      "date": "YYYYMMDD",
      "analysis_url": "https://drive.google.com/...",
      "venue": "中山",
      "race": 11
    }

analysis_url is required and must identify the immutable Analysis Parquet archive containing current.json and the verified generation assets. The workflow downloads and validates that archive, preserves supplied Raw cache and Archive resolution, runs the Router with --analysis-root and --analysis-backend parquet, uploads the normal artifact, comments the machine-readable result, and closes the Issue. SQLite Analysis archives are not accepted on the normal path.

## Historical and as-of rules

Target date and later result rows are excluded from history. Warehouse historical routing is explicit and coverage-guarded. There is no silent historical Raw downgrade. Archive is a delivery cache, not the canonical rebuild source. Output schema and Forecast/Freeze/Guard meaning are unchanged.

## Verification contract

Focused tests prove native Parquet current resolution, manifest/SHA/canonical-key validation, strict as-of exclusion of target and future rows, SQLite compatibility isolation, false/not_required Stats Mart metadata, and workflow absence of SQLite materialization on the production path.

Phase B does not change RaceNote output schema, forecast semantics, historical Warehouse meaning, or legacy asset retention. The completion markers are RACENOTE_PHASE_B_PARQUET_NATIVE=PASS, RACENOTE_ANALYSIS_BACKEND=PARQUET_DUCKDB, RACENOTE_SQLITE_MATERIALIZATION_REQUIRED=false, RACENOTE_STATS_MART_ACTIVE_DEPENDENCY=false, RACENOTE_HISTORICAL_BACKEND=HISTORICAL_WAREHOUSE, RACENOTE_2026_BACKEND=PACI, and RACENOTE_OUTPUT_SEMANTICS_UNCHANGED=true.
