# RaceNote v0.5.3 Candidate — Evidence-Preserving Boundary Compression

Status: **CURRENT CANDIDATE — IMPLEMENTED**
Date: 2026-10-12
Logic ID: `RaceNote-Human-Context-Reader-0.5.3-candidate`

## 1. Purpose

v0.5.3 preserves the promoted v0.5.2 character:

- protected ordinary candidate formation;
- `WIN_FIRST_NOT_PLACE_FIRST` for ◎;
- `ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK` for ▲;
- no fixed-weight score;
- no result/market access before Freeze.

The change is limited to candidate-boundary quality. Post-race review of v0.5.2 found three related failure modes: a boundary explanation can disagree with Reader evidence; strong condition-relevant Reader evidence can disappear before compression; and admitting an external challenger can remove a stronger ordinary horse without a sufficiently explicit exchange comparison.

v0.5.3 does not add three exception rules. It rewrites candidate formation as one evidence-preserving procedure.

## 2. Reader invariants

The model-facing Reader projection is unchanged from v0.5.2. No new evidence surface, score, probability or market field is introduced.

The lane remains clean-blind: target result, target-day final odds/popularity/payouts and sibling forecasts are forbidden before Freeze.

## 3. Decision procedure

### Step A — race model

Read the complete Reader and identify the concrete race structure: pace, position, ability, suitability, condition, repeatability and condition-relevant historical evidence. Do not start from public marks.

### Step B — ordinary five

Choose five horses whose realistic winning routes deserve protection under ordinary race development.

Use the evidence as a whole. Recent finishing position must not automatically erase strong historical evidence that directly matches the present surface/distance/class/race shape. Conversely, `hidden_strength=HIGH`, a STRONG tag or a high forecast position is never an automatic admission rule.

The objective is not to protect tags. It is to avoid losing a materially supported winning route already present in the Reader.

### Step C — ◎ and ○

Assign ◎ and ○ only inside the ordinary five.

◎ uses `WIN_FIRST_NOT_PLACE_FIRST`: choose the clearest realistic win route, not the safest board horse. ○ is the next strongest mainline contender route. Ordinary rank 1 need not be ◎.

### Step D — external asymmetric challenger

When there are six or more runners, identify exactly one horse outside the ordinary five whose winning route is materially different from merely being sixth best. The mode remains `ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK`.

Finding a distinct route does not itself justify admission.

### Step E — direct boundary exchange

Keep ◎ and ○ fixed. Compare the challenger directly with the ordinary-five horse whose removal would cost the least candidate-set value.

Candidate-set value includes ability/repeatability, direct relevance to the current conditions, current condition, race-model fit and whether the route is replaceable by another retained horse.

Use `ADMIT_CHALLENGER` only when the added asymmetric route is worth more than the ordinary route being removed. Otherwise use `KEEP_ORDINARY_FIVE`.

Compression is therefore an exchange decision, not a challenger-appreciation decision.

### Step F — one-pass coherence check

Before Freeze, perform one bounded consistency pass. Do not restart the prediction.

Check only:

1. **Evidence continuity** — no excluded boundary horse has materially relevant Reader evidence that was never considered.
2. **Comparative consistency** — the stated comparison reason agrees with the actual Reader evidence used for that reason.
3. **Exchange value** — an admitted challenger does not improve novelty by discarding a clearly stronger indispensable ordinary route.

If a contradiction is found, repair that boundary comparison once. Do not loop through all horses again.

### Step G — final marks and reasoning

Final marks are ◎ ○ ▲ △ △.

- ◎/○ remain those assigned in Step C.
- Under `ADMIT_CHALLENGER`, challenger is ▲.
- Under `KEEP_ORDINARY_FIVE`, ▲ is the strongest asymmetric route among the three non-anchor ordinary horses.

Reasoning fields are audit records of the already-made judgment, not a second scoring pass.

## 4. Boundary semantics

`boundary_review` always represents the last direct keep/drop comparison.

- `ADMIT_CHALLENGER`: `boundary_review.alternative_horse_no` MUST equal the displaced ordinary horse (`excluded_horse_no`).
- `KEEP_ORDINARY_FIVE`: `boundary_review.alternative_horse_no` MUST equal the external challenger.
- five-runner `NO_EXTERNAL_CHALLENGER`: `boundary_review.alternative_horse_no` MUST be null.

This invariant is enforced structurally by the v0.5.3 validator. The validator does not numerically judge racing evidence.

## 5. What v0.5.3 must not become

v0.5.3 is not:

- an automatic rescue for `hidden_strength=HIGH`;
- an automatic rescue for STRONG evidence;
- an automatic rescue for forecast-finish rank;
- a special newcomer exception table;
- a fixed-weight or additive score;
- a six-horse public prediction;
- a repeated self-review loop;
- a retreat from win-first ◎ or asymmetric ▲.

Unpredictable misses remain acceptable. The target is narrower: reduce cases where the model already had important pre-race evidence but lost it through its own compression process.

## 6. Evaluation

2026-10-12 remains an immutable v0.5.2 forward cohort because it was already frozen before v0.5.3 implementation.

The first unresolved future day after implementation may use v0.5.3.

Keep prediction and settlement evidence separate. In addition to existing ◎/▲/ROI metrics, audit:

- ordinary-five winner coverage;
- final-five winner coverage;
- challenger admission count;
- admitted challenger result;
- displaced ordinary-horse result;
- KEEP challenger result;
- preventable boundary misses.

Historical known-result days may validate structure and diagnose prior failure modes, but they are not prospective performance evidence for v0.5.3.

## 7. Promotion principle

v0.5.3 is successful only if boundary quality improves without flattening the v0.5.2 attacking character. Higher winner-in-five coverage alone is not enough if ◎ becomes place-first or ▲ loses asymmetric payout value.
