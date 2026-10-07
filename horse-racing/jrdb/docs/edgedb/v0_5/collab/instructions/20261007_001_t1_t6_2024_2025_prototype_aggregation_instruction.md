# 20261007_001 — EdgeDB v0.5 T1-T6 2024-2025 Prototype Aggregation

Status: TODO  
Date: 2026-10-07  
Design authority: ChatGPT  
Execution worker: Codex  
Production impact: NONE  
Research generation: EdgeDB v0.5 prototype

## Objective

Implement and execute the first EdgeDB v0.5 prototype aggregation defined in:

`horse-racing/jrdb/docs/edgedb/v0_5/EdgeDB_v0_5_Niche_Value_Memo_Discovery_Design_20261007.md`

The purpose is to answer one question:

> Can the six frozen v0.5 template families over the 2024-2025 discovery window produce concise, human-readable, TARGET-style betting memos that are worth reviewing?

This task is not a production promotion task.

Do not change v0.2 STANDARD, v0.3 SHADOW, v0.4 OBSERVE_ONLY, RaceNote scoring, Newspaper/PWA serving, or `current_manifest.json`.

---

## Required reading

Before implementation/execution, read at minimum:

- `horse-racing/jrdb/docs/edgedb/v0_5/EdgeDB_v0_5_Niche_Value_Memo_Discovery_Design_20261007.md`
- `horse-racing/jrdb/docs/edgedb/v0_4/EdgeDB_v0_4_Research_Execution_Redesign_20261005.md`
- `horse-racing/jrdb/README.md`
- `.gpt/GITHUB_OPERATION_POLICY.md`
- `tools/data-storage/README.md`
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`
- current Analysis / Warehouse / Feature Mart generation resolvers and manifests
- existing v0.4 feature derivation/evaluation modules for reusable pre-race semantics
- `horse-racing/jrdb/src/jrdb_result_query.py`
- `horse-racing/jrdb/src/jrdb_horse_history_query.py`

Reuse existing canonical semantics and data access where valid.

Do not fork a second Parquet/DuckDB utility stack.

---

## Hard research rules

### 1. Discovery window

Candidate membership and primary metrics:

`2024-01-01 <= race_date <= 2025-12-31`

### 2. Historical context window

Background/freshness only:

`2022-01-01 <= race_date <= 2023-12-31`

2022-2023 must never define whether a 2024-2025 candidate exists.

### 3. 2026 exclusion

Do not use any 2026 result in candidate discovery or ranking in this task.

2026 is reserved for later historical blind replay / forward validation.

### 4. Market-blind candidate generation

Forbidden in candidate definition/group membership:

- popularity
- odds
- payout
- favorite rank
- "5th favorite or worse"
- "10x or higher"

These may be joined only after candidate condition membership has been frozen.

### 5. Performance vs betting-return separation

Never collapse occurrence/performance and return/value into one metric.

Keep separate fields and reporting sections for:

Performance / occurrence:
- n
- wins
- places
- win_rate
- place_rate
- misses
- unique_horses
- unique_race_days

Betting return:
- win_return_sum
- place_return_sum
- win_roi
- place_roi

Market diagnostics:
- popularity-band hits
- largest payout
- popularity distribution

### 6. No jackpot rejection

Do not reject a candidate because:

- ROI excluding top1 falls below 100;
- top1 contribution is high;
- only one historical longshot produced most of the return.

Top1/top3 diagnostics may be calculated, but are descriptive only.

Example:

```
n=5
places=1
10th favorite 3rd
place payout=810
```

is not automatically WEAK or rejected.

It is low-support LONGSHOT_EVIDENCE and must remain visible for review.

### 7. Minimum support

Initial serving/review candidate floor:

- n < 5: raw audit only; not shortlist eligible
- MICRO: n=5-9
- SMALL: n=10-19
- MEDIUM: n=20-49
- LARGE: n>=50

Do not invent a higher n cutoff in this task.

---

## Stage A — Canonical input discovery

Before writing aggregation logic, resolve the canonical source(s) needed to reproduce 2022-2025 rows with:

### Pre-race dimensions

- race_date
- race_key
- race_horse_key
- horse_id
- horse_no
- venue_code
- surface
- distance
- frame
- sire identity/name
- going
- previous-race surface/distance as required
- first turf / first dirt
- blinkers / first blinkers
- any fields needed for one-turn/two-turn derivation

### Outcome/evaluation fields

- finish
- win payout
- place payout
- popularity
- odds if canonical and available

Use current accepted Analysis / Warehouse / Feature Mart assets and existing canonical result-query paths.

Document:

- generation IDs
- manifests
- source hashes/digests
- coverage
- row count
- required-column coverage
- any missing field

Do not guess field semantics from names if a canonical derivation already exists.

If one required feature is unavailable, continue with all unaffected template families and mark only the blocked family as BLOCKED.

---

## Stage B — Canonical v0.5 feature mart

Implement a compact deterministic research mart if one does not already exist.

Suggested module:

`horse-racing/jrdb/src/jrdb_edge_v05_feature_mart.py`

The mart should contain only fields needed by T1-T6 plus outcome/diagnostic fields.

Hard boundary:

```
PRE_RACE FEATURES
-----------------
candidate membership

