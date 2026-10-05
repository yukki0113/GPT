# 20261005_005 — R1 canonical Actions fallback rerun and R3 decision

- Status: **DONE — `CANONICAL_R1_ACCEPTED`**
- Repository: `yukki0113/GPT`
- Main head used as the result PR base: `49708645b2ad78092c7e67e6ed66b8bfe775a546`
- Canonical source commit: `9aba7103f944ea419189c104be4e48485b819d0d`
- Production impact: **NONE**

## Data Storage routing and fallback evidence

The required local-first check was performed from `tools/data-storage/`. `.venv-data-storage` was present, but `check-deps` reported missing DuckDB and PyArrow. One normal install attempt from `tools/data-storage/requirements.txt` was blocked by the managed runtime proxy (`proxy:8080`, `Operation not permitted`); the repeated check remained `DEPENDENCY_MISSING`.

The repository Actions fallback smoke evidence was verified from Issue #1802 / run `37317982545` (PASS; DuckDB 1.1.3; PyArrow 25.0.1). The first full request, Issue #1804 / run `37320245372`, installed DuckDB and PyArrow and passed planning, then failed on missing NumPy before C1 evaluation. This exposed a concrete gap in shared `tools/data-storage/requirements.txt`; `numpy>=1.26,<3` was added on PR #1803. The fallback was recreated with a new request ID and the corrected source commit; no scientific output from the failed attempt was used.

Successful execution:

