# RaceNote Forecast Human-Context Reader v0.4.3 Candidate

Status: **A/B VALIDATION CANDIDATE — NOT YET CURRENT BASELINE**  
Date: 2026-10-02  
Candidate logic id: `RaceNote-Human-Context-Reader-0.4.3-candidate`  
Baseline for A/B comparison: `RaceNote-Human-Context-Reader-0.4.2-candidate`  
RRDB recommendation contract: `rrdb-recommendation-signals-v0.3`

Research basis:
- Discovery: BTDAY-0023〜0026 / 144R
- Retest: BTDAY-0027〜0029 / 96R
- total reviewed population: 240R
- Hierarchy review: Discovery 64R + Retest 45R
- Coverage detailed review: 3着無印 Discovery 68頭 + Retest 24頭

## 1. Purpose

v0.4.3 is a **bounded comparison-stage refinement** of v0.4.2.

It does not replace v0.4.2 yet.
It exists so the next unused BTDAYs can freeze both versions from the same
market-blind input and test whether the refinement actually improves results.

v0.4.3 does **not** introduce:
- a score;
- a fixed weight;
- a threshold table;
- a matched-signal count;
- a popularity/odds proxy;
- a new mark;
- a sixth selected horse;
- an automatic RRDB promotion rule.

The five marks remain ◎ ○ ▲ △1 △2.

The only intended change is an explicit final consistency pass after the
ordinary v0.4.2 whole-race reading.

## 2. Inherited v0.4.2 contract

Unless this document explicitly changes a point, v0.4.2 remains inherited.

In particular:
- read the whole race before assigning marks;
- integrate ability, recent content, direct-condition fit, pace, training,
  pedigree, Trend, RRDB and other available pre-Freeze evidence flexibly;
- current market information is unavailable and must not be inferred;
- RRDB is reinterpretation evidence, not an additive vote;
- ▲ remains an independently selected single-shot / 単穴 role;
- ▲ may beat ◎○ outright without that outcome itself constituting a Forecast failure;
- reader-facing prose remains governed by
  `FORECAST_READER_FACING_PROSE_v0_1.md`.

## 3. Why v0.4.3 exists

### 3.1 Hierarchy finding

Discovery:
- mechanical Hierarchy failures: 64R
- clear pre-race correction candidates: 12R / 64 = 18.8%
- boundary cases: 11R / 64 = 17.2%
- original hierarchy reasonable or ▲ role success: 41R / 64 = 64.1%

Retest:
- mechanical Hierarchy failures: 45R
- clear pre-race correction candidates: 7R / 45 = 15.6%
- boundary cases: 6R / 45 = 13.3%
- original hierarchy reasonable or ▲ role success: 32R / 45 = 71.1%

The same correction patterns appeared in both sets:
1. `race_model` and final hierarchy become inconsistent;
2. direct-condition evidence is underweighted;
3. visible 2nd/3rd-place stability can outrank stronger "can win" evidence;
4. visible finishing position can override hidden load/time evidence;
5. ▲ should almost never be promoted merely because it later wins.

### 3.2 ▲ role finding

Discovery ▲ winners:
- 11R
- 9 single-shot successes
- 1 promotion miss
- 1 ambiguous

Retest ▲ winners:
- 9R
- 8 single-shot successes
- 1 promotion miss

Therefore v0.4.3 must preserve the independent ▲ role.
It must not flatten ▲ back into rank 3.

### 3.3 Coverage finding

3着無印 review:

Discovery:
- SWAP_CANDIDATE 32 / 68 = 47.1%
- COMPLETE_MISS 30 / 68 = 44.1%
- AMBIGUOUS 6 / 68 = 8.8%

Retest:
- SWAP_CANDIDATE 7 / 24 = 29.2%
- COMPLETE_MISS 13 / 24 = 54.2%
- AMBIGUOUS 4 / 24 = 16.7%

The borderline challenger idea partially replicated but much less strongly.
Therefore Coverage changes must be narrow and conservative.

## 4. v0.4.3 reasoning flow

Conceptually:

```text
read the whole race
  -> build ordinary mainline contenders
  -> independently identify the best single-shot / ▲ case
  -> provisional ◎ ○ ▲ △1 △2
  -> HIERARCHY CONSISTENCY PASS
  -> ▲ PROMOTION GATE
  -> NARROW COVERAGE CHALLENGER CHECK
  -> final five unique marks
  -> reader-facing explanation
  -> Freeze
```

These are semantic comparison passes, not deterministic rules.

## 5. Hierarchy consistency pass

After provisional marks exist, compare ◎ primarily against ○ and,
when relevant, against △1 / △2.

Ask four questions.

### H1. race_model consistency

> `race_model`で最も重要だと自分で判断した条件を、
> 実際に最も直接満たしているのは◎か。

Examples of relevant evidence:
- same course / same distance;
- same class;
- the race shape explicitly identified in `race_model`;
- sustained pace tolerance;
- ability to make or survive the expected position.

Do not promote a horse merely because it has one same-distance run.
The evidence must be material in this race.

### H2. direct-condition evidence

Before keeping a horse above another, ask whether a lower-marked horse has
substantially more direct evidence under today's course / distance / class /
shape.

A good generic run at another condition does not automatically outrank a
credible direct-condition performance.

This is comparative, not a fixed hierarchy of evidence.

### H3. runs-well vs can-win

Re-check whether ◎ is mainly supported by:
- repeated 2nd / 3rd-place finishes;
- stability;
- safe positioning;
- generic repeatability;

while another serious contender has a more direct first-place route, such as:
- already winning under the same or very similar condition;
- creating the race rather than merely following it;
- surviving heavier pace/load;
- showing class/time strength hidden by visible finish;
- demonstrating a stronger ability to decide the race.

