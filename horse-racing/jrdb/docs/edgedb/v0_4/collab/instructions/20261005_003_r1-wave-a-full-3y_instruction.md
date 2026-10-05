# EdgeDB v0.4 R1 Wave A — Full 3y Discovery / Robustness Instruction

Status: TODO  
Date: 2026-10-05  
Research decision owner: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Execute the full EdgeDB v0.4 R1 Wave A research pass over the frozen trailing-3y window, using the already validated local sequential route.

This task must complete:

1. C1 full Wave A discovery;
2. deterministic merge;
3. C2A shortlist / parent-request preparation;
4. C2B exact child/parent robustness metrics;
5. child-vs-parent incrementality join;
6. compact R1 summary / report / bounded shortlist for ChatGPT research review.

Do **not** perform a 5y expansion or depth-4+ expansion in this task.

## Canonical references

Research redesign:

`horse-racing/jrdb/docs/edgedb/v0_4/EdgeDB_v0_4_Research_Execution_Redesign_20261005.md`

R0 result:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_001_r0-existing-asset-audit_result.md`

R1 preflight result:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_002_r1-preflight-and-wave-a-enable_result.md`

## Frozen inputs

Use exactly the pinned inputs validated in R1 preflight unless an integrity check proves them unavailable/corrupt.

### Feature Mart

- source run: `36116777782`
- artifact: `jrdb-edge-feature-mart-parquet-36116777782`
- generation: `edge_feature_mart_v0_2_g20260925_pq1`
- expected `edge_runner_fact.parquet` rows: `781,161`
- expected SHA-256:
  `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`

### Stage B catalog

- source run: `36262821119`
- artifact: `jrdb-edge-v04-stage-b-36262821119`
- expected templates: `47,371`
- expected catalog SHA-256:
  `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba`

If the inputs are redownloaded, verify hashes before execution.

Do not silently substitute a newly rebuilt Feature Mart or Stage B catalog.

## Frozen R1 research request

### Window

- `discovery_years = 3`
- explicit `as_of_date = 2025-12-28`
- expected inclusive discovery window:
  `2022-12-28 .. 2025-12-28`

### Wave A lanes

- `TRANSITION_PRIORITY`
- `PEDIGREE_INTERACTION`
- `PEDIGREE_BASELINE`

### Depth

- min depth: 2
- max depth: 3

### C1 admission parameters

Keep existing frozen values:

- min win ROI: 110
- min place ROI: 105
- max per template: 100
- existing lane/depth support floors

Do not tune any threshold after seeing results.

## Expected planner identity

Preflight observed:

- selected templates: `1,106`
- shards: `6`
- depth 2: `123`
- depth 3: `983`
- TRANSITION_PRIORITY: `586`
- PEDIGREE_INTERACTION: `64`
- PEDIGREE_BASELINE: `456`

A fresh deterministic plan from the same catalog/options should reproduce the same selected template set and shard assignment semantics.

If materially different, stop and explain before running broad evaluation.

## Execution route

Canonical route for this task:

`LOCAL_SEQUENTIAL`

Parallelism:

`1`

Reason: representative high-cost Wave A shard passed in 7.946s at ~619.5 MiB peak RSS and the plan contains only 6 shards.

Do not move to multi-process parallel execution simply to reduce wall-clock time.

GitHub Actions is fallback only if the frozen canonical inputs cannot be used locally or local execution encounters a demonstrated capacity/runtime failure.

## Phase A — C1 full Wave A

1. resolve and hash-verify frozen inputs;
2. generate the Wave A shard plan;
3. execute all six shards sequentially;
4. retain per-shard audit records;
5. merge only after every planned shard passes;
6. verify merge provenance / unique candidate IDs / common input hashes.

Record per shard:

- shard id;
- lane/depth;
- template count;
- estimated cost;
- elapsed time;
- peak RSS if measurable;
- terminal groups evaluated;
- admitted-before-cap count;
- final candidate count;
- output size;
- audit status.

Do not commit broad candidate Parquet to Git.

