# RaceNote RaceReviewDB Adapter v0.1

Status: IMPLEMENTED SIDE-CAR / NOT YET FORECAST-ACTIVE  
Date: 2026-09-25

## 1. Purpose

RaceReviewDB を RaceNote の historical review evidence source として接続する。

RaceReviewDB は prediction engine ではない。過去走の時計水準、ペース、
位置取り変化、上がり、JRDB trouble raw 等を as-of-exclusive に再構成し、
RaceNote が今回条件との比較・全馬比較へ利用できる historical evidence を提供する。

責務は次のように分離する。

```text
RaceReviewDB
  過去走で実際に何が起きたか / どのような走行内容だったか
        |
        v
RaceNote RaceReview Adapter
  stable fields only / deterministic tags / provenance
        |
        v
RaceNote Evidence Card
  今回条件で何を重視するか / 矛盾 / repeatability
        |
        v
GPT comparison / prediction
```

## 2. Initial integration boundary

v0.1 は既存 RaceNote v1.0 bundle を破壊しない sidecar とする。

Input:

- RaceNote Gen0.2 `INDEPENDENT` view
- extracted RaceReviewDB CURRENT root

Output:

- `racereview_evidence.json`
- schema: `schema/racenote_racereview_evidence_schema_v0_1.json`

Implementation:

- `src/racenote_racereview_adapter.py`

RaceReviewDB の取得は既存 `RaceReviewReader` を利用する。

## 3. Horse identity

RaceReviewDB history join は馬名ではなく JRDB 血統登録番号を使用する。

Canonical identity:

`horse_id = blood_registration_no`

RaceNote base converter は KYI から既に blood registration number を parse
しているため、v0.1 から `horse.basic.horse_id` として additive に保持する。

Name fallback is forbidden.

`horse_id` が無い場合は `NO_HORSE_ID` とし、馬名による推測 join はしない。

## 4. As-of boundary

History query:

`race_date < target_date`

Adapter は Reader の as-of-exclusive query に加え、返却 row 自体も再検査する。
target date 以上の history row が存在した場合は fail closed とする。

## 5. Stable v0.1 fields

v0.1 が読む RaceReviewDB field は adapter 内 `STABLE_RUN_FIELDS` に固定する。

Main groups:

- ability/time
  - declared_class_group
  - time_class_equivalent
  - time_class_equivalent_numeric
  - horse_adjusted_delta_sec
  - horse_adjusted_delta_per_1000m
- pace
  - pace_shape
- position
  - corner1-4 frontness
  - early/middle/late/overall position gain
- finish
  - last3f rank / percentile
  - closing_gain_sec
  - winner_gap_sec
- trouble raw
  - JRDB track/pace/late-break/position/trouble fields

## 6. Explicitly not consumed in v0.1

RaceReviewDB is still evolving. The adapter therefore does not consume:

- `performance_label`
- `reason_codes_json`
- calibrated `start_delay_confidence`
- causal / shrunk track-bias as a prediction signal

Track bias remains `NOT_USED_UNCALIBRATED_V0_1`.

JRDB trouble metrics are persisted as `RAW_ONLY_UNCALIBRATED`; the adapter does
not invent thresholds for positive/negative trouble interpretation.

## 7. Deterministic review tags

v0.1 tags are threshold-free observed transformations only.

Examples:

- `TIME_ABOVE_DECLARED_CLASS`
- `TIME_AT_DECLARED_CLASS`
- `TIME_BELOW_DECLARED_CLASS`
- `EARLY_POSITION_GAIN / LOSS`
- `MIDDLE_POSITION_GAIN / LOSS`
- `LATE_POSITION_GAIN / LOSS`
- `CLOSING_GAIN / LOSS`
- `MOVE_THEN_FADE`
- `FASTEST_LAST3F`
- `PACE_<RaceReviewDB pace_shape>`

These are evidence descriptors, not additive scores.

## 8. Multi-run profile

Per horse, Adapter aggregates tag occurrence counts.

A tag observed at least twice is recorded under `repeated_patterns`.

v0.1 deliberately does not yet derive:

- hidden_strength_signals
- fragile_form_signals

Both arrays remain empty with:

`composite_signal_status = NOT_DERIVED_V0_1`

This keeps the first connection reproducible while leaving the next RaceNote
research step free to design candidate-up / popular-risk composites explicitly.

## 9. Forecast lifecycle

The sidecar is pre-market historical evidence and may be built before Forecast
Freeze.

It must never open:

- current market
- current JRDB consensus
- Training Edge

Planned future lifecycle:

```text
RaceNote INDEPENDENT view
  + RaceReview evidence sidecar
  + EdgeDB performance evidence
        |
        v
Horse Evidence Card
        |
        v
Pairwise comparison / scenario robustness
        |
        v
Independent Forecast
        |
      Freeze
        |
        +--> JRDB consensus
        +--> Market / RL / Value
```

v0.1 adapter availability does not automatically activate a new Forecast
generation or modify Gen0.2 frozen semantics.

## 10. Short-comment direction

The sidecar is designed so the same evidence used by prediction can later feed
short comments.

The comment renderer should not re-read RaceReviewDB and invent a separate
opinion. It should consume the Evidence Card selected by the forecast process.

Target style examples are data comparison plus historical-run interpretation:

- high time-class performance despite an unfavorable pace/position context
- visible result better than the underlying running content
- repeated position recovery / move-then-fade profile
- strong closing evidence with explicit uncertainty

Composite wording such as "着順以上" or "前走は展開利大" is intentionally not
hard-coded in Adapter v0.1. Those belong to the next RaceNote Evidence Card
contract, where duplicate evidence and contradiction handling can be audited.
