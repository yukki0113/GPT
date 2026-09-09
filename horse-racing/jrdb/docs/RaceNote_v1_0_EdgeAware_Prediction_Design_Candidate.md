# RaceNote v1.0 Edge-Aware Prediction Design Candidate

## Status

**PREREGISTERED CANDIDATE / MUST BE TESTED ON POST-2025 UNTOUCHED RACES**

Established: 2026-09-09

This document defines the first RaceNote prediction candidate that consumes the released JRDB Edge Registry through the consumer contract in `JRDB_Edge_Consumer_Integration_v0_1.md`.

The purpose is not to retune v0.3-v0.6 style P3/P4 thresholds. It adds a new evidence layer while preserving the tested v0.2 ability scaffold and keeping performance, edge and value conceptually separate.

## 1. Source contracts

Control prediction model:

- `RaceNote_v0_2_Tested_Implementation_Spec_144R.md`

Edge source:

- Registry Phase1 baseline: Issue #572 / run `34299375131`
- Registry version: `phase1-003-research-2010-2025-d`
- ACTIVE registry SHA-256: `845d3e1078d2b0d98534c4bfb1a25a7b927f2b6d91b16f181b369a8a8bd64be4`
- consumer input: EdgeDB-produced `edge_matches.jsonl`
- default status: **ACTIVE only**

Consumer must not independently rediscover or rematch Edge conditions.

## 2. Leakage boundary

The released Registry was discovered and validated using JRDB history through 2025. Therefore a clean evaluation of this exact Registry must use target races dated **2026 or later**.

Do not apply the full 2010-2025 Registry to a 2025 target and call it blind/prospective. That would allow the target year to contribute to Registry discovery/validation.

For historical/past-date 2026 evaluation:

- target pre-race PACI only for current-race facts;
- exact previous history only under the Edge consumer leakage contract;
- no target SED/HJC/final odds/final popularity before prediction freeze;
- no later-dated history may be used to fill an unresolved transition;
- target dates already used in EdgeDB development smoke/calibration are excluded from untouched testing.

2026-09-05/06 are therefore not eligible as the first untouched v1.0 test block.

## 3. Core principle

Keep three layers separate:

```text
Ability / base suitability = v0.2 pre-race predictive scaffold
Edge performance evidence  = statistically validated condition-specific up/down evidence
Value evidence             = historically observed pricing/value disagreement, used only for value-role shadow
```

Historical ROI is **not** converted into prediction points.

`strength_score` is not used as a numerical contribution to the prediction score because it incorporates the magnitude of historical performance/value deviation. It may be used only to choose which Edge text to display first.

## 4. Control

`v0.2_control` is unchanged:

`Good = 0.42*AbilityGood + 0.38*SuitabilityGood + 0.10*Condition + 0.10*ForecastGood`

with the tested contradiction / weak-ability penalties unchanged.

The first v1.0 experiment keeps **v0.2 top-five membership unchanged**. Edge can reorder the five already-viable candidates, but cannot pull P6+ into the marked five in this first test.

This isolates whether Edge improves ordering before testing candidate-set expansion.

## 5. Performance Edge aggregation

### 5.1 Eligible matches

For predictive ranking use only matches satisfying all:

- `status == ACTIVE`
- `evidence.performance_signal in {POSITIVE, NEGATIVE}`
- not expired (owned by Matcher)

`value_signal` must not influence predictive ranking.

### 5.2 Correlation control — one family vote

Multiple Edge definitions from the same `evidence.family` are not allowed to stack mechanically.

For each horse and family:

1. collect all eligible performance matches in that family;
2. determine the strongest confidence level represented for POSITIVE and NEGATIVE separately;
3. if both directions occur at the same strongest confidence level, family vote = 0 (`MIXED_FAMILY`);
4. otherwise vote for the stronger-confidence direction.

Confidence voting weight:

- ACTIVE confidence `A` = magnitude 2
- ACTIVE confidence `B` = magnitude 1
- if `evidence.review_due == true`, downgrade by one magnitude step: A -> 1, B -> 0

A review-due B therefore contributes no predictive family vote, while its text remains available for explanation.

### 5.3 Horse-level PerformanceEdgeTier

Sum family votes and clamp:

`PerformanceEdgeTier = clamp(sum(family_votes), -2, +2)`

Meaning:

- `+2`: strong/independent positive condition evidence
- `+1`: modest positive condition evidence
- `0`: absent, neutral or materially conflicting evidence
- `-1`: modest opposing evidence
- `-2`: strong/independent opposing evidence

No raw sample rate, place rate, ROI or `strength_score` enters this tier numerically.

## 6. Edge-aware predictive ranking candidate

Define a bounded Edge adjustment:

`EdgeAdjustment = 0.02 * PerformanceEdgeTier`

Therefore the maximum numerical change is ±0.04.

For the existing v0.2 top five only:

`EdgeAwareGood = clamp(v0.2_Good + EdgeAdjustment, 0, 1)`

Rank those same five horses by descending `EdgeAwareGood`.

