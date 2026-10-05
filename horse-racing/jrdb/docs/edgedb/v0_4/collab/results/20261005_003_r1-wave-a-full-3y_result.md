# EdgeDB v0.4 R1 Wave A Full 3y — Result

Status: DONE  
Date: 2026-10-05  
Instruction: `collab/instructions/20261005_003_r1-wave-a-full-3y_instruction.md`  
Instruction commit: `8259b357fcf72bede30ca6723dee7ddc6a9a9bbc`  
Instruction blob on main: `0f7787aa4eaa36fae91568993d28ddfe5b9b9c4c`  
Repository main base observed: `bdb6fef165847d5f5a999b6c11b2920d43356268`  
Production impact: NONE

## Summary

Completed C1 Wave A discovery, deterministic merge, C2A shortlist / parent requests, C2B exact metrics, immediate parent comparisons, temporal warnings, and bounded outputs. No five-year run, depth-4+ run, market-conditioned generation, SHADOW publication, or production serving change was made.

- Window: inclusive `2022-12-28 .. 2025-12-28`; as-of `2025-12-28`.
- C1 plan: 1,106 templates / 6 shards; plan SHA-256 `de823224c0f10690232835b35557517c474377734b2df347ca3a9a08daa3ded8`. Recomputed selected set and shard assignments matched the preflight plan exactly.
- C1 merge: PASS, 68,685 candidates, no duplicate candidate IDs.
- C2A: 17,807 shortlisted candidates; 52,171 child-parent links; 14,129 unique parent metric requests; 30,733 total exact requests. The `EMERGING_HIGH_ORDER` route was naturally zero at depths 2–3.
- C2B: 30,733 requests / 30,733 unique results; no missing, extra, or duplicate IDs; no missing value branches; same pinned Feature Mart hash and window.
- Incrementality labels: 367 `INCREMENTAL_CANDIDATE`, 17,350 `JACKPOT_DEPENDENT`, 90 `MIXED_PARENT_INCREMENTALITY`.
- Temporal warnings: 3,402 contradicted 730d/full-window directions; 226 single-year value; 66 no 365d support; 17,350 lost both-lane break-even after top-three exclusion. Warning counts can overlap.
- Git-facing shortlist: 100 rows; compact JSON arrays retain every immediate parent and its metric comparison for each listed candidate.

## Frozen inputs and source identity

- Feature Mart: run `36116777782`, artifact `jrdb-edge-feature-mart-parquet-36116777782`, generation `edge_feature_mart_v0_2_g20260925_pq1`; 781,161 rows; parquet SHA-256 `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`; ZIP SHA-256 `19d713da2e6ebf57965de98952fbf18d79f9ddfd5c1996833af3267b1a53f725`.
- Stage B: run `36262821119`, artifact `jrdb-edge-v04-stage-b-36262821119`; 47,371 templates; catalog SHA-256 `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba`; ZIP SHA-256 `5e71e15aba78228404441790bf9a67e7cd461bed542bc510ee6e8744de20805d`.
- The local workspace base was `21f7c58116bbc8ee75f1d05ccfebb60ae66f0821`, with the prior preflight implementation present as uncommitted workspace changes. The execution source SHA-256 values for the planner, C1 evaluator/merger, C2B evaluator, and window helper are recorded in `r1_summary.json` so the exact working-tree code is identifiable.

## C1 shards

All six shards passed sequentially (`LOCAL_SEQUENTIAL`, parallelism 1). Outcomes and per-shard elapsed time, peak RSS, input hashes, candidate rows, estimated cost, output size, and audit status are in `r1_report.md` and `r1_summary.json`.

- Total evaluator time: 89.428s.
- Maximum shard RSS: 709,660 KiB (~693.0 MiB).
- Selected templates with zero candidates: 14.
- Templates reaching the 100-candidate cap: 490.
- Candidate counts by family: `PEDIGREE_CROSS` 41,012; `PEDIGREE_TRANSITION_CROSS` 18,531; `TRANSITION_CROSS` 9,142.

By lane × depth, candidate counts were: `PEDIGREE_BASELINE` D2 3,503 / D3 31,211; `PEDIGREE_INTERACTION` D2 350 / D3 5,948; `TRANSITION_PRIORITY` D2 932 / D3 26,741. Full descriptive distributions for support, wins/places, ROI, top-one share, jackpot rate, and 365/730/1095-day metrics are in the compact summary.

## C2 execution note and integrity

This executor did not have an importable DuckDB package; shell package download was blocked by the configured proxy. To complete the research pass, C2A's existing frozen SQL predicates were reproduced deterministically with PyArrow without changing thresholds. The existing C2B exact evaluator ran unchanged. Because all exact requests fit one sequential shard, that shard is already the complete exact metric table; its IDs and feature/window provenance were audited. Immediate-parent joining used a deterministic Python join over unique request IDs. Complete all-candidate join evidence stayed under `/tmp`, outside Git; the 100-row review file retains full parent comparisons for its rows.

The fallback implementation hashes and exact request/result integrity are recorded in the summary. The limitation is that C2A's DuckDB SQL implementation itself was not executed in this runtime; its predicates were mirrored literally and returned audited counts. No output depends on a changed scientific threshold.

## Decision and next action

Recommended R3 decision: **`MIXED_BRANCH_DECISION`**. `PEDIGREE_CROSS` contributes the largest absolute count of all-parent incremental candidates (266 of 11,963 C2A rows); `PEDIGREE_TRANSITION_CROSS` contributes 81 of 4,204; `TRANSITION_CROSS` contributes 20 of 1,640. The high number of top-three-sensitive candidates and temporal warnings argue for reviewing the families separately before selecting any five-year extension or controlled depth-4 work. Do not begin R3 as part of this task.

## Git handoff

Requested compact outputs:

- `collab/results/r1_wave_a_3y/r1_summary.json`
- `collab/results/r1_wave_a_3y/r1_report.md`
- `collab/results/r1_wave_a_3y/shortlist.csv` (100 rows)

This result file is the handoff record. Git commit / PR identifiers will be recorded here after the connector write completes.

Open PR preflight found no open PRs. PR #1799 was confirmed merged as `c8628f4c1dd571d6eea3436da21262f5dc53c171`; no relevant pending merge remains.
