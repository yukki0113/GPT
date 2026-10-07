# 20261007_003 — EdgeDB v0.5 First Surface + First Blinkers Full-History Aggregation

Status: TODO
Date: 2026-10-07
Design authority: ChatGPT
Execution worker: Codex
Production impact: NONE

## Objective

Complete the currently blocked v0.5 history-dependent template families using the newly materialized accepted JRDB Warehouse artifact.

This task must add:

- sire × FIRST_DIRT
- sire × FIRST_TURF
- sire × FIRST_BLINKERS

to the same v0.5 research population and evaluate them under the exact same adoption rules already frozen for the first prototype.

Do not change the current positive Value gate or support floor in this task.

---

## Frozen input artifacts

### Accepted Warehouse research materialization

Run:

`37592837881`

Artifact:

`jrdb-warehouse-research-37592837881`

Artifact ID:

`11468713930`

Artifact digest:

`sha256:fb28c17889cf2a9028b58e1bac3164b89a0b4c66eadfb5d3dba19d1ace88499a`

Contents:

- KYI 2010-2025
- SED 2010-2025
- accepted Warehouse generation:
  `jrdb_normalized_warehouse_v1_2010_2025_g20260921`

The materialization workflow verified:

- generation ID
- exact asset count
- per-Parquet SHA256
- per-Parquet size

Issue #1878 closed completed.

### Existing Feature Mart

Run:

`36116777782`

Artifact:

`jrdb-edge-feature-mart-parquet-36116777782`

Digest:

`sha256:19d713da2e6ebf57965de98952fbf18d79f9ddfd5c1996833af3267b1a53f725`

### Existing Analysis/result artifact

Run:

`36437363166`

Artifact:

`jrdb-post-race-parquet-refresh-36437363166`

Digest:

`sha256:d159c2fca9959d9b144d55f9b3ba98228158cc38b85fcc730032a53f29252a55`

---

## Required reading

Read before implementation:

- `horse-racing/jrdb/docs/edgedb/v0_5/EdgeDB_v0_5_Niche_Value_Memo_Discovery_Design_20261007.md`
- `horse-racing/jrdb/docs/edgedb/v0_5/collab/instructions/20261007_001_t1_t6_2024_2025_prototype_aggregation_instruction.md`
- `horse-racing/jrdb/docs/edgedb/v0_5/collab/instructions/20261007_002_v05_prototype_scientific_correction_and_roi_gate_instruction.md`
- current merged v0.5 implementation from PR #1871
- `horse-racing/jrdb/src/jrdb_edge_v05_prototype_aggregation.py`
- `horse-racing/jrdb/src/jrdb_raw.py`
- Warehouse materialization manifest inside artifact 11468713930
- Data Storage documentation

---

## Frozen scientific rules

Do not alter these.

### Discovery window

`2024-01-01 through 2025-12-31`

### Historical context window

`2022-01-01 through 2023-12-31`

### 2026

Excluded from discovery/ranking.

### Support floor

Positive Value shortlist:

`n >= 5`

### Positive Value gate

`2024-2025 place ROI >= 100%`

combined over both years.

Do not require each year separately to exceed 100.

### Jackpot rule

Do not reject:

- top1-heavy candidates;
- one-hit MICRO candidates;
- candidates whose ROI ex-top1 is below 100.

Top1/top3 dependence is descriptive only.

### Candidate generation

Must remain market-blind.

Popularity, odds and payout may be joined only after candidate membership is frozen.

---

## Stage A — Consume exact Warehouse artifact

Download artifact ID `11468713930`.

Verify:

- artifact digest if available from Actions metadata;
- embedded research materialization manifest;
- accepted Warehouse generation;
- selected years 2010-2025;
- KYI 16 partitions;
- SED 16 partitions;
- every file SHA256/size against embedded manifest.

Fail closed on mismatch.

Do not re-download these Parquets from Drive inside the aggregation workflow.

The purpose of instruction 003 is to use the artifact bridge that now exists.

---

## Stage B — Build exact career chronology

Use canonical horse identity.

Preferred identity:

- `blood_registration_no`

Cross-check joins with:

- race_key_raw
- horse_no
- race_date

Do not use horse name matching.

For every horse, create strict chronological starts through 2025.

Requirements:

- target row itself must not be included in prior-history checks;
- same-date duplicate/source rows must be reconciled deterministically;
- malformed/unresolved identity rows must be UNKNOWN, not guessed;
- left-censored history must be handled explicitly.

Because Warehouse coverage begins in 2010, horses whose observed history is plausibly incomplete at the left boundary must not be falsely classified as first-surface or first-blinker.

For 2022-2025 target runners, document whether 2010 coverage is sufficient to eliminate practical left-censoring for normal JRA horse ages. If yes, state the reasoning and evidence. If any exceptional identities remain ambiguous, mark UNKNOWN.

---

## Stage C — FIRST_DIRT / FIRST_TURF

Derive:

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

This is career-first exposure.

Do not approximate from:

- prev1 surface;
- turf->dirt transition alone;
- dirt->turf transition alone.

A runner can be TURF_TO_DIRT without FIRST_DIRT.

These are separate template semantics.

---

## Stage D — FIRST_BLINKERS

Use canonical KYI `blinker_code` semantics.

Repository audit already found codes:

- 1 = first worn
- 2 = re-worn
- 3 = blinkers active

Before using the raw code as authoritative, reconcile parser/codebook semantics.

Preferred canonical definition:

```
FIRST_BLINKERS =
  current race has blinkers active
  AND no strictly earlier race has blinkers active
```

If `blinker_code == 1` is proven to be an authoritative exact first-use flag for every row, compare it against chronology-derived first-use and report parity.

Do not silently trust one path when the two disagree.

Output mismatch count and representative mismatch rows if any.

---

## Stage E — Add template families

Add history-dependent templates without changing existing T1/T2/T3/T4-switch/T6 definitions.

### T4 extension

Add separate candidates:

```
sire × FIRST_DIRT
sire × FIRST_TURF
```

Keep these distinct from:

```
sire × TURF_TO_DIRT
sire × DIRT_TO_TURF
```

### T5

Add:

```
sire × FIRST_BLINKERS
```

Use deterministic candidate IDs and memo text.

Suggested memo style:

- `キズナ産駒は初ダートでプラス`
- `○○産駒は初芝でプラス`
- `○○産駒は初ブリンカーでプラス`

Do not invent stronger language than the evidence supports.

---

## Stage F — Metrics

For FIRST_DIRT / FIRST_TURF / FIRST_BLINKERS, calculate exactly the same metrics as existing v0.5 candidates:

- n
- wins
- places
- win_rate
- place_rate
- unique_horses
- unique_race_days
- win_return_sum
- place_return_sum
- win_roi
- place_roi
- 2024 metrics
- 2025 metrics
- 2022-23 context metrics
- freshness
- support class
- parent diagnostics
- 5+/8+/10+ popularity hits
- largest payouts
- top1/top3 contribution
- ROI ex top1/top3 diagnostics

Do not alter definitions between existing and new families.

---

## Stage G — Positive / negative classification

### Positive Value

Exactly:

```
n >= 5
AND
2024-2025 place ROI >= 100
```

### Performance

Keep separate:

- PERFORMANCE_POSITIVE
- PERFORMANCE_NEGATIVE

### Negative Edge

Reuse the already frozen conservative gate from instruction 002.

Do not redesign negative Edge here.

---

## Stage H — Unified candidate inventory

After new history-dependent families are added, produce one combined inventory covering:

- T1 course × frame
- T2 sire × course
- T3 sire × distance change
- T4 sire × surface switch
- T4 sire × FIRST_DIRT
- T4 sire × FIRST_TURF
- T5 sire × FIRST_BLINKERS
- T6 sire × surface × going

Do not introduce any new filtering beyond the frozen gates.

The purpose is to get the planned condition families onto one comparable table before deciding the next sieve.

Report:

- raw n>=5 count
- positive Value count
- negative Edge count
- counts by family
- counts by support class
- positive Value by family
- LONGSHOT_EVIDENCE by family
- EMERGING/CURRENT/DECAYING by family

---

