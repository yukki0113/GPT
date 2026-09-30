# RaceNote Forecast Human-Context Reader v0.3.5 Candidate

Status: **CANDIDATE — WIN-FIRST WITH MARKET-AWARE JUDGMENT**
Date: 2026-10-01
Base logic: `RaceNote-Human-Context-Reader-0.3.4-candidate`
Candidate logic id: `RaceNote-Human-Context-Reader-0.3.5-candidate`

## 1. Purpose

BTDAY-0007 / BTDAY-0008 showed that v0.3.4 preserved strong five-horse candidate
coverage but did not improve the final ◎ win rate as intended.

The main issue was not candidate extraction. It was the final ordering of the
marked horses.

v0.3.5 therefore leaves the five-horse candidate formation unchanged and
adjusts only the final ◎ decision.

The guiding idea is:

> **◎ should primarily be the horse the Reader thinks is most likely to win this
> race, while still allowing market disagreement / buyability to influence that
> judgment when supported by real race evidence.**

This is deliberately not "pick the favorite" and not "pick the value horse".

## 2. Candidate set remains unchanged

The Reader should form and understand the relevant candidate cluster using the
same flexible race reading as before.

Do not change candidate inclusion or exclusion merely to support a preferred ◎.

The five-horse cluster remains a separate forecast asset from the final mark
ordering.

## 3. ◎ — Win-first main selection

◎ answers first:

> 今回、最も1着になる可能性が高いと自分は考える馬はどれか。

The Reader should make this judgment from the race itself:

- ability;
- current condition;
- race shape;
- course / distance fit;
- prior-run reinterpretation;
- class context;
- training;
- pace / position;
- pedigree where relevant;
- and any other evidence allowed by the active RaceNote contract.

No single lane controls the decision.

### 3.1 Market information is context, not a tie-break-only rule

Market information should remain visible while judging ◎.

Do **not** use popularity merely after the win judgment as a mechanical
tie-breaker.

Instead ask:

> 市場の評価は、この馬の今回の勝つ可能性を適切に表しているか。

A horse may become ◎ despite lower market support when the Reader has concrete,
race-specific reasons to believe the market is underrating its winning chance.

Likewise, a favorite may remain ◎ when the evidence supports it.

This preserves an "穴党" character as willingness to disagree with the market
when warranted, not as an obligation to avoid popular horses.

### 3.2 Do not confuse upside with win probability

The following alone are not enough to justify ◎:

- "improvement is possible";
- "training is better";
- "distance change may suit";
- "RRDB upgraded the prior run";
- "the price is attractive";
- "this horse is more interesting".

Those may contribute to the final judgment, but ◎ should still represent the
Reader's best race-specific estimate of the winner.

## 4. ○ — Stability slot remains

○ keeps the existing role:

> 今回、地力・実績・再現性の面で最も信頼して走ってきそうな馬は何か。

○ is not automatically the second-most-likely winner.

It remains useful as:

- the principal stability benchmark;
- a major comparison horse;
- a counterweight when ◎ takes more race-specific risk.

If the win-first choice and stability choice identify the same horse, keep the
CONVERGE state.

## 5. CONVERGE

When win-first judgment and stability judgment point to the same horse:

- that horse remains ◎;
- treat the case conceptually as a **堅軸型◎**;
- assign ○ to the best remaining stability / comparison horse;
- preserve the convergence state for research.

Do not force divergence for originality, price, or style.

Do not assume CONVERGE means guaranteed win. It is evidence of agreement
between two different judgments.

## 6. DIVERGE

When ◎ and ○ differ, the Reader does **not** need to manufacture a formal
"how ◎ beats ○" narrative.

Instead it should be able to state naturally:

- why ◎ is the most likely winner in today's race;
- why ○ is still the more stable / repeatable horse;
- what evidence causes those two judgments to differ.

A race-specific winning explanation is welcome when genuinely present, but it
must not be generated merely to satisfy a template.

If the only reason to prefer ◎ is that it is more exciting, less popular, or
has vague upside, reconsider the selection.

## 7. Popularity concentration guard — semantic, not mechanical

v0.3.5 explicitly avoids a hidden drift toward "favorite = ◎".

Before Freeze, the Reader should perform a semantic check:

> If this horse were not the market favorite, would the same race evidence still
> make me choose it as ◎?

This is not a popularity filter and must not force a different horse.

The purpose is only to detect accidental substitution of market consensus for
independent race reading.

Conversely:

> If this horse were more popular, would I still like its winning case?

This check helps avoid choosing a horse merely because it looks like value.

No popularity rank or odds threshold is introduced.

## 8. Reader-facing explanation

Reader-facing prose should explain:

> why this horse is the Reader's most likely winner today.

Avoid mandatory phrases such as:

- "○を上回れる勝ち筋";
- "射程圏を保てれば";
- "自身のリズムで運べれば";

unless they are genuinely race-specific and useful.

Do not require a fixed sentence structure.

The explanation should sound like an actual race forecast, not a compliance
statement proving that a rule was satisfied.

## 9. Flexible reasoning remains mandatory

Do not introduce:

- fixed scores;
- fixed weights;
- odds thresholds;
- popularity thresholds;
- automatic favorite selection;
- automatic outsider selection;
- mandatory "value" promotion;
- deterministic mark rules.

The conceptual reasoning is:

```text
understand the race
  -> form the candidate cluster
  -> ask who is most likely to win
  -> keep market disagreement visible as context
  -> independently identify the stability horse
  -> assign ◎ / ○ / remaining marks
```

This is not a fixed algorithm.

## 10. RRDB and other evidence

RRDB remains an evidence-reinterpretation layer, not a mark rule.

UPGRADE / DOWNGRADE / CONFIRM / NEUTRAL, Next-Watch grade, IDM, training,
Trend, pedigree, direct-condition history, and market information are all
evidence lanes.

No single lane determines ◎.

## 11. Research discipline

BTDAY-0007 and BTDAY-0008 remain Frozen v0.3.4 evidence.

Do not retrospectively re-mark any prior backtest.

The next untouched blind backtests should evaluate:

- ◎ win / place / show rates;
- ◎ win / place returns;
- ◎ popularity / odds distribution;
- ○ performance;
- DIVERGE ◎ vs ○;
- CONVERGE performance;
- five-horse winner coverage;
- all-podium-in-five coverage;
- ◎-marked-horse quinella;
- five-horse trifecta-box / trio-box behavior as separate betting diagnostics.

The main question for v0.3.5 is:

> Can the Reader improve ◎ win selection without collapsing into market-following
> favorite selection and without damaging the already-strong candidate cluster?
