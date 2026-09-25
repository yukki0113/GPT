# JRDB Edge v0.3 Stage-E Forward Shadow Freeze — 2026-09-26 / 09-27

Status: **FROZEN BEFORE TARGET RESULTS / SHADOW ONLY**  
Frozen: 2026-09-25

## 1. Purpose

Stage-D operational replay完了後のv0.3設計を、未来開催で結果参照なしに観測する。

このfreeze以後、対象日2026-09-26 / 2026-09-27の結果を理由として、semantic hierarchy、B2b Performance gate、Stage-C serving class、reversal定義を変更しない。

## 2. Frozen target block

- 2026-09-26
- 2026-09-27
- expected scheduled races: **24 races per target date** (Nakayama 12 + Hanshin 12)

対象は日単位で固定し、Edgeの有無・人気・レース難度・結果による個別race除外は行わない。
PACI source availabilityや開催変更がある場合はfail-closedで記録し、結果確認後の代替選択は行わない。

At freeze time:
- target result data used: **false**
- SED / finish / payout used: **false**
- v0.3 remains **SHADOW_ONLY**

## 3. Frozen upstream contracts

### v0.2 production comparator

- mode: STANDARD
- publication run: 34620664640
- artifact: jrdb-edge-serving-v02-full-2010-2025-standard-r1-34620664640
- catalog SHA-256: fe1182e1e8beed952d5f4b740642fd3ec1262c353d6d46036e19a457f27d7469

v0.2 production serving remains unchanged.

### Stage-C v0.3 shadow serving

- run: 36045237262
- artifact: jrdb-edge-v03-shadow-catalog-36045237262
- edge_serving_catalog_v0_3_shadow.jsonl SHA-256: a724a005ec40446f4a982a79de17ba7a2ae169c09260ecee98a159b663914379
- Stage-C summary SHA-256: c310e7dcaf059f78e39dcbb1f223bf02635700ec1490a42997f9789f75789ce2
- shadow serving rows: 2,044
  - ORTHOGONAL: 1,950
  - INCREMENTAL_PERFORMANCE: 94
- target-hierarchy Value gate: DEFERRED_FAIL_CLOSED

### Stage-D historical replay

Canonical replay:
- Issue: #1352
- run: 36109287229
- artifact: jrdb-edge-v03-operational-replay-36109287229
- status: PASS
- production serving changed: false

Observed on 2026-09-12 / 09-13 / 09-19:
- v0.2 Performance matches: 1,922
- v0.3 Performance matches: 1,031
- reduction: 891
- target hierarchy Context/Insufficient absorption: 863
- non-target channel normalization: 28
- exact decomposition: 863 + 28 = 891
- mixed runners: 269 -> 154
- 3+ Performance hits: 320 -> 108
- 5+: 68 -> 6
- 6+: 32 -> 2
- v0.3 target-hierarchy Performance matches: 63
- reversal matches observed in replay block: 0

The absence of replay reversal matches does not remove or redefine the five frozen reversal candidates.

## 4. Forward execution contract

Driver: horse-racing/jrdb/src/run_jrdb_edge_v03_forward_shadow_freeze.py

For each target date:

1. obtain pre-race PACI;
2. resolve canonical Analysis Parquet current;
3. verify v0.2 publication SHA;
4. verify frozen Stage-C v0.3 shadow catalog SHA;
5. enforce the existing TRUE_FORWARD earliest-post time guard;
6. require PACI BAC scheduled-race count to equal the frozen full-day count (**24**); partial snapshots fail closed;
7. build Current Facts once;
8. create v0.2 STANDARD matches;
9. create v0.3 SHADOW_ONLY matches from exactly the same Current Facts;
10. freeze PACI, catalogs, facts, both match outputs, provenance, and hashes;
11. do not use SED/result data in Freeze.

The v0.3 output is observational only and must not replace Newspaper/RaceNote production serving.

## 5. Evaluation after the block

After both freezes are anchored and results become available, evaluate without retuning:

- Performance matched-runner rate
- Performance match count per runner
- 3+ / 5+ / 6+
- mixed direction rate
- semantic cluster count
- Context absorption
- incremental reversal activation
- Performance outcome by frozen class
- Value evidence only under the already frozen fail-closed/carry-forward contract

Do not interpret lower density alone as correctness.

## 6. Promotion boundary

This two-day block does not by itself promote v0.3 to STANDARD.

Any later promotion decision requires a separate review after:
- immutable Stage-E forward artifacts exist,
- no leakage is established,
- replay and forward behavior are compared,
- Value channel design is explicitly resolved,
- rollback to v0.2 remains available.

Until then: **v0.2 = STANDARD production / v0.3 = SHADOW_ONLY.**

## 7. PACI completeness correction

An early 2026-09-27 PACI retrieval produced only one BAC race / 16 runners.
That snapshot is explicitly non-canonical for Stage-E because the frozen target is the full 24-race JRA day.
The Stage-E driver/workflow therefore requires `expected_scheduled_races=24` and rejects partial PACI snapshots.

2026-09-26 is also re-frozen under the same 24-race completeness guard so both target days use one contract.
