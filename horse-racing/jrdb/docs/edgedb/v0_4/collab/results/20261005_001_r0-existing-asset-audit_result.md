# EdgeDB v0.4 R0 Existing-Asset Audit — Result

Status: DONE  
Date: 2026-10-05  
Instruction: `collab/instructions/20261005_001_r0-existing-asset-audit_instruction.md`  
Audited repository revision: `e6f1d2c6c9ebf9a530dd9589cbc42533e944e894`  
Production impact: NONE

## Executive findings

1. **Trailing 3y:** the current C1 evaluator supports `--discovery-years 3`. It derives the as-of date from the maximum valid `race_date`, calculates a calendar-year start, and applies an inclusive lower-bound filter before candidate grouping. Metrics and the 365/730/1095-day rollups are calculated from that filtered table. No full-history result/ROI statistic is used to admit a candidate. This is code inspection, not a successful post-fix run; focused date-window tests are still needed before R1.
2. **Wave A:** the Stage B catalog already contains the necessary lane/depth metadata and can be reused. The C1 planner currently has no lane or depth filter, so a small planner change is required before running only Wave A. Filter at planning time, before shard assignment; do not regenerate the 47,371-row catalog.
3. **5y-r3 failure:** run `36803275900` failed during shard evaluation due to a code defect: `max_date` was referenced but not defined when recent-window cutoffs were built. The sampled job traceback points to evaluator line 122 at commit `8106ce8122976bcf2e0d07c8ba5f427f6826dc54`. The run's job list reports 29 failures. This is not evidence of OOM, timeout, or shard imbalance. The evaluator at the audited revision now derives `max_date` and accepts `--discovery-years`; the missing-name defect was therefore fixed after the failed run.
4. **Execution route:** prefer deterministic Codex/local execution for R1 C1/C2 after a small representative-shard resource preflight and after pinning the two input artifacts. Use Actions when local memory/runtime is inadequate, when Actions-only artifacts or credentials are required, or when a formal hosted audit trail is needed. The failed 5y run provides no reason to make Actions the default.
5. **Before R1:** add lane/depth filters to the planner and focused tests for planner selection and date-window semantics. No full aggregation is warranted in R0.

## Files and evidence inspected

GitHub connector reads were performed against `yukki0113/GPT` at the audited revision above. The local checkout is older than that revision; source findings below refer to the GitHub revision, not the stale local source tree.

- `horse-racing/jrdb/src/audit_jrdb_edge_v04_feature_feasibility.py` — Stage A read-only feature, leakage, coverage, and feasibility audit.
- `horse-racing/jrdb/src/build_jrdb_edge_v04_candidate_templates.py` — Stage B template catalog generator.
- `horse-racing/jrdb/src/build_jrdb_edge_v04_candidates.py` — earlier value-candidate builder; not the current catalog-first C1 route.
- `horse-racing/jrdb/src/plan_jrdb_edge_v04_stage_c1_shards.py` — deterministic C1 planner.
- `horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c1_shard.py` — current C1 shard evaluator.
- `horse-racing/jrdb/src/merge_jrdb_edge_v04_stage_c1_shards.py` — deterministic merge and provenance checks.
- `horse-racing/jrdb/src/prepare_jrdb_edge_v04_stage_c2.py` and `horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c2b_shard.py` — C2 shortlist, parent requests, and exact metrics.
- `horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c.py` — older one-shot C stage entrypoint.
- `.github/workflows/jrdb_edge_v04_stage_a_issue.yml`, `jrdb_edge_v04_stage_b_issue.yml`, `jrdb_edge_v04_stage_c1_sharded_issue.yml`, and `jrdb_edge_v04_stage_c2a_issue.yml` — execution and artifact routing.
- `horse-racing/jrdb/docs/EdgeDB_v0_4_HighOrder_Transition_Value_Discovery_Design_20260926.md` and `horse-racing/jrdb/docs/edgedb/v0_4/EdgeDB_v0_4_Research_Execution_Redesign_20261005.md` — original and current research designs.
- Stage C1 run `36803275900`, its run metadata, job list, and a failed evaluator job log; parent issue `#1536`.

The repository tree at the audited revision contains no dedicated EdgeDB v0.4 C1 planner/evaluator test module. The failed run's artifact listing was empty, so no shard output or input-size evidence was available there. The artifact listing for historical run `36697607028` was also empty at inspection time.