POST_RACE EVALUATION
--------------------
finish / payout / popularity / odds
```

Keep the boundary explicit in code/schema.

Prefer Parquet + DuckDB through `tools/data-storage/`.

Do not create a persistent DuckDB file.

---

## Stage C — Required derived features

### C1. Distance change

Canonical v0.5 values:

- EXTEND
- SHORTEN
- NONE / SAME

Only EXTEND and SHORTEN are used in T3.

Do not include SAME_BAND as an Edge condition.

Use established repository semantics for what counts as meaningful extension/shortening where available.

If v0.4 already contains a canonical no-leakage derivation, reuse/factor it rather than inventing a conflicting rule.

### C2. Surface switch

Required:

- TURF_TO_DIRT
- DIRT_TO_TURF

Do not include:

- TURF_TO_TURF
- DIRT_TO_DIRT

as T4 candidate values.

### C3. First surface

Required distinct flags:

- FIRST_DIRT
- FIRST_TURF

These must mean true career-first exposure known before the target race, not merely "previous race was on the other surface".

### C4. First blinkers

Required:

- FIRST_BLINKERS

Do not treat generic blinkers-on or blinkers-return as equivalent.

### C5. Going bucket

Initial buckets:

- GOOD
- SOFT_OR_WORSE

Use canonical JRDB going code mapping.

Document exact mappings.

### C6. Course topology

Implement or reuse a deterministic lookup:

```
venue + surface + distance (+ course variant if required)
-> ONE_TURN / TWO_TURN / STRAIGHT / OTHER
```

This is required because the prototype must be capable of finding memo forms such as:

> ミッキーアイル産駒は芝ワンターン

Do not infer topology from distance alone.

If a complete canonical mapping cannot be established from repository evidence, report C6 as BLOCKED rather than guessing.

---

## Stage D — Frozen T1-T6 aggregation

Evaluate exactly these initial families.

Do not add arbitrary depth-4/5/6 expansions.

### T1 — Course × frame

```
venue × surface × distance × frame
```

Use exact frame as the canonical first pass.

### T2 — Sire × course

```
sire × venue × surface × distance
```

Also evaluate the semantic topology variant as a distinct template family when C6 is available:

```
sire × surface × course_topology
```

This topology variant is part of T2 prototype evidence, not a new open-ended search lane.

### T3 — Sire × distance change

```
sire × EXTEND
sire × SHORTEN
```

No SAME.

### T4 — Sire × surface transition / first surface

Evaluate separately:

```
sire × TURF_TO_DIRT
sire × DIRT_TO_TURF
sire × FIRST_DIRT
sire × FIRST_TURF
```

No surface-continuity candidate.

### T5 — Sire × first blinkers

```
sire × FIRST_BLINKERS
```

### T6 — Sire × surface × going

```
sire × surface × GOOD
sire × surface × SOFT_OR_WORSE
```

---

## Stage E — Candidate identity and deterministic output

Each candidate must have a deterministic identity derived from:

- template family/version
- canonical ordered conditions

Suggested fields:

- candidate_id
- template_id
- template_version
- conditions
- condition_fingerprint

The same condition must not receive a new ID because of row ordering or execution shard.

---

## Stage F — 2024-2025 primary metrics

For every candidate with n >= 5 calculate at minimum:

### Overall 2024-2025

- n
- wins
- places
- misses
- win_rate
- place_rate
- unique_horses
- unique_race_days
- win_return_sum
- place_return_sum
- win_roi
- place_roi

### By year

For 2024 and 2025 separately:

- n
- wins
- places
- win_rate
- place_rate
- win_roi
- place_roi

Do not require both years to be profitable.

Do not rank 2025 growth as invalid merely because 2024 was poor.

---

## Stage G — 2022-2023 freshness context

For the exact same frozen candidate definitions, compute context metrics on 2022-2023:

- n
- wins
- places
- win_rate
- place_rate
- win_roi
- place_roi

Attach a descriptive freshness label.

Use initial labels:

- EMERGING
- CURRENT
- DECAYING
- OLD_ONLY
- VOLATILE
- INSUFFICIENT_HISTORY

Do not optimize thresholds by manually looking for desired famous examples.

If threshold boundaries are required, make them simple, explicit, versioned, and report sensitivity.

---

## Stage H — Market diagnostics after freeze

Only after T1-T6 candidate membership is frozen, enrich with popularity/payout evidence.

At minimum:

- hits at 5th favorite or worse
- hits at 8th favorite or worse
- hits at 10th favorite or worse
- best/maximum longshot popularity among hits
- largest win payout
- largest place payout
- 1-4 popularity band n/hits/ROI
- 5-7 popularity band n/hits/ROI
- 8+ popularity band n/hits/ROI
- average popularity
- median popularity if practical

"Hit" for the longshot diagnostics should mean place / top-3 success unless a field explicitly says win hit.

Document this definition.

Popularity bands are diagnostics only.

Never regenerate candidate groups by popularity.

---

## Stage I — Jackpot diagnostics

Calculate, but do not gate:

- top1 win-return contribution
- top1 place-return contribution
- top3 contribution
- win ROI excluding top1
- place ROI excluding top1
- win/place ROI excluding top3 where practical

A candidate must remain in raw output even when these are extreme.

Add descriptive flags when useful:

- ONE_BIG_HIT
- LONGSHOT_EVIDENCE

Do not convert either flag into automatic rejection.

---

## Stage J — Parent/context diagnostics

Compute natural parent comparisons where unambiguous.

Examples:

T1:
`venue × surface × distance`

T2:
`sire`
or
`sire × surface` when comparing topology/course specialization

T3:
`sire`

T4:
`sire`

T5:
`sire`

T6:
`sire × surface`

At minimum store:

- parent_n
- parent_win_rate
- parent_place_rate
- parent_win_roi
- parent_place_roi
- delta_win_rate
- delta_place_rate
- delta_win_roi
- delta_place_roi

Parent comparison is diagnostic.

Do not require a child to beat every parent metric.

---

## Stage K — Redundancy prototype

Implement a first deterministic redundancy audit across candidates that can collide on the same runners.

At minimum calculate:

- overlap_count
- union_count
- Jaccard similarity
- subset/superset relationship where exact
- condition-depth/semantic simplicity

Do not delete raw candidates.

Create a separate presentation/review field such as:

- redundancy_cluster_id
- representative_candidate_id
- redundancy_status
- redundancy_reason

Initial principle:

> Prefer the simpler/broader memo when it explains essentially the same historical runner set and evidence.

But do not invent an aggressive automatic threshold if evidence is unclear.

If needed, produce suggested clusters for ChatGPT review rather than pretending the clustering policy is scientifically frozen.

---

## Stage L — Human-readable memo text

Every shortlist candidate must receive a concise Japanese memo generated deterministically from its canonical conditions.

Examples of target style:

- `ミッキーアイル産駒は芝ワンターンでプラス`
- `ドゥラメンテ産駒は距離延長でプラス`
- `キズナ産駒は初ダートでプラス`
- `東京ダ1600mは8枠が近年プラス`

Avoid:

- raw feature codes
- machine enum dumps
- long statistical prose in the memo itself

Memo text is presentation metadata.
It must not alter candidate membership or metrics.

---

## Stage M — Research labels and shortlist

Do not collapse candidates into one opaque scalar score.

Attach descriptive labels such as:

- NICHE_VALUE_POSITIVE
- NICHE_VALUE_NEGATIVE
- LONGSHOT_EVIDENCE
- CURRENT_BUT_LOW_SUPPORT
- EMERGING
- DECAYING
- SATURATED_OR_PRICED
- REDUNDANT
- WEAK
- INSUFFICIENT

A candidate may have multiple labels.

### Important

For this first prototype, do not tune a complex ranker.

Produce:

1. full candidate table n>=5;
2. compact review shortlist;
3. examples of:
   - promising positive memo
   - promising negative memo
   - longshot-evidence memo
   - famous/obvious condition whose recent ROI appears saturated
   - redundant cluster
   - weak/noisy candidate

The shortlist is for human research review, not promotion.

---

## Required outputs

Store large artifacts outside Git as appropriate.

Git must receive compact code/config/docs/results only.

Expected durable research outputs should include, at minimum:

- v0.5 feature mart manifest/audit
- T1-T6 candidate Parquet
- compact candidate CSV/JSON summary
- redundancy summary
- shortlist summary

Result report:

`horse-racing/jrdb/docs/edgedb/v0_5/collab/results/20261007_001_t1_t6_2024_2025_prototype_aggregation_result.md`

The result report must contain enough information for ChatGPT to decide the next research step without requiring raw console logs.

---

## Result report required sections

### 1. Source provenance

- source commit
- Analysis/Warehouse/Feature Mart generations
- source manifests/hashes
- date coverage
- source row counts

### 2. Feature availability

For each required v0.5 feature:

- available / unavailable
- source field/derivation
- null/coverage
- leakage classification

### 3. Execution route

Record:

- local Data Storage preflight
- DuckDB/PyArrow versions
- fallback use if any
- fallback run/artifact/audit when applicable

### 4. Candidate counts

By:

- T1-T6
- support class
- positive/negative/research label
- freshness label

### 5. Distribution summary

For each family:

- n distribution
- win/place ROI distribution
- 2024 vs 2025
- longshot hit distribution

### 6. Top review examples

Provide a compact table of human-readable memos with:

- candidate_id
- memo
- template
- support class
- n
- wins
- places
- win ROI
- place ROI
- 2024 place ROI
- 2025 place ROI
- 2022-23 context place ROI
- 5+ hit count
- 8+ hit count
- 10+ hit count
- largest place payout
- parent delta
- freshness
- jackpot diagnostic
- redundancy status

Do not show only the highest ROI rows.
Include representative patterns.

### 7. Desired-pattern check

Explicitly answer whether the system can now express/discover conditions structurally equivalent to:

- sire × turf one-turn
- sire × distance extension
- sire × first dirt

Do not require the specific example sires to actually be profitable.

The check is about search expressiveness and discovered memo quality, not cherry-picking those names.

### 8. Failure modes

List:

- ordinary/obvious conditions still flooding results
- excessive low-support candidates
- semantic duplicates
- impossible/missing features
- suspected saturation
- performance bottlenecks

### 9. Recommendation

Return control to ChatGPT with one of:

- READY_FOR_RESEARCH_REVIEW
- PARTIAL_WITH_BLOCKED_FAMILIES
- EXECUTION_BLOCKED
- SCIENTIFIC_OUTPUT_TOO_NOISY

Do not promote anything to OBSERVE_ONLY/STANDARD in this task.

---

## Data Storage mandatory route

Parquet/DuckDB work must use the repository-wide Data Storage contract.

From repository root:

```
PYTHONPATH=tools/data-storage \
  .venv-data-storage/bin/python -m data_storage check-deps