## Stage I — Do not solve signal density yet

This instruction must NOT add:

- higher minimum n;
- ROI > 120 or >150 as a new gate;
- significance tests as mandatory gates;
- extra popularity gates;
- extra year-consistency gates;
- manual top-N caps;
- pruning solely because T2 is large.

The user explicitly wants all planned condition families available under the same rule before choosing the next sieve.

So instruction 003 is an inventory-completion task.

---

## Stage J — Existing candidate parity

Existing T1/T2/T3/T4-switch/T6 candidates must remain unchanged under identical inputs.

Verify parity against the merged PR #1871 results for:

- candidate IDs
- n
- place ROI
- positive Value eligibility
- negative eligibility

Any drift must be explained and must not be accepted silently.

---

## Required outputs

Update/add durable result documentation under:

`horse-racing/jrdb/docs/edgedb/v0_5/collab/results/`

Suggested result:

`20261007_003_first_surface_and_blinker_full_history_aggregation_result.md`

Large Parquet outputs should remain Actions artifacts.

Required compact outputs:

- combined candidate summary
- history-dependent candidate summary
- first-surface audit
- first-blinker audit
- parity audit
- updated family counts

---

## Required result report sections

### 1. Input provenance

Include:

- Warehouse run 37592837881
- artifact ID 11468713930
- digest
- Feature Mart run/digest
- Analysis run/digest
- source commit

### 2. Warehouse verification

Include:

- partition counts
- year coverage
- SHA verification
- identity coverage
- duplicate reconciliation counts

### 3. First surface audit

Include:

- FIRST_DIRT candidate runner count
- FIRST_TURF candidate runner count
- UNKNOWN count
- source/join failures
- example chronology checks

### 4. First blinkers audit

Include:

- chronology-derived count
- code==1 count
- parity/mismatch count
- UNKNOWN count

### 5. Candidate counts

By all template families.

### 6. Positive Value counts

Using the same ROI100/n>=5 gate.

### 7. Representative examples

Include at least:

- positive FIRST_DIRT
- positive FIRST_TURF if present
- positive FIRST_BLINKERS if present
- MICRO longshot example if present
- negative example if present
- no-example statement if a category has none

Do not cherry-pick named historic examples.

### 8. Existing-family parity

PASS/FAIL.

### 9. Unified inventory

State the new total candidate counts after all available planned families are combined.

### 10. Recommendation

Return one:

- READY_FOR_NEXT_SIEVE_DESIGN
- PARTIAL_WITH_TOPOLOGY_BLOCKED
- HISTORY_DERIVATION_BLOCKED
- EXECUTION_BLOCKED

If all history families are complete and only topology remains blocked, use:

`PARTIAL_WITH_TOPOLOGY_BLOCKED`

and explicitly state that the core original T1-T6 set plus first-surface extensions are now on one comparable rule set.

---

## Tests

Add focused tests for:

- first dirt exact chronology
- first turf exact chronology
- transition != first-surface semantics
- target row excluded from history
- first blinkers exact chronology
- code==1 parity where applicable
- repeat/re-wear blinkers not first
- UNKNOWN handling
- same-day duplicate reconciliation
- deterministic candidate IDs
- ROI100 gate unchanged
- n=5 gate unchanged
- one-hit MICRO still passes
- existing family parity

---

## Production safety

Do not modify:

- `current_manifest.json`
- v0.2 STANDARD
- v0.3 SHADOW
- v0.4 OBSERVE_ONLY
- RaceNote scoring
- Newspaper/PWA serving
- EdgeDB production query profile

No v0.5 promotion in this task.

---

## Acceptance gate

Instruction 003 is accepted only if:

1. artifact 11468713930 is consumed and verified;
2. full 2010-2025 KYI/SED chronology is used;
3. FIRST_DIRT/FIRST_TURF are true career-first semantics;
4. FIRST_BLINKERS is chronology-safe;
5. T4-first-surface and T5 are actually aggregated;
6. existing candidates retain parity;
7. the ROI100/n>=5 gate is unchanged;
8. combined inventory is produced;
9. no new sieve is introduced;
10. production remains unchanged.
