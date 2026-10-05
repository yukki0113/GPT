# EdgeDB v0.4 R1 Preflight / Wave-A Enablement — Result

Status: DONE  
Date: 2026-10-05  
Instruction: `collab/instructions/20261005_002_r1-preflight-and-wave-a-enable_instruction.md`  
Production impact: NONE

## Summary

- Wave A planner filters now run before shard assignment. The canonical lanes/depths produce 1,106 selected templates in 6 deterministic shards from the existing 47,371-template Stage B catalog.
- C1 and C2B now share a date-window helper and support the same explicit inclusive as-of endpoint. The endpoint is rejected if malformed or later than the maximum source race date. Nonpositive discovery years and malformed/all-null date domains fail cleanly.
- All 9 focused unit and synthetic-Parquet integration tests passed. Compilation and C1 workflow YAML parsing passed.
- A single representative depth-3 `PEDIGREE_INTERACTION` shard passed with the pinned canonical inputs. It took 7.946 seconds, peaked at 634,388 KiB RSS (about 619.5 MiB), and emitted 5,948 candidate rows in a 569,267-byte Parquet file.
- Recommended full Wave A route: **`LOCAL_SEQUENTIAL`**, parallelism 1. The full Wave A aggregation was not launched.

## Files changed

- `horse-racing/jrdb/src/jrdb_edge_v04_preflight.py` — shared deterministic lane/depth selection, catalog digest, strict ISO date validation, and calendar-window resolution.
- `horse-racing/jrdb/src/plan_jrdb_edge_v04_stage_c1_shards.py` — repeatable lane selection and min/max depth options; selection, source digest, and actual counts recorded before deterministic sharding.
- `horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c1_shard.py` — explicit `--as-of-date`, positive years and date-domain validation, inclusive lower/upper filter, endpoint-relative recent cutoffs, and requested/resolved endpoint audit fields.
- `horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c2b_shard.py` — matching date behavior and audit fields for exact parent/child metrics.
- `horse-racing/jrdb/tests/test_edge_v04_preflight.py` — standard-library unit tests and synthetic Parquet CLI integration tests for planner, C1, and C2B.
- `.github/workflows/jrdb_edge_v04_stage_c1_sharded_issue.yml` — Wave A defaults (three canonical lanes, depths 2–3, trailing 3y), optional as-of propagation, planner filter propagation, and Actions fallback concurrency set to 1.

The planner reads but never rewrites the canonical catalog. Explicit lane selection remains possible for any lane present in a catalog; `STATIC_CROSS` is not included in the Wave A defaults.

## Planner behavior

The planner applies lane/depth predicates to in-memory catalog rows before grouping and shard assignment. Empty selection, invalid depth ranges, duplicate template assignment, and shard-cap overflow fail closed. The plan includes:

- full source catalog count and SHA-256;
- requested lane list and depth range;
- actual selected counts by lane and depth;
- selected template IDs and their deterministic shard digests;
- explicit `uses_results=false`, `uses_roi=false`, and `uses_odds_or_popularity=false` provenance.

Identical input and options yielded identical plans in both unit and CLI tests.

## As-of and window semantics

- Without `--as-of-date`, the endpoint remains the maximum valid source `race_date`.
- With `--as-of-date YYYY-MM-DD`, the strict ISO date is the inclusive endpoint and must be no later than the maximum valid source date.
- The lower endpoint is calendar `as_of_date - discovery_years`, inclusive. A Feb. 29 endpoint falls back to Feb. 28 when the target year is not a leap year.
- C1 and C2B use the same helper and Arrow predicates `race_date >= start` and `race_date <= as_of`. Recent 365/730/1095-day cutoffs are derived from the resolved endpoint.
- Null dates are ignored when deriving the date domain; all-null/missing and malformed non-null dates fail. Null rows are dropped by the explicit boolean mask.

The integration fixture confirmed that rows before the 3y start and after explicit as-of do not affect C1 support/ROI/recent metrics or C2B exact metrics.

## Tests and validation

Command:

```text
PYTHONPATH=/tmp/edge-v04-deps python -m unittest discover -s horse-racing/jrdb/tests -p 'test_edge_v04_preflight.py' -v
```

Result: **9 tests passed in 4.561 seconds; 0 failures; 0 skips.** This includes synthetic Parquet CLI runs for the planner, C1, and C2B. The tests cover lane/depth filtering, exact one-time assignment, exclusions, empty selection, catalog hash, deterministic plans, inclusive explicit windows, later-row exclusion, leap-day fallback, positive years, malformed/all-null dates, C1/C2B window parity, and outside-window metric exclusion.

Also passed:

- `python -m compileall -q` on the shared helper, planner, C1, and C2B scripts;
- PyYAML `safe_load` of `.github/workflows/jrdb_edge_v04_stage_c1_sharded_issue.yml`.

## Pinned inputs and expected Wave A plan

The inputs were resolved from successful, unexpired GitHub Actions artifacts; no rebuild or alternate data route was used.

| Input | Canonical identity | Artifact and content hashes |
|---|---|---|
| Feature Mart | Run `36116777782`, `jrdb-edge-feature-mart-parquet-36116777782`; generation `edge_feature_mart_v0_2_g20260925_pq1`; producing commit `1ffbb5a4d8477c07d4fd2fa8f086677609ad5379` | Artifact ID `10856365234` (29,793,468-byte ZIP), artifact SHA-256 `19d713da2e6ebf57965de98952fbf18d79f9ddfd5c1996833af3267b1a53f725`; `edge_runner_fact.parquet`: 781,161 rows, 30,112,029 bytes, SHA-256 `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6` |
| Stage B catalog | Run `36262821119`, `jrdb-edge-v04-stage-b-36262821119`; producing commit `637dd32c64c23050472b023e6773b3c5657ac94d` | Artifact ID `10912552938` (5,623,586-byte ZIP), artifact SHA-256 `5e71e15aba78228404441790bf9a67e7cd461bed542bc510ee6e8744de20805d`; 47,371 templates; catalog SHA-256 `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba` |

