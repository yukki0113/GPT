# 20261007_004 — EdgeDB v0.5 2026 Pre-Race Match Freeze

Status: TODO  
Date: 2026-10-07  
Design authority: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Execute Turn 2 of the EdgeDB v0.5 historical blind replay plan.

Take the already frozen **1,620 positive-value candidates** from Turn 1 and match them against every eligible 2026 JRA runner from the beginning of 2026 through the latest date for which canonical pre-race facts can be reconstructed.

This turn must end with an immutable **2026 pre-race match freeze**.

Do **not** open, join, inspect, rank by, or otherwise use:

- finish position;
- win/place result;
- payout;
- popularity;
- odds;
- post-race performance;
- 2026 result-side Analysis fields.

Turn 2 is strictly a pre-race reconstruction and matching task.

---

## Frozen Turn 1 cohort

Canonical Git files:

- `horse-racing/jrdb/config/edgedb/v0_5/frozen/v05_positive_value_frozen_cohort.json`
- `horse-racing/jrdb/config/edgedb/v0_5/frozen/v05_positive_value_freeze_manifest.json`

Turn 1 cohort:

- candidate count: **1,620**
- cohort SHA-256:
  `a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9`

Frozen gate:

```
n >= 5
AND
combined 2024-2025 place ROI >= 100%
```

Discovery window:

`2024-01-01 through 2025-12-31`

Context window:

`2022-01-01 through 2023-12-31`

2026 was not used in candidate discovery or candidate selection.

### Turn 1 Actions artifact

Run:

`37598903743`

Artifact:

`edgedb-v05-positive-value-freeze-37598903743`

Artifact ID:

`11471917437`

Artifact digest:

`sha256:3cfc6e4cbc5e6b67b0c02bce3a11e26d283df3603add8155f208714145e7bcef`

Frozen Parquet SHA-256:

`a57c9dcbc9c8c93d9c88e98a0db26818b628dbd580c2c9108d20a67adbab425b`

The cohort must not be regenerated or modified in Turn 2.

---

## Required reading

Before implementation, read:

- `horse-racing/jrdb/docs/edgedb/v0_5/EdgeDB_v0_5_Niche_Value_Memo_Discovery_Design_20261007.md`
- `horse-racing/jrdb/docs/edgedb/v0_5/collab/instructions/20261007_001_t1_t6_2024_2025_prototype_aggregation_instruction.md`
- `horse-racing/jrdb/docs/edgedb/v0_5/collab/instructions/20261007_002_v05_prototype_scientific_correction_and_roi_gate_instruction.md`
- `horse-racing/jrdb/docs/edgedb/v0_5/collab/instructions/20261007_003_first_surface_and_blinker_full_history_aggregation_instruction.md`
- `horse-racing/jrdb/docs/edgedb/v0_5/collab/results/20261007_004_positive_value_freeze_result.md`
- `horse-racing/jrdb/src/aggregate_jrdb_edge_v05_first_history.py`
- `horse-racing/jrdb/src/build_jrdb_edge_current_facts.py`
- `horse-racing/jrdb/src/jrdb_edgedb_query.py`
- current JRDB/PACI canonical-generation runbooks
- Data Storage local-first / Actions fallback documentation

---

# 1. Scientific boundary

Turn 2 is a **HISTORICAL_BLIND_REPLAY pre-race freeze**.

Its only scientific question is:

> Given the frozen 1,620 candidate conditions and only information available before each 2026 race, which runners matched which candidates?

No result-side information may influence:

- candidate membership;
- candidate conditions;
- runner eligibility;
- history-derived flags;
- match status;
- match ordering;
- candidate IDs;
- match fingerprints.

---

# 2. First task: identify canonical 2026 pre-race source route

Before coding, audit the repository and existing Actions workflows to identify the canonical route for reconstructing 2026 pre-race runner facts.

Preferred source hierarchy:

1. existing canonical 2026 PACI / Edge Feature Mart / pre-race Parquet if available;
2. canonical JRDB pre-race files and existing builders;
3. existing daily artifacts that can be deterministically consolidated;
4. only if no existing annual source exists, build a deterministic 2026 pre-race mart from the canonical daily route.

