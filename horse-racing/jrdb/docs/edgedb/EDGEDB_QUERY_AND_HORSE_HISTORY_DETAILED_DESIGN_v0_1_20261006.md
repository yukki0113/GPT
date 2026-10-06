# EdgeDB Query / Horse History Query Detailed Design v0.1

Date: 2026-10-06  
Status: DESIGN APPROVED FOR IMPLEMENTATION  
Scope: JRDB / EdgeDB / RaceNote / PWA Newspaper / Backtest / Chat  
Production impact of this document: NONE

## 1. Goal

Create one stable query boundary above the evolving EdgeDB research/serving implementations.

Consumers must no longer need to know whether the current Edge implementation is v0.2, v0.3, v0.4, or a later generation.

The common operational model is:

```
JRDB pre-race facts
      |
      v
EdgeDB Query  <---- current_manifest.json
      |
      +---- STANDARD source(s)
      +---- SHADOW source(s)
      +---- OBSERVE_ONLY source(s)
      |
      v
stable EdgeSignal[] contract
      |
      +---- Backtest
      +---- Chat
      +---- RaceNote adapter
      +---- Newspaper/PWA adapter
```

A separate Horse History Query provides fast horse-centric history lookup:

```
horse_id
   |
   v
Horse History Query
   |
   +---- Analysis / Warehouse scan
   +---- optional exact result/payout enrichment
   |
   v
chronological starts[]
```

The two query tools share JRDB identities but have different responsibilities.

## 2. Identity contract

Do not create a new horse identity scheme.

### 2.1 Stable horse identity

`horse_id`

Meaning: one physical horse across races.

Primary use:

- horse history;
- cross-race analysis;
- Chat lookup;
- longitudinal RaceNote evidence.

### 2.2 Stable runner identity

`race_horse_key`

Meaning: one horse in one specific race.

Primary use:

- Edge matching;
- Newspaper/PWA exact join;
- RaceNote exact join;
- backtest freeze/result join.

### 2.3 Race identity

`race_key`

Supplement with:

- race_date;
- venue_code;
- race_no;
- horse_no.

A query result must preserve all available identity fields.

## 3. Design principle: query contract version != research generation

The public query contract is stable and independent from Edge research generations.

Use:

- EdgeDB query schema: `edgedb-query/v1`
- Horse history schema: `jrdb-horse-history/v1`
- Manifest schema: `edgedb-current-manifest/v1`

Never expose a consumer-facing API contract such as `edgedb-query-v0.2`.

Research/source generations remain metadata:

- `source_generation: "v0.2"`
- `source_generation: "v0.3"`
- `source_generation: "v0.4"`

This prevents the historical problem where implementation files moved from 0.2.0 to 0.2.1/0.2.2 while an operational wrapper continued reporting an older semantic generation.

## 4. Canonical manifest

Create:

`horse-racing/jrdb/config/edgedb/current_manifest.json`

The query tool must not hard-code a specific registry/cohort path as the operational source of truth.

### 4.1 Manifest responsibilities

The manifest declares:

- query contract version;
- manifest revision;
- latest known EdgeDB generation;
- active source definitions;
- lifecycle per source;
- matcher adapter type;
- source path;
- source semantic generation;
- serving eligibility;
- display eligibility;
- whether the source may affect prediction logic;
- source SHA/fingerprint metadata when available.

### 4.2 Initial lifecycle model

Supported lifecycle values:

- `STANDARD`
- `SHADOW`
- `OBSERVE_ONLY`

Meaning:

#### STANDARD

Allowed for existing operational serving subject to the source's existing evidence/profile gates.

#### SHADOW

Matched and returned for diagnostics/research but must not silently affect production marks or prediction decisions.

#### OBSERVE_ONLY

Research observation only. Returned only when explicitly requested by a research-capable profile. Never production eligible.

### 4.3 Initial profile model

The stable EdgeDB Query accepts:

- `STANDARD`
- `STANDARD_PLUS_SHADOW`
- `RESEARCH_ALL`

Profile semantics:

```
STANDARD
  include lifecycle STANDARD only

STANDARD_PLUS_SHADOW
  include STANDARD + SHADOW

RESEARCH_ALL
  include STANDARD + SHADOW + OBSERVE_ONLY
```