Tie-breakers:

1. higher original v0.2 Good;
2. higher AbilityGood;
3. lower horse number only as deterministic final tie-break.

Marks in the predictive candidate `v1.0-R`:

- ◎ = EdgeAware rank 1
- ○ = EdgeAware rank 2
- ▲ = EdgeAware rank 3
- △1 = EdgeAware rank 4
- △2 = EdgeAware rank 5

### Why ±0.04

This is deliberately bounded below the scale of a major v0.2 suitability/ability difference. Edge may resolve close calls but should not turn a materially inferior base horse into the axis solely because a historical condition fires.

This constant is preregistered and must not be calibrated against target results.

## 7. Value-role shadow candidate

The first test also records a separate shadow `v1.0-V` to test whether EdgeDB's **value_signal** helps the eventual ▲ role.

This does **not** change ◎ or ○ from `v1.0-R`.

Candidate pool: EdgeAware ranks 3-5 only.

For each candidate, aggregate `evidence.value_signal` with the same one-family-vote / confidence procedure to obtain:

`ValueEdgeTier in [-2,+2]`.

A horse is value-role eligible only if:

- `ValueEdgeTier >= +1`, and
- `PerformanceEdgeTier >= 0`.

This prevents a historically underpriced but performance-negative condition from being promoted as ▲.

If one or more candidates qualify, choose by:

1. higher `ValueEdgeTier`;
2. higher `PerformanceEdgeTier`;
3. better `v1.0-R` predictive rank.

If none qualify, ▲ remains v1.0-R rank 3.

The other two horses remain △ in their v1.0-R order.

Important: `v1.0-V` is a **ticket-role shadow**, not the primary predictive ranking. It must not be promoted from one favorable block.

## 8. Confidence

Keep the existing v0.2/v0.3 A/B/C confidence rule unchanged in the first Edge experiment.

Reason: changing ranking, Edge logic and confidence simultaneously would prevent attribution.

Edge evidence may be shown in the explanation but does not alter the A/B/C label in v1.0.

## 9. User-facing explanation

For ◎ / ○ / ▲ comments, Edge may provide a concise supporting or opposing reason.

Display at most:

- one strongest supporting ACTIVE Edge;
- one strongest opposing ACTIVE Edge.

Display ordering may use `confidence_band`, then `strength_score`, solely to choose which text is most informative. It does not affect the numerical ranking beyond the categorical PerformanceEdgeTier defined above.

Example:

> 能力は上位圏。今回は中山・内枠条件でプラスEdgeが入り、基礎評価が近い相手より今回条件を上に取った。不安は距離替わり側にマイナスEdgeが残る点。

If Edge is MIXED or absent, do not force an Edge sentence.

## 10. Frozen blind comparison

First untouched test should use a randomly selected three-day 2026 block, excluding any race/date previously used for Edge development smoke, RaceNote logic calibration, or known-result diagnosis.

Before HJC/result acquisition freeze for every race:

- v0.2 control top five
- `PerformanceEdgeTier` for each marked horse
- v1.0-R marks
- `ValueEdgeTier`
- v1.0-V marks
- A/B/C confidence
- comments / displayed Edge IDs
- Edge Registry provenance
- `edge_matches.jsonl` SHA / Freeze provenance

## 11. Primary evaluation questions

### A. Predictive ranking — v1.0-R vs v0.2

Primary:

1. ◎ win / top2 / top3
2. changed-◎ head-to-head: v0.2 winner vs v1.0-R winner
3. Q2 `◎-○ / ◎-▲`
4. changed-mark race hit/return diagnostics

Secondary:

- Q4
- trio A6 / B5
- performance by PerformanceEdgeTier

### B. Value role — v1.0-V vs v1.0-R

Primary:

1. changed-▲ quinella head-to-head
2. Q2 hit count / return
3. ◎-▲ wide
4. payout concentration

The test should explicitly distinguish:

- predictive improvement from performance Edge;
- ticket-economics improvement from value Edge.

## 12. Interpretation rules

Do not promote v1.0 from one three-day block.

After the first block:

- if v1.0-R produces practically no rank changes, do not immediately loosen `0.02`; inspect Edge coverage/family distribution first;
- if it changes many races but loses materially, retire/rethink the aggregation rather than micro-tuning the constant;
- if it improves, repeat unchanged on a second untouched block;
- v1.0-V requires changed-role evidence across at least two untouched blocks before replacing orthodox P3 as ▲.

The prior v0.3-v0.6 experience is treated as a warning against iterative threshold search on settled races.

## 13. Future extensions explicitly excluded from v1.0

Not part of this first test:

- Edge pulling P6+ into top five;
- direct use of historical ROI or `strength_score` as prediction weight;
- PROVISIONAL/WATCH Edge;
- automatic Ability/index score mutation;
- probabilistic win/top2 model training;
- learned Edge coefficients;
- target final odds/value calculation.

If the first Edge integration is useful, these become separately versioned experiments rather than silent extensions.