Do not scrape or substitute a new web source.

Do not use result-side Analysis Parquet as a shortcut for pre-race fields.

### Required source audit output

Record:

- source generation(s);
- Actions run/artifact IDs;
- year/date coverage;
- row count;
- schema;
- canonical key;
- whether each required v0.5 condition field exists;
- whether any field is post-race or leakage-prone.

---

# 3. Required 2026 coverage

Target date range:

`2026-01-01 through latest canonically reconstructable pre-race date`

The latest date must be derived from canonical input coverage, not hardcoded.

Report:

- first covered race date;
- latest covered race date;
- number of race days;
- number of races;
- number of runners;
- missing canonical days, if any.

If isolated dates are missing:

- do not fabricate;
- record them explicitly;
- continue only if the omission is understood and bounded.

If coverage is materially incomplete, return `PARTIAL_PRE_RACE_COVERAGE` rather than silently treating it as complete.

---

# 4. Build one 2026 canonical pre-race fact mart

Create a deterministic research-only fact mart for Turn 2.

Suggested module:

`horse-racing/jrdb/src/jrdb_edge_v05_2026_pre_race_match_freeze.py`

Suggested fact artifact:

`v05_2026_pre_race_facts.parquet`

Minimum identity fields:

- race_date
- race_key
- race_horse_key
- horse_id / blood_registration_no
- horse_no
- venue
- surface
- distance

Condition fields required by the 1,620 frozen cohort may include:

- frame
- sire_name
- track condition / going bucket
- distance-change direction
- surface switch
- FIRST_DIRT
- FIRST_TURF
- FIRST_BLINKERS

Do not include:

- finish position
- popularity
- odds
- payout
- post-race IDM/performance
- result flags

A schema audit must explicitly prove these are absent from the matching input.

---

# 5. 2026 history semantics

This section is critical.

## 5.1 FIRST_DIRT / FIRST_TURF

For each 2026 target start:

```
FIRST_DIRT =
  current surface is dirt
  AND no strictly earlier career start on dirt
```

```
FIRST_TURF =
  current surface is turf
  AND no strictly earlier career start on turf
```

History must include:

- canonical history through 2025;
- plus all strictly earlier 2026 starts.

Do not freeze first-surface flags once at 2025 year-end.

Do not use future 2026 starts when evaluating an earlier 2026 date.

## 5.2 FIRST_BLINKERS

Use the same conservative chronology-safe semantics accepted in Turn 1/003.

For each 2026 target start:

- inspect all strictly earlier known starts;
- reconcile canonical KYI blinker semantics;
- if chronology and code semantics materially disagree, use UNKNOWN rather than guessing.

Do not treat code==1 alone as authoritative if chronology contradicts it.

## 5.3 Temporal ordering

For every history-dependent flag:

`history_date < target_race_date`

The target row itself must not be part of its own prior history.

Future 2026 rows must never leak backward.

---

# 6. Frozen candidate matcher

Implement a matcher for the Turn 1 cohort.

The matcher must consume:

- the frozen cohort JSON/Parquet;
- one canonical 2026 pre-race runner fact.

It must evaluate the condition object deterministically.

### Supported frozen families

The matcher must support every condition form present in the 1,620-cohort, including:

- T1
- T2
- T3
- T4 surface-switch
- T4 FIRST_DIRT
- T4 FIRST_TURF
- T5 FIRST_BLINKERS
- T6

Do not regenerate candidates from templates.

Do not use family-level heuristics.

Use the exact frozen `conditions` object of each candidate.

### Fail closed

If the frozen cohort contains an unsupported condition key:

- fail;
- report the candidate ID and key;
- do not silently skip it.

---

# 7. Match output contract

Canonical match key:

```
race_date
race_key
race_horse_key
candidate_id
```

At minimum output:

- race_date
- race_key
- race_horse_key
- horse_id
- horse_no
- candidate_id
- template_id
- family
- condition_fingerprint
- memo
- matched_conditions
- pre_race_fact_fingerprint

