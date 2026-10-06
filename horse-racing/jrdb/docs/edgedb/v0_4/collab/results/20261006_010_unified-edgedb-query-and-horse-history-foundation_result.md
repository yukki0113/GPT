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

The manifest SHA-256 is `b3e086704ec0ec31093f017f1ec0f3065317c1933ee6e2976780f2aa448f9bae`. The runtime checks the base64 asset SHA-256, decodes XZ, verifies the compressed snapshot SHA-256 (`88e548338d9004ad69c1c884937656ddae347960ca1422707f6eb815a2af8983` for v0.2; `0e1b9fc24533fc94f42fe2e5907d638a4beb8f9806c9ad2be1ebfa15cebba41b` for v0.3), then passes the decoded JSONL through the existing registry loader. The manifest records the canonical uncompressed publication hashes separately.

## Verification

Command:

```text
PYTHONPATH=horse-racing/jrdb/src python -m unittest -v \
  horse-racing/jrdb/tests/test_jrdb_edgedb_query.py \
  horse-racing/jrdb/tests/test_jrdb_horse_history_query.py
```

Result: **9 tests passed**. Coverage includes source hashes and cohort fingerprint/row count, v0.2 STANDARD matcher parity on a deterministic fixture, v0.4 cohort membership parity, exact lifecycle visibility, manifest fail-closed cases, deterministic ordering, identity filters, and SQLite compatibility history date/order/limit/duplicate/provenance behavior.

`py_compile` passed for the two new query modules and the v0.4 cohort/shadow modules.

The local `.venv-data-storage` dependency check reported DuckDB and PyArrow missing. The single normal requirements repair attempt was blocked by the managed proxy (`proxy:8080`, operation not permitted), so the canonical Data Storage fallback was used. The fallback run passed with the pinned DuckDB `1.1.3` and PyArrow `25.0.1`; its exact run, source, artifact, and real-query evidence are recorded below. The focused tests were run successfully with the Python standard-library unittest runner; pytest is not installed in this workspace.


## Canonical Analysis Parquet fallback evidence

- Local route: LOCAL_DATA_STORAGE_BLOCKED; fallback_candidate=true. check-deps found DuckDB/PyArrow missing, and the one allowed pip install -r tools/data-storage/requirements.txt repair was blocked by the managed proxy (proxy:8080 operation not permitted).
- Requirements source: exact fallback source commit 589b6c7e76cb00edc7976af796f044be438b3399; tools/data-storage/requirements.txt SHA-256 4bd66c0c022454e909f5fddd55b276bddff1d16f5713aa238bc54f6444a71b07.
- Fallback workflow run 37431244572 used exact source_ref / resolved commit 589b6c7e76cb00edc7976af796f044be438b3399. The run artifact is data-storage-fallback-37431244572, digest sha256:8f197bb2fdca5785d96937d06f984d91c809fecbde3d76828ef6b4836ce215d8. fallback-audit.json status: PASS. Runtime: Python 3.12.14, DuckDB 1.1.3, PyArrow 25.0.1.
- Immutable input: Analysis generation analysis-v1_4-canonical-20260928-02; manifest generations/analysis-v1_4-canonical-20260928-02/manifest.json SHA-256 e9c391e76fac86a15526e8ab453558e68fc00400a18674e26edf64aad9feec9e; fact_entry_result_lite; 11 partitions; 517,622 rows; date coverage 2016-01-05 through 2026-09-27. Upstream run 36437363166, artifact jrdb-post-race-parquet-refresh-36437363166, digest sha256:d159c2fca9959d9b144d55f9b3ba98228158cc38b85fcc730032a53f29252a55.
- Real Horse History query: audit-only horse ID 13105621; 7 rows returned in chronological order, exact horse filtering and unique (race_key, horse_no) identity checks passed. Inclusive 2016-01-05 to 2016-01-05 query returned one row under limit=1; provenance reports the canonical generation. The resolver validated the immutable manifest and all Parquet assets before querying.
- Two initial fallback executions failed on the helper's assumption that the candidate pointer was already CURRENT; the helper was corrected to validate SHADOW_PASS and materialize an execution-local current pointer. The successful retry is the evidence above. No publication pointer or production consumer changed.

## Equivalence and profile results

- v0.2 STANDARD parity: **PASS** on deterministic fixture; matched edge IDs, performance/value evidence levels, matched conditions, and presentation roles match `jrdb_edge_matcher_v0_2.match_runner(..., profile=STANDARD)`.
- v0.4 parity: **PASS** for frozen cohort membership fixture; query returns the same cohort ID after using the factored pure v0.4 predicate.
- Profile visibility: **PASS** — STANDARD includes STANDARD only; STANDARD_PLUS_SHADOW adds SHADOW; RESEARCH_ALL adds OBSERVE_ONLY. Observe-only signals are explicitly non-production eligible and carry `UNASSESSED` value evidence.
- Horse History exact lookup: **PASS** on the SQLite compatibility backend fixture and on canonical Analysis Parquet/DuckDB using the real query above.
- Production consumer migration: **NONE**.

## Consumer migration map

| consumer | current input | future input | required adapter delta | parity test | risk |
|---|---|---|---|---|---|
| `racenote_edge_performance_adapter.py` | v0.2 `edge_matches` keyed by `race_horse_key` | `edgedb-query/v1` STANDARD signals | Map eligible performance signals and evidence/presentation fields to RaceNote's existing adapter row; retain exact runner key and current evidence gates. | Same runner keys, edge IDs, performance eligibility, score inputs, and serialized forecast for frozen days. | Score or mark changes if lifecycle/evidence gates are weakened. |
| `jrdb_newspaper_edge_adapter.py` | v0.2 registry and matcher output; adapter applies existing serving eligibility | `edgedb-query/v1` STANDARD signals | Convert only currently eligible STANDARD signals to the adapter's reader-facing payload; keep rendering outside the matcher. | Same runner set, displayed signal IDs/text, evidence eligibility, and payload snapshots. | Accidental display of SHADOW/OBSERVE_ONLY or text drift. |
| `jrdb_newspaper_merge_edge.py` | exact join between newspaper rows and v0.2 `edge_matches` | query rows joined by `race_horse_key` | Replace source-row shape with normalized signal projection; preserve exact join and no-recalculation behavior. | Join cardinality, matched runner keys, and final merged JSON parity on frozen publication fixtures. | Join loss/duplication or output-shape changes. |
| related operational runbooks | generation-specific source paths and commands | manifest revision, query profile, stable schema | Document source refresh, profile selection, provenance checks, and rollback to the existing generation-specific commands during rollout. | Dry-run command and artifact hash comparison before a consumer change. | Stale manifest/artifacts or rollback ambiguity. |

## Acceptance state

- Instruction 010 acceptance gate: **PASS** with the canonical Analysis Parquet fallback and focused tests.
- Production consumer migration: **NONE**; RaceNote/PWA remain unchanged.
- PR #1822 remains unmerged under its merge hold, pending review.
