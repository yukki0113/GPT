# RaceNote Forecast Gen0 — 2026 PACI Historical Backtest Design v0.1

Status: **DESIGN ACCEPTED / IMPLEMENTATION PENDING**

Date: 2026-09-29

## 1. Purpose

2026年のJRDB PACIを、当時の開催前入力として再生し、
RaceNote-Forecast-Gen0.xの読み方・比較方法・軸選択ロジックを
結果盲検のまま検証・改善するためのhistorical backtest laneを定義する。

このlaneはTRUE_FORWARD activationとは別である。

- historical backtest = ロジック研究・改善
- TRUE_FORWARD = 現行世代の実運用activation / forward validation

Historical backtestの成績だけでGen0-G001をACTIVEにしてはならない。

## 2. Authoritative 2026 PACI source

Google Drive canonical folder:

- path: `horse-racing/00_raw/PACI`
- folder ID: `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`

2026-09-29 inventory snapshot:

- PACI files: 82
- first: `PACI260104.zip`
- last: `PACI260927.zip`
- coverage: 2026-01-04 through 2026-09-27
- naming rule: `PACIyymmdd.zip`

Month counts:

| month | race days |
|---|---:|
| 2026-01 | 10 |
| 2026-02 | 9 |
| 2026-03 | 9 |
| 2026-04 | 8 |
| 2026-05 | 10 |
| 2026-06 | 8 |
| 2026-07 | 8 |
| 2026-08 | 10 |
| 2026-09 | 10 |

The Drive folder is the source of truth for PACI availability.
A backtest run must freeze an immutable source manifest containing at least:

- race_date
- Drive file ID
- file name
- size
- downloaded SHA-256

Do not identify PACI only by file name after a run has started.

## 3. Core blindness contract

One historical race must pass through the same information boundary as a
real pre-race prediction.

```text
PACI / as-of historical evidence
  -> RaceNote
  -> Independent firewall
  -> General Evidence
  -> All-Runner Synthesis
  -> Pairwise
  -> Scenario
  -> Forecast
  -> immutable Freeze
================ RESULT FIREWALL ================
  -> target result open
  -> objective evaluation
  -> error classification
```

### Before Freeze: allowed

- target-date PACI pre-race facts
- RaceNote history with strict `historical race date < target date`
- Analysis historical Trend with strict as-of-exclusive boundary
- RaceReview history with `race_date < target_date`
- current Gen0 contract's allowed pre-Freeze lanes

### Before Freeze: forbidden

- target SED / HJC
- target finish position
- target payout
- final odds / final popularity
- current JRDB consensus lanes hidden by the firewall
- Edge Value / RL Value
- any post-race review generated from the target race
- previously computed evaluation label for the same target race

A backtest process that can read prediction input and target result from the
same authoring payload is invalid, even if the code claims not to use the
result.

## 4. Physical stage separation

Historical replay uses separate immutable artifacts.

### Stage A — SOURCE

Input:
- PACI source manifest
- PACI bytes
- Analysis generation identity
- RaceReview generation identity

Output:
- one or more RaceNote bundles
- no target result payload

### Stage B — PREPARE

Input:
- Stage A RaceNote artifact
- explicitly bound RaceReview artifact/generation

Output:
- independent view
- General Evidence
- authoring requests
- firewall audit

No result source is mounted in this stage.

### Stage C — AUTHOR / FREEZE

Baseline Forecast behavior:

**1 race = 1 LLM call**

Each call receives exactly one target race's pre-Freeze evidence package.
Outputs are deterministically validated and frozen before proceeding to result
open.

A full day may be orchestrated as a batch, but reasoning must remain
race-independent. One giant 12R / 36R reasoning call is prohibited.

### Stage D — RESULT OPEN

Only after every usable race in the frozen batch has a valid immutable Freeze:

- acquire result-side data
- join by exact race identity
- record result-open timestamp/provenance
- never modify the frozen Forecast

### Stage E — EVALUATION

Produce machine metrics and human-readable error tags.
Evaluation may read prediction + result, but its output is not fed back into
the already frozen batch.