- Fallback Issue #1806: closed as completed, result PASS.
- Workflow run: [37321021557](https://github.com/yukki0113/GPT/actions/runs/37321021557)
- Artifact: `data-storage-fallback-37321021557`
- Artifact SHA-256 digest: `ceadecafe0e1b78ce6c3f370439c446cc39017943b510f175e81fbe67bd43269`
- Source commit: `9aba7103f944ea419189c104be4e48485b819d0d`
- Python: 3.12.14; DuckDB: 1.1.3; PyArrow: 25.0.1
- Runner audit: PASS; canonical step exit code 0; no production publication.

The source commit contains the local-first fallback runner/workflow, the canonical planner/C1/C2A/C2B entrypoints, the orchestration entrypoint, and the NumPy dependency requirement.

## Frozen input and planner integrity

- Feature Mart artifact: run `36116777782`, `jrdb-edge-feature-mart-parquet-36116777782`; archive digest matched GitHub artifact metadata; extracted `edge_runner_fact.parquet` SHA-256 `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`; rows 781,161.
- Stage B artifact: run `36262821119`, `jrdb-edge-v04-stage-b-36262821119`; archive digest matched GitHub artifact metadata; extracted catalog SHA-256 `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba`; 47,371 templates.
- Frozen window: 3 years, inclusive `2022-12-28 .. 2025-12-28`.
- Planner: 1,106 templates in 6 shards; D2 123 / D3 983; `TRANSITION_PRIORITY` 586, `PEDIGREE_INTERACTION` 64, `PEDIGREE_BASELINE` 456.
- Planner SHA-256: `de823224c0f10690232835b35557517c474377734b2df347ca3a9a08daa3ded8`, exactly the frozen preflight plan identity.
- All six C1 shard audits PASS with matching Feature Mart/catalog/plan hashes, frozen dates and thresholds. Canonical merge PASS; 68,685 candidates; no duplicate candidate IDs; max-per-template 100.
- Thresholds remained win ROI 110, place ROI 105, max-per-template 100; no threshold tuning.

## Canonical C2A and C2B

Canonical DuckDB C2A ran through `horse-racing/jrdb/src/prepare_jrdb_edge_v04_stage_c2.py`. It produced 17,807 shortlist candidates, all `ESTABLISHED_CURRENT`; 52,171 child-parent links; 14,129 unique parent metric requests; 30,733 unique total request IDs.

| Depth | Lane | Route | Count |
|---:|---|---|---:|
| 2 | PEDIGREE_BASELINE | ESTABLISHED_CURRENT | 876 |
| 2 | PEDIGREE_INTERACTION | ESTABLISHED_CURRENT | 134 |
| 2 | TRANSITION_PRIORITY | ESTABLISHED_CURRENT | 240 |
| 3 | PEDIGREE_BASELINE | ESTABLISHED_CURRENT | 9,009 |
| 3 | PEDIGREE_INTERACTION | ESTABLISHED_CURRENT | 1,944 |
| 3 | TRANSITION_PRIORITY | ESTABLISHED_CURRENT | 5,604 |

Canonical C2B used 16 deterministic sequential shards over the same frozen window and Feature Mart. All 16 shard audits PASS; 0 missing value branches. There are 30,733 unique results for 30,733 unique C2A request IDs; the orchestrator checked exact request/result ID set equality. C2B merge PASS; 17,807 enriched shortlist rows. The canonical C2B request Parquet SHA-256 is `6ceddc75974661084aa3261b3220492639178fe499c87189ac420b325079ce61`.

## Sanity comparison and R1 acceptance

The canonical rerun matches PR #1800's provisional aggregate reference on C1 68,685; C2A 17,807; parent links 52,171; parent requests 14,129; and total exact requests 30,733. The recomputed labels also match the provisional totals: 367 incremental, 90 mixed, 17,350 jackpot-dependent.

The C2B request Parquet byte hash differs from the provisional local hash (`be76f7ecf8ccf453c3b7c1f0b23ca4d4db2931bc89a8c451a9086d05a840a371`). A Parquet byte hash is not a sorted request-ID set hash. The complete PyArrow fallback ID set was not retained in Git, so this task did not claim byte or exact-ID equivalence to that provisional run. Instead, the canonical rerun is the replacement authority: all frozen inputs and planner identity passed, C1 counts match, canonical DuckDB C2A counts/routes/parent/request totals match, and canonical C2B validated exact set equality internally. No unexplained aggregate membership/count difference remained before R3 decisions.

**R1 acceptance: `CANONICAL_R1_ACCEPTED`.** PR #1800 is now a provisional reference only.

## R3 family decisions

Rates use each family's C2 shortlist as denominator. Parent ROI delta min/median below are across available immediate-parent comparisons for incremental candidates. No composite score was used.

| Family | C1 | C2 | Incremental | Mixed | Jackpot-dependent | D2 / D3 incremental | Child support min / p10 / median / p90 / max | Recent 365d / 730d support median | Parent ROI delta min / median | Decision |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| PEDIGREE_CROSS | 41,012 | 11,963 | 266 (2.22%) | 68 (0.57%) | 11,629 (97.21%) | 30 / 236 | 16 / 23 / 50 / 161 / 683 | 21 / 38 | -117.21 / 89.26 | `EXTEND_FROZEN_FAMILY_TO_5Y` |
| PEDIGREE_TRANSITION_CROSS | 18,531 | 4,204 | 81 (1.93%) | 17 (0.40%) | 4,106 (97.67%) | 2 / 79 | 11 / 15 / 32 / 85 / 277 | 11 / 24 | -157.36 / 139.10 | `KEEP_3Y_OBSERVE_ONLY` |
| TRANSITION_CROSS | 9,142 | 1,640 | 20 (1.22%) | 5 (0.30%) | 1,615 (98.48%) | 0 / 20 | 47 / 48 / 112 / 521 / 561 | 39 / 69 | -81.75 / 78.94 | `STOP_FAMILY_EXPANSION` |

Temporal diagnostics by family (direction contradiction / one-year confinement / no 365d support / top3 exclusion removes both lanes):

- PEDIGREE_CROSS: 2,304 / 153 / 53 / 11,629.
- PEDIGREE_TRANSITION_CROSS: 786 / 72 / 13 / 4,106.
- TRANSITION_CROSS: 312 / 1 / 0 / 1,615.

Among incremental candidates, recent 365d win/place positive-direction counts are 209/184, 61/67, and 15/10 respectively; recent 730d counts are 231/223, 73/71, and 18/13. The largest coherent non-jackpot pool is PEDIGREE_CROSS, but its recent support and temporal diagnostics still warrant a frozen 5y stability check before any later design expansion. PEDIGREE_TRANSITION_CROSS remains observe-only. TRANSITION_CROSS has only 20 incremental candidates against a 98.48% jackpot-dependent shortlist and stops.

Representative examples are included in `results/r1_wave_a_3y_canonical/r1_summary.json`: 10 strongest non-jackpot incremental and 5 jackpot/temporal rejects per family. Each record contains readable conditions, exact child metrics, every immediate-parent comparison, and temporal diagnostics. `shortlist.csv` contains 100 rows, within the required bound. These examples are research evidence, not betting recommendations.

## PR disposition and next task

At review time PR #1800 and PR #1801 remain open and unmerged; neither is accepted as the final canonical R1 result. Recommend superseding/closing #1800 as provisional and #1801 as blocked-only, following repository GitHub policy. PR #1803 contains the orchestration helper and missing NumPy requirement used by the successful pinned-source run; it remains open for review. No PR was merged by this task.

Next instruction prepared: `horse-racing/jrdb/docs/edgedb/v0_4/collab/instructions/20261005_006_pedigree-cross-frozen-5y-extension_instruction.md`. It selects only the frozen `PEDIGREE_CROSS` family, reuses the same as-of date and thresholds, and prohibits depth-4 execution in that task.

No 5-year run, depth-4 run, threshold tuning, market-conditioned generation, SHADOW publication, or production serving change was performed.