The profile controls source visibility, not condition semantics.

### 4.4 Manifest fail-closed rules

Fail if:

- schema version unsupported;
- source path missing;
- source lifecycle unsupported;
- adapter type unsupported;
- required source hash/fingerprint mismatches;
- two source entries claim the same immutable source identity with contradictory lifecycle;
- manifest references a generation that cannot be loaded.

Do not silently fall back to an older generation.

## 5. EdgeDB Query

Create:

`horse-racing/jrdb/src/jrdb_edgedb_query.py`

This becomes the only supported consumer-neutral query boundary.

Existing generation-specific matchers remain internal adapters.

### 5.1 Supported inputs

Two modes.

#### A. Canonical facts mode

Caller supplies one or more runner fact rows already compatible with Edge dimensions.

Required identity when available:

- race_date;
- race_key;
- race_horse_key;
- horse_id;
- horse_no.

#### B. PACI mode

Caller supplies PACI plus Analysis history source.

The tool reuses existing current-fact builders rather than reimplementing PACI parsing.

Preferred internal builder:

`build_jrdb_edge_current_facts_v0_2.py`

until a newer superset builder is explicitly promoted.

The important point is that the builder implementation may evolve while the query contract remains stable.

### 5.2 Source adapter architecture

Do not make one giant matcher.

Define internal source adapters behind a common interface:

```
load(source_spec)
match(runner_fact) -> source_match[]
normalize(source_match) -> EdgeSignal
```

Initial adapters:

#### Registry adapter

For current v0.2 / v0.3 registry-style rows.

Reuse:

- `jrdb_edge_matcher.py`
- `jrdb_edge_matcher_v0_2.py`

Do not duplicate condition logic.

#### Observe cohort adapter

For v0.4 frozen 347-row cohort.

Reuse condition semantics from:

- `jrdb_edge_v04_observe_cohort.py`
- `jrdb_edge_v04_observe_shadow.py`

Do not use the prospective freeze writer for ordinary per-runner query; factor/reuse the pure matching primitive.

### 5.3 Stable EdgeSignal output

Each signal should normalize to at least:

```json
{
  "signal_id": "...",
  "source_generation": "v0.4",
  "source_lifecycle": "OBSERVE_ONLY",
  "source_id": "...",
  "family": "PEDIGREE_CROSS",
  "status": "OBSERVE_ONLY",
  "production_eligible": false,
  "performance": {
    "signal": "MATCH",
    "evidence_level": "OBSERVE_ONLY"
  },
  "value": {
    "signal": "UNASSESSED",
    "evidence_level": "OBSERVE_ONLY"
  },
  "presentation": {
    "performance_role": "NONE",
    "value_role": "NONE",
    "conflict": false
  },
  "matched_conditions": [],
  "audit": {}
}
```

For v0.2/v0.3, map existing performance/value evidence and presentation fields without losing information.

For v0.4 observe-only:

- performance.signal = `MATCH`;
- value.signal = `UNASSESSED`;
- evidence level = `OBSERVE_ONLY`;
- production_eligible = false;
- retain cohort_id/candidate_id/template_id/fingerprint in audit.

Do not invent positive/negative semantics for v0.4 where the cohort only means historical incremental membership.

### 5.4 Query response

One runner response:

```json
{
  "schema_version": "edgedb-query/v1",
  "query_engine_version": "1.0.0",
  "manifest_revision": "...",
  "profile": "RESEARCH_ALL",
  "key": {
    "race_date": "2026-10-04",
    "race_key": "...",
    "race_horse_key": "...",
    "horse_id": "...",
    "horse_no": 7
  },
  "signals": [],
  "source_audit": []
}
```

The output is deterministic for the same:

- manifest bytes;
- source bytes;
- runner facts.

### 5.5 Sorting

Stable sort order:

1. lifecycle: STANDARD, SHADOW, OBSERVE_ONLY;
2. source generation semantic order from manifest;
3. existing source-level presentation precedence where defined;
4. stable source ID / signal ID.

No ROI/popularity sorting in pre-race query.

### 5.6 CLI

Required examples:

```bash
python horse-racing/jrdb/src/jrdb_edgedb_query.py \
  --manifest horse-racing/jrdb/config/edgedb/current_manifest.json \
  --facts-jsonl facts.jsonl \
  --profile RESEARCH_ALL \
  --output-jsonl edge-query.jsonl
```

