# RaceNote Forecast Human-Context Reader v0.3.3 Candidate

Status: **CANDIDATE — ATTRACTION / STABILITY ROLE SEPARATION**
Date: 2026-09-30
Base logic: `RaceNote-Human-Context-Reader-0.3.2`
Candidate logic id: `RaceNote-Human-Context-Reader-0.3.3-candidate`

## 1. Purpose

BTDAY-0003 / BTDAY-0004 diagnosis suggests that the current Reader can identify
many viable runners but may overuse direct-condition repeatability / recent
stability when deciding the final ◎.

This candidate does **not** introduce fixed weights, scores, thresholds, or a
deterministic ranking procedure.

The goal is to preserve flexible LLM judgment while giving ◎ and ○ clearer,
different jobs.

Human teacher evidence remains authoritative:

- ◎ is not the highest generic score by definition;
- ◎ is the horse the forecaster most wants to buy in this race;
- race context determines which evidence matters;
- concerns do not automatically veto ◎;
- there may be no obvious safe axis.

## 2. Role model

### ◎ — Attraction slot / 魅力枠

◎ answers:

> 今回、この馬を一番買いたい理由は何か。

The reason should be specific to **this race**, not merely that the horse is
generally strong or reliable.

Possible forms of attraction include, without forming a checklist:

- prior result understates the run and today's conditions make that strength usable;
- condition / distance / course / pace change creates a meaningful upside;
- the horse owns a race-specific winning path that rivals do not;
- current state or training makes this start more attractive than the visible form suggests;
- direct evidence is strong **and** there is little reason to oppose the horse today;
- another context-specific reason makes the horse more buyable than a nominally
  stronger or safer rival.

Do not require an outsider, price angle, RRDB UPGRADE, or novel condition change.
A favorite may be ◎ when it is still the most attractive horse in context.

### ○ — Stability slot / 安定枠

○ answers:

> 今回、地力・実績・再現性の面で最も信頼して走ってきそうな馬は何か。

Typical supporting evidence may include:

- proven class ability;
- repeated recent good performance;
- same-course / same-distance evidence;
- repeatable running style or race shape;
- fewer important uncertainties than rivals.

These are examples, not a fixed evidence hierarchy.

○ is not simply "second-best ◎".
It has a distinct role: the most convincing stability / reliability case among
the contenders.

## 3. When attraction and stability point to the same horse

Attraction and stability are separate questions. They may identify the same
horse.

When they do:

- that horse remains ◎;
- treat the case conceptually as a **堅軸型◎**;
- ○ is then assigned to the best remaining stability / comparison horse;
- preserve an internal note that both attraction and stability converged on ◎.

### 3.1 Counter / reversal handling under CONVERGE

When attraction and stability converge on ◎, audit fields that describe a
counterargument must **never point back to ◎ itself**.

In a CONVERGE case:

- `strongest_counter` must describe the strongest remaining rival or scenario
  that could defeat ◎;
- `reversal_condition` must describe a condition under which that remaining
  rival / scenario could reverse the forecast;
- the preferred source is normally ○, but another marked horse may be used when
  it is clearly the stronger counterargument;
- do not generate self-referential text such as "◎の安定材料が強く出れば◎を
  上回る" or any equivalent construction.

This is an audit-integrity rule only. It does not alter marks, re-rank horses,
or force ○ to be the strongest counter when another rival presents the more
meaningful race-specific threat.

Before Freeze, a CONVERGE record should pass the following semantic guard:

```text
counter horse != ◎
reversal target != ◎
```

If no single rival is the meaningful counter, use a race-shape / scenario
counterargument instead of inventing a horse-specific one.

This convergence may support a future confidence / axis-reliability parameter,
but v0.3.3-candidate does not define a numeric confidence value or threshold.

Do not force attraction and stability to different horses for the sake of role
separation.

## 4. Flexible reasoning, not a fixed procedure

This role separation is a thinking aid, not an algorithm.

Forbidden interpretations include:

- attraction score + stability score;
- fixed points for RRDB / Ability / Training / direct evidence;
- "if condition X then ◎";
- mandatory weighting ratios;
- mechanical selection of ○ from the highest IDM / best recent finish;
- mandatory preference for a longer-priced horse in the attraction slot.

The Reader should first understand the race and each runner as before in v0.3.2.

Before final marks, it should be able to explain, in concise auditable form:

- which horse presents the most compelling **buy case** today;
- which horse presents the most convincing **stability case** today;
- whether those judgments converge or diverge;
- when they diverge, why the attraction case is strong enough to justify ◎
  rather than simply defaulting to the safer horse.

No private chain-of-thought is required.

## 5. Relationship to betting intent

The intended mark structure is:

- ◎ = attraction / the horse most worth buying;
- ○ = stability / the most reliable major rival;
- ◎-○ therefore naturally covers the common case where the attractive horse
  runs well but the more stable horse proves stronger on the day.

This is a forecast-design principle, not a guarantee of betting profitability.

The target is not to optimize historical BTDAY-0003 / BTDAY-0004 returns after
results are known. Those days remain diagnosis evidence only.

## 6. Interaction with RRDB

RRDB retains the v0.3.2 role:

```text
visible past result
  -> RRDB reinterpretation
  -> revised understanding of that horse
  -> current-race comparison
```

RRDB may contribute to attraction or stability, but:

- UPGRADE / S / A never automatically means ◎;
- CONFIRM never automatically means ○;
- DOWNGRADE does not automatically exclude either mark;
- the relevant question is what the reinterpreted run means **today**.

## 7. Reader-facing explanation

For ◎, reader-facing prose should communicate the race-specific attraction:
why this horse is the one to buy today.

For ○, when comparison is discussed, prose should communicate why it is the
stable / reliable counterweight rather than merely "the next-ranked horse".

When ◎ is also the stability choice, prose may naturally describe it as having
both a strong upside / buy case and little reason to oppose it. Do not print
internal labels such as "魅力枠" or "安定枠" unless the output surface explicitly
calls for research/audit terminology.

## 8. Research discipline

BTDAY-0003 and BTDAY-0004 must not be re-marked to show hypothetical gains.

Use them to diagnose the role-confusion problem only.

The next untouched blind day should test whether this role separation improves,
among other metrics:

- ◎ win / place / show rates;
- ◎ win / place returns;
- ◎-marked-horse quinella returns;
- ○ performance;
- winner coverage within ◎○ and within the full marked cluster;
- whether attraction/stability convergence behaves like a stronger axis without
  becoming a mechanical favorite-selection rule.

Promotion to CURRENT logic requires new blind evidence, not retrospective
re-labeling.
