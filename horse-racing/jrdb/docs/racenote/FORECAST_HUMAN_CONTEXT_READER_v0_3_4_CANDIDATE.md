# RaceNote Forecast Human-Context Reader v0.3.4 Candidate

Status: **CANDIDATE — WINNING VALUE REFINEMENT**
Date: 2026-09-30
Base logic: `RaceNote-Human-Context-Reader-0.3.3-candidate`
Candidate logic id: `RaceNote-Human-Context-Reader-0.3.4-candidate`

## 1. Purpose

BTDAY-0005 / BTDAY-0006 support keeping the v0.3.3 separation between:

- ◎ = attraction / the horse most worth buying in this race;
- ○ = stability / the most reliable major rival;
- attraction + stability convergence = conceptual **堅軸型◎**.

The next adjustment is deliberately small.

The diagnosis from BTDAY-0005 / BTDAY-0006 is that a DIVERGE ◎ can sometimes
represent a horse with plausible improvement or upside without explaining
clearly enough why that upside can **actually defeat the stability horse today**.

v0.3.4 therefore refines attraction from generic "upside / improvement" toward:

> **a credible winning path that makes the horse more buyable than the market
> and/or the safer rival in this specific race.**

This is not a value-betting formula and does not introduce fixed odds,
popularity thresholds, scores, weights, or expected-value calculations.

## 2. ◎ — Attraction slot / 魅力枠

◎ still answers:

> 今回、この馬を一番買いたい理由は何か。

But a DIVERGE attraction case should now distinguish between:

- **improvement case** — why the horse may run better than before; and
- **winning case** — why that improvement can plausibly be enough to beat the
  main stability rival and win this race.

Improvement alone is not necessarily sufficient for ◎.

Examples of a winning case may include, without becoming a checklist:

- a pace / position scenario in which the horse's strength becomes decisive;
- a condition change that removes a meaningful prior limitation;
- hidden strength in a prior run that is especially transferable to today's race;
- current state plus race shape creating a higher ceiling than the safer rival;
- a class / opponent-strength read showing that visible form understates the
  horse's actual winning ability;
- another race-specific path by which the horse can reasonably finish ahead of
  the stability choice.

The Reader should not invent a winning path merely to justify a less popular
horse. If the evidence supports only "better than last time" but not "can beat
the safer rival today", the horse may belong below ◎.

## 3. Market context / 買い妙味

Pre-race market information may be used as **context for buyability**, not as a
ranking rule.

The useful question is:

> 市場の評価と自分の今回評価がズレている馬はいるか。そのズレには、
> このレースを勝てるだけの具体的な根拠があるか。

This means:

- a less popular horse is not attractive merely because it is less popular;
- a favorite is not disqualified merely because it is popular;
- no minimum odds or minimum popularity rank is required for ◎;
- no automatic preference is given to outsiders;
- market disagreement matters only when the Reader can explain the underlying
  race-specific winning case.

The intended "穴党" character is therefore expressed as:

> **being willing to make an underappreciated winning case ◎ when the evidence
> supports it, rather than mechanically avoiding favorites.**

## 4. ○ — Stability slot / 安定枠

○ retains the v0.3.3 role:

> 今回、地力・実績・再現性の面で最も信頼して走ってきそうな馬は何か。

Typical support may include class ability, repeated recent performance,
same-course / same-distance evidence, repeatable race shape, and fewer major
uncertainties.

○ is not "second-best ◎".

When ◎ and ○ diverge, ○ remains the main benchmark the attraction case must be
able to challenge.

## 5. DIVERGE comparison

When attraction and stability identify different horses, the Reader should be
able to state, concisely and without fixed scoring:

1. why ◎ is attractive today;
2. why ○ is the safer / more repeatable horse;
3. **how ◎ can actually finish ahead of ○ and win**.

The third item is the v0.3.4 refinement.

