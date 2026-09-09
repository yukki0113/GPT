# JRDB Newspaper Neutral Dependency Inventory v0.1

Status: DESIGN ACCEPTED / IMPLEMENTATION PRECHECK

## 1. Purpose

JRDB PWA向け自分用競馬新聞（Newspaper）のJRDB Base / historyを、RaceNote内部実装へ依存させず構築するための依存棚卸し。

NewspaperとRaceNoteは兄弟consumerとし、依存方向を次に固定する。

```text
JRDB Raw / PACI
  -> neutral JRDB layer
       -> RaceNote adapter
       -> Newspaper adapter
```

禁止:

```text
RaceNote bundle -> Newspaper JRDB Base/history
racenote_* internal module -> Newspaper JRDB Base/history
```

RaceNote predictionの完成成果物（印・短評等）は、後段のexternal addonとしてのみNewspaperへmerge可能とする。

## 2. Newspaper v0.1 needs

### Target race / current runner

- race date / venue / race no / start time
- race name / surface / distance / turn / course layout
- race type / class / grade / weight rule / field size
- frame / horse no / horse name
- sex / age
- carried weight
- jockey / trainer
- sire / dam / broodmare sire
- running style / distance aptitude
- JRDB pre-race ability fields / marks
- training score / arrow / workout material
- pace / expected-position material

### Historical run

Initial visible = 3 runs; bundle target maximum = 8 runs.

Desired detailed recent fields:

- date / venue / race no / race name / class / grade
- surface / distance / actual track condition
- finish / field size / popularity
- jockey / carried weight
- corner positions
- time / first3f / last3f
- IDM / selected result indices
- body weight / change
- abnormal code

Older 6-8 runs may be compact if exact detailed source is not cheaply available.

## 3. Existing neutral modules — direct dependency allowed

### 3.1 `src/jrdb_raw.py`

Role: fixed-width source truth / neutral parser.

Supported families include:

- BAC
- KYI
- CHA
- CYB
- SED / ZED
- SKB / ZKB
- UKC

Policy:

- Newspaper may import `Parser`, archive iteration and key helpers directly.
- Newspaper must not introduce independent fixed-width offsets for fields already supported here.
- New Raw fields must be added here first with characterization/regression tests.

This is the primary Newspaper raw-data dependency.

### 3.2 `src/jrdb_raw_history.py`

Role: consumer-neutral cross-year history access on top of Common Reader.

Current useful API:

- `get_horses_runs(...)`
- `get_horse_runs(...)`
- exclusive `before` date
- batch scan for multiple horse IDs
- newest-first selection
- configurable run limit

It returns parsed SED plus provenance and is explicitly suitable for RaceNote **and other consumers**.

Direct Newspaper use is allowed.

Limitation:

- current implementation resolves the standard annual `SED/SED_YYYY.zip` layout.
- season-in-progress history may require PACI ZED and/or Analysis Lite compact fallback if an annual current-year SED archive is not present.

### 3.3 `src/jrdb_store.py`

Role: verified artifact resolver/cache for large shared artifacts.

Direct Newspaper use is allowed in local/CLI environments when appropriate, while GPT/Work may continue using the existing Google Drive adapter policy.

### 3.4 Analysis Lite schema/artifact

Analysis Lite is a shared JRDB production artifact, not a RaceNote-owned store.

Newspaper may query it directly for compact older history or supplemental identity when that is cheaper than Raw history scanning.

Rules:

- Newspaper owns its own SQL projection.
- do not call `racenote_history_engine.py` for Analysis queries.
- always enforce `race_date < target_date` for history.
- missing detail stays null; do not fabricate values absent from Analysis.

## 4. Existing modules — reference allowed, runtime dependency not preferred

### 4.1 `src/jrdb_index_base_adapter.py`

This module is technically clean in that it uses `jrdb_raw.Parser` and contains no fixed-width offsets. It demonstrates validated normalization for BAC/KYI/SED/CHA/CYB/UKC and is useful as a field/typing reference.

However it projects specifically into the Index Base schema.

Decision for Newspaper v0.1:

- **do not make Newspaper runtime depend on the Index Base adapter.**
- use it as a regression/reference source when defining Newspaper-owned projection.
- if a normalization primitive proves genuinely consumer-neutral, promote that primitive to a neutral `jrdb_*` helper and let both adapters use it.

Reason: Newspaper should not become an Index-project derivative any more than a RaceNote derivative.

### 4.2 Index Base SQLite

Validated 2010-2025 Index Base is excellent research/history evidence and preserves detailed pre/result/workout/profile data.

Accepted audit characteristics include:

- 781,161 runner rows
- 100% runner/result match
- previous-link resolution 93.8538%
- integrity check ok
- accepted DB size about 1.73 GB

Decision:

- useful for offline research, regression comparison and Edge/index consumers.
- **not a mandatory per-day Newspaper input** because transferring/resolving ~1.7 GB for routine newspaper generation is disproportionate.

## 5. Logic currently inside RaceNote that must NOT be imported directly

### 5.1 PACI previous-run assembly

RaceNote currently contains logic that combines KYI previous links with ZED/ZKB into detailed `recent_runs`.

This concept is JRDB-generic, but the existing implementation is RaceNote-shaped.

Decision:

- Newspaper must not import the RaceNote implementation.
- before sharing, extract neutral previous-link resolution into a new neutral module candidate such as:

```text
src/jrdb_paci_history.py
```

Neutral responsibilities only:

- collect KYI `previous[1..5]` result/race keys
- map ZED by result key
- optionally map ZKB by result key
- preserve requested sequence
- enforce run date `< target_date`
- expose unresolved-link diagnostics
- return neutral parsed records / provenance, not RaceNote JSON

