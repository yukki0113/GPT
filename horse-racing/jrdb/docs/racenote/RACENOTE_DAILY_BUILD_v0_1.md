# RaceNote Daily Build v0.1

Status: **D3 RRDB CONNECTED / D4 READER+VALIDATION+PACKAGE PENDING**
Date: 2026-09-30

## 1. Purpose

RaceNote daily build turns a short operational request such as:

> 「09/27のRaceNote生成してください」

into one deterministic day-level build.

The daily builder is an orchestration layer only. It must not change RaceNote
evidence semantics, Forecast logic, Trend logic, P1/P2 pedigree semantics, or
RRDB semantics.

Final target path:

```text
PACI ZIP
  -> base RaceNote bundles for all races
  -> Analysis history / Trend / P1 / P2 enrichment
  -> formal RRDB enrichment
  -> authoritative RaceNote v1.0
  -> Reader View
  -> round-trip / firewall / provenance validation
  -> daily manifest + validation report
```

No human-in-the-loop handoff is allowed between these stages in normal
operation.

## 2. Non-goals

This project does not:

- change Forecast logic;
- change `RaceNote-Human-Context-Reader-0.3.2`;
- change Trend selection or fallback semantics;
- add pedigree scoring;
- add RRDB scoring;
- change Next-Watch grading;
- expose target result, market, final odds or final popularity;
- replace current one-race builders before equivalence gates pass;
- make intermediate stage files canonical.

## 3. Canonical stage model

The daily build has six stages.

### Stage A — BASE

Input:
- one PACI ZIP for the target date.

Responsibilities:
- parse PACI once;
- build every base RaceNote bundle for the date;
- preserve existing `racenote_jrdb.py` semantics;
- produce base validation metadata in memory.

Stage A must not independently reimplement PACI parsing.

### Stage B — HISTORY

Input:
- all base bundles from Stage A;
- one resolved Analysis canonical backend.

Responsibilities:
- open Analysis once per daily request;
- call the shared bulk enrichment path;
- add historical profile, race trends, P1 pedigree identity and P2 pedigree
  context;
- preserve strict as-of-exclusive behavior.

The intended implementation is the existing
`racenote_history_enrichment.enrich_production_many()`.

### Stage C — RRDB

Input:
- Stage B bundles;
- one resolved RaceReviewDB generation;
- one loaded frozen Next-Watch contract.

Responsibilities:
- resolve RRDB CURRENT only once per daily request;
- load the Next-Watch contract only once;
- review historical rows with `race_date < target_date`;
- add per-horse `racereview` blocks;
- never use horse-name fallback;
- preserve existing single-bundle RRDB semantics.

D3 may introduce a bulk API, but it must be semantically equivalent to current
`racenote_rrdb_enrichment.enrich_bundle()`.

### Stage D — READER

Input:
- authoritative RaceNote v1.0 bundles.

Responsibilities:
- build one lossless Reader View per RaceNote;
- verify semantic round-trip for every Reader View;
- never add prediction logic or semantic compression.

### Stage E — VALIDATION

Request-level gates:
- source resolution;
- PACI ZIP integrity;
- Analysis backend availability;
- RRDB source availability when RRDB is required;
- frozen Next-Watch contract validity.

Race-level gates:
- race/horse structural validity;
- target-result firewall;
- historical date boundary;
- provenance;
- Reader View semantic round-trip.

Request-level source failures fail the whole request.
Race-local failures may become `TECHNICAL_SKIP` only when the source itself is
healthy and the failure is isolated to one race.

### Stage F — PACKAGE

Normal output layout:

```text
RaceNote_YYYYMMDD/
  authoritative/
    race_bundle_YYYYMMDD_<venue><race>R.json
  reader/
    racenote_reader_YYYYMMDD_<venue><race>R.json
  manifest.json
  validation_report.json
```

Intermediate Stage A/B/C files are not normal outputs.

A future explicit `--keep-intermediate` debug option may retain them under a
non-canonical debug directory.

## 4. One request = one source resolution

A daily request should perform these expensive operations at most once:

- PACI ZIP parse;
- Analysis backend open;
- RRDB CURRENT resolution;
- Next-Watch frozen-contract load.

Per-race repetition of these operations is considered an implementation smell.

## 5. Authoritative vs Reader output

`authoritative/` contains complete RaceNote v1.0 bundles.

`reader/` contains lossless Reader View projections for Forecast consumption.

Reader View is not a second semantic source of truth. The authoritative bundle
remains the source; Reader View must reconstruct it exactly by semantic hash.

## 6. Manifest contract

Schema:

`schema/racenote_daily_build_manifest_v0_1.json`

Required high-level fields:

- `schema_version`
- `target_date`
- `status`
- `pipeline_version`
- `stages`
- `sources`
- `counts`
- `firewall`
- `validation`
- `artifacts`
- `warnings`
- `errors`

Allowed final status:

- `PASS`
- `PARTIAL_PASS`
- `FAIL`

D1 skeleton plans use `PLANNED`; they are not production manifests.

## 7. Firewall invariants

Daily orchestration must preserve the existing pre-Freeze firewall.

Forbidden in final pre-race RaceNote:

- target race result;
- same-day post-race Review;
- historical row with `race_date >= target_date`;
- final odds / final popularity exposed through a target-day path;
- current market;
- future RRDB rows.

The daily builder must not weaken an existing lower-level firewall in order to
simplify orchestration.

## 8. Equality migration gate

The daily path is not promoted merely because it completes.

For representative already-used/ineligible dates, compare:

```text
existing one-race path
vs
daily orchestrator path
```

For every compared race require:

