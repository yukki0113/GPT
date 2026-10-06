# 20261006_010 — Unified EdgeDB Query / Horse History Foundation Result

Date: 2026-10-06  
Instruction source commit: `e74675a099dc2718972903454003a45f36ed8362`  
Query contract: `edgedb-query/v1`  
Query engine: `1.0.0`  
Production impact: **NONE**

## Implemented

- Added `current_manifest.json` as the source-selection authority. It declares independent `v0.2` STANDARD, `v0.3` SHADOW, and `v0.4` OBSERVE_ONLY lifecycles.
- Added compressed immutable v0.2/v0.3 serving-catalog snapshots to the config assets directory. Both were downloaded from the published GitHub Actions artifacts, decompressed through the existing v0.2 registry loader, and checked against their frozen publication hashes.
- Added `jrdb_edgedb_query.py`: JSONL fact and PACI modes, lifecycle profiles, exact identity filters, deterministic JSONL-compatible rows, source audit, and fail-closed path/hash/adapter/lifecycle validation. v0.2/v0.3 matching calls the existing v0.2 matcher. v0.4 uses the pure membership predicate shared with the existing observation runner.
- Factored `condition_matches()` from `jrdb_edge_v04_observe_shadow.py`; the existing observation runner now calls that function, preserving its comparison behavior.
- Added `jrdb_horse_history_query.py`: one DuckDB query over the fact partitions selected by the canonical Analysis current-generation resolver, exact `horse_id` predicate, date bounds, ordering, limit, duplicate-start guard, optional compatible SQLite input, and source provenance. No raw ZIP history scan or persistent cache is introduced. Payout enrichment is deferred because no clean result-query reuse path was needed for the base response.
- Added focused tests and this result report. RaceNote and Newspaper/PWA consumers were not switched.

## Canonical manifest inputs

| Lifecycle | Canonical source | Validation |
|---|---|---|
| STANDARD v0.2 | Successful GitHub Actions run `34620664640`; artifact `jrdb-edge-serving-v02-full-2010-2025-standard-r1-34620664640`; committed snapshot `horse-racing/jrdb/config/edgedb/assets/edge_serving_catalog_v0_2_34620664640.jsonl.xz.b64` | 3,009 rows; SHA-256 `fe1182e1e8beed952d5f4b740642fd3ec1262c353d6d46036e19a457f27d7469`; matches the frozen publication evidence and canonical Registry migration record. |
| SHADOW v0.3 | Successful GitHub Actions run `36045237262`; artifact `jrdb-edge-v03-shadow-catalog-36045237262`; committed snapshot `horse-racing/jrdb/config/edgedb/assets/edge_serving_catalog_v0_3_shadow_36045237262.jsonl.xz.b64` | 2,044 rows; SHA-256 `a724a005ec40446f4a982a79de17ba7a2ae169c09260ecee98a159b663914379`; rows retain `v03_shadow.mode=SHADOW_ONLY`. |
| OBSERVE_ONLY v0.4 | `horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_v0_1.json` | 347 rows; fingerprint-set SHA-256 `ad0cf386601fb0366db27197072205c565eef189fa2e1062a97702f4b30f4876`; membership validator passes. |

The manifest SHA-256 is `21e528792946556b774c092fa49eccef0ae8b7dfac38785319ef051d2c5ffce9`. The runtime checks the base64 asset SHA-256, decodes XZ, verifies the compressed snapshot SHA-256 (`88e548338d9004ad69c1c884937656ddae347960ca1422707f6eb815a2af8983` for v0.2; `0e1b9fc24533fc94f42fe2e5907d638a4beb8f9806c9ad2be1ebfa15cebba41b` for v0.3), then passes the decoded JSONL through the existing registry loader. The manifest records the canonical uncompressed publication hashes separately.

## Verification

Command:

```text
PYTHONPATH=horse-racing/jrdb/src python -m unittest -v \
  horse-racing/jrdb/tests/test_jrdb_edgedb_query.py \
  horse-racing/jrdb/tests/test_jrdb_horse_history_query.py
```

