# RaceNote Forecast Human-Context Reader v0.4.2 Candidate

Status: **CANDIDATE — MAINLINE + SINGLE-SHOT FIVE-MARK FORECAST**
Date: 2026-10-01
Research basis: BTDAY-0003 through BTDAY-0016 (BTDAY-0016 福島2R excluded from comparative research because of pre-Freeze market-field exposure)
Candidate logic id: `RaceNote-Human-Context-Reader-0.4.2-candidate`

## 1. Purpose

v0.4.2 keeps the v0.4.1 forecast structure intact.

It is not an additive rule patch. The only intended change is a wording-level
clarification of what the independent single-shot / ▲ role is trying to find.

BTDAY-0011 / BTDAY-0012 motivated the v0.4.1 structure:

1. ◎ often represented a strong placing case without clearly distinguishing
   evidence for "runs well" from evidence for "can win";
2. ▲ was frequently produced as an ordinary third-ranked candidate with a
   single-shot explanation attached afterward.

BTDAY-0013 through BTDAY-0016 then showed that the independent ▲ search can
surface two useful forms of asymmetric value: a horse capable of overturning
the main line, and a horse capable of intruding into the main-line finish and
lifting quinella / trio / trifecta value.

v0.4.2 does not change the selection shape or add rules. It only makes that
broader single-shot intent explicit.

The forecast is built from two complementary views:

- **mainline view** — horses that deserve ordinary serious support;
- **single-shot view** — a horse with a credible race-specific route to create
  asymmetric betting value around the main line, including by overturning it
  or by intruding into its finish.

The final five marks remain ◎ ○ ▲ △1 △2.

## 2. Core forecasting principle

Read the race before assigning marks.

Ability, recent race content, condition fit, pace / position, training,
direct-condition history, Trend, pedigree, RRDB reinterpretation, opponent
strength, and other available evidence are integrated flexibly.

There is no universal weighting and no aggregate score.

Do not select marks by:

- sorting one numeric field;
- summing evidence into a hidden total score;
- mapping an RRDB / Next-Watch / training / pedigree label directly to a mark;
- reconstructing current popularity or odds;
- filling a mark because a template requires a horse of a particular type.

The question is always what the evidence means **in this race**.

## 3. RRDB

RRDB remains an interpretation layer:

```text
visible prior result
  -> inspect the current RRDB recommendation signals and measured strength
  -> reinterpret what the run actually showed
  -> revise understanding of the horse
  -> return to today's race
  -> compare with today's rivals
```

The current RRDB recommendation contract is
`rrdb-recommendation-signals-v0.2`.

Current recommendation evidence may include:

- `TIME_CLASS_PLUS1` — the prior run reached an upper-class time level;
- `FRONT_SURVIVE_GAP05` — the horse survived a strongly forward-pressing race near the front;
- `REAR_HIGH_LAST3F90` — the horse produced a high-end late section against a rear-unfriendly pace shape;
- `HV01` / `HV02` — the adjusted time content was stronger than the visible finishing position suggests.

Read the signal together with its measured strength and source-run context.
Signal IDs are evidence labels, not marks.

There is no S/A recommendation grade in current operation.
Do not reconstruct one from signal count or apparent strength.

Multiple RRDB signals from the same prior run are not additive votes.
They are different descriptions of one historical performance and should be
integrated as one evidence story.

A RRDB match is not automatically positive for today's race.
Ask whether the prior-run evidence transfers to today's class, course, distance,
pace shape, condition, and opposition.

`NO_MATCH` is neutral, not negative.

Use the reinterpreted run only when it changes how the horse should be understood
under today's conditions.

## 4. Build the forecast from two views

### 4.1 Mainline view

From the full field, identify the horses the Reader would normally want to keep
as serious betting contenders.

The mainline view is about robust race relevance, not popularity.

A horse may belong because of ability, repeatability, suitability, current
condition, race shape, hidden prior strength, or another convincing
race-specific case.

From this view, establish the ordinary core of the forecast.

### 4.2 Single-shot view

Independently scan the full field for the best **single-shot / 単穴** case.

Ask:

> 通常の本線評価とは別に、今回の条件が噛み合ったとき、◎○を脅かす、または
> ◎○と共存して2・3着へ割って入ることで、馬券の見返りを大きくできるだけの
> 具体的な魅力を持つ馬はいるか。

This is not a search for a low-popularity horse. Current market information is
not available.

A valid single-shot case needs a concrete reason that can produce a materially
better result **today** and make the horse materially relevant to the betting
shape, for example:

- race shape strongly activating one horse's weapon;
- a meaningful condition change;
- hidden prior-run strength that transfers directly;
- an ability ceiling obscured by visible recent results;
- current preparation / position / opponent context creating unusual upside.

Volatility, novelty, or "interesting" status alone is not enough.

The single-shot search is performed across the full field, not only after a
five-horse set has already been fixed.

If the best single-shot horse was already in the provisional mainline group,
that horse may become ▲ and the vacated normal-support slot is filled by the
next strongest ordinary contender.

If no genuinely distinct single-shot case exists, ▲ may come from the mainline
group as the horse with the clearest reversal case. Do not invent a weak
outsider merely to make ▲ look adventurous.

## 5. Mark meanings

### ◎ — Main

◎ is:

> **今回、自分なら最も買いたい主役。**

When comparing serious mainline candidates, distinguish two kinds of positive
evidence:

- evidence that mainly says **this horse should run well / remain in contention**;
- evidence that supports **this horse reaching first place in today's race**.

◎ should be the horse whose overall case is most persuasive **with enough
evidence pointing through to winning, not only to safe placement**.

This is a comparative judgment, not a checklist.

Do not require a formal "winning-path sentence".
Do not require one named winning factor.
Do not convert the distinction into points or thresholds.