Using the Wave A lanes `TRANSITION_PRIORITY`, `PEDIGREE_INTERACTION`, `PEDIGREE_BASELINE` and depths 2–3, the planner returned:

- by lane: `TRANSITION_PRIORITY` 586; `PEDIGREE_INTERACTION` 64; `PEDIGREE_BASELINE` 456;
- by depth: depth 2: 123; depth 3: 983;
- total: **1,106 templates, 6 shards**;
- plan SHA-256: `de823224c0f10690232835b35557517c474377734b2df347ca3a9a08daa3ded8`.

## Representative resource preflight

- Status: **PASS**
- Evaluator source commit: `a03dd1558c447964dec261a7adcb99b2634f9993`
- Shard: `pedigree_interaction-d3-s000` (the highest estimated-cost depth-3 transition/pedigree-interaction shard in the filtered plan)
- Selected templates: 60
- Estimated cost: 27,599,991
- Frozen request: discovery years 3; as-of `2025-12-28`; inclusive window `2022-12-28` through `2025-12-28`; win ROI 110; place ROI 105; max 100 candidates per template
- Input rows: 781,161 all-history; 143,102 in-window
- Terminal groups evaluated: 85,235; admitted before template cap: 23,557
- Output candidates: 5,948; Parquet size 569,267 bytes; SHA-256 `78743657dabf01ec063ca61dd8817d44aa7d8feaac84b2b6051e9eff407062e2`
- Elapsed wall time: 7.946 seconds
- Peak child RSS: 634,388 KiB (about 619.5 MiB), measured with `resource.getrusage(RUSAGE_CHILDREN)`
- Audit status: `PASS`; the audit records input hashes, requested/resolved as-of, window, and source artifact IDs.

The 3y endpoint is the input's maximum race date, `2025-12-28`. Recent cutoffs in the audit are `2024-12-28`, `2023-12-29`, and `2022-12-29` for 365/730/1095-day windows.

## Execution route

Recommend **`LOCAL_SEQUENTIAL`** for full R1 Wave A, with parallelism **1**. The actual highest-estimated-cost depth-3 transition/pedigree-interaction shard completed locally under 8 seconds with about 620 MiB peak RSS. The plan has only six shards. Sequential execution avoids multiplying the full Feature Mart read and peak memory. The Actions workflow remains available with `max-parallel: 1` for a case where canonical artifact access or formal hosted provenance is needed.

This is a measured route recommendation from one representative shard, not a claim that every failure mode is exhausted. The broad aggregation, merge, C2 enrichment, and any 5y/depth-4+ run remain unexecuted.

## Commits and remaining risks

- `511f04cf9f03f775aae62ae0acdde9b8dfaf2917` — planner/window implementation, tests, and Wave A workflow enablement.
- `a03dd1558c447964dec261a7adcb99b2634f9993` — keep planner lane selection explicit and unrestricted to known lane labels.
- The representative candidate Parquet is temporary under `/tmp`; it is not committed. Broad candidate rows remain outside Git.
- No production-serving code or support/ROI thresholds were changed.
- Remaining risk: the 5y rerun has not been performed; C2B behavior is integration-tested on a small synthetic fixture, not a full shortlisted candidate set. Future C2B callers must pass the same pinned Feature Mart, `discovery-years`, and explicit `as-of-date` as C1.

## Recommended next task

Run full R1 C1 Wave A locally and sequentially using the same pinned run/artifact IDs and frozen endpoint. After re-downloading and verifying the artifacts, set `FEATURE` and `TEMPLATES` to the extracted canonical Parquet paths, then run:

```bash
PLAN=work/r1-wave-a/shard_plan.json
SHARDS=work/r1-wave-a/shards
FINAL=work/r1-wave-a/final

python horse-racing/jrdb/src/plan_jrdb_edge_v04_stage_c1_shards.py \
  --template-parquet "$TEMPLATES" --output "$PLAN" \
  --search-lane TRANSITION_PRIORITY \
  --search-lane PEDIGREE_INTERACTION \
  --search-lane PEDIGREE_BASELINE \
  --min-depth 2 --max-depth 3

for SHARD_ID in $(python -c 'import json,sys; print(" ".join(s["shard_id"] for s in json.load(open(sys.argv[1]))["shards"]))' "$PLAN"); do
  python horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c1_shard.py \
    --feature-parquet "$FEATURE" --template-parquet "$TEMPLATES" \
    --shard-plan "$PLAN" --shard-id "$SHARD_ID" \
    --output-dir "$SHARDS/$SHARD_ID" \
    --discovery-years 3 --as-of-date 2025-12-28 \
    --min-win-roi 110 --min-place-roi 105 --max-per-template 100
done

python horse-racing/jrdb/src/merge_jrdb_edge_v04_stage_c1_shards.py \
  --shard-plan "$PLAN" --shards-dir "$SHARDS" \
  --output-dir "$FINAL" --max-per-template 100
```

The next task should run C2A/C2B using the identical feature hash, `--discovery-years 3`, and `--as-of-date 2025-12-28`, then produce `r1_summary.json`, `r1_report.md`, and bounded `shortlist.csv`. Keep the full candidate Parquet outside Git.
