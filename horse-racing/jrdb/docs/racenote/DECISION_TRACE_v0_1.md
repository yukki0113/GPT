# RaceNote Decision Trace v0.1

Status: IMPLEMENTED FORECAST PROVENANCE CONTRACT  
Date: 2026-09-25

## 1. Purpose

Forecast Gen0.3 が出す理由文を、上流Evidenceから切り離さない。

従来からForecast horseには:

- primary_reason
- secondary_support
- main_concern
- why_above_next
- scenario_adjustment_reason

を保持していた。

Decision Trace v0.1 は、それぞれの文章が参照できる根拠集合を明示する。

文章の自然言語自体を機械判定するのではない。
「存在しないEvidenceを理由として持ち込めない」ことを保証する。

## 2. Position in the pipeline

```text
General Evidence
  -> Prediction Interpretation
  -> Pairwise
  -> Scenario
  -> Base Forecast
  -> Edge Performance
  -> Final Forecast
       |
       +-> Decision Trace
              |
              +-> future Short Comment
  -> Freeze
```

Decision TraceもFreeze対象である。

## 3. Trace object

各Forecast horseは次を持つ。

```text
decision_trace
  trace_version
  primary
    lane
    evidence_codes
  secondary
    lane
    evidence_codes
  concern
    lane
    evidence_codes
  pairwise_support_horse_nos
  scenario_risk_ids
  edge_ids
  comment_evidence_codes
```

validated outputでは:

`short_comment_status = SOURCE_READY`

を付与する。

## 4. Traceable lanes

v0.1:

- DATA_TREND
- RACEREVIEW
- ABILITY_ANCHOR
- RACE_STRUCTURE
- SCENARIO
- EDGE_PERFORMANCE
- UNCERTAINTY
- MIXED
- NONE

`NONE` は secondary のみ許可する。

primary / concern は必ず実在Evidenceを1つ以上持つ。

## 5. DATA_TREND codes

General Evidenceに実際に存在するcodeだけを参照できる。

例:

- SAME_SURFACE
- SAME_DISTANCE
- DISTANCE_RANGE_1
- SAME_VENUE
- FRAME_TREND
- SIRE_TREND
- JOCKEY_TREND

存在しないcodeはfail closed。

同じ redundancy group のcodeを複数書いても
独立票として加点してはならない。

## 6. RACEREVIEW codes

Horse Evidence Card / General Evidenceに実際に存在する
RaceReview codeだけを参照できる。

例:

- RESULT_UNDERRATES_TIME
- RESULT_OVERRATES_TIME
- PACE_POSITION_AGAINST_GOOD_RUN
- PACE_POSITION_AIDED_RESULT
- LOSS_WITH_FASTEST_LAST3F
- MOVE_THEN_FADE
- repeated variants

hidden_strength / fragile_form の reason_codes もtrace可能。

RaceReviewDBに存在しない意味ラベルをForecast側で捏造しない。

## 7. Ability codes

Ability Anchorは実際に値が存在する項目だけtrace可能。

canonical trace codes:

- ABILITY_LATEST
- ABILITY_PEAK
- ABILITY_TYPICAL
- ABILITY_MINIMUM
- ABILITY_CONSISTENCY

ただしDecision TraceがAbilityを参照できても、
Gen0.3の読み順は変わらない。

```text
DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY
```

Ability単独でのupgrade / downgradeは禁止のまま。

## 8. Race Structure codes

Prediction Interpretationに実在するRace Structureから:

- PACE_PRESSURE_LOW
- PACE_PRESSURE_MEDIUM
- PACE_PRESSURE_HIGH
- POSITION_TENDENCY_FRONT
- POSITION_TENDENCY_FORWARD
- POSITION_TENDENCY_MID
- POSITION_TENDENCY_BACK

をtraceできる。

UNKNOWNは理由codeにしない。

これらはcontextであり、自動的なpositive/negativeではない。

## 9. Pairwise support

`pairwise_support_horse_nos` は、
Pairwise auditで実際にその馬がpreferredになった直接比較だけを参照できる。

例:

```text
A > B
A > C
```

ならAはB/Cをtraceできる。

Pairwiseのまま最終◎を維持した馬は、
最終2位に対する直接Pairwise supportを必須とする。

Edge PerformanceによりPairwise順位を逆転して最終◎になった場合は例外。
その場合は後述のEdge traceが必須となる。

## 10. Scenario risk

`scenario_risk_ids` は実際のScenario順位からderiveする。

その馬のScenario rankがPairwise rankより悪化したケースを
すべて記載しなければならない。

例:

```text
Pairwise rank = 1
SLOW   = 1
MEDIUM = 1
FAST   = 2

scenario_risk_ids = [FAST]
```

リスクScenarioを隠すことはできない。

Scenarioで使われたreason code:

- SCENARIO_SLOW
- SCENARIO_MEDIUM
- SCENARIO_FAST
- Scenario auditのkey_reason_codes

もtrace可能。

## 11. Edge trace

Edge PerformanceをForecastでUSEDにした場合、
`edge_ids` に実際に使われたEdge IDを1件以上記録する。

存在しないEdge IDは禁止。

Base ForecastからFinal Forecastで順位変更した場合は、
従来どおりEdge Performance evidenceが必須であり、
Decision TraceでもそのEdge IDを残す。

Edge ValueはFreeze前には存在しないためtraceできない。

## 12. Comment evidence

`comment_evidence_codes` は、
primary / secondary / concern / Edge traceに含まれるcodeのsubsetとする。

したがって将来のShort Comment rendererは:

```text
Forecast Decision Trace
  -> comment_evidence_codes
  -> prose renderer
```

の順でのみ文章化できる。

「予想では使っていなかったが、結果を見た後に都合の良い理由を追加する」
経路を作らない。

## 13. Reason text relationship

Decision Traceは文章そのものの意味一致をNLP判定しない。

代わりに:

- primary_reason -> primary trace required
- secondary_supportが非空 -> secondary trace required
- main_concern -> concern trace required
- why_above_next -> direct Pairwise support または Edge trace required

とする。

これにより自然な文章生成の自由度を残しつつ、
根拠なしの自由作文を防ぐ。

## 14. Freeze

Decision TraceはForecast object内に含まれる。

したがって:

- trace
- reason prose
- rank
- mark
- probability
- Edge evidence

はすべて同じprediction hashでFreezeされる。

Freeze後にcomment evidenceだけ書き換えることも改ざん扱いとなる。

## 15. Short-comment target

将来のShort Commentは、例えば次のように生成できる。

```text
Primary:
  DATA_TREND / SAME_DISTANCE

Secondary:
  RACEREVIEW / RESULT_UNDERRATES_TIME

Concern:
  SCENARIO / SCENARIO_FAST

Pairwise:
  5番より上

Comment:
  同距離実績を評価。前走も着順以上の内容で、
  通常の流れなら上位。ハイペース時の逆転余地は残る。
```

Commentの文面はfuture rendererの責務。
Decision Traceは使える根拠だけを固定する。

## 16. Canonical implementation

- `src/racenote_forecast_gen0_3.py`
- `schema/racenote_forecast_gen0_schema_v0_3.json`
- `tests/test_racenote_forecast_gen0_3.py`
- `docs/racenote/DECISION_TRACE_v0_1.md`
