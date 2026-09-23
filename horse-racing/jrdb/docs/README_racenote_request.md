# RaceNote Request Router

## Current contract

src/racenote_request.py is the unified operational entrypoint.

    RaceNote request
      -> PACI or accepted Historical Warehouse base
      -> JRDB Analysis canonical enrichment
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

Normal usage passes Analysis only:

    python horse-racing/jrdb/src/racenote_request.py \
      --date 20260923 \
      --analysis ./jrdb_analysis.sqlite \
      --output ./output_racenote_request

--mart is a hidden deprecated compatibility option. It is ignored, never resolved, validated, downloaded, or passed to enrichment. New commands must not use it.

Store-managed operation resolves only jrdb://analysis/current. jrdb://stats/current is not a RaceNote input.

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

analysis_url is required. mart_url is a deprecated extra field accepted for old callers, ignored, and never downloaded. The workflow materializes Analysis only, preserves supplied Raw cache and Archive resolution, runs the Router without --mart, uploads the normal artifact, comments the machine-readable result, and closes the Issue.

## Historical and as-of rules

Target date and later result rows are excluded from history. Warehouse historical routing is explicit and coverage-guarded. There is no silent historical Raw downgrade. Archive is a delivery cache, not the canonical rebuild source. Output schema and Forecast/Freeze/Guard meaning are unchanged.

## Verification contract

Focused tests prove explicit Analysis without Stats Mart, Analysis-only Store resolution, deprecated mart compatibility, false/not_required Stats Mart metadata, TRUE_FORWARD compatibility, and workflow absence of Stats Mart download/materialization or Router --mart invocation.

Phase B may optimize internal Analysis storage access, including native Parquet. Phase A does not change RaceNote output schema, forecast semantics, historical Warehouse meaning, or legacy asset retention.