## 5. Result source hierarchy

Prediction source and result source are deliberately separate.

### Primary objective result source

Validated JRDB Analysis v1.4 canonical may supply:
- finish position
- race/horse identity
- result-side structural fields already covered by its schema

### Optional settlement / market diagnostic

SED / HJC may be opened after Freeze for:
- final popularity
- final odds where available
- win/place payout
- supported ticket settlement

Betting diagnostics must remain separate from Forecast-quality evaluation.

No target result may be reconstructed from Analysis, SED, HJC, Eval, or any
other source before the complete batch Freeze gate passes.

## 6. Backtest unit

The preferred unit is a **complete race day**, not cherry-picked races.

Reasons:
- prevents selection after seeing difficult/easy race characteristics
- preserves the natural mix of class / distance / surface / field size
- makes failure rates visible
- matches actual day operation

A normal JRA 3-venue day is approximately 36 races.

The initial improvement unit remains approximately 50 races. In practice:

- 2 complete days ~= 72 races

is the preferred research block.

If a race fails source/validation, retain it in the denominator as
`TECHNICAL_SKIP`; do not silently substitute a more convenient race.

## 7. Development / validation discipline

Historical data is not one undifferentiated tuning pool.

### 7.1 DEV_REPLAY

Purpose:
- inspect recurring reading errors
- prototype one bounded logic change
- compare candidate against frozen baseline

Results may be inspected and used for design.

### 7.2 OOS_VALIDATION

Purpose:
- test a candidate version frozen before result open
- no tuning inside the block

Once a block has been opened for evaluation, it may inform the **next**
version, but it can no longer be cited as OOS evidence for that next version.

### 7.3 PROMOTION_HOLDOUT

Purpose:
- final historical gate before TRUE_FORWARD
- multiple untouched complete days
- no parameter/prompt/reading-policy change between holdout days

Historical holdout PASS still does not replace TRUE_FORWARD.

## 8. Known contamination registry

The project already opened results for some 2026 RaceNote research targets.
They remain useful DEV material but are not clean OOS for a new candidate.

Initial known entries:

| scope | target | reason |
|---|---|---|
| full day | 2026-07-25 | Gen0.3 day rehearsal + result review |
| full day | 2026-07-26 | Gen0.3 day rehearsal + result review |
| full day | 2026-08-01 | Semantic v0.3 OOS result already opened |
| full day | 2026-08-08 | Semantic v0.3 OOS result already opened |
| single race | 2026-09-13 中山10R | Gen0.3 real-data dry run / 初風S |
| single race | 2026-08-16 札幌11R | Trend structural test; result known |

This registry is additive. Before selecting a new OOS/HOLDOUT block, repository
artifacts and the ledger must be checked for prior result exposure.

The registry records project-process contamination, not a claim about model
training data.

## 9. Selection policy

Do not choose validation days because prior results look interesting.

Selection is frozen mechanically before target-result access.

Recommended selection hierarchy:

1. eligible PACI date exists
2. not in contamination registry for the requested scope
3. PACI validates
4. date selected by deterministic seed / chronological rule
5. complete day retained regardless of race mix

For reproducibility, a selection manifest records:

- selection_policy_version
- seed
- eligible date set hash
- selected date list
- excluded/contaminated targets and reasons

## 10. Walk-forward research cycle

Recommended Gen0 iteration:

```text
baseline version frozen
  -> 2 DEV full days
  -> error aggregation
  -> ONE bounded candidate logic change
  -> candidate version frozen
  -> 2 untouched OOS full days
  -> compare baseline vs candidate
  -> accept / reject / inconclusive
  -> if accepted, candidate becomes next research baseline
  -> next untouched block
```

Do not make multiple unrelated changes from one 72-race block.

Examples of one bounded change:
- revise interpretation of contradictory Trend/RaceReview evidence
- revise pairwise tie-breaking language
- revise candidate-cluster -> ◎ selection guidance
- revise scenario recheck trigger

Examples that are too broad for one experiment:
- rewrite Trend, Pairwise, Scenario, probability and mark policy together
- add a weighted score and change evidence inputs simultaneously

