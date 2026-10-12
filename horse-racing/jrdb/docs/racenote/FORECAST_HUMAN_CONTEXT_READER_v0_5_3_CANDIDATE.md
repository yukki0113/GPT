# RaceNote v0.5.3 Candidate — Boundary Safety Rebuild

Status: **CURRENT CANDIDATE — REBUILT R2**
Date: 2026-10-12
Logic ID: `RaceNote-Human-Context-Reader-0.5.3-candidate`
Contract revision: `v053-boundary-safety-r2`

## 1. Purpose

v0.5.3 r2 is a narrow safety revision of the promoted v0.5.2 baseline.

It preserves the v0.5.2 prediction character:

- protected ordinary-five candidate formation;
- `WIN_FIRST_NOT_PLACE_FIRST` for ◎;
- `ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK` for ▲;
- no fixed-weight score;
- no target result / target final market access before Freeze.

The rebuild exists because the first v0.5.3 contract widened Step E too far. The phrase "candidate-set value" allowed the model to re-optimize the five-horse set around route diversity after the ordinary five had already been formed. That made the same Reader materially more sensitive to thread/model variation and produced both over-KEEP and over-ADMIT authoring.

r2 therefore restores the v0.5.2 separation:

> first protect the ordinary five, then allow one narrowly defined boundary challenge.

It is not a portfolio-diversification optimizer.

## 2. Cohort boundary

Pre-rebuild v0.5.3 sessions do not contain `contract_revision`. They remain immutable audit evidence and continue to verify under their original structural semantics.

New v0.5.3 sessions MUST contain:

`contract_revision = v053-boundary-safety-r2`

BTDAY-0077 and BTDAY-0078 are closed as unprocessed / excluded from performance evaluation. Their artifacts remain only as audit evidence of the pre-rebuild contract.

v0.5.2 remains the promoted baseline and reproduction reference.

## 3. Reader invariants

The model-facing Reader projection is unchanged from v0.5.2.

No new evidence surface, score, probability or market field is introduced.

The lane remains clean-blind:

- target result prohibited;
- target-day final odds/popularity/payout prohibited;
- sibling forecasts prohibited before Freeze.

## 4. Decision procedure

### Step A — race model

Use the v0.5.2 procedure unchanged.

Read the complete Reader and identify what decides the race from pace, position, ability, suitability, condition, repeatability and relevant historical evidence.

Do not start from public marks.

### Step B — ordinary five

Use the v0.5.2 procedure unchanged.

Choose an ordered ordinary five before looking for an external shot:

`ordinary_five = [ordinary_rank_1, ordinary_rank_2, ordinary_rank_3, ordinary_rank_4, ordinary_rank_5]`

These five are the protected candidate set under ordinary race development.

Recent finishing position must not automatically erase strong condition-relevant evidence already present in the Reader. Conversely, `hidden_strength=HIGH`, a STRONG tag or a high forecast position is never an automatic inclusion rule.

### Step C — ◎ and ○

Use the v0.5.2 procedure unchanged.

Choose ◎ and ○ from the ordinary five only.

◎ uses `WIN_FIRST_NOT_PLACE_FIRST`: choose the clearest realistic route to winning, not the safest board horse.

○ is the next strongest mainline contender route.

The ordinary order and the public ◎○ order may differ.

### Step D — one external asymmetric challenger

Use the v0.5.2 procedure unchanged.

When there are six or more runners, choose exactly one horse outside the ordinary five whose win route is materially different from merely being sixth best.

The required mode remains:

`ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK`

A distinct route qualifies a horse to be the challenger. It does **not** by itself create exchange value.

### Step E — narrow boundary safety compression

Keep ◎ and ○ fixed.

The ordinary horse exposed to the challenger is determined before the exchange:

> the lowest-ranked horse in `ordinary_five` after excluding ◎ and ○.

Do not search the ordinary five for a more convenient horse to remove.

The challenger may displace only that one boundary horse.

The default is `KEEP_ORDINARY_FIVE`.

Use `ADMIT_CHALLENGER` only when the Reader already contains concrete, current-condition-relevant evidence that makes the challenger genuinely competitive with the fixed boundary horse **without relying on route uniqueness itself**.

Direct comparison should use the same evidence already read in Steps A-D, especially:

- ability and repeatability;
- direct relevance to current surface / distance / class / race shape;
- current condition;
- material historical evidence that remains relevant.

Route diversity may break a genuinely close comparison. It may not compensate for materially weaker direct ability, repeatability or current-condition support.

Do not admit a challenger merely because:

- its running style differs;
- another retained ordinary horse covers a similar route;
- the five-horse set would look more diversified;
- the challenger has `hidden_strength=HIGH` or STRONG evidence in isolation;
- the boundary horse is less exciting than the challenger.

If the exchange remains ambiguous, KEEP.

#### ADMIT_CHALLENGER

- challenger enters as ▲;
- ◎ and ○ remain fixed;
- only the deterministic boundary horse may be displaced;
- `excluded_horse_no` is that boundary horse.

#### KEEP_ORDINARY_FIVE

- challenger is excluded;
- all five ordinary horses remain;
- ▲ is chosen from the three ordinary-five non-anchor horses by the asymmetric-route principle.

#### NO_EXTERNAL_CHALLENGER

Only for exactly five runners.

## 5. Evidence continuity rule

r2 keeps the useful part of the original v0.5.3 objective but removes the second candidate-set optimization.

Important Reader evidence already used to form the ordinary five must not disappear silently at the boundary.

This is a continuity rule, not an auto-rescue rule.

A strong historical signal must be considered when it is directly relevant, but it does not force KEEP or ADMIT.

## 6. Decision Core recording

Record the already-made judgment once.

Field roles are strict:

- `race_model`: compact race structure;
- `honmei_win_case`: how ◎ realistically wins;
- `second_case`: strongest case for ○;
- `ranking_reason`: only the decisive ◎ versus ○ comparison;
- `external_challenger_case`: why the outside horse qualifies as an asymmetric challenger;
- `boundary_review.reason`: direct challenger versus fixed boundary-horse comparison;
- `candidate_compression.reason`: concise final KEEP / ADMIT conclusion;
- `mainline_cases`: final non-▲ marked horses;
- `single_shot_case`: final ▲ route;
- `reader_facing_reason`: compact natural-language summary.

Do not use `ranking_reason` to explain ▲.

Do not copy `race_model` wholesale into the comparison fields.

Factual statements such as surface, distance, finish, running style or prior-race result must be supported by the already-open Reader. Recording may check those facts while writing; it must not reopen the prediction or perform a second ranking pass.

Repeated wording is acceptable only when the underlying judgment is genuinely the same.

## 7. Mechanical r2 guard

The v0.5.3 single-day session binds `contract_revision=v053-boundary-safety-r2`.

For r2 sessions, the Decision Core validator additionally enforces:

- the existing v0.5.2 structural contract;
- existing v0.5.3 boundary identity semantics;
- under ADMIT, the displaced ordinary horse must be the lowest-ranked non-anchor horse in the already-authored `ordinary_five`.

The validator still does not numerically score racing evidence and cannot prove prose truth. Racing judgment remains model-authored.

Legacy pre-rebuild sessions without `contract_revision` remain verifiable for audit/reproduction.

## 8. What r2 must not become

r2 is not:

- a candidate-set portfolio optimizer;
- an automatic route-diversity bonus;
- an automatic rescue for `hidden_strength=HIGH`;
- an automatic rescue for STRONG evidence;
- an automatic rescue for forecast-finish rank;
- a fixed-weight or additive score;
- a repeated self-review loop;
- a retreat from win-first ◎ or asymmetric ▲.

The protected ordinary five is again the primary stability mechanism.

## 9. Evaluation

New r2 BTDAYs must be clean-blind and must not reuse BTDAY-0077 / 0078 as performance observations.

Track:

- ◎ win / top-3;
- ▲ win / top-3;
- ordinary-five winner coverage;
- final-five winner coverage;
- ADMIT count;
- admitted challenger result;
- displaced boundary-horse result;
- KEEP challenger result;
- settlement ROI.

Also monitor reproducibility:

- ADMIT rate across comparable cards;
- ordinary-five churn under independent fresh authoring;
- unsupported factual claims in recorded reasons.

The target is not to maximize ADMIT or KEEP. The target is to preserve v0.5.2 behavior while preventing avoidable boundary loss with less thread/model sensitivity.