A reliable horse may be ◎ when its evidence genuinely supports winning.
A less stable horse may be ◎ when its race-specific case makes victory more
convincing.

### ○ — Principal opponent

○ is:

> **◎以外で、本線として最も強く相手評価する馬。**

○ has no mandatory "stability" identity.

It may be safer than ◎, more accomplished than ◎, or simply the next strongest
ordinary case.

### ▲ — Single-shot / 単穴

▲ is:

> **通常の本線比較とは別に、今回の条件が噛み合ったときに本線へ割って入り、馬券の見返りを大きくし得る魅力を買いたい馬。**

▲ is selected through the independent single-shot view described above.

▲ may beat ◎○ outright. That is a valid single-shot outcome when the horse's
race-specific upside genuinely warrants it.

▲ may also finish behind ◎ or ○ while still doing exactly what the role is
for: intruding into the top two or three and materially improving the payout
shape of quinella / exacta / trio / trifecta tickets built around ◎.

▲ is not "rank 3" and is not required to have the third-highest placing
probability.

It may have lower ordinary reliability than △1 or △2.

Do not turn this clarification into a popularity rule, minimum-odds rule,
required finishing position, or payout threshold. Market information remains
post-Freeze only.

### △1 / △2 — Supporting contenders

△1 and △2 are the remaining ordinary support candidates.

They are not special-purpose marks.

Between the two, △1 is the Reader's stronger ordinary supporting preference and
△2 the next.

## 6. Final composition

The five marks represent **four ordinary serious contenders plus one explicit
single-shot view**, while allowing overlap during reasoning.

Conceptually:

```text
read the whole race
  -> form the ordinary mainline contenders
  -> compare them for ◎ / ○ / supporting roles
  -> independently scan the whole field for the best single-shot case
  -> assign ▲
  -> complete △1 / △2 from the ordinary contenders
  -> Freeze
```

This is a reasoning shape, not a deterministic ranking algorithm.

The final set must contain five unique horses.

## 7. What the marks do not mean

The marks are not five calibrated probabilities.

In particular:

- ▲ may be less likely than △1 or △2 to finish in the top three;
- ▲ does not have to beat ◎ to succeed as a single-shot case;
- ▲ beating ◎ is not a failure when the underlying asymmetric case was real;
- ○ does not have to be the safest horse;
- ◎ does not have to be the horse with the highest generic ability value;
- ▲ does not have to be an outsider;
- △2 is not an automatic longshot slot.

The structure intentionally preserves both a main line and one asymmetric
upside view for quinella / trio / trifecta use.

## 8. Market-blind boundary

Current odds, current popularity, favorite / outsider status, and equivalent
market signals remain outside the Forecast Reader input.

Do not infer them from IDM, jockey, recent finishes, name recognition, or other
proxies.

Market comparison is post-Freeze evaluation only.

## 9. Reader-facing explanation

Reader-facing prose is governed by:

`horse-racing/jrdb/docs/racenote/FORECAST_READER_FACING_PROSE_v0_1.md`

The forecasting logic decides the marks. The prose contract decides how those
Frozen decisions are explained to the reader.

Do not derive reader-facing text by filling mark-role templates.

Do not copy structured audit fields directly into `reader_facing_reason`.

Reader-facing comments should be regenerated from the underlying race evidence
and the Frozen decision in natural racing language.
## 10. Minimal audit trace

Keep only concise audit material needed to inspect the decision:

- `race_model` — what matters in this race;
- `mainline_cases` — ordinary serious contenders and their decisive evidence;
- `single_shot_case` — the independent ▲ candidate and why the case is
  genuinely different;
- `mark_reason` — concise race-specific reasons for the five final marks;
- `rrdb_evidence` — material reinterpretation when relevant;
- result-leakage / market-blind guards;
- prediction hash / Freeze integrity.

Do not require:

- ATTRACTION / STABILITY;
- CONVERGE / DIVERGE;
- strongest_counter;
- reversal_condition;
- a mandatory "how ◎ beats ○" narrative;
- a mandatory sentence proving ◎ can win.

Legacy schema fields may remain null for compatibility but must not influence the
decision.

## 11. Research questions

BTDAY-0003 through BTDAY-0012 remain Frozen under their original logic versions.

Do not retrospectively re-mark them.

The next blind evidence should test:

- ◎ win / top2 / top3 performance;
- whether ◎ reduces "strong but second-place" selections without collapsing
  into generic safe favorites;
- five-horse winner and podium coverage;
- ○ / △ support quality;
- ▲ win / top3 performance as secondary descriptive context;
- final popularity of ▲ only after Freeze;
- ◎-○ versus ◎-▲ quinella / exacta hit rate, payout, and ROI;
- how often ▲ contributes to ◎-anchored trio / trifecta hits and payouts;
- how much of the ◎-anchored multi-race payout is produced by tickets that
  include ▲;
- whether ▲ captures valuable runners that ordinary mainline selection would
  otherwise omit;
- whether reader-facing explanations become race-specific rather than templated.

For exotic bets, a small number of large legitimate hits is part of the target
distribution. Largest-payout removal may be shown as a concentration diagnostic
but is not a primary quality criterion.

## 12. Summary

```text
whole-race reading
  -> ordinary serious contenders
      -> ◎ main: strongest buy case with evidence that reaches through to winning
      -> ○ principal opponent
      -> △ support
  -> independent whole-field single-shot search
      -> ▲: asymmetric race-specific value around the main line
  -> five unique marks
  -> natural race-specific explanation
  -> Freeze
```

No fixed score.
No fixed weight.
No market input.
No automatic favorite.
No automatic outsider.
No role-playing between ◎ and ○.
No post-hoc rank-3-to-▲ conversion.
No mandatory winning-path prose.