- same race identity;
- same horse identities;
- same evidence-semantic SHA-256;
- same P1/P2 semantics;
- same RRDB provenance and per-horse semantics;
- same Reader View round-trip result.

Migration hashing deliberately excludes execution-only metadata that is
expected to differ between independent runs:

- `metadata.generated_at`
- local Analysis `path` / `manifest_path`
- Analysis `query_count` / `parquet_scan_count`

These fields remain present in the actual RaceNote artifact; they are ignored
only by the old-vs-daily migration comparator. Evidence/provenance fields such
as Analysis generation, coverage and RaceNote content remain hash-significant.

Any remaining evidence-semantic difference must be explained and explicitly
approved before cutover.

## 9. Error policy

### Request-level FAIL

Examples:
- PACI corrupt / wrong date;
- Analysis canonical cannot be resolved;
- RRDB required but CURRENT cannot be resolved;
- frozen Next-Watch contract invalid;
- output contract cannot be satisfied.

### Race-local TECHNICAL_SKIP

Allowed only for isolated race-level problems after healthy source resolution.

Examples:
- malformed race-local identity;
- irreconcilable race-local structural mismatch.

A local skip must appear in manifest race status and validation report.

## 10. Execution routing

Daily build is deterministic transformation.

When all inputs already exist locally or are materialized through the native
connectors, execute as Route C / pure deterministic execution.

Do not create GitHub Issues or Actions runs merely to orchestrate local RaceNote
building.

Secrets-required PACI acquisition remains a separate Route D concern.
Drive transport remains outside GitHub Actions.

## 11. D1-D5 implementation plan

### D1 — Contract / skeleton

Deliver:
- this contract;
- manifest schema;
- `src/build_racenote_daily.py` skeleton.

Acceptance:
- CLI `--help` contract is stable;
- `--plan` can emit a non-production execution plan;
- production execution is fail-closed as NOT_IMPLEMENTED;
- no existing RaceNote semantic source is modified.

### D2 — Base + Analysis/P1/P2 batch

**IMPLEMENTED.**

Stage A:
- `build_base_bundles()` parses PACI once and reuses the existing
  `racenote_jrdb.Audit / parse_zip / BundleBuilder` implementation.
- requested date must match the PACI BAC date.
- any base bundle-generation error fails D2 rather than silently dropping a race.

Stage B:
- `build_through_history()` opens Analysis once.
- `enrich_history_bundles()` calls
  `racenote_history_enrichment.enrich_production_many()` once for the full day.
- History / Trend / P1 / P2 are therefore produced by the existing canonical
  bulk engine rather than a new daily reimplementation.
- Analysis source/provenance is attached after the bulk run.
- `evidence_semantic_sha256()` supports old-vs-daily migration comparison
  while excluding execution-only telemetry.

D2 stage behavior:
- BASE/HISTORY execute through the shared bulk path;
- D2 can be exercised directly through `build_through_history()`;
- the current public daily CLI now continues into D3 before fail-close;
- `--keep-intermediate` may retain non-canonical debug bundles.

Focused tests:
- `tests/test_racenote_daily_build_d2.py`

D2 acceptance intent:
- PACI parse once;
- Analysis open once;
- bulk history enrichment once;
- execution metadata does not create false migration mismatches;
- evidence changes remain hash-significant.

### D3 — RRDB daily bulk

**IMPLEMENTED.**

RRDB module:
- `racenote_rrdb_enrichment.enrich_bundles()` added.
- all target races must share one target date.
- all daily horse IDs are collected before latest-prior Next-Watch reconstruction.
- `_latest_next_watch()` is therefore called once for the full day.
- shared Next-Watch output is then applied to each race through
  `_apply_bundle_enrichment()`.
- existing single-race `enrich_bundle()` remains backward compatible and now
  delegates to the same apply helper.
- existing RaceReview adapter + Horse Evidence Card semantics are reused rather
  than reimplemented.

Daily orchestrator:
- frozen Next-Watch contract is loaded once.
- RRDB CURRENT is resolved once, or one explicit generation root is opened.
- all Stage B bundles are passed to `rrdb.enrich_bundles()` once.
- RRDB source / generation / rule version are recorded in the D3 report.
- RRDB source failures are request-level FAIL.
- default Next-Watch extraction work is temporary and removed automatically.
- `--keep-intermediate` is required to retain RRDB debug/work output.

Focused tests:
- `tests/test_racenote_daily_build_d3.py`

D3 acceptance intent:
- RRDB source resolution once;
- frozen-rule load once;
- Next-Watch reconstruction once per day;
- single vs bulk semantic equality for the same precomputed evidence;
- no name fallback / no scoring;
- one target-date boundary for the batch.

### D4 — Reader / validation / package

Connect Stages D-F.

Acceptance:
- authoritative and Reader directories produced;
- all Reader Views round-trip;
- manifest and validation report complete;
- no canonical intermediate artifacts.

### D5 — Real-data equivalence / cutover

Use an already-used/ineligible date.

Acceptance:
- daily build completes;
- representative/all-race old-vs-new semantic equality passes;
- docs/HANDOFF/current operation point to daily builder;
- old one-race path remains available for audit/rollback.

## 12. Current operational status

D1 contract is frozen and D2-D3 are connected.

The daily CLI can now execute through:

```text
PACI -> BASE -> HISTORY / Trend / P1 / P2 -> RRDB
```

It intentionally stops before Reader View / final validation / package. It is
not yet the production daily entrypoint.

Until D5 cutover, the existing RaceNote one-race and enrichment entrypoints
remain production truth.

Next implementation turn: **D4 — Reader View + validation + package**.