and:

```bash
python horse-racing/jrdb/src/jrdb_edgedb_query.py \
  --manifest ... \
  --paci PACI.zip \
  --analysis-root ... \
  --profile STANDARD \
  --output-jsonl edge-query.jsonl
```

Optional filters:

- `--race-horse-key`
- `--horse-id`
- `--only-matched`

Filtering may restrict output rows but must not change source matching semantics.

## 6. Horse History Query

Create:

`horse-racing/jrdb/src/jrdb_horse_history_query.py`

Goal: quickly return historical starts for one horse without scanning raw ZIP files date by date.

### 6.1 Primary source

Use canonical Analysis/Parquet or accepted normalized Warehouse where possible.

Preferred first implementation:

- resolve current Analysis Parquet generation;
- DuckDB predicate `horse_id = ?`;
- sort by race_date/race_key/horse_no.

Do not build a new persistent DB merely for this query unless benchmarks prove necessary.

### 6.2 Minimal response row

Return:

- horse_id;
- race_date;
- race_key;
- race_horse_key if reconstructible/canonical;
- venue_code if derivable;
- race_no if derivable;
- horse_no;
- track/surface;
- distance;
- frame_no;
- finish;
- final popularity/odds if the canonical fact table contains them;
- win/place payout if present;
- source generation/provenance.

Do not fabricate unavailable values.

### 6.3 Optional payout enrichment

The fast path should be a single Analysis/Warehouse scan.

Full race payout maps are optional and should be requested explicitly, e.g.:

`--include-race-payouts`

When enabled, reuse `jrdb_result_query.py`.

Do not embed a second independent HJC parser.

### 6.4 Query filters

Support:

- `--horse-id` required;
- `--from-date`;
- `--to-date`;
- `--limit`;
- ascending/descending chronological order.

Potential future extension:

- horse name lookup to horse_id is separate and must not be silently fuzzy inside the core query.

### 6.5 Response

```json
{
  "schema_version": "jrdb-horse-history/v1",
  "horse_id": "...",
  "source": {...},
  "start_count": 12,
  "starts": [...]
}
```

## 7. Backtest integration

Backtest must use the same EdgeDB Query as live/current serving.

Historical blind replay flow:

```
historical pre-race PACI/facts
      |
      v
jrdb_edgedb_query.py --profile RESEARCH_ALL
      |
      v
freeze query output + manifest SHA + fact SHA
      |
      v
open historical result source only after freeze
      |
      v
join on race_horse_key / exact race+horse identity
      |
      v
metrics
```

Past dates are allowed.

They are labelled:

- `HISTORICAL_BLIND_REPLAY`

not:

- `TRUE_FORWARD`.

The historical date itself is never a blocker.

Leakage separation remains mandatory.

## 8. RaceNote integration

RaceNote must not call v0.2/v0.3/v0.4 matchers directly after migration.

Flow:

```
EdgeDB Query
  |
  v
RaceNote Edge adapter
  |
  v
RaceNote evidence
```

Existing:

`racenote_edge_performance_adapter.py`

should be extended or fronted by a new thin adapter for `edgedb-query/v1`.

Rules:

- STANDARD signals may follow existing policy;
- SHADOW signals remain diagnostic unless existing RaceNote policy explicitly permits them;
- OBSERVE_ONLY signals never alter Forecast marks/scores;
- RaceNote may display OBSERVE_ONLY as research context if explicitly enabled.

No consumer-side rematching.

## 9. Newspaper / PWA integration

The browser/PWA must not run Python matching logic.

Preferred deployment:

```
PACI / facts
   |
server/build step
   |
EdgeDB Query
   |
normalized edge-query JSONL
   |
Newspaper adapter
   |
day-package
   |
PWA
```

Existing Newspaper merge philosophy is retained:

"Edge conditions are never recalculated here."

The Newspaper adapter should consume the stable query contract and convert eligible signals to display memos.

Suggested display policy:

- STANDARD: normal current display behavior;
- SHADOW: only if research/debug display enabled;
- OBSERVE_ONLY: hidden by default in public/normal newspaper; optional research badge/memo in research mode.

