
## RaceNote research-work handoff area — 2026-10-05

Substantial design / execution / audit handoffs are stored under:

`docs/racenote/research-work/`

Use:

- `instructions/` for canonical work orders;
- `reports/` for actual execution/analysis results;
- `audits/` for acceptance/revision decisions.

Current parallel research lane: **RaceNote 0.5.x JRDB Feature Audit**.
The active v0.4.6 prediction cohort remains unchanged while this research is exploratory.
Historical feature analysis must start with **2023-2025** and may extend to **2021-2025** only if the three-year result is inconclusive. If five years still yield no stable practical signal, stop expanding the horizon and retain the 0.4.x Human-Context principle rather than forcing a new feature hierarchy.

Current Stage A instruction:
`docs/racenote/research-work/instructions/20261005_JRDB_FEATURE_AUDIT_STAGE_A_INSTRUCTION.md`

# RaceNote current guide

For new unused BTDAY selections, the current operational baseline is
`RaceNote-Human-Context-Reader-0.5.2-candidate` and the canonical procedure is
`docs/racenote/RACENOTE_V052_SINGLE_DAY_RUNBOOK_v0_1.md`.
BTDAY source routing is unified: 2026 uses PACI and 2010–2025 uses the accepted
Historical Warehouse according to the reserved row's `source_mode`.
The production `current_logic_version` remains a separate pointer.
`BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md` is retained as the legacy
v0.4.6 procedure only.

## 1. Current architecture

Current production path:

    2010-2025 accepted Historical Warehouse / 2026 PACI
      -> RaceNote base bundle
      -> Analysis Parquet canonical
      -> DuckDB direct enrichment
      -> RaceNote v1.0 bundle
      -> Forecast Gen0 / Freeze / Guard / downstream delivery

Stats Mart is legacy-only. Analysis SQLite is explicit audit/rollback compatibility only.
Archive is an optional immutable delivery cache and is never the historical source of truth.


RaceNote is a facts/evidence/provenance layer for GPT comparison and prediction.

    PACI / Historical Warehouse
      -> RaceNote base bundle
      -> JRDB Analysis canonical enrichment
      -> Reader View / GPT Forecast
      -> Freeze / Guard / downstream delivery

The active architecture is JRDB + Historical Warehouse + Analysis canonical. Stats Mart is a frozen legacy cache and is not an active dependency.

## RaceNote Daily Build — production day-level path

Day-level RaceNote production is consolidated under:

- `docs/racenote/RACENOTE_DAILY_BUILD_v0_1.md`
- `schema/racenote_daily_build_manifest_v0_1.json`
- `src/build_racenote_daily.py`

Current status: **D5 PASS / production day-level cutover complete**.

The daily CLI executes all deterministic orchestration stages through final package generation and is the standard full-day production entrypoint.

The current production daily path is:

```text
PACI -> all base RaceNotes -> Analysis/P1/P2 bulk enrichment
     -> formal RRDB enrichment -> Reader Views
     -> validation -> daily manifest/package
```

This work changes orchestration only. It must not change RaceNote evidence
semantics, Trend, P1/P2, RRDB or Forecast logic.

D5 passed on 2026-05-23 across 36 races / 549 horses. Existing one-race entrypoints remain available for explicit single-race use, audit and rollback.

## 2. Current prediction direction

RaceNote Forecast Gen0 is the current prediction **research** program.

The project currently separates two things explicitly:

### Fixed / current invariants

- RaceNote is a facts / evidence / provenance layer and does not choose ◎.
- target result and prohibited post-race / market information remain hidden before Freeze.
- historical evidence is as-of-exclusive to the target date.
- prediction is frozen immutably before result acquisition.
- result evaluation never rewrites the frozen prediction.
- historical tuning and TRUE_FORWARD validation are separate.
- fixed numeric weights / one hidden score are not a Gen0 default.

### Not yet fixed

The detailed Forecast decision logic remains open research:

