# RaceNote Phase C — Legacy Isolation / Repository Cleanup Completion

Date: 2026-09-24  
Repository: `yukki0113/GPT`  
Branch: `codex/racenote-phaseb-parquet-native-cutover`  
PR: #1224  
Validation commit: `a9f86a1d4429fb18b27b219bfc12d7b3c103bef6`

## Result

```text
RACENOTE_PHASE_C_LEGACY_ISOLATION=PASS
RACENOTE_CURRENT_ARCHITECTURE_UNAMBIGUOUS=true
RACENOTE_STATS_MART_CURRENT_REFERENCES=0
RACENOTE_DEPRECATED_MART_INPUT_REMOVED=true
RACENOTE_DEPRECATED_SQLITE_INPUT_REMOVED_OR_AUDIT_ONLY=true
RACENOTE_LEGACY_PREDICTION_ISOLATED=true
RACENOTE_ARCHIVE_ROLE=OPTIONAL_CACHE
RACENOTE_CURRENT_DOCS_SINGLE_SOURCE_OF_TRUTH=true
RACENOTE_FULL_DAY_E2E=PASS
```

The zero-reference markers above apply to the current production request/router/enrichment
path. Legacy, audit, reproducibility, and historical documentation may retain explicit
references by design.

## Current architecture

- 2010–2025: accepted Historical Warehouse.
- 2026 current/future: PACI.
- Analysis: current verified Analysis Parquet generation through DuckDB direct.
- SQLite Analysis: explicit compatibility/audit/rollback only; no silent fallback.
- Stats Mart: legacy-only; not a RaceNote dependency.
- Archive: optional immutable delivery cache, not the canonical historical rebuild source.
- Forecast Gen0: current prediction system.
- v0.2/v1.1-P/Edge deterministic prediction: legacy reproduction/benchmark only.
- Raw direct: explicit audit, rollback, or boundary fallback only.

## Repository changes

- Removed hidden `--mart` from the current RaceNote router and production enrichment CLI.
- Removed the obsolete mart parameter from the bulk production enrichment API.
- Updated resolver tests to the current two-value resolver contract.
- Added `docs/racenote/legacy/README.md` as the retained legacy boundary and inventory.
- Marked Stats Mart builder and post-race mart-refresh documents as legacy/historical.
- Updated `docs/racenote/README.md`, `docs/README_racenote_request.md`, and `.gpt/CONTEXT.md`
  as the current architecture truth.
- Added `test_racenote_current_architecture_contract.py`.
- Added the architecture guard to the Phase B focused workflow.
- Kept legacy builders, schemas, prediction modules, Archive tooling, workflows, and SQLite
  materializer physically intact for reproducibility and rollback.

No Analysis schema, Warehouse schema, Forecast Gen0 semantics, PWA/Newspaper schema, or
historical boundary policy was changed.

## Current Analysis verification

- Generation: `analysis-v1_3-dryrun-20260918-03`
- Total rows: `516061`
- Assets: `13`
- Manifest/current pointer: resolved and validated before use.
- Asset SHA-256, size, schema, canonical key, and row count checks: PASS.
- Evidence artifact: Actions run `35949412838`, artifact `10788186953`.

## Historical full-day E2E

Target: `2018-12-02`, 36 races, 501 runners.

| Check | Result |
|---|---:|
| Compatibility SQLite route generated | PASS |
| Parquet/DuckDB direct route generated | PASS |
| Historical backend | `historical_warehouse` |
| Analysis backend | `parquet_duckdb` |
| Stats Mart | false |
| SQLite materialization required | false |
| warnings | 0 |
| future leakage | 0 |
| semantic equivalence, all 36R | PASS |
| 2026 plan regression | `base_backend=paci` |

Semantic hashes excluded only non-semantic metadata such as generated timestamps and backend
source diagnostics.

## Benchmark

Measured in the same Actions run:

| Metric | SQLite compatibility | Parquet/DuckDB |
|---|---:|---:|
| cold start | 2.612 s | 0.052 s |
| 1R enrichment | 1.239 s | 1.799 s |
| Full-day enrichment | 31.262 s | 0.996 s |
| E2E total | 33.873 s | 1.048 s |
| horse query x5 | 0.000066 s | 0.021016 s |
| sire query x5 | 0.013279 s | 0.018393 s |
| jockey query x5 | 0.002368 s | 0.018464 s |
| frame query x5 | 0.136670 s | 0.018096 s |
| SQL query count | 10,555 | 397 |
| Parquet scan count | 0 | 397 |

The single-race and point-query microbenchmarks remain slower on Parquet, while the primary
full-day use case is substantially faster. The benchmark does not use SQLite fallback.

## CI

- RaceNote Phase B Parquet native tests: PASS.
- Current architecture guard: PASS.
- Common Reader tests: PASS.
- Real-data Phase B native E2E and related tests: PASS.
- Actions run: https://github.com/yukki0113/GPT/actions/runs/35949412838
- Evidence artifact: https://github.com/yukki0113/GPT/actions/runs/35949412838/artifacts/10788186953

## Retained technical debt

- Legacy files remain at their historical paths to preserve imports and replayability.
- Archive maintenance workflows remain available but are explicitly separate from current request
  workflows.
- SQLite compatibility remains available for audit/equivalence/rollback consumers only.
- A future separately authorized cleanup may physically move or remove assets after a complete
  zero-reference and reproducibility audit.