Result: **8 tests passed**. Coverage includes source hashes and cohort fingerprint/row count, v0.2 STANDARD matcher parity on a deterministic fixture, v0.4 cohort membership parity, exact lifecycle visibility, manifest fail-closed cases, deterministic ordering, identity filters, and SQLite compatibility history date/order/limit/duplicate/provenance behavior.

`py_compile` passed for the two new query modules and the v0.4 cohort/shadow modules.

The local `.venv-data-storage` dependency check reported DuckDB and PyArrow missing. One normal install attempt was blocked by the managed proxy (`proxy:8080`, operation not permitted). Therefore the canonical Analysis Parquet/DuckDB integration could not be executed in this workspace. The implementation resolves the live Analysis generation at runtime and includes the repository Data Storage repair/Actions-fallback route in its missing-dependency error, but the Horse History Parquet acceptance gate remains **BLOCKED pending an Actions run with the pinned dependencies and a canonical Analysis fixture/current root**. The test suite could not be run through pytest because pytest is also absent; the same focused tests were run successfully with the Python standard-library unittest runner.

## Equivalence and profile results

- v0.2 STANDARD parity: **PASS** on deterministic fixture; matched edge IDs, performance/value evidence levels, matched conditions, and presentation roles match `jrdb_edge_matcher_v0_2.match_runner(..., profile=STANDARD)`.
- v0.4 parity: **PASS** for frozen cohort membership fixture; query returns the same cohort ID after using the factored pure v0.4 predicate.
- Profile visibility: **PASS** — STANDARD includes STANDARD only; STANDARD_PLUS_SHADOW adds SHADOW; RESEARCH_ALL adds OBSERVE_ONLY. Observe-only signals are explicitly non-production eligible and carry `UNASSESSED` value evidence.
- Horse History exact lookup: **PASS** on the SQLite compatibility backend fixture; canonical Parquet/DuckDB execution is **BLOCKED** as described above.
- Production consumer migration: **NONE**.

## Consumer migration map

| consumer | current input | future input | required adapter delta | parity test | risk |
|---|---|---|---|---|---|
| `racenote_edge_performance_adapter.py` | v0.2 `edge_matches` keyed by `race_horse_key` | `edgedb-query/v1` STANDARD signals | Map eligible performance signals and evidence/presentation fields to RaceNote's existing adapter row; retain exact runner key and current evidence gates. | Same runner keys, edge IDs, performance eligibility, score inputs, and serialized forecast for frozen days. | Score or mark changes if lifecycle/evidence gates are weakened. |
| `jrdb_newspaper_edge_adapter.py` | v0.2 registry and matcher output; adapter applies existing serving eligibility | `edgedb-query/v1` STANDARD signals | Convert only currently eligible STANDARD signals to the adapter's reader-facing payload; keep rendering outside the matcher. | Same runner set, displayed signal IDs/text, evidence eligibility, and payload snapshots. | Accidental display of SHADOW/OBSERVE_ONLY or text drift. |
| `jrdb_newspaper_merge_edge.py` | exact join between newspaper rows and v0.2 `edge_matches` | query rows joined by `race_horse_key` | Replace source-row shape with normalized signal projection; preserve exact join and no-recalculation behavior. | Join cardinality, matched runner keys, and final merged JSON parity on frozen publication fixtures. | Join loss/duplication or output-shape changes. |
| related operational runbooks | generation-specific source paths and commands | manifest revision, query profile, stable schema | Document source refresh, profile selection, provenance checks, and rollback to the existing generation-specific commands during rollout. | Dry-run command and artifact hash comparison before a consumer change. | Stale manifest/artifacts or rollback ambiguity. |

## Outstanding gate

Do not claim full acceptance until the pinned DuckDB/PyArrow Actions fallback (or equivalent approved runner) exercises Horse History against a canonical Analysis current generation and the PR checks pass. Historical blind replay remains allowed by the instruction and must be labeled `HISTORICAL_BLIND_REPLAY`; it is distinct from `TRUE_FORWARD`.