```

If dependencies are missing:

1. one normal repair attempt using `tools/data-storage/requirements.txt`;
2. if blocked by proxy/network policy, report:
   `LOCAL_DATA_STORAGE_BLOCKED`
   and `fallback_candidate=true`;
3. use the documented `[DATA_STORAGE_FALLBACK]` Actions route when inputs are reproducible;
4. inspect fallback audit/artifact;
5. continue.

Do not stop at "DuckDB/PyArrow unavailable" when fallback_candidate=true.

Do not substitute ad-hoc pandas/SQLite computation for the canonical DuckDB/Parquet path solely because the managed runtime is missing dependencies.

---

## GitHub routing

Follow `.gpt/GITHUB_OPERATION_POLICY.md`.

Use:

- A Read/Audit for repository/source inspection;
- B direct Git changes for code/tests/docs/config;
- C local deterministic execution when dependencies/inputs permit;
- D Actions-native only where required, including Data Storage fallback and immutable artifact chains.

Do not create generic Issues merely to perform ordinary Git changes.

---

## Tests

Add focused tests for at least:

- 2024-2025 discovery window exactness
- 2022-2023 context not affecting membership
- 2026 excluded
- popularity/odds cannot affect candidate membership
- T3 excludes SAME
- T4 excludes TURF_TO_TURF and DIRT_TO_DIRT
- FIRST_DIRT/FIRST_TURF semantics
- FIRST_BLINKERS semantics
- going bucket mapping
- deterministic candidate IDs
- n<5 exclusion from shortlist
- MICRO n=5 retained
- jackpot-heavy MICRO candidate not auto-rejected
- performance/return fields kept separately
- market diagnostics applied only after freeze
- no duplicate candidate IDs

If course topology is implemented:

- representative ONE_TURN / TWO_TURN / STRAIGHT mappings
- no distance-only guessing

---

## Acceptance gate

This task is accepted only if:

1. canonical 2022-2025 inputs are identified and audited;
2. pre-race/result boundary is explicit;
3. T1-T6 are implemented without arbitrary high-order expansion;
4. 2024-2025 candidate generation is market-blind;
5. performance and betting-return metrics are separate;
6. n=5 MICRO candidates survive;
7. jackpot dependence is diagnostic, not an automatic rejection;
8. 2022-2023 context is attached without affecting candidate membership;
9. popularity/odds enrichment occurs only after membership freeze;
10. output includes human-readable memo text;
11. redundancy is at least audited;
12. result report contains compact review examples;
13. Data Storage route is followed correctly;
14. no production EdgeDB manifest/consumer is changed.

---

## Non-goals

- no v0.2/v0.3/v0.4 production changes;
- no v0.5 publication;
- no RaceNote score change;
- no Newspaper/PWA migration;
- no automatic staking;
- no popularity-conditioned candidate generation;
- no exhaustive depth-4-to-6 exploration;
- no mandatory top1-exclusion profitability;
- no requirement that blind-buy ROI exceed 100 for every shortlisted memo.