## Reusable assets

### Stage A and B

- Stage A reads the accepted Feature Mart and records feature availability, leakage roles, cardinality/coverage, and unsupported/deferred transitions. Its audit artifact and Stage B's audit JSON provide usable contracts and provenance.
- Stage B's catalog-first generator is deterministic and market/result blind. Its rows include `template_id`, `depth`, `search_lane`, `family`, `dimensions_json`, and `parent_template_ids_json`. It already records the exact feature-set parent graph. The reported 47,371 templates are small enough to retain and filter; Stage B does not need to be rebuilt for Wave A.
- The catalogs describe dimension templates, not value-specific candidate prefixes. The older value materializer is not needed for the current C1 flow.

### Stage C1

- The planner assigns every input template to exactly one deterministic shard, balances using `estimated_group_upper_bound`, and records template digests. It is result/ROI blind.
- The evaluator reads the fixed set of candidate dimensions plus date and result labels; it constructs a template trie, filters rows by the discovery window, then traverses/group-by values. Support floors, ROI/rate inputs, top-one dependence, recent metrics, candidate IDs, and per-template caps are already implemented.
- The merge checks expected shard files, shard status/digests, unique candidate IDs, and common source/catalog/plan/policy provenance. It reapplies the global per-template cap and writes the candidate parquet, audit/manifest, and shard inventory.
- The catalog, C1 planner/evaluator/merge, and C2 scripts provide a reusable route; the old one-shot Stage C workflow is not the preferred R1 entrypoint.

### C2 and downstream

- C2A builds a shortlist from C1 results and derives immediate parent metric requests. C2B re-evaluates requested exact predicates and calculates top-three exclusion and temporal/year metrics. C2B has its own `--discovery-years` parameter, so the same window must be passed to it and recorded; otherwise child and parent metrics could be incomparable.
- This split is suitable for keeping broad discovery separate from the more expensive parent/robustness calculations. No production-serving path is involved in these scripts or workflows.

## Window support and caveats

In the audited C1 evaluator:

- `--discovery-years` is an integer argument with default 5; set it to `3` for R1.
- `max_date` is the maximum non-null date after string conversion. `discovery_start` is computed by subtracting calendar years (with Feb. 29 falling back to Feb. 28); the filter is `race_date >= discovery_start`. Both endpoints are therefore included through the maximum source date. The resolved start/end dates and row counts are written to each shard audit.
- Filtering occurs on the Arrow table before dimension encoding, trie traversal, support checks, grouping, or ROI calculation. Full-history is used only to find the as-of maximum and report `source_rows_all_history` / input digest. No full-history ROI, support, or parent metric participates in a 3y candidate decision.
- The 365/730/1095-day metrics use inclusive string comparisons from `max_date - N days`. These are rolling day windows, not exact calendar-year windows.
- C2B independently applies the same `discovery-years` procedure to the same feature artifact. The C2B request/workflow must be pinned to the same feature artifact, years value, and effective end date as C1.

Risks to close before starting R1:

- The evaluator derives as-of from the maximum date in the supplied artifact; it has no explicit `--as-of-date` override. Pinning the artifact hash makes this deterministic, but a future explicit as-of option would make window comparisons clearer.
- The current code assumes ISO-sortable date strings for the lexical filter. Stage A's contract and workflow use `race_date` as a string, but the failed r3 run stopped before exercising date filtering. Add tests using the actual parquet date type and ISO boundary rows; reject malformed/all-null date columns rather than silently forming an invalid window.
- The integer option is not visibly validated as positive. Add a positive-years check in the same focused patch.
- No C1/C2 post-fix execution or regression test was performed in R0. Thus 3y is supported by implementation shape, but should not be declared empirically validated until the focused tests pass.

## Wave A lane/depth restriction

Current planner groups every catalog row by `(search_lane, depth)` and then asserts every row was assigned. It has no lane/depth selection options. Evaluator-side filtering would leave the plan, template digests, shard counts, and provenance describing work that was not evaluated. Filtering the shared catalog file itself would also obscure its canonical digest.

**Smallest safe change:** add explicit repeatable lane selection and min/max depth options to the planner. Apply them to in-memory catalog rows before grouping/assignment; record requested and selected lanes/depths and source catalog hash in the plan; fail if selection is empty; assign each selected template once. Leave the source Stage B parquet untouched. The evaluator and merger can then keep consuming the resulting plan as they do today.

