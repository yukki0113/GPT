# RaceNote RRDB Integration Design v0.3

Status: **ACTIVE — RRDB RECOMMENDATION v0.3**
Date: 2026-10-01
Supersedes: `RACENOTE_RRDB_INTEGRATION_DESIGN_v0_2.md` for current operation

## 1. Purpose

RaceReviewDB (RRDB) is a historical reinterpretation lane for RaceNote Forecast.

Current operational recommendation contract:

`rrdb-recommendation-signals-v0.3`

Canonical source:

`horse-racing/jrdb/src/jrdb_recommendation_signals.py`

## 2. Current evidence contract

Current operational signals are exactly:

- `TIME_CLASS_PLUS1`
- `FRONT_SURVIVE_GAP05`
- `REAR_HIGH_LAST3F90`
- `HV02_Q85_Q90`

The broad v0.2 HV signals are not current output:

- `HV01`
- broad `HV02`

They remain historical research concepts only.

`HV02_Q85_Q90` means:

- source finish >= 6
- performance_signal >= Q85
- performance_signal < Q90
- Q85 = `0.03422932330827132`
- Q90 = `0.16777149321267684`

S/A grades remain disabled.

## 3. Operational lookback

Current recommendation consumption uses a 730-day target-date-relative lookback.

For target date D:

- source run must satisfy `race_date < D`
- source run must satisfy `race_date >= D - 730 days`
- horse identity is JRDB blood registration number
- horse-name fallback is prohibited

No target-race result, next-start result, current odds, final popularity, or future
RRDB row may be read pre-Freeze.

## 4. RaceNote per-horse shape

RaceNote exposes:

`racereview.recommendation`

with fields including:

- `status`
- `contract_version`
- `grade = null`
- `grade_status = DISABLED`
- `matched_signal_ids`
- `matched_signal_count`
- `signals[]` with label and measured strength
- `human_summary`
- `lookback_days`
- source-run context

A deprecated `racereview.next_watch` compatibility stub may remain, but Forecast
must not use it for current interpretation.

## 5. Forecast reading semantics

Forecast should read RRDB as prior-run evidence, not as a direct mark.

- TIME_CLASS_PLUS1: prior clock maps at least one class above the source class.
- FRONT_SURVIVE_GAP05: survived a front-loaded race while racing forward and
  stayed within 0.50 sec of the winner.
- REAR_HIGH_LAST3F90: raced from the rear in a rear-favoring/slow-late shape and
  still produced an upper-tail last3F.
- HV02_Q85_Q90: source finish was sixth or worse but adjusted-time content fell
  in the operational Q85–Q90 band.

A MATCH is not an automatic upgrade. NO_MATCH is neutral.

## 6. Newspaper / PWA boundary

RaceNote may consume internal IDs and measured strength. Newspaper/PWA receives
only target-horse identity plus RRDB short prose.

Current short prose:

- TIME_CLASS_PLUS1 -> `前走時計はクラス水準より上。`
- FRONT_SURVIVE_GAP05 -> `前傾ラップ戦を前で受け、勝ち馬と僅差まで踏ん張った。`
- REAR_HIGH_LAST3F90 -> `後傾ラップ戦も後方から上位の上がりは使った。`
- HV02_Q85_Q90 -> `敗戦でもタイムは水準以上。`

Newspaper mark policy:

- preserve an existing RaceNote mark and make it tappable;
- if no RaceNote mark exists, show `注`;
- show RRDB prose in the same modal;
- do not create a standalone RRDB column.

## 7. Decision trace

`decision_trace.rrdb_evidence` should preserve:

- recommendation contract version
- matched signal IDs
- materially relevant strength values
- source-run reference
- decision role

Do not derive grades or numeric bonuses from signal count.

## 8. De-duplication

Evidence from the same historical run must not be counted twice across recent
runs, RRDB history, and recommendation signals.

## 9. Provenance

RaceNote metadata should preserve:

- RRDB generation identity
- recommendation contract version
- grade status DISABLED
- operational lookback days
- target-date-exclusive boundary
- blood-registration-number identity
- name_fallback=false
- scoring=false

## 10. Evidence basis for the narrowed HV lane

The narrowed operational HV lane follows the 2026-06〜09 fine-band comparison:

`docs/RaceReviewDB_202606_202609_HV_FineBand_Comparison_v0_1.md`

HV02 Q85–Q90:

- 2026-06〜07: 3着内率 29.87%
- 2026-08〜09: 3着内率 28.57%
- 2026-06〜09: N=154 / 3着内率 29.22% / 複勝ROI 125.39%

These figures are exploratory serving evidence, not a universal strength grade.

## 11. Acceptance

Current RRDB integration is correct when:

- RaceNote exposes `racereview.recommendation`
- current contract version is `rrdb-recommendation-signals-v0.3`
- only the four current signals are returned
- broad HV01/HV02 do not create current MATCH output
- grades remain disabled
- 730-day and target-date-exclusive boundaries hold
- Forecast reviews RRDB without converting it to an automatic mark or score
- Newspaper/PWA can project matched horses into the existing mark cell / `注` behavior