Do not let OBSERVE_ONLY affect horse marks.

## 10. Manifest migration and generation ownership

Codex must identify the actual canonical current sources for v0.2 STANDARD and v0.3 SHADOW from existing publication/config/runbooks.

Do not guess a registry path.

The initial manifest should contain only verified canonical sources.

The already verified v0.4 source is:

`horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_v0_1.json`

with:

- lifecycle `OBSERVE_ONLY`;
- generation `v0.4`;
- expected cohort rows 347;
- fingerprint-set SHA `ad0cf386601fb0366db27197072205c565eef189fa2e1062a97702f4b30f4876`.

If v0.2/v0.3 canonical publication location is ambiguous, fail closed and report the ambiguity before wiring the manifest.

## 11. Version policy

There are three independent versions.

### Query engine version

Code release of `jrdb_edgedb_query.py`.

Example: `1.0.0`.

### Query schema version

Stable response contract.

`edgedb-query/v1`.

Breaking JSON contract change => v2.

### Edge source generation

Scientific/registry generation.

Examples v0.2, v0.3, v0.4.

A source-generation bump does not imply a query-schema bump.

This separation is mandatory.

## 12. Test strategy

### Manifest tests

- unsupported schema rejected;
- missing source rejected;
- hash/fingerprint mismatch rejected;
- lifecycle/profile visibility exact;
- source ordering deterministic.

### EdgeDB Query tests

- same input => byte-stable normalized output;
- STANDARD excludes SHADOW/OBSERVE_ONLY;
- STANDARD_PLUS_SHADOW excludes OBSERVE_ONLY;
- RESEARCH_ALL includes all;
- v0.2/v0.3 normalized fields preserve existing matcher semantics;
- v0.4 exact condition matching equals observe matcher;
- no odds/popularity/result field affects pre-race membership;
- race_horse_key and horse_id filters do not change match result for retained rows.

### Horse History tests

- horse_id exact filter;
- chronological ordering;
- date bounds;
- no other horse leakage;
- duplicate start guard;
- parity with known Analysis rows;
- optional result-query enrichment does not mutate base start identity.

### Consumer parity tests

For a fixed current fixture:

- old operational v0.2 matcher STANDARD output;
- new EdgeDB Query STANDARD normalized back to legacy adapter shape;

must be semantically equivalent before migration.

Newspaper and RaceNote integration should have fixture equivalence tests for STANDARD mode.

## 13. Performance targets

These are engineering targets, not scientific requirements.

For already-local Analysis/registry assets:

- one horse history query should avoid whole raw ZIP iteration;
- one race-day EdgeDB query should load each configured source once, not once per horse;
- matching should process all runners in one pass;
- source artifacts should be cached in-process for repeated runner queries.

No persistent cache should weaken manifest/source SHA validation.

## 14. Migration plan

### Phase A — foundation

Implement:

1. `current_manifest.json`
2. `jrdb_edgedb_query.py`
3. `jrdb_horse_history_query.py`
4. tests.

No consumer migration yet.

### Phase B — equivalence

Prove STANDARD equivalence against current v0.2 operational path on fixtures/one known day.

Prove v0.4 RESEARCH_ALL matches the 347-row matcher semantics.

### Phase C — consumers

Move:

1. Newspaper adapter/build;
2. RaceNote adapter;
3. Chat/backtest runbooks

to EdgeDB Query.

Generation-specific matchers remain internal compatibility modules.

### Phase D — deprecation

Mark direct consumer use of:

- `run_jrdb_edge_match_current_v0_2.py`
- generation-specific matcher CLIs

as compatibility-only.

Do not delete them until parity and rollback windows are complete.

## 15. Acceptance criteria

The design is implemented successfully when:

- one manifest controls which Edge sources are queried;
- one stable query returns normalized signals from all allowed lifecycles;
- PWA/RaceNote/backtest no longer need Edge generation-specific matching semantics;
- v0.4 347 OBSERVE_ONLY definitions are queryable but cannot affect production by default;
- horse_id can retrieve a chronological result/start history efficiently;
- STANDARD parity with current operational output is demonstrated;
- past-day blind replay can use the same query path without result leakage;
- source generation updates do not require consumer code changes unless the matcher semantics themselves introduce a genuinely new condition type.