## Phase B — C1 descriptive summary

Before C2A, summarize C1 without altering thresholds.

Required by lane × depth:

- templates evaluated;
- terminal groups evaluated;
- candidate count;
- candidate rate per terminal group;
- n distribution: min / p10 / median / p90 / max;
- wins and places distribution;
- win ROI distribution;
- place ROI distribution;
- top1 win contribution distribution;
- top1 place contribution distribution;
- jackpot flag count/rate;
- n_365 / n_730 / n_1095 distributions;
- win/place ROI 365/730/1095 distributions.

Also report:

- candidate count by family;
- duplicate candidate ID count;
- number of templates producing zero candidates;
- number of templates hitting the max-per-template cap.

These are descriptive research facts, not new gates.

## Phase C — C2A

Run:

`prepare_jrdb_edge_v04_stage_c2.py`

against the merged C1 candidate artifact.

Important:

- do not change C2A thresholds;
- Wave A contains depth 2–3, so the historical `EMERGING_HIGH_ORDER depth>=5` route should naturally contribute zero records;
- report this fact rather than modifying the C2A policy to force a second route.

Record:

- C1 candidate count;
- C2 shortlist count;
- entry route counts;
- child-parent map count;
- unique parent metric requests;
- unique metric requests.

## Phase D — C2B exact metrics

Execute C2B locally with the same frozen:

- Feature Mart hash;
- `--discovery-years 3`;
- `--as-of-date 2025-12-28`.

Choose a deterministic sequential shard count appropriate for the request volume.

Do not use a different window for parents.

Aggregate all C2B metric result shards into one exact-metric table after verifying:

- every request has exactly one result;
- no duplicate metric_request_id;
- common feature hash;
- common discovery start/end;
- common resolved as-of;
- no missing shard.

If no existing merger exists, implement a small deterministic merger/auditor rather than manual concatenation.

## Phase E — Child / parent incrementality

Join:

- `c2_shortlist_with_metric_id.parquet`;
- `child_parent_map_raw.parquet`;
- exact C2B child/parent metrics.

For each child, calculate each immediate parent's metrics and preserve **all immediate parents**.

At minimum calculate:

- child n / wins / places;
- child win/place rate;
- child win/place ROI;
- child ROI ex top1 / ex top3;
- child unique race days / years;
- child recent 365/730 metrics;
- parent n / wins / places;
- parent win/place rate;
- parent win/place ROI;
- parent ROI ex top1 / ex top3;
- parent unique race days / years;
- absolute child-parent win-rate delta;
- absolute child-parent place-rate delta;
- child-parent win-ROI delta;
- child-parent place-ROI delta;
- support ratio child_n / parent_n.

Do not collapse multiple parents into one number only.

Also provide:

- strongest parent comparison;
- weakest parent comparison;
- whether the child appears incremental against **all** immediate parents;
- whether the apparent edge is driven mainly by one removed dimension.

### Research-only incrementality labels

Use these as descriptive labels; do not interpret them as production grades.

- `INCREMENTAL_CANDIDATE`
  - child remains positive after top3 exclusion in at least one of win/place;
  - child is not top1-jackpot dependent on the corresponding lane;
  - child improves the corresponding ROI versus every immediate parent;
  - child has nonnegative corresponding hit-rate delta versus every immediate parent.

- `MIXED_PARENT_INCREMENTALITY`
  - child improves versus some but not all immediate parents.

- `PARENT_REDUNDANT`
  - no meaningful directional improvement versus immediate parents.

- `JACKPOT_DEPENDENT`
  - apparent value is materially dependent on top1/top3 payouts and does not survive exclusion.

- `TEMPORALLY_THIN`
  - evidence exists but recent/temporal support is too sparse for interpretation.

These labels are for compact review only. Preserve underlying metrics so ChatGPT can override the interpretation.

Do not invent a new ROI cutoff to decide "meaningful." Where the label cannot be assigned without a new arbitrary cutoff, prefer `MIXED_PARENT_INCREMENTALITY` / explicit metrics instead of tuning.