For Wave A, plan the lane set `TRANSITION_PRIORITY`, `PEDIGREE_INTERACTION`, and `PEDIGREE_BASELINE`, depths 2–3. `TRANSITION_PRIORITY` already includes pedigree-transition templates; `family` lets reports separate those from pure transition crosses. `PEDIGREE_BASELINE` retains baseline candidates. C2's parent metric request stage can additionally measure exact parents for shortlisted children, even when a parent is not itself an admitted C1 candidate.

## Progressive expansion

The Stage B catalog supports structural expansion without rebuilding: it contains depth 2–6 templates and each template's immediate parent template IDs. For Wave B, select depth-4 templates whose parent template is among approved Wave A families. This avoids regenerating Stage B.

It does **not** support value-prefix-directed expansion today. C1 traverses every observed value branch for every template in a shard. The minimum compatible addition for a truly approved-parent/prefix-only Wave B is an allowlist of approved parent condition fingerprints in the plan plus evaluator pruning/admission that extends only value combinations matching those parent predicates. Preserve that allowlist and digest in each shard audit. For exceptional depth 5–6 work, apply the same mechanism recursively to approved lower-depth conditions. If only structural parent-template filtering is added, explicitly label that as template-family restriction; it still evaluates all value combinations in each selected depth-4 template.

## 5y-r3 failure diagnosis