- evidence reading priority
- Trend / RaceReview / Ability conflict handling
- whether All-Runner Synthesis is mandatory
- whether Pairwise is mandatory
- whether Scenario Robustness is mandatory
- whether EdgeDB Performance is used pre-Freeze
- probability / confidence policy
- detailed ◎ / ○ / ▲ / △ selection policy
- prompt wording

`RaceNote-Forecast-Gen0.3` is an implemented **research candidate** containing
General Evidence, All-Runner Synthesis, Pairwise, Scenario and optional
EdgeDB Performance overlay. It is useful for comparison and reproducibility,
but is not the adopted Gen0 prediction logic.

Gen0-G001 activation preparation is paused until a detailed Forecast logic
version is explicitly selected. The existing G001 manifest / ledger / transport
PASS evidence is retained as infrastructure evidence only.

Canonical research plan:
`docs/racenote/FORECAST_GEN0_PLAN.md`

G001 status:
`docs/racenote/GEN0_G001_ACTIVATION_STATUS.md`

2026 PACI blinded backtest design:
`docs/racenote/FORECAST_GEN0_2026_PACI_BACKTEST_DESIGN_v0_1.md`


### Forecast research thread split

Current chat-role boundary:

- Research thread: result review + Forecast logic research / version updates
- Forecast execution thread: pre-result forecast + Freeze + daily HTML + handoff only

Canonical:

- `docs/racenote/FORECAST_GEN0_THREAD_ROLES_v0_1.md`
- `docs/racenote/FORECAST_EXECUTION_THREAD_BOOTSTRAP_v0_1.md`
- `schema/racenote_forecast_turn_handoff_v0_1.json`

### Current Backtest / TRUE_FORWARD research operating assets — 2026-09-29

The common operating contract is now:

- `docs/racenote/FORECAST_GEN0_RESEARCH_PROTOCOL_v0_1.md`
- `docs/racenote/FORECAST_GEN0_OUTPUT_CONTRACT_v0_1.md`
- `schema/racenote_forecast_research_record_v0_1.json`
- `docs/racenote/FORECAST_GEN0_BASELINE_READER_v0_1.md` — initial simple reader for turn 1
- `config/racenote_forecast_logic_current.json` — current Forecast logic pointer
- `docs/racenote/FORECAST_GEN0_BASELINE_READER_v0_2.md` — current observable baseline
- `docs/racenote/FORECAST_DECISION_TRACE_CONTRACT_v0_1.md` — per-race comparison trace
- `src/validate_racenote_forecast_decision_trace.py` — pre-Freeze trace gate

Current baseline status:

- BTDAY-0001: immutable v0.1 historical baseline
- current: `RaceNote-Baseline-Reader-0.2`
- v0.2 change reason: pre-result observability fix, not result-based tuning
- each usable race must preserve explicit ◎ vs ○ comparison and Decision Trace

Historical standard cadence (legacy context):

- random PICK previously used only eligible PACI days
- current v0.5.2 BTDAY lottery may select a 2026 PACI day or a 2025 Historical Warehouse day
- typically about 24–36 races per selected day
- one logic_version for the whole turn
- one race = one independent forecast
- Freeze all usable predictions before any target result open
- review the two days as one turn
- change at most one bounded logic theme before the next turn

Day state:

- `src/racenote_backtest_day_picker.py`
- `config/racenote_backtest_day_pool_2026.json`

User-facing daily output is compact HTML generated only from frozen canonical
records:

- `src/render_racenote_forecast_html.py`
- `forecast_YYYYMMDD.html`

This same common record / presentation contract is intended to carry forward
to TRUE_FORWARD after a detailed Forecast logic version is selected.

## 3. Current data boundaries

- 2010–2025 historical RaceNote input: accepted JRDB Historical Warehouse
- 2026 current/future input: PACI daily route
- Analysis canonical: the only active enrichment source
- Raw: rollback/audit and explicit 2010 previous-result boundary fallback
- Archive: optional immutable delivery cache; Warehouse remains the canonical rebuild source
- Stats Mart: legacy-only, retained for old research and reproducibility

All history statistics are computed as-of-exclusive from Analysis canonical. Existing RaceNote v1.0 schema and Forecast/Freeze/Guard semantics remain unchanged.