If introduced, RaceNote should be migrated to the neutral resolver and regression-tested before Newspaper relies on it as shared logic.

### 5.2 Analysis older-history selection

`racenote_history_engine.py` contains useful SQL ideas such as selecting rows older than detailed recent runs, but its output and policies are RaceNote-oriented.

Decision:

- do not import it from Newspaper.
- Newspaper may implement its own simple compact query directly against Analysis for PoC.
- if both consumers need exactly the same selection semantics, extract a neutral query helper candidate:

```text
src/jrdb_analysis_history.py
```

which returns neutral rows rather than RaceNote schema objects.

### 5.3 Stats Mart enrichment

RaceNote's sire/jockey/frame stats enrichment is not required for the initial Newspaper general-newspaper display.

Decision: defer. Newspaper must not import RaceNote stats enrichment simply because it exists.

## 6. Candidate generic promotion: labels / normalization

Multiple consumers currently carry overlapping code-to-label mappings such as:

- JRA venue code
- surface
- turn / course layout
- race type
- class
- grade
- weight rule
- running style
- track condition
- training arrow etc.

For Newspaper v0.1, duplicating fixed-width offsets is forbidden; duplicating a small display mapping is less dangerous but still undesirable if semantics are meant to be identical.

Candidate neutral module:

```text
src/jrdb_labels.py
```

Possible responsibilities:

- stable code -> Japanese display label
- no consumer schema
- unknown code -> null/original + diagnostic policy chosen by caller

This promotion is useful but is not required to block the first structural Newspaper PoC. It should be introduced when a concrete shared mapping set is identified and accompanied by consumer regression tests.

## 7. Newspaper-owned logic

The following stays inside the Newspaper module and must not be promoted merely for convenience.

### 7.1 Newspaper projection

Common Reader neutral facts -> Newspaper schema:

```text
race
horses[].basic
horses[].jrdb
horses[].history
```

This projection is Newspaper-specific.

### 7.2 Addon merge

- Eval -> `addons.eval`
- RaceNote prediction output -> `addons.racenote_prediction`
- keibailuka -> `addons.keibailuka`
- independent index -> `addons.my_index`
- Edge Registry -> `edge_matches`

Namespace ownership and idempotent merge are Newspaper responsibilities.

### 7.3 Daily manifest / publishing / OPFS

These are Newspaper delivery concerns and remain independent of RaceNote.

## 8. Recommended v0.1 data path

### Current race and first 5 historical runs

```text
PACI
  -> jrdb_raw.py
     BAC  -> race header
     KYI  -> current runner + previous links
     CHA  -> main workout
     CYB  -> training analysis
     UKC  -> pedigree/profile
     ZED  -> detailed historical result rows
     ZKB  -> optional historical comments/material
  -> Newspaper-owned projection
```

No RaceNote bundle or converter is involved.

### Older runs 6-8

Preferred PoC fallback:

```text
Analysis Lite
  -> Newspaper-owned `race_date < target_date` compact history query
```

Alternative/longer-term:

```text
jrdb_raw_history.py
  -> annual SED history
```

Use the cheapest validated path available for the target season; source layer must be recorded per history row.

## 9. Source-layer marker in Newspaper schema

Each history row should preserve a source layer, for example:

```text
paci_previous_detail
analysis_compact
raw_sed_history
```

This is important because 1-5 and 6-8 may have different field density.

Do not imply that a compact row is missing data due to parser failure when the source contract itself does not provide that field.

## 10. Leakage / as-of contract

Target-race Newspaper Base is pre-race.

Forbidden for the target race:

- target finish
- target final odds/popularity
- target payout
- target final track condition
- target result indices

Historical rows may use finalized result information only when:

```text
history_date < target_date
```

UKC/profile selection for historical reconstruction must not select a future observation.

## 11. First implementation sequence

### P0 — complete

- module boundary
- Newspaper race/manifest draft schemas
- RaceNote-derivative dependency explicitly prohibited
- this neutral dependency inventory

### P1 — neutral previous-history resolver

Characterize current RaceNote previous-link behavior and extract consumer-neutral key resolution if necessary.

Acceptance:

- no `racenote_*` dependency in neutral module
- KYI previous ordering preserved
- ZED/ZKB exact key match
- unresolved diagnostics
- as-of fail-closed
- RaceNote behavior regression if RaceNote migrates to shared helper

### P2 — Newspaper JRDB Base builder synthetic PoC

Inputs:

- one synthetic PACI ZIP
- optional synthetic Analysis SQLite

Output:

- one Newspaper race JSON

Acceptance:

- schema valid
- headcount exact
- current fields from BAC/KYI/CHA/CYB/UKC
- detailed history up to 5 from ZED/ZKB
- compact older rows optional up to total 8
- all addons null/PENDING
- no `racenote_*` imports

### P3 — real-data PoC

Candidate:

```text
2026-08-16 札幌11R 札幌記念
```

Measure:

- JSON bytes
- per-horse history counts/source layers
- null distributions by field
- target/headcount identity
- 3/5/8-run UI suitability

### P4 — PWA display PoC

Only after P3 data contract is reviewed.

## 12. Current architectural judgment

**GO.**

Newspaper does not need RaceNote as a parent data product. Existing neutral JRDB infrastructure is sufficient to begin an independent builder.

The only material shared-logic question before implementation is detailed PACI previous-link assembly. That should either be implemented directly as a new neutral helper and shared by both consumers, or kept as a Newspaper-owned projection over Common Reader if semantic behavior intentionally differs. Direct import from RaceNote is not permitted.
