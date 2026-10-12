# RaceNote v0.5.3 Rebuild — 2026-10-12

Status: **REBUILT R2 ACCEPTED FOR NEW CLEAN-BLIND CANDIDATE RUNS**

Logic ID: `RaceNote-Human-Context-Reader-0.5.3-candidate`  
Contract revision: `v053-boundary-safety-r2`

## 1. Why the first v0.5.3 contract was rejected

The first v0.5.3 contract intended to repair three boundary failures observed under v0.5.2:

1. Decision Core prose contradicting Reader evidence.
2. Strong condition-relevant evidence disappearing before compression.
3. An admitted challenger displacing an ordinary horse whose loss cost more candidate value than the challenger added.

The implementation preserved the same Reader but widened Step E into an integrated candidate-set value comparison. In practice this created too much authoring freedom.

Observed failure pattern:

- BTDAY-0078: 36/36 KEEP with templated Decision Core recording and factual inconsistencies.
- BTDAY-0077 fresh re-authoring from the same Reader: 14/36 ADMIT versus 1/36 in the prior authoring.
- The same Reader therefore produced materially different five-horse sets depending on authoring context.
- Route diversity was repeatedly used as positive exchange value, allowing a different running style to displace a stronger ordinary candidate.
- The validator checked structure but could not prevent that semantic drift.

BTDAY-0077 and BTDAY-0078 are therefore closed as unprocessed and excluded from performance evaluation. Their artifacts are retained for audit only.

## 2. Root cause

v0.5.2 had a useful separation:

```text
form protected ordinary five
  -> choose win-first ◎ / ○ inside it
  -> identify one asymmetric outside challenger
  -> compress six to five
```

The first v0.5.3 contract weakened that separation by asking the model to search the ordinary five for the horse whose removal would cost least candidate-set value while also considering route overlap.

That effectively turned Step E into a second candidate-set optimization.

The same "different route" property was then used twice:

- once to qualify the external challenger;
- again to justify displacing an ordinary horse.

This produced thread/model sensitivity and excessive discretion.

## 3. r2 design

r2 returns Step A-D to the promoted v0.5.2 semantics.

The additional v0.5.3 rule is now deliberately narrow.

### Fixed ordinary boundary

After ◎ and ○ are chosen, the only ordinary horse exposed to the external challenger is:

> the lowest-ranked horse in `ordinary_five` after excluding ◎ and ○.

The model does not search for another removable horse.

### KEEP presumption

`KEEP_ORDINARY_FIVE` is the default.

The challenger must be genuinely competitive with the fixed boundary horse on direct pre-race support relevant to the current race.

Route diversity alone cannot earn admission.

### Route diversity is a qualifier, not a score

A horse becomes the external challenger because its win route is asymmetric.

Once at Step E, that route difference does not compensate for materially weaker:

- ability / repeatability;
- direct surface / distance / class relevance;
- current condition.

It may only break a genuinely close comparison.

### Evidence continuity without auto-rescue

Strong Reader evidence may not be silently ignored, but no tag automatically forces KEEP or ADMIT.

The model must consider the evidence already used in Steps A-D. It must not start a second full-race scan.

## 4. Recording discipline

Decision Core fields retain distinct jobs.

- `ranking_reason` = ◎ versus ○ only.
- `external_challenger_case` = why the outside horse qualifies for asymmetric review.
- `boundary_review.reason` = challenger versus the fixed boundary horse.
- `candidate_compression.reason` = final KEEP / ADMIT conclusion.

Concrete factual claims must be supported by the already-open Reader.

Recording is a fact-preserving trace of a completed judgment, not another prediction pass.

## 5. Mechanical compatibility

New v0.5.3 sessions bind:

`contract_revision=v053-boundary-safety-r2`

For r2 sessions, the validator rejects ADMIT when the displaced horse is not the deterministic ordinary boundary.

Legacy pre-rebuild sessions omit `contract_revision` and remain verifiable under the old structural rule. This avoids rewriting or invalidating immutable historical Freeze artifacts.

## 6. Evaluation reset

r2 performance evidence begins with new clean-blind runs after this rebuild.

Do not use BTDAY-0077 or BTDAY-0078 as r2 performance samples.

v0.5.2 remains the promoted baseline. r2 must demonstrate that it reduces preventable boundary loss without destabilizing:

- ordinary-five membership;
- win-first ◎ behavior;
- asymmetric ▲ behavior;
- settlement characteristics.

Reproducibility itself is now an explicit evaluation item.