## 4. RaceReviewDB historical review evidence

RaceReviewDB is consumed through the additive sidecar adapter
`src/racenote_racereview_adapter.py`. Normal operation resolves the stable
Drive CURRENT through `src/racenote_racereview_current.py` and caches the
validated generation locally before opening it with the read-only
`RaceReviewReader`. Audit/replay may still point the adapter at an already
extracted immutable generation root.

The adapter joins by JRDB blood registration number
(`horse.basic.horse_id`), queries history with
`race_date < target_date`, and emits only the stable v0.1 Review fields
needed for historical evidence.

Current consumer contract:

- `docs/racenote/RACEREVIEW_CURRENT_CONSUMER_v0_1.md`
- stable Drive file ID: `1UwNfrupMTHRPhkzULPvClGre4MWz2TFg`

The adapter is implemented but is not an automatic Forecast-generation
activation. It does not mutate the authoritative RaceNote v1.0 bundle, does
not open current market/JRDB-consensus information, and does not consume
unfinished RaceReviewDB semantic labels or uncalibrated causal track-bias
signals. See `docs/racenote/RACEREVIEW_ADAPTER_v0_1.md`.

The first downstream Horse Evidence Card slice is also implemented:

- `src/racenote_horse_evidence_card.py`
- `schema/racenote_horse_evidence_card_schema_v0_1.json`
- `docs/racenote/HORSE_EVIDENCE_CARD_v0_1.md`

It converts historical Review evidence into primary/supporting positives,
concerns, mixed context, repeatability, hidden-strength candidates,
fragile-form candidates, contradiction, uncertainty, and comment evidence.
It does not score horses and remains non-active for Forecast generation.

Prediction reading is normalized before full-field synthesis through:

- `docs/racenote/PREDICTION_INTERPRETATION_v0_1.md`
- `PredictionInterpretation-v0.1` embedded per horse in General Evidence

This layer does not score or rank. It preserves directional trend evidence,
sample size, trend redundancy, Race Structure, RaceReview repeatability and
target-condition overlap, plus Ability Anchor context. All-Runner Synthesis
reads every profile before Pairwise verifies the important ranking boundaries.

The next aggregation layer is also implemented as a research input:

- `src/racenote_general_evidence.py`
- `schema/racenote_general_evidence_schema_v0_1.json`
- `docs/racenote/GENERAL_EVIDENCE_PRIORITY_v0_1.md`

This layer joins Independent RaceNote evidence with the RaceReview Horse
Evidence Card and enforces the ordinal reading policy
`DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR`. It does not create rankings,
marks, or probabilities.

The full-field draft layer is now implemented:

- `src/racenote_all_runner_synthesis.py`
- `schema/racenote_all_runner_synthesis_schema_v0_1.json`
- `docs/racenote/ALL_RUNNER_SYNTHESIS_v0_1.md`

The authoring request is built by
`build_synthesis_request(general)`. It carries every runner's Interpretation
but deliberately leaves draft rank, confidence, primary lane, and reasons
unset, so the request builder itself cannot choose an order.

All-Runner Synthesis reads every runner's Prediction Interpretation and authors
a complete draft order without numeric scoring. It validates full-field
coverage, forbids Ability-only primary ordering, and derives HIGH-priority
adjacent boundaries from low confidence, mixed evidence, small-sample-only
evidence, and RaceReview contradiction. The draft is not a Forecast; it is
bound by hash and passed to Pairwise for direct comparison.

The downstream Pairwise Comparison research contract is also implemented:

- `src/racenote_pairwise_comparison.py`
- `schema/racenote_pairwise_comparison_schema_v0_1.json`
- `docs/racenote/PAIRWISE_COMPARISON_v0_1.md`

Pairwise does not mechanically select a horse. It validates GPT-authored
relative comparisons, requires direct evidence at every final-order boundary,
requires reversal conditions, and requires an explicit reason whenever lower
priority evidence overrides contrary trend/RaceReview evidence.

Scenario Robustness v0.1 is also implemented:

