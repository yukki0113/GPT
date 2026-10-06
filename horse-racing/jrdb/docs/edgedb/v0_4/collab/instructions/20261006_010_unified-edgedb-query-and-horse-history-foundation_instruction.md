# 20261006_010 — Unified EdgeDB Query / Horse History Foundation

Status: TODO  
Date: 2026-10-06  
Design authority: ChatGPT  
Execution worker: Codex  
Production impact: NONE until explicit consumer migration

## Objective

Implement Stage A/B of the unified EdgeDB / horse-history query architecture defined in:

`horse-racing/jrdb/docs/edgedb/EDGEDB_QUERY_AND_HORSE_HISTORY_DETAILED_DESIGN_v0_1_20261006.md`

The primary goal is to create one stable consumer-neutral EdgeDB query boundary and one fast horse-centric history query.

Do not migrate RaceNote or Newspaper/PWA serving in this task unless needed only for non-production parity fixtures.

## Required repository reading

Before changes, read at minimum:

- detailed design above;
- `horse-racing/jrdb/README.md`;
- `.gpt/GITHUB_OPERATION_POLICY.md`;
- `tools/data-storage/README.md`;
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`;
- `horse-racing/jrdb/src/jrdb_edge_matcher.py`;
- `horse-racing/jrdb/src/jrdb_edge_matcher_v0_2.py`;
- `horse-racing/jrdb/src/run_jrdb_edge_match_current_v0_2.py`;
- `horse-racing/jrdb/src/build_jrdb_edge_current_facts_v0_2.py`;
- `horse-racing/jrdb/src/jrdb_edge_v04_observe_cohort.py`;
- `horse-racing/jrdb/src/jrdb_edge_v04_observe_shadow.py`;
- `horse-racing/jrdb/src/jrdb_edge_analysis_history.py`;
- `horse-racing/jrdb/src/jrdb_result_query.py`;
- existing RaceNote/Newspaper Edge adapters for compatibility constraints.

## Mandatory source discovery

Before writing `current_manifest.json`, identify and document the canonical current source for:

1. v0.2 STANDARD serving;
2. v0.3 SHADOW serving;
3. v0.4 OBSERVE_ONLY cohort.

v0.4 is already known:

`horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_v0_1.json`

Expected:

- rows: 347
- fingerprint-set SHA-256:
  `ad0cf386601fb0366db27197072205c565eef189fa2e1062a97702f4b30f4876`

For v0.2/v0.3, use repository publication/config/runbook evidence. Do not guess filenames.

If canonical v0.2 or v0.3 source is ambiguous, record the ambiguity and fail closed before claiming manifest completion. It is acceptable to implement the query engine with fixtures and a partial manifest only if the result clearly says manifest source resolution is BLOCKED.

## Stage A — manifest and stable query contract

### A1. Manifest

Create:

`horse-racing/jrdb/config/edgedb/current_manifest.json`

Schema:

`edgedb-current-manifest/v1`

Required top-level fields:

- schema_version
- manifest_revision
- query_contract = `edgedb-query/v1`
- latest_generation
- sources
- generated_from
- production_impact = NONE

Each source requires:

- source_key
- source_generation
- lifecycle: STANDARD / SHADOW / OBSERVE_ONLY
- adapter_type
- path
- enabled
- production_eligible
- display_eligible_default
- prediction_eligible_default
- expected_sha256 or semantic identity/fingerprint where available
- notes/provenance

The manifest is the operational source of truth for source selection.

Do not encode source selection inside `jrdb_edgedb_query.py`.

### A2. Unified query implementation

Create:

`horse-racing/jrdb/src/jrdb_edgedb_query.py`

Required contract:

- schema `edgedb-query/v1`
- query engine version starts at `1.0.0`
- profiles:
  - STANDARD
  - STANDARD_PLUS_SHADOW
  - RESEARCH_ALL
- input modes:
  - `--facts-jsonl`
  - `--paci` with existing Analysis source options
- filters:
  - `--race-horse-key`
  - `--horse-id`
  - `--only-matched`
- output JSONL.

### A3. Adapter rules

Implement internal adapters rather than reimplementing scientific semantics.

#### Registry adapter

Reuse current matcher modules.

Preserve:

- current profile/status eligibility;
- evidence levels;
- performance/value signals;
- presentation role/conflict;
- existing condition semantics.

#### v0.4 observe adapter

Reuse/factor the pure condition-match behavior of:

`jrdb_edge_v04_observe_shadow.py`

Do not call result-evaluation logic.

Normalized v0.4 signal:

- lifecycle OBSERVE_ONLY
- status OBSERVE_ONLY
- production_eligible false
- performance.signal MATCH
- performance.evidence_level OBSERVE_ONLY
- value.signal UNASSESSED
- value.evidence_level OBSERVE_ONLY
- audit includes:
  - cohort_id
  - candidate_id
  - template_id
  - condition_fingerprint
  - historical_source

Do not infer positive/negative betting meaning.

### A4. Stable output

One runner row must include:

- schema_version
- query_engine_version
- manifest_revision
- profile
- key
- signals
- source_audit

Identity key should preserve available:

- race_date
- race_key
- race_horse_key
- horse_id
- horse_no

Signals must use stable normalized fields specified in the detailed design.

### A5. Determinism

For identical manifest/source/facts:

- row ordering deterministic;
- signal ordering deterministic;
- JSON serialization deterministic in tests.

Load each source once per process/query, not once per runner.

## Stage B — Horse History Query

Create:

`horse-racing/jrdb/src/jrdb_horse_history_query.py`

Schema:

`jrdb-horse-history/v1`

### B1. Primary backend

Prefer current Analysis Parquet through DuckDB.

Reuse current-generation resolution code rather than maintaining a second current pointer.

Query by exact:

`horse_id = ?`

Do not scan raw SED/HJC ZIPs date by date for the base history response.

### B2. Required CLI

- `--horse-id` required
- one of:
  - `--analysis-root`
  - compatibility `--analysis-db` if practical
- `--from-date`
- `--to-date`
- `--limit`
- `--order asc|desc`
- `--output`
- optional `--pretty`

Optional payout enrichment may be implemented only if it cleanly reuses `jrdb_result_query.py`; otherwise explicitly defer it to a later task.

### B3. Base row contract

Return whatever is truly available from canonical Analysis, including when present:

- horse_id
- race_date
- race_key
- race_horse_key or canonical reconstruction if guaranteed
- venue_code
- race_no
- horse_no
- track/surface
- distance
- frame
- finish
- odds/popularity
- win/place payout
- source provenance

Missing data must be null/omitted, never invented.

### B4. Performance

Use one DuckDB predicate scan over relevant Parquet partitions.

Do not issue one query per start.

No new persistent cache is required in this task.

## Stage C — compatibility/equivalence tests

Do not migrate consumers yet.

### C1. STANDARD matcher parity

Using deterministic fixtures or an existing known day:

Compare:

old:
`run_jrdb_edge_match_current_v0_2.py`

versus:

new:
`jrdb_edgedb_query.py --profile STANDARD`

Normalize the new output back to the existing matcher row semantics and prove:

- same runner identity set;
- same matched edge IDs;
- same performance/value evidence;
- same presentation roles/conflicts.

If a difference is intentional due solely to manifest source scoping, document it and do not call equivalence PASS until approved.

### C2. v0.4 parity

For fixture canonical facts:

- old pure v0.4 observe matcher;
- new `RESEARCH_ALL` v0.4 adapter

must return the same matching cohort IDs/candidate IDs.

### C3. Profile visibility

Test exact lifecycle inclusion:

- STANDARD => STANDARD only
- STANDARD_PLUS_SHADOW => STANDARD + SHADOW
- RESEARCH_ALL => STANDARD + SHADOW + OBSERVE_ONLY

### C4. Manifest fail closed

Tests for:

- bad schema
- missing source
- bad SHA/fingerprint
- unsupported adapter
- unsupported lifecycle
- disabled source excluded
- no silent fallback.

### C5. Horse history tests

At minimum:

- exact horse_id filtering
- chronological order
- date bounds
- limit
- duplicate start guard
- no rows from another horse
- Analysis source provenance
- Parquet dependency error gives repository-standard Data Storage guidance/fallback route.

## Stage D — consumer readiness report only

Audit what must change later in:

- `racenote_edge_performance_adapter.py`
- `jrdb_newspaper_edge_adapter.py`
- `jrdb_newspaper_merge_edge.py`
- related operational runbooks.

Do not switch production consumers in this task.

Produce a concise migration map:

```
consumer
current input
future input
required adapter delta
parity test
risk
```

## Backtest rule clarification

Past dates ARE allowed for blind replay.

Do not block because a target date is historical.

For historical validation:

1. reconstruct/materialize pre-race facts only;
2. run unified EdgeDB Query;
3. freeze output/hash;
4. only then open result data;
5. label the evidence `HISTORICAL_BLIND_REPLAY`.

Only a genuinely not-yet-resulted date is `TRUE_FORWARD`.

Do not conflate these statuses.

## Data Storage

Horse History Parquet/DuckDB work follows:

1. local `.venv-data-storage`;
2. `check-deps`;
3. one normal repair;
4. if blocked by managed proxy/network, use documented Actions fallback.

Do not replace DuckDB with ad-hoc pandas/SQLite solely because local dependencies are missing.

## Expected files

At minimum:

- `horse-racing/jrdb/config/edgedb/current_manifest.json`
- `horse-racing/jrdb/src/jrdb_edgedb_query.py`
- `horse-racing/jrdb/src/jrdb_horse_history_query.py`
- focused tests, suggested:
  - `horse-racing/jrdb/tests/test_jrdb_edgedb_query.py`
  - `horse-racing/jrdb/tests/test_jrdb_horse_history_query.py`
- result:
  `horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261006_010_unified-edgedb-query-and-horse-history-foundation_result.md`

Additional small helper modules are allowed if they reduce coupling.

## Required result report

Record:

- exact source commit;
- canonical v0.2 STANDARD source resolved path/provenance;
- canonical v0.3 SHADOW source resolved path/provenance;
- v0.4 fingerprint verification;
- manifest SHA;
- query engine version/schema;
- Horse History backend and source generation;
- test commands and counts;
- STANDARD parity result;
- v0.4 parity result;
- profile visibility result;
- consumer migration map;
- any BLOCKED item;
- production impact = NONE.

## Acceptance gate

This task is accepted only if:

1. manifest source identities are unambiguous and validated;
2. unified query uses adapters/reuse, not duplicated scientific matching logic;
3. query schema is independent from Edge generation version;
4. STANDARD parity passes;
5. v0.4 parity passes;
6. OBSERVE_ONLY cannot enter STANDARD profile;
7. horse history exact lookup works against canonical Analysis source;
8. tests pass;
9. no RaceNote/PWA production switch was performed.

If accepted, the next task may migrate Newspaper/PWA and RaceNote consumers to the stable query boundary.

## Non-goals

- no new Edge discovery;
- no v0.4 retuning;
- no production promotion;
- no result leakage;
- no deletion of generation-specific compatibility matchers;
- no PWA browser-side matching engine;
- no RaceNote scoring-policy change.