Do not automatically prefer the previous winner.
The question is whether today's winning case is actually stronger.

### H4. visible finish vs hidden content

When visible finishing position conflicts with RRDB / RaceReview evidence,
explicitly compare both stories.

Examples:
- `TIME_CLASS_PLUS1`
- `FRONT_SURVIVE_GAP05`
- `REAR_HIGH_LAST3F90`
- `HV02_Q85_Q90`
- RESULT_UNDERRATES_TIME
- PACE_POSITION_AGAINST_GOOD_RUN
- REPEATED_FASTEST_LAST3F

A hidden-strength label is not itself a promotion rule.
It matters only if the underlying run transfers to today's race.

## 6. ▲ promotion gate

Default:
**do not return ▲ to the ordinary mainline merely because its single-shot case
is attractive.**

The Discovery + Retest evidence strongly supports preserving ▲ as an independent
role.

Return ▲ to mainline comparison only when its pre-Freeze case is no longer just
conditional asymmetric upside and already contains **mainline-grade direct
winning evidence**.

Examples of promotion-worthy structure:
- same/near condition win evidence;
- strong class/time evidence that transfers today;
- direct current-condition fit;
- strong preparation;
- and the provisional ◎ is mainly a "runs well" case.

Do not promote ▲ when the case depends mainly on:
- pace collapse;
- distance-change speculation;
- trouble rebound;
- first-time condition upside;
- "if everything goes right" volatility.

If promotion is warranted, re-run ordinary mainline comparison.
Do not simply relabel ▲ as ◎ mechanically.

## 7. Narrow coverage challenger check

This is deliberately narrower than the Discovery hypothesis.

After provisional △1 / △2 are chosen, inspect whether there is **one**
unmarked borderline challenger deserving direct comparison with the support
boundary.

A challenger should normally satisfy both:

1. meaningful **direct-condition evidence** for today's course / distance /
   class / shape; and
2. no large **ability gap** versus △2.

Optional supporting evidence:
- hidden strength;
- prior trouble;
- training improvement;
- RRDB reinterpretation.

These supporting signals are not sufficient alone.

Do not:
- rescan the entire field looking for any interesting outsider;
- promote on hidden-strength labels alone;
- make six selections;
- weaken ▲ to make room;
- force a swap.

If no unmarked horse clearly challenges △2, keep the original five.

If one challenger is materially stronger than △2, replace only the weakest
ordinary support slot and preserve five unique marks.

## 8. Mark meanings

### ◎ — Main

今回、自分なら最も買いたい主役。

The final consistency pass should reduce cases where ◎ means only
"most likely to run well" while another horse has the stronger first-place case.

### ○ — Principal opponent

◎以外で、本線として最も強く相手評価する馬。

○ may become ◎ after the consistency pass when the comparative winning case is
materially stronger.

### ▲ — Single-shot / 単穴

通常の本線比較とは別に、今回の条件が噛み合ったときに本線へ割って入り、
馬券の見返りを大きくし得る魅力を買いたい馬。

▲ may win.
That outcome alone is not evidence that ▲ should have been ◎.

### △1 / △2 — Supporting contenders

Remaining ordinary support candidates.
The coverage challenger check acts only at this support boundary.

## 9. Minimal audit additions

v0.4.3 should retain the ordinary v0.4.2 decision trace and add concise
research-only audit fields when practical:

```json
{
  "consistency_pass": {
    "hierarchy_reviewed": true,
    "hierarchy_changed": false,
    "hierarchy_reason": null,
    "single_shot_promotion_reviewed": true,
    "single_shot_promoted": false,
    "single_shot_promotion_reason": null,
    "coverage_challenger_reviewed": true,
    "coverage_challenger": null,
    "coverage_changed": false,
    "coverage_reason": null
  }
}
```

These fields record the reasoning result.
They are not inputs and must not be transformed into scores.

A/B validation may store this sidecar separately if the current Forecast schema
does not yet accept these fields.

## 10. A/B validation status

v0.4.3 is **not the default Forecast logic yet**.

Until promotion:
- ordinary/current output remains v0.4.2;
- v0.4.3 is generated only for explicit A/B validation;
- the same pre-Freeze input must be used for both;
- both versions must be frozen before target results are opened;
- neither version may see the other's result performance before Freeze.

Canonical A/B procedure:
`BTDAY_AB_VALIDATION_RUNBOOK_v0_1.md`

## 11. Promotion question

Do not promote v0.4.3 because individual corrected races look persuasive.

The next evidence must answer whether v0.4.3 improves the system as a whole:

Primary:
- ◎ win rate / win ROI;
- winner in five;
- all Top3 in five;
- ◎○ / ◎▲ quinella;
- ◎→○ / ◎→▲ exacta;
- ◎-key trio;
- ◎-first-fixed trifecta.

Diagnostics:
- how many races changed from 0.4.2;
- which pass caused each change;
- whether unchanged races remain stable;
- whether Coverage changes improve podium coverage without reducing winner
  coverage;
- whether ▲ role integrity remains intact.

A few large exotic payouts are part of the target distribution and must not be
automatically removed from the primary comparison.

## 12. Summary

```text
v0.4.2 whole-race Human-Context Reader
  + semantic hierarchy consistency
  + conservative ▲ promotion gate
  + narrow △2 coverage challenger gate
  = v0.4.3 candidate
```

No score.
No fixed weight.
No automatic RRDB promotion.
No popularity rule.
No sixth horse.
No automatic ▲ promotion.
No forced coverage swap.
Market blind remains mandatory.