- `src/racenote_scenario_robustness.py`
- `schema/racenote_scenario_robustness_schema_v0_1.json`
- `docs/racenote/SCENARIO_ROBUSTNESS_v0_1.md`

It tests SLOW / MEDIUM / FAST pace scenarios, derives whether the Pairwise
axis is ROBUST / CONDITIONAL / FRAGILE, and records horse-by-horse rank
sensitivity without automatically replacing the Pairwise order.

Forecast reason provenance is enforced by:

- `docs/racenote/DECISION_TRACE_v0_1.md`
- `RaceNote-Decision-Trace-0.1` embedded per Forecast horse

Primary / secondary / concern reasons may reference only evidence that exists in
General Evidence, Pairwise, Scenario, or the actual Edge Performance overlay.
Scenario risks cannot be omitted, and future short-comment evidence must be a
subset of the traced Forecast evidence.

Real-data dry-run audit:

- `docs/racenote/GEN0_3_REALDATA_DRYRUN_HATSUKAZE_20260913.md`

The Gen0.3 research-candidate Forecast implementation is:

- `src/racenote_forecast_gen0_3.py`
- `src/racenote_edge_performance_adapter.py`
- `schema/racenote_forecast_gen0_schema_v0_3.json`
- `config/racenote_forecast_gen0_ledger_v0_3.json`
- `docs/racenote/FORECAST_GEN0_3_PREDICTION_CONTRACT_v0_3.md`

As a candidate, Gen0.3 consumes General Evidence -> All-Runner Synthesis ->
Pairwise -> Scenario -> Base Forecast and then permits only EdgeDB Performance
as a pre-Freeze overlay. This ordering and overlay policy are **candidate-specific**
and remain subject to blinded historical comparison. The information firewall
itself remains a project-level invariant.

## 5. Legacy boundary

The complete retained-asset inventory and import boundary is docs/racenote/legacy/README.md.
v0.2 control, v1.1-P gated prediction, Edge policy, and related frozen outputs remain
historical reproducibility/benchmark assets. They are not current Forecast Gen0 logic,
and their output is not an automatic fallback or current prediction input.

## 6. Operating rules

Use latest main, current contracts, and current source as truth. Do not reintroduce Stats Mart into RaceNote request payloads, Store resolution, workflow downloads, or active enrichment. Keep legacy builders and schemas physically retained until a separately authorized phase.

For current research, follow this guide and the Forecast Gen0 contract. For deterministic/legacy reproduction, use the dedicated legacy documents and preserved artifacts.


### Legacy Human-Context Reader v0.4.6 prospective validation — 2026-10-05

This section is retained for historical reproducibility. New unused BTDAYs use
`RaceNote-Human-Context-Reader-0.5.2-candidate` through
`RACENOTE_V052_SINGLE_DAY_RUNBOOK_v0_1.md`.

v0.4.6 remains one prediction cohort. The 2026-10-05 refinements affect
reader-facing prose, RRDB trace sparsity and deterministic execution only; they
do not change how ◎ ○ ▲ △1 △2 are selected.

Active assets:

- logic: `FORECAST_HUMAN_CONTEXT_READER_v0_4_6_CANDIDATE.md`
- Decision Core: `schema/racenote_decision_core_v0_4_6.json`
- final record: `schema/racenote_forecast_research_record_v0_4_6.json`
- prepare request: `schema/racenote_btday_v046_request.json`
- prepare workflow: `.github/workflows/racenote_btday_v046_prepare.yml`
- finalizer: `.github/workflows/racenote_btday_v046_finalize.yml`

Normal operation predicts a venue continuously and commits one
`authored_decisions/<venue>.json` recovery file. It then continues immediately.
The permanent finalizer waits until every expected venue exists, then performs
venue validation/batch materialization, bind, Freeze, Validator and archive once.

Per-race checkpoints, mandatory Reader chunks and per-BTDAY temporary workflows
are not part of the active v0.4.6 route.

Canonical procedure:
`BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md`.

The production Forecast pointer remains unchanged pending explicit promotion.