- Run: [36803275900](https://github.com/yukki0113/GPT/actions/runs/36803275900), title `[JRDB_EDGE_V04_STAGE_C1_SHARDED] roi-screen-trailing5y-r3`.
- Run head: `8106ce8122976bcf2e0d07c8ba5f427f6826dc54`; 29 jobs concluded failure in the job listing.
- A failed `evaluate (pedigree_baseline-d4-s001)` job log shows `NameError: name 'max_date' is not defined` at `evaluate_jrdb_edge_v04_stage_c1_shard.py:122`, while building the 365/730/1095-day cutoffs. The evaluator at that run commit had no `--discovery-years` argument and did not derive `max_date` before the reference.
- Classification: **code defect**. The exception occurred before candidate traversal/ROI aggregation. This rules out memory, timeout, artifact size, and imbalance as the cause of the observed failure. The job list shows multiple evaluator failures; only a representative traceback was inspected, so identical tracebacks across all failed jobs were not independently verified.
- At the audited revision, the evaluator accepts `--discovery-years`, validates that dates exist, derives `max_date`, and filters the discovery table before candidate evaluation. This fixes the specific undefined-name defect. The unavailable run artifacts prevent inspection of partial outputs, memory consumption, artifact sizes, and per-shard work distribution. The current fix also lacks a focused regression test in the repository tree.

## Minimal changes before R1

1. Add planner lane and depth filters, plan provenance for the filter/source catalog, and an empty-selection failure.
2. Add focused small-fixture tests for: 3-year inclusive start/end boundaries; pre-group filtering; discovery ROI/support unaffected by rows before the window; recent-window cutoffs; matching C1/C2B window configuration; planner lane/depth selection and one-template/one-shard invariants; and invalid/all-null dates or nonpositive years.
3. Add a compact report step that consumes C1/C2 outputs. Keep full candidate rows in run artifacts only, not Git.
4. Before full R1, run one representative shard as a resource preflight and record elapsed time, peak memory, input size, and output size. No large aggregation is part of R0.

No production code change is required. The undefined-`max_date` defect was already fixed in the audited revision; do not reapply it.

## R1 execution entrypoint

After item 1 is implemented, create a filtered shard plan from the existing catalog:

```bash
python horse-racing/jrdb/src/plan_jrdb_edge_v04_stage_c1_shards.py \
  --template-parquet inputs/candidate_template_catalog.parquet \
  --output work/r1-wave-a/shard_plan.json \
  --search-lane TRANSITION_PRIORITY \
  --search-lane PEDIGREE_INTERACTION \
  --search-lane PEDIGREE_BASELINE \
  --min-depth 2 --max-depth 3
```

Then invoke `evaluate_jrdb_edge_v04_stage_c1_shard.py` once per generated `shard_id`, passing the same pinned Feature Mart/catalog/plan, `--discovery-years 3`, output directory, and frozen admission thresholds. Merge only after every planned shard passes using `merge_jrdb_edge_v04_stage_c1_shards.py`. Run C2A and C2B against the merged C1 artifact with the same feature hash and `--discovery-years 3`. Current planner does **not** accept the proposed lane/depth flags yet; the command is the target entrypoint after the minimal planner patch, not a command that can be run unchanged today.

## R1/R2 execution routing

- **R1 broad C1 screen:** Codex/local is preferred after the resource preflight if the immutable Feature Mart and Stage B artifacts can be made available locally. Lane/depth filtering reduces the number of templates and emitted candidates; local execution avoids multiplying a full feature-table read across 12 hosted runners and makes small deterministic reruns easier. Pin SHA-256 hashes and save request, plan, per-shard audits, and compact summary.
- **R1 C2 exact parent/robustness work:** Codex/local is also preferred if the shortlist and feature input fit the available memory. C2B shards by request ID, so it can be run sequentially or with controlled parallelism. Keep only compact parent/child evidence in the handoff.
- **Use GitHub Actions** if canonical input artifacts are only accessible there, local memory/runtime is insufficient, or a hosted immutable execution record is required. If used, reduce `max-parallel` from 12 based on preflight measurements, retain per-shard evidence long enough for audit, and avoid retrying successful shards. Current workflow depends on GitHub artifact access and `GITHUB_TOKEN`; source evaluation itself shows no external secret dependency. Actions remains a deliberate fallback/audit route, not an automatic default.
- **R2 conditional 5y or depth expansion:** run only if R1 evidence justifies it. Use the same frozen definitions and input hashes; local execution remains suitable after resource checks. Use Actions when the same artifact-access, capacity, or immutable-audit constraints apply. For depth 4–6, do not run until approved-prefix support is implemented.

## Compact R1 output contract

Produce `r1_summary.json` and `r1_report.md`, plus a small `shortlist.csv` (or Parquet) containing shortlist and near-shortlist records. Keep the broad candidate parquet and shard evidence outside Git.

`r1_summary.json` should contain:

- `schema_version`, `status`, run ID, source commit/policy version, input artifact IDs and SHA-256 hashes, requested lane/depth set, frozen thresholds, as-of date, inclusive window start/end, and execution/resource measurements;
- per lane × depth: templates planned/evaluated, terminal groups evaluated, candidate counts, gate-pass counts, and top rejection-reason counts;
- support `n` and win/place rate/ROI distributions (count, min, p10, median, p90, max); use wins/n and places/n for rates;
- jackpot dependence: top-one contribution distributions and counts/ratios over the existing 70% flag; include top-three exclusion after C2B;
- temporal dispersion: distinct race days and years/periods, plus recent 365/730/1095-day support and ROI distributions;
- parent incrementality: child and exact parent IDs/conditions, parent support/metrics, absolute ROI/rate deltas, and pass/fail gate;
- shortlist and near-shortlist counts with a bounded reason-coded record list.

Each shortlist row should include candidate/template IDs, lane, family, depth, conditions, `n`, wins/places, rates, win/place ROI, recent support/ROI, top-one/top-three dependency and exclusion metrics, temporal counts, immediate parent IDs and deltas, decision bucket, and rejection/near-shortlist reasons. The Markdown report should summarize the distributions and list the bounded records. Do not commit millions of rows or tune thresholds against observed ROI.

## Tests, commits, and unresolved items

- Tests run: none. R0 was source/workflow/log inspection only; no aggregation was launched and no tests were added or run.
- Code changes: none. Only this audit result is produced.
- Commit made: none in this working copy. Audited GitHub source revision is `e6f1d2c6c9ebf9a530dd9589cbc42533e944e894`.
- Unresolved: current input artifact's actual `race_date` Arrow type and size were not retained in the failed run; per-shard memory/runtime/output sizes are unknown; successful historical C1 artifacts were unavailable at inspection; post-fix 3y behavior remains untested; prefix-directed value pruning is not implemented.

## Recommended next action

Implement the planner lane/depth selection and small date/planner regression tests, then run a single representative Wave A shard as a resource preflight. If those pass, execute R1 C1 and C2 locally with pinned inputs and produce only the compact summary/report as the Git handoff. Keep 5y and depth-4+ work gated on R1 evidence.
