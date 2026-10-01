# RaceNote Forecast Human-Context Reader v0.4.0 Candidate

Status: **CANDIDATE — CONSOLIDATED FIVE-MARK FORECAST**
Date: 2026-10-01
Base evidence: v0.3.1–v0.3.5 blind research and human forecast evidence
Candidate logic id: `RaceNote-Human-Context-Reader-0.4.0-candidate`

## 1. Purpose

v0.4.0 is a consolidation, not another additive patch.

The v0.3.x series was useful for research, but successive experiments added
special roles, counter-rules, guards, and exceptions around ◎ / ○. The result
was increasingly difficult to read as one coherent forecasting philosophy.

v0.4.0 keeps the parts that remained useful across the blind generations and
removes research scaffolding that began to shape the forecast itself.

The retained core is:

- read the race before mechanically ranking horses;
- integrate evidence flexibly rather than with fixed scores or weights;
- use RRDB to reinterpret past runs, then return to today's race;
- form a serious five-horse candidate set;
- give the five marks distinct but simple betting meanings;
- keep current market information outside the Forecast Reader input boundary.

The five marks are:

- ◎ = main buy / main winning case;
- ○ = principal opponent;
- ▲ = single-shot reversal / upside opponent;
- △1 = supporting contender;
- △2 = supporting contender.

The aim is not to force a favorite, an outsider, a stable horse, or a high-upside
horse into any mark. The marks should express the Reader's race judgment.

## 2. Human forecast anchor

The human forecast evidence remains the style anchor.

Preserve these principles:

1. race-level context comes first;
2. evidence importance can change from race to race;
3. ◎ is not defined by a generic numeric rank;
4. a concern does not automatically veto a horse;
5. recent form must be interpreted in context;
6. a race may have no obvious safe axis;
7. historical examples are evidence of style, not deterministic templates.

The central ◎ question is:

> 今回、自分なら最も買いたい馬はどれか。

For v0.4.0, "most want to buy" must include **credible winning reality**.

A horse is not ◎ merely because it is interesting, improving, unusual, or has
one positive angle. The Reader should be able to believe that the horse can
actually win this race.

At the same time, ◎ is not redefined as "the mathematically highest win
probability horse". Human comparative judgment remains broader than that.

## 3. Race reading

Before fixing marks, understand the race as a race.

Consider whichever supplied evidence is materially relevant, including:

- ability / class;
- recent race content;
- course / distance / surface suitability;
- pace and likely position;
- current condition and training;
- direct-condition history;
- Trend;
- pedigree where informative;
- RRDB reinterpretation;
- opponent strength;
- other evidence explicitly available in the active RaceNote input.

No universal evidence hierarchy is imposed.

Do not:

- sum visible fields into an implicit total score;
- sort by a single numeric field and explain the order afterward;
- use one RRDB / Next-Watch / training / pedigree label as an automatic mark;
- manufacture a fixed checklist whose completion determines the marks.

Numbers may inform judgment. They do not replace it.

## 4. RRDB

RRDB is an interpretation layer.

Use the following conceptual flow:

```text
visible prior result
  -> reinterpret what the run actually showed
  -> revise understanding of the horse
  -> return to today's race
  -> compare with today's rivals
```

UPGRADE / DOWNGRADE / CONFIRM / NEUTRAL and Next-Watch grades are not mark
instructions.

A materially reinterpreted past run matters only insofar as it changes the
horse's meaning in today's race.

Do not count the same prior run twice merely because the same story appears in
multiple evidence lanes.

## 5. Form the five-horse candidate set

Before assigning the final five marks, identify the horses that genuinely
deserve serious inclusion in the betting picture.

Normally produce five candidates.

The candidate set should contain horses that the Reader can plausibly imagine
playing a material role in the race through some combination of:

- winning ability;
- strong placing ability;
- race-specific fit;
- hidden prior strength;
- favorable setup;
- meaningful upside;
- another concrete race-specific case.

The candidate set is not simply "the five safest horses".

It should preserve genuinely different ways the race can be run when the
evidence supports them.

This is especially important for exotic betting: a lower-certainty horse may
deserve inclusion if it owns a meaningful race-specific route to a major
performance.

Do not include a horse merely for variety.

## 6. Mark meanings

### ◎ — Main

◎ is:

> **今回、自分なら最も買いたい馬。勝ち切る現実性を伴う主役。**

The Reader should prefer the horse whose complete case is most compelling in
this race after considering both strengths and weaknesses.

◎ may be:

- the strongest horse;
- the best-suited horse;
- a horse whose visible form understates its ability;
- a horse whose current setup creates a strong winning opportunity;
- or another race-specific main case.

No specific type is required.

### ○ — Principal opponent

○ is:

> **◎以外で最も強く相手評価する馬。**

○ is the normal principal opponent, not a dedicated "stability slot".

Its strength may come from ability, consistency, suitability, race shape,
hidden strength, or another reason.

○ does not need to be chosen for a different kind of reason from ◎.

### ▲ — Single-shot / 単穴

▲ is:

> **◎・○を一発で逆転し得る、今回固有の強い買い材料を持つ馬。**

▲ is deliberately not defined as "third-highest placing probability".

It is the mark for a horse whose case may contain more uncertainty than the
main line but whose upside / reversal possibility is important enough that the
Reader does not want to treat it as an ordinary supporting mark.

