# RaceNote Forecast Gen0 — 2026 PACI Historical Backtest Design v0.1

Status: **DESIGN ACCEPTED / IMPLEMENTATION PENDING**

Date: 2026-09-29

## 1. Purpose

2026年のJRDB PACIを、当時の開催前入力として再生し、
RaceNoteからどのように読み、比較し、軸を選ぶべきかという
**未固定のForecast logic** を、結果盲検のまま探索・比較するための
historical backtest laneを定義する。

このlaneはTRUE_FORWARD activationとは別である。

- historical backtest = Forecast logicの探索・比較・改善
- TRUE_FORWARD = **ロジック選定後**のforward validation / activation evidence

現時点ではGen0-G001 activation自体をPAUSEする。
Historical backtestの目的はGen0.3を追認することではなく、Gen0.3を含む
複数のForecast reader候補から採用ロジックを選ぶことである。

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
  -> pre-result firewall
  -> candidate Forecast reader
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
- only the historical evidence sources permitted by the candidate under test

Output:
- result-independent candidate input package
- provenance / firewall audit
- candidate-specific authoring request where required

No result source is mounted in this stage.

General Evidence / Synthesis / Pairwise / Scenario are reusable Gen0.3 research
assets, but are **not mandatory for every candidate reader**.

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

## 5.1 Persistent random day pool

Historical target-day selection is implemented by:

- `src/racenote_backtest_day_picker.py`
- `config/racenote_backtest_day_pool_2026.json`

Each PACI date stores `date`, `file_name`, `drive_file_id`, `used`,
`used_at`, and `selection_id`.

`pick -n N` samples only unused dates and immediately marks them used.
The actual seed is stored in the selection history so the draw is reproducible.
`release` returns an accidental draw to the unused pool.

A newer PACI Drive inventory can be merged with `sync`. Existing usage flags
are preserved; previously unseen PACI dates are added as unused candidates.
The deterministic picker itself does not access Google Drive credentials.

### Default research turn

The default research turn is **2 randomly selected complete PACI days**.
This normally yields roughly **48-72 races per turn** depending on the number
of active venues.

```text
pick 2 unused PACI days
  -> freeze target-set identity
  -> blind forecast each race independently
  -> Freeze all usable predictions
  -> open results
  -> aggregate the two-day errors / metrics
  -> make at most one bounded Forecast-logic change
  -> next 2-day turn
```

Do not redraw a selected date merely because its race count, venue mix, or
results are inconvenient.

## 6. Backtest unit

The atomic selection unit is a **complete race day**, not cherry-picked races. The default research turn is two randomly selected unused complete days.

Reasons:
- prevents selection after seeing difficult/easy race characteristics
- preserves the natural mix of class / distance / surface / field size
- makes failure rates visible
- matches actual day operation

A normal JRA 3-venue day is approximately 36 races.

The default improvement turn is two complete days, typically about 48-72 races. This is the normal cadence for one bounded logic adjustment.

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
5. common result firewall / provenance / Freeze infrastructure
6. candidate-pluggable one-race author/freeze orchestration contract
7. post-Freeze result join
8. deterministic evaluation summary
9. baseline-vs-candidate comparison report

First smoke:

- one clean historical date
- all races on that date
- use a deliberately simple baseline reader plus the existing Gen0.3 candidate where practical
- purpose = validate candidate-pluggable execution, firewall, source identity, freeze-before-result, and metrics

Only after the smoke PASS should the first 2-day DEV tuning block be opened.

## 16. Relationship to Gen0-G001 activation

Gen0-G001 activation is currently **PAUSED BEFORE ACTIVATION** because the
detailed Forecast logic has not yet been selected.

The backtest lane exists specifically to resolve that uncertainty.

Current rule:

- RaceNote extraction / evidence contract = fixed
- pre-result firewall / provenance / immutable Freeze / result-after-Freeze = fixed
- detailed Forecast reading / comparison / mark logic = unfrozen
- Gen0.3 = research candidate
- Gen0-G001 activation = paused
- TRUE_FORWARD gate = defined only after a Forecast logic version is selected

When a candidate is accepted from historical research, create or explicitly
bind a Forecast logic version and only then define the activation generation
and TRUE_FORWARD gate. Do not silently reactivate the former Gen0.3/G001 plan.