Do not reduce this to a mandatory sentence template. It is a semantic
requirement for the judgment, not a formatting rule.

If the Reader cannot find a credible race-specific route by which the attraction
horse beats the stability horse, it should reconsider whether the attraction
horse truly deserves ◎.

This does **not** mean "always promote ○ to ◎".
Another candidate may own the stronger winning case, or attraction and stability
may converge.

## 6. CONVERGE / 堅軸型◎

When attraction and stability point to the same horse:

- the horse remains ◎;
- treat the case conceptually as a **堅軸型◎**;
- assign ○ to the best remaining stability / comparison horse;
- preserve the convergence state for research.

A popular CONVERGE horse is valid when the Reader independently reaches both
judgments.

Do not force divergence merely to make the forecast look more original or
higher-paying.

Likewise, do not treat CONVERGE as proof that the favorite is automatically
correct. It is a research signal, not a fixed confidence score.

### 6.1 Counter / reversal handling

CONVERGE audit fields must never point back to ◎ itself.

- `strongest_counter` must describe a remaining rival or meaningful race-shape
  scenario that could defeat ◎;
- `reversal_condition` must describe how that counter could materialize;
- ○ is a natural source, but another rival or scenario may be more meaningful.

Semantic guard before Freeze:

```text
counter horse != ◎
reversal target != ◎
```

## 7. Flexible reasoning remains mandatory

This candidate does **not** introduce:

- attraction / stability / value scores;
- fixed weights;
- popularity-rank thresholds;
- odds thresholds;
- expected-value cutoffs;
- mandatory outsider selection;
- fixed "if X then ◎" rules;
- mechanical IDM / RRDB / training / Trend ranking.

The LLM should continue to read the race as a human forecaster:

```text
understand the race
  -> understand the candidates
  -> identify stability
  -> identify a real winning attraction, if one exists
  -> compare them in today's context
  -> assign marks
```

This sequence is conceptual, not a deterministic pipeline.

## 8. RRDB and other evidence

RRDB keeps its existing semantic role:

```text
visible past result
  -> reinterpret prior run
  -> revise horse understanding
  -> return to current race
  -> compare candidates
```

UPGRADE / DOWNGRADE / CONFIRM / NEUTRAL, Next-Watch grades, training, Trend,
pedigree, IDM, direct-condition history, and market information are evidence
lanes, not mark rules.

A single evidence lane must not determine ◎ or ○ by itself.

## 9. Reader-facing explanation

For a DIVERGE ◎, reader-facing prose should preferably make the winning
attraction understandable:

- not only why the horse may improve;
- but why that improvement matters enough to buy it over the safer rival today.

For ○, prose should make the reliability case understandable when relevant.

For CONVERGE, prose may naturally communicate that the horse has both a strong
buy case and little reason to oppose it.

Do not expose internal labels such as `ATTRACTION`, `STABILITY`, `DIVERGE`,
or `CONVERGE` on ordinary reader-facing surfaces unless explicitly requested.

## 10. Research discipline

BTDAY-0005 and BTDAY-0006 remain Frozen v0.3.3 evidence.

Do **not** retrospectively re-mark them under v0.3.4.

Use their results only as diagnosis supporting this refinement:

- role separation should remain;
- CONVERGE is worth continuing to observe;
- DIVERGE attraction should be tested for genuine winning ability rather than
  generic improvement alone.

The next untouched blind backtests should evaluate at minimum:

- ◎ win / place / show rates;
- ◎ win / place returns;
- ◎ final popularity / odds distribution;
- ○ performance;
- DIVERGE ◎ versus DIVERGE ○;
- CONVERGE performance;
- winner coverage within ◎○ and within all marks;
- ◎-marked-horse quinella returns;
- whether DIVERGE ◎ wins often enough to justify taking market / stability risk.

Promotion requires new blind evidence. Historical return optimization is not a
reason to rewrite prior Frozen forecasts.