Do not include result-side fields.

Sort deterministically by:

```
race_date ASC
race_key ASC
race_horse_key ASC
candidate_id ASC
```

---

# 8. Freeze fingerprints

Produce at least three fingerprints.

## 8.1 Cohort fingerprint

Must equal:

`a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9`

## 8.2 Pre-race fact fingerprint

Fingerprint the exact canonical 2026 pre-race fact population used for matching.

## 8.3 Match fingerprint

Fingerprint the canonical sorted match rows.

This fingerprint becomes the immutable Turn 2 boundary used by Turn 3.

Also produce monthly or day-level fingerprints so partial replay can be audited later.

---

# 9. Density counts are audit-only

Turn 2 may calculate descriptive counts needed to verify the freeze:

- runners with 0 matches;
- runners with 1 match;
- runners with 2 matches;
- runners with 3+ matches;
- matches by family;
- matches by month;
- maximum matches on one runner.

However:

**Do not use these counts to alter the cohort or matching.**

Do not:

- remove T2;
- raise the ROI gate;
- raise n;
- cap signals per horse;
- choose top-N;
- suppress overlaps;
- change candidate definitions.

Signal-density interpretation belongs to Turn 4.

---

# 10. Explicit result-data prohibition audit

Add an automated leakage audit.

The Turn 2 pipeline must fail if matching input or intermediate fact mart contains fields with canonical result semantics such as:

- finish_position
- finish_order
- result_rank
- popularity
- odds
- win_payout
- place_payout
- win_return
- place_return
- result_hit
- settled
- post_race

Use explicit schema allowlisting where practical rather than only substring blocking.

Also document all source tables consulted.

---

# 11. 2026 market data prohibition

Even though popularity and odds are pre-race in a chronological sense, they are **not allowed in Turn 2 matching**.

This preserves the v0.5 candidate-generation / matching contract.

Do not use:

- popularity
- win odds
- place odds
- market rank

for:

- matching;
- candidate prioritization;
- row ordering;
- candidate filtering.

These may first be joined in Turn 3 after the match freeze exists.

---

# 12. Reuse existing infrastructure

Use:

- shared Data Storage tools;
- DuckDB/Parquet;
- existing canonical PACI/Edge fact builders where semantically valid;
- existing Warehouse materialization bridge if 2026 history files are required;
- Actions-native path for large annual reconstruction and immutable artifacts.

Do not introduce:

- SQLite canonical storage;
- ad-hoc pandas-only year scans;
- a separate private schema unrelated to existing Edge facts.

---

# 13. Execution routing

This task is expected to be Actions-native because it requires:

- year-scale 2026 reconstruction;
- history-aware first-surface/blinker derivation;
- full 1,620-candidate matching;
- immutable artifact chain.

If a local environment lacks Parquet/DuckDB:

1. try the standard Data Storage environment;
2. one repair attempt;
3. if blocked, use the documented Actions fallback.

Do not repeatedly retry local package installation.

---

# 14. Required artifacts

Large outputs should remain in Actions artifacts.

Required artifact files:

- `v05_2026_pre_race_facts.parquet`
- `v05_2026_match_freeze.parquet`
- `v05_2026_match_freeze_manifest.json`
- `v05_2026_match_freeze_audit.json`
- `v05_2026_match_counts_by_day.csv`
- `v05_2026_match_counts_by_family.csv`

Optional:

- monthly split Parquets if one monolithic file is inconvenient.

---

# 15. Durable Git outputs

Commit only compact, non-sensitive outputs.

Suggested paths:

`horse-racing/jrdb/config/edgedb/v0_5/frozen/v05_2026_match_freeze_manifest.json`

`horse-racing/jrdb/docs/edgedb/v0_5/collab/results/20261007_005_2026_pre_race_match_freeze_result.md`

Do not commit large row-level match Parquet to Git.

If row-level identifiers trigger automated review restrictions, keep row-level outputs only in Actions artifact and commit:

- fingerprints;
- counts;
- coverage;
- anonymized audit summaries.