This is the forecast's explicit **一発枠**.

Examples may include, without becoming rules:

- a race shape that could strongly activate one horse's weapon;
- a condition change with meaningful upside;
- hidden prior-run strength that could surface today;
- an ability ceiling not fully represented by visible recent results;
- a preparation / positional / class-context change that creates a genuine
  reversal case.

▲ is not an "outsider slot".

The Reader has no current market input and must not infer popularity in order to
fill ▲.

A horse should not receive ▲ merely because it is volatile or interesting.

### △1 / △2 — Supporting contenders

△1 and △2 are:

> **5頭候補の中で残したい通常の相手候補。**

They complete the candidate set after ◎ / ○ / ▲.

Unlike ▲, they do not need an explicit single-shot reversal identity.

Their order should reflect the Reader's ordinary comparative preference between
the two remaining contenders.

Do not invent a special role for △1 or △2.

## 7. Relationship among the marks

The marks are **not** one pure probability ranking.

In particular:

- ◎ is the main buy with credible winning reality;
- ○ is the main conventional opponent;
- ▲ is intentionally allowed to be a lower-certainty but higher-upside reversal
  candidate;
- △1 / △2 are the remaining supporting contenders.

Therefore:

- ▲ does not have to be more likely than △1 to finish in the top three;
- △1 may be the safer horse while ▲ is the more dangerous upset candidate;
- the order ◎○▲△1△2 should not be interpreted as five calibrated probabilities.

This is intentional.

The mark structure supports multiple betting views without changing the
forecast:

- ◎–○ / ◎–▲ as the main quinella ideas;
- ◎–○▲△1△2 as a wider quinella spread;
- ◎-anchored trio / trifecta structures;
- five-horse trio box;
- other downstream betting research.

Betting profitability is evaluated after Freeze. It must not rewrite the
forecast.

## 8. Market-blind input boundary

Current market information is not available to the Forecast Reader.

During DAY PREP / Forecast, do not request, infer, reconstruct, or use:

- current win odds;
- current popularity rank;
- market-implied probability;
- favorite / outsider status;
- equivalent current-market information.

Do not use visible race evidence as a proxy to guess who is likely to be
favorite.

The Reader should make an independent race judgment.

Final popularity / odds may be used after Freeze for research and evaluation.
They must not flow backward into the prediction.

## 9. Reader-facing explanation

Reader-facing text should sound like a race forecast.

For ◎, explain naturally why this is the main horse to buy today.

For ○, explain the strongest case for the principal opponent when comparison is
useful.

For ▲, make the specific reversal / upside angle understandable when it matters.

For △ horses, concise supporting reasons are sufficient.

Avoid:

- lists of raw numbers followed by "therefore this is the pick";
- compliance language such as "DAY PREP materials imply...";
- repeating internal research labels as the explanation;
- mandatory sentence templates;
- inventing a scenario merely to justify a mark already chosen.

A good explanation should not be reusable unchanged for most other races.

## 10. Minimal audit trace

v0.4.0 deliberately reduces research scaffolding.

Preserve concise, auditable summaries for:

- `race_model`: what matters most in this race;
- `candidate_cases`: why the five candidates remain live;
- `mark_reason`: why ◎ / ○ / ▲ / △1 / △2 received their roles;
- `rrdb_evidence`: material reinterpretation when relevant;
- result-leakage guard state;
- prediction hash / Freeze integrity.

Do not require forecast reasoning fields whose main effect is to manufacture
counterarguments or prove rule compliance.

In particular, v0.4.0 does not require the Reader to reason in terms of:

- ATTRACTION vs STABILITY;
- CONVERGE vs DIVERGE;
- strongest_counter;
- reversal_condition.

Legacy schema fields may remain for compatibility during migration, but they are
not part of the v0.4.0 decision contract and must not shape the marks.

## 11. Research interpretation

BTDAY-0003 through BTDAY-0010 remain Frozen evidence under their original logic
versions.

Do not retrospectively re-mark them.

The v0.3.x evidence suggests several useful research questions for v0.4.0:

- can the five-horse set retain strong winner / podium coverage?
- can ◎ retain credible winning performance without collapsing into a generic
  safest-horse choice?
- does ▲ contribute disproportionally to high-return quinella / trio / trifecta
  hits, consistent with its single-shot role?
- do △1 / △2 continue to provide useful supporting coverage?
- does reader-facing prose regain race-specific variety after removing the
  accumulated v0.3.x compliance rules?

For exotic bets, high-return hits are part of the intended distribution.

Do not treat "remove the largest payout and recompute ROI" as a primary quality
criterion for trio / trifecta strategies. Such a calculation may be used only as
a descriptive concentration diagnostic, not as evidence that a legitimate
high-payout hit should be discounted.

## 12. Summary

v0.4.0 is intentionally compact.

```text
read the race
  -> reinterpret relevant past evidence
  -> form five serious candidates
  -> ◎ main buy with credible winning reality
  -> ○ principal opponent
  -> ▲ single-shot reversal / upside opponent
  -> △1 / △2 supporting contenders
  -> explain the race naturally
  -> Freeze
```

No fixed score.
No fixed weight.
No market input.
No mandatory favorite.
No mandatory outsider.
No forced role separation between ◎ and ○.
No CONVERGE / DIVERGE decision machinery.

The goal is a coherent human-style five-mark forecast rather than a stack of
rules correcting previous rules.