## Phase F — Temporal evidence

For shortlisted candidates, report:

- unique race days;
- unique years;
- win hit years;
- place hit years;
- annual ROI standard deviation;
- n / ROI for 365d;
- n / ROI for 730d;
- n / ROI for 1095d;
- full 3y n / ROI.

Flag obvious cases where:

- all value is confined to one year;
- recent 365d has no support;
- 730d direction contradicts full 3y direction;
- top3 exclusion destroys the value signal.

Do not create a universal stability score.

## Phase G — Compact research outputs

Implement a deterministic compact reporter if none exists.

Create locally:

- `r1_summary.json`
- `r1_report.md`
- `shortlist.csv`

### r1_summary.json

Must include:

- schema version;
- status;
- source commit;
- frozen input identities/hashes;
- frozen window/as-of;
- request parameters;
- planner counts;
- per-shard resource metrics;
- C1 lane/depth distributions;
- C2 counts;
- C2B request/result integrity;
- incrementality label counts;
- temporal warning counts;
- no-market-generation assertion;
- production unchanged assertion.

### shortlist.csv

Bound the Git-facing shortlist to at most **100 rows**.

Selection for the bounded review file must be deterministic and transparent.

Preferred order:

1. all `INCREMENTAL_CANDIDATE` rows, sorted by:
   - non-jackpot first;
   - larger minimum parent ROI delta on the successful lane;
   - larger support;
   - stable candidate_id;
2. then `MIXED_PARENT_INCREMENTALITY` rows if fewer than 100;
3. do not pad with clearly redundant/jackpot-dependent rows merely to reach 100.

This ordering is for human review, not a production rank.

The broad C1/C2 Parquet artifacts stay outside Git.

## Git handoff result

Write:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_003_r1-wave-a-full-3y_result.md`

Also commit the compact machine-readable outputs if reasonably small under:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/r1_wave_a_3y/`

Allowed Git files:

- `r1_summary.json`
- `r1_report.md`
- `shortlist.csv`

Do not commit:

- full research candidate Parquet;
- all C2B exact metrics;
- raw feature data;
- large shard outputs.

## Required result report

The result Markdown must state:

- DONE / BLOCKED;
- exact source commit used;
- exact input hashes;
- exact as-of/window;
- planner identity;
- all six C1 shard outcomes/resources;
- merged C1 candidate count;
- C1 descriptive distribution highlights;
- C2A counts;
- C2B request/result integrity;
- incrementality label counts;
- temporal warning counts;
- bounded shortlist count;
- top 10–20 most research-relevant examples with readable conditions and metrics;
- any surprising failure mode / data quality issue;
- commits made;
- production impact = NONE;
- recommended R3 decision:
  - `CONTINUE_3Y_HIGHER_DEPTH`
  - `EXTEND_SELECTED_FAMILIES_TO_5Y`
  - `MIXED_BRANCH_DECISION`
  - `STOP_V04_EXPANSION`
  - or `BLOCKED`.

The recommendation must explain which candidate families support it.

Do not actually start R3 expansion in this task.

## Acceptance criteria

This task is accepted when ChatGPT can decide from the compact Git outputs:

1. How many Wave A candidates exist by lane/depth?
2. How many survive top1/top3 robustness checks?
3. Which candidates add evidence beyond all immediate parents?
4. Which are jackpot-dependent or temporally thin?
5. Are useful patterns concentrated in transition, pedigree-transition, or baseline pedigree?
6. Is trailing 3y sufficient, or are specific promising families underpowered enough to justify a frozen 5y extension?
7. Is there enough coherent evidence to justify controlled depth-4 expansion?

## Non-goals

- no 5y aggregation;
- no depth 4–6 execution;
- no prefix-directed expansion implementation unless strictly required to produce this task's compact outputs;
- no threshold tuning;
- no market/popularity-conditioned candidate generation;
- no SHADOW publication;
- no production serving change;
- no RaceNote/PWA integration change.