---

# 16. Required result report

The Turn 2 result report must include:

## A. Input provenance

- Turn 1 cohort path
- cohort SHA
- Turn 1 artifact/run
- 2026 pre-race source generations
- source artifact/run IDs
- source commit

## B. Pre-race coverage

- first date
- latest date
- race days
- races
- runners
- missing days

## C. Leakage audit

Explicit PASS/FAIL for:

- result fields absent
- payout fields absent
- popularity absent
- odds absent
- post-race fields absent

## D. History audit

- FIRST_DIRT derivation counts
- FIRST_TURF derivation counts
- FIRST_BLINKERS derivation counts
- UNKNOWN counts
- 2026 incremental-history proof
- chronology violation count = 0

## E. Frozen cohort verification

- candidate count = 1,620
- cohort SHA exact match
- unsupported condition count = 0

## F. Match counts

- total matched rows
- unique matched runners
- runners with 0/1/2/3+ matches
- family-level match counts
- monthly counts
- maximum matches on one runner

These are audit diagnostics only.

## G. Fingerprints

- pre-race fact fingerprint
- total match fingerprint
- per-month/day fingerprints

## H. Recommendation

Return exactly one:

- `READY_FOR_TURN3_OUTCOME_JOIN`
- `PARTIAL_PRE_RACE_COVERAGE`
- `MATCHER_CONTRACT_BLOCKED`
- `HISTORY_RECONSTRUCTION_BLOCKED`
- `EXECUTION_BLOCKED`

Use `READY_FOR_TURN3_OUTCOME_JOIN` only if the match freeze is immutable and result-blind.

---

# 17. Required tests

Add focused tests for:

1. frozen cohort SHA exact match;
2. all 1,620 candidates parse;
3. unsupported condition key fails closed;
4. T1 exact match;
5. T2 exact match;
6. T3 EXTEND/SHORTEN exact match;
7. T4 surface-switch exact match;
8. FIRST_DIRT chronology through 2026;
9. FIRST_TURF chronology through 2026;
10. FIRST_BLINKERS chronology through 2026;
11. future 2026 history cannot affect earlier race;
12. target row cannot affect itself;
13. UNKNOWN does not match a TRUE-only candidate;
14. result fields rejected from match input;
15. popularity rejected from match input;
16. odds rejected from match input;
17. deterministic row ordering;
18. deterministic fact fingerprint;
19. deterministic match fingerprint;
20. rerun with identical inputs is byte/semantic stable.

---

# 18. Turn 2 non-goals

Do not:

- join 2026 results;
- calculate 2026 ROI;
- calculate 2026 place/win rates from results;
- assign CONFIRMED/DECAYING/CONTRADICTED labels;
- change the 1,620 cohort;
- redesign the ROI gate;
- prune T2;
- introduce top-N display caps;
- publish v0.5;
- touch current_manifest;
- modify RaceNote scoring;
- modify Newspaper/PWA serving.

These belong to later turns.

---

# 19. Production safety

Production impact remains NONE.

Do not modify:

- `horse-racing/jrdb/config/edgedb/current_manifest.json`
- v0.2 STANDARD
- v0.3 SHADOW
- v0.4 OBSERVE_ONLY
- RaceNote scoring
- Newspaper/PWA
- production query profiles

---

# Acceptance gate

Turn 2 is accepted only if all are true:

1. exact Turn 1 cohort SHA is verified;
2. all 1,620 candidates are consumed without regeneration;
3. 2026 pre-race coverage is documented;
4. no result-side fields are used;
5. popularity and odds are absent from matching;
6. FIRST_DIRT/FIRST_TURF/FIRST_BLINKERS use strict prior-history semantics including earlier 2026 starts;
7. all frozen condition forms are supported;
8. match rows are deterministic;
9. pre-race fact and match fingerprints are emitted;
10. row-level match artifact is preserved;
11. compact manifest/report are committed;
12. production remains unchanged;
13. recommendation is suitable for ChatGPT audit before Turn 3.

Do not start Turn 3 in the same task.