## 11. Evaluation metrics

Backtest evaluation is layered.

### A. Axis quality
- ◎ win
- ◎ top2
- ◎ top3

### B. Candidate-set quality
- winner forecast rank
- winner in top3
- winner in top5
- actual podium contained in forecast top5
- top3 set overlap

### C. Full-order quality
- Spearman rank correlation
- mean absolute rank error

### D. Calibration / confidence
- confidence bucket vs realized axis/top3 behavior
- coverage state vs realized quality
- scenario robustness vs realized quality

These are descriptive until enough samples exist.
Coverage / robustness labels do not automatically become weights.

### E. Error taxonomy
At minimum:
- DATA_TREND_OVERREAD
- DATA_TREND_UNDERREAD
- RACEREVIEW_OVERREAD
- RACEREVIEW_UNDERREAD
- ABILITY_OVERREAD
- ABILITY_UNDERREAD
- PAIRWISE_REVERSAL_ERROR
- SCENARIO_ASSUMPTION_ERROR
- CANDIDATE_CLUSTER_OK_AXIS_WRONG
- MISSING_EVIDENCE
- TECHNICAL_SKIP
- UNRESOLVED

### F. Betting diagnostics
Only post-Freeze and secondary to Forecast quality.

Do not optimize Forecast reading directly against ROI in the first pass.

## 12. Baseline-vs-candidate comparison

Every experimental run must preserve both outputs.

For the same target races:

- baseline Forecast version
- candidate Forecast version
- identical pre-Freeze evidence identity
- identical target set
- independent immutable prediction hashes

Primary comparison asks:

1. Did candidate change the axis?
2. Did candidate change top3/top5 membership or only order?
3. Were changed decisions directionally better?
4. Did gains repeat across more than one date?
5. Did any segment improve only because of a small number of outliers?
6. Did technical skip/missing evidence change?

A candidate is not promoted from aggregate ROI alone.

## 13. Generation/version policy

Historical experiments do not mutate `Gen0-G001` in place.

Use research identities such as:

- `Gen0.3-BT-R001-B` baseline
- `Gen0.3-BT-R001-C1` candidate 1

If C1 is accepted as a new research contract, create a new Forecast logic
version / evidence-policy version before the next OOS block.

Do not rewrite old frozen prediction artifacts.

## 14. Ledger model

The existing `RaceNote Forecast Gen0 検証台帳` remains the main ledger, but
historical tuning must be distinguishable from TRUE_FORWARD.

Required fields/semantics:

- evaluation_mode = `BLINDED_HISTORICAL`
- backtest_experiment_id
- logic_version
- baseline_or_candidate
- target_set_manifest_id
- source_paci_id / SHA
- pre_result_guard = PASS
- prediction_hash
- frozen_at
- result_opened_at
- evaluation_status
- contamination_status

Do not set `forecast.current_generation` from historical backtest rows.

## 15. First implementation milestone

Implement only the reusable infrastructure first:

1. PACI 2026 source inventory / immutable manifest builder
2. contamination registry
3. deterministic date selector
4. historical RaceNote build from selected PACI
5. existing Gen0.3 firewall / Prepare reuse
6. one-race author/freeze orchestration contract
7. post-Freeze result join
8. deterministic evaluation summary
9. baseline-vs-candidate comparison report

First smoke:

- one clean historical date
- all races on that date
- no logic change
- purpose = validate firewall, source identity, freeze-before-result, and metrics

Only after the smoke PASS should the first 2-day DEV tuning block be opened.

## 16. Relationship to Gen0-G001 activation

This backtest lane may improve the Forecast contract before or after
Gen0-G001 activation, but it does not weaken the activation gate.

Current rule remains:

- Gen0-G001 = READY
- historical backtest may continue
- first genuine TRUE_FORWARD pre-result Freeze is still required for ACTIVE

If historical research produces a materially different contract before the
first TRUE_FORWARD race, do not silently replace Gen0.3 under the same
activation identity. Version the contract explicitly and update the activation
plan.
