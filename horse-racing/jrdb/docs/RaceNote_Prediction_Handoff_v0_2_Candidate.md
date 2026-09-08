# RaceNote Prediction Handoff v0.2 Candidate

## 1. Status

**CANDIDATE / NOT PRODUCTION / MUST BE PROSPECTIVELY BLIND-TESTED AGAINST v0.1**

This document defines a candidate GPT prediction procedure for RaceNote.

It does **not** replace `RaceNote_Prediction_Handoff_v0_1.md`.

The existing `provisional_handoff_v0.1_unweighted` remains the control model until a preregistered blind comparison supports promotion.

Core design change:

```text
v0.1 tendency:
ability / JRDB consensus upper horses
  -> qualitative reordering
  -> ◎○▲△

v0.2 candidate:
ability threshold / contender extraction
  -> course-frame-running-style fit
  -> projected pace / position fit
  -> distance suitability by comparable time evidence
  -> state / training adjustment
  -> uncertainty and contradictory-evidence control
  -> ◎○▲△
  -> separate value/disagreement flag for betting layer
```

The objective is not to force longshots into the marks. The objective is to identify **which sufficiently capable horse is best suited to this particular race** and to explain that judgment in a user-facing short comment.

## 2. Design principles

### 2.1 Ability is a gate, not the final answer

Use the following to identify realistic contenders:

- IDM
- total_index
- recent-run IDM / performance level
- JRDB class / ratings
- class and recent performance evidence
- training / condition as current-state evidence

Do not mechanically make the highest-index horse ◎.

The question after contender extraction is:

> Among horses with enough ability to win/place at this level, which horse has the best **today-specific fit**?

### 2.2 Suitability is the primary differentiator

Suitability is evaluated in this order:

1. course / layout context;
2. frame × running style interaction;
3. projected race shape / pace;
4. projected position and running-style advantage/disadvantage;
5. distance suitability from comparable historical evidence;
6. surface / going suitability;
7. state / training;
8. supplementary sire / jockey / statistical context;
9. uncertainty / missing evidence.

No single suitability signal is absolute. Contradictions must remain visible in the final judgment.

## 3. Race-level context first

Before ranking horses, read and summarize:

- venue
- surface
- distance
- turn / course_layout
- class / grade
- field size
- race conditions
- race trends
- frame trends
- projected pace / pace symbol
- distribution of running styles / likely leaders

Create a short internal race-shape hypothesis before evaluating the horses.

Examples of acceptable hypotheses:

- likely steady pace; front / forward-position horses have an advantage;
- multiple pace horses may create pressure; late-running horses can benefit if they retain position;
- outer-draw front runners face extra positional cost;
- inner-draw closers may be boxed unless projected position improves;
- course geometry makes sustained speed more important than one short closing burst.

Do not rely on generic course folklore when RaceNote evidence does not support it.

## 4. Horse-level evaluation layers

### 4.1 Ability layer

Assess whether the horse belongs in the contender set.

Primary evidence:

- IDM
- total_index
- recent detailed IDM / performance indices
- class-level evidence
- recent finishing performance, interpreted with context

Output internally as one of:

- `ability_core`
- `ability_competitive`
- `ability_borderline`
- `ability_unproven`

These are qualitative labels, not numeric probabilities.

### 4.2 Course / frame / running-style fit

Evaluate the interaction, not each factor separately.

Read:

- race `race_trends.frame`
- horse frame / draw where available
- `ability.running_style`
- start / front / position-related indices
- forecast positions
- recent corner positions

Questions:

1. Is the draw helpful for the horse's normal style?
2. Does the course/layout reward or punish the likely position?
3. Is there a realistic path to the preferred position after the start?
4. Does the field's style distribution increase congestion or pace pressure?

A strong index horse can be downgraded if its expected trip is structurally unfavorable.

### 4.3 Projected pace / position fit

Use RaceNote pace information explicitly:

- forecast_pace
- front / pace / late / position indices and ranks
- forecast_positions
- pace symbol
- start_index / late_break_rate where relevant
- recent corner-position evidence

Assess:

- expected early position;
- whether the horse must spend extra energy to obtain it;
- whether the predicted pace helps or hurts its style;
- whether a deep closer risks being too far back even if the pace is theoretically favorable;
- whether a front runner is likely to get uncontested or contested control.

### 4.4 Distance suitability by comparable-time evidence

This is a major change from v0.1 usage.

Read:

- `ability.distance_fit`
- `historical_profile.same_distance`
- `historical_profile.distance_ranges`
- `recent_runs` distance / time / first-last 3F / corner positions / carried weight / condition
- older-run distance evidence when needed

Decision sequence:

#### A. Same-distance comparable evidence exists

Compare same-distance or materially equivalent performances.

Use raw time only when comparison is meaningful. Consider race level, track/surface/condition, carried weight, pace/position, and finishing sectionals when available.

Do not treat a faster raw time from a materially easier/faster context as automatically superior.

#### B. No same-distance evidence

Expand to **nearby / analogous distances**.

Use the nearest available distance evidence that is still reasonably informative for the target test.

Record internally that the evidence is approximate.

#### C. No useful nearby-distance evidence

Do not convert `same_distance.starts = 0` into neutral suitability.

Set:

- `distance_evidence = insufficient`
- distance uncertainty increases;
- inspect `distance_fit`, sire distance-range evidence, running style and sustained-speed evidence as secondary support only.

#### D. Explicit contradiction

If `distance_fit` indicates a materially shorter/longer aptitude than the target and there is no successful comparable-distance proof, retain an explicit distance-risk flag.

Example class of failure to avoid:

> elite overall indices + no 2400m proof + `distance_fit = mile`
> must not silently become distance-neutral merely because `same_distance.starts = 0`.

### 4.5 Surface / going fit

Read:

- surface_fit
- heavy_track_fit
- same_surface history
- recent runs under similar going where available

Use only when target conditions make it relevant.

### 4.6 Training / current condition

Read:

- training_index / training_arrow
- main_workout
- workout clock indices
- one-week-ago work
- condition_index / volume_grade
- improvement
- stable_evaluation
- rotation interval / rest reason

Use this as an adjustment to an already-grounded ability/suitability view.

Do not let one positive workout erase a major ability or suitability deficit.

### 4.7 Supplementary statistics and pedigree

Use as secondary evidence only:

- sire statistics and target-relevant distance ranges
- jockey statistics
- frame trends
- exact-condition stats

Pedigree is especially useful when direct distance evidence is sparse.

It may soften or strengthen an uncertainty judgment, but must not become a standalone reason to force a horse into the top marks.

### 4.8 Prior-market disagreement as a value clue

Target-race live/final popularity remains prohibited before freeze.

Past-race popularity / odds contained in as-of-safe history may be used diagnostically.

Potential value clues include:

- previous low popularity despite competitive IDM / performance content;
- previous high popularity followed by a context-explainable failure;
- repeated mismatch between market rank and underlying performance evidence.

This is **not** a main prediction factor.

It is used mainly to nominate a separate `value/disagreement` candidate after the prediction ranking is formed.

## 5. Ranking discipline

### 5.1 Marks remain prediction marks

Assign:

- ◎ = horse judged most likely to win under today's conditions;
- ○ = strongest alternative / highest rival to ◎;
- ▲ = third prediction rank, not a mandatory longshot;
- △1 / △2 = next prediction ranks / complementary contenders.

Do not force a market-disfavored horse into ▲ solely to improve theoretical payout.

### 5.2 Ability and suitability must both be stated for ◎

◎ should normally satisfy:

1. sufficient ability evidence;
2. no unresolved major suitability contradiction, or a clearly explained reason to accept it;
3. a plausible trip under the projected race shape;
4. acceptable distance evidence or an explicitly acknowledged uncertainty.

If the highest-ability horse fails 2-4, a lower raw-ability horse may be promoted.

### 5.3 Contradictory-evidence handling

For every serious ◎ candidate, identify at least one possible failure condition.

Examples:

- distance extension without proof;
- poor frame/style interaction;
- pace pressure;
- projected position too deep;
- weak comparable-time evidence;
- current-state concern;
- small history sample.

Do not hide the concern merely because the horse remains ◎.

## 6. Separate value/disagreement flag

After marks are fixed, optionally assign **one** separate value flag:

- `☆ value/disagreement`

The horse may be ○, ▲, △1 or △2. It does not have to be ▲.

Selection logic is qualitative and preregistered:

1. horse remains genuinely competitive on ability/suitability;
2. there is evidence of market-vs-performance disagreement in available **pre-target** information;
3. at least one race-specific support factor exists (pace, frame/style, distance evidence, condition, pedigree support, etc.);
4. do not select a horse merely because it appears unpopular;
5. if no horse satisfies the conditions, output no ☆.

No fixed odds/popularity threshold is introduced in this candidate version.

## 7. Confidence

A/B/C remains **evidence confidence**, not hit probability.

Suggested interpretation:

- A: major evidence layers broadly agree; little unresolved uncertainty;
- B: reasonable top choice but one or more meaningful risks / close alternatives exist;
- C: sparse/contradictory evidence, new conditions, weak separation, or trip uncertainty.

Do not assign A simply because multiple JRDB indices point to the same horse if suitability evidence is uncertain.

## 8. User-facing short-comment contract

The user ultimately places the wager, so the output must expose the judgment rather than only the ranking.

Default candidate format:

```text
◎ 6 Horse A
○ 5 Horse B
▲ 13 Horse C
△ 15 Horse D
△ 11 Horse E
☆ 15 Horse D   # only when a value/disagreement candidate exists

展開:
<1-2 sentences: expected pace, positional advantage/disadvantage>

◎短評:
<ability + today-specific suitability + one risk>

○短評:
<why this horse can reverse ◎ / principal strength>

▲短評:
<why third; if value-like, say why without calling it a longshot merely from popularity>

△・☆:
<one concise sentence for complementary or value reason>

買う上での注意:
<largest unresolved uncertainty, especially distance / pace / trip>

自信度: A/B/C
```

### 8.1 Required content in ◎短評

At least two of the following must be concrete:

- course/frame/style fit;
- projected pace/position;
- comparable-distance/time evidence;
- condition/training;
- ability edge.

And at least one meaningful risk must be stated when present.

### 8.2 Avoid empty generic comments

Avoid comments such as:

- `能力上位で本命`
- `展開が向きそう`
- `血統的に面白い`

unless followed by specific RaceNote-supported evidence explaining why.

## 9. Separation from betting layer

Prediction marks are not rewritten to optimize tickets.

Betting-layer experiments remain separate.

Current prospective candidates:

### Quinella baseline

- ◎-○
- ◎-▲

### Trio Policy A — control

- ◎ axis to ○ / ▲ / △1 / △2 = 6 tickets

### Trio Policy B — candidate

- `◎ -> ○▲ -> ○▲△1△2` = 5 tickets
- equivalently remove only `◎△1△2`

### Optional value-ticket diagnostic

A future preregistered test may compare a ticket using `☆ value/disagreement` against the fixed baseline.

Do not backfit a target-market-rank threshold from the existing 219R and call it v0.2.

## 10. Blind validation protocol

For every new untouched target block:

1. select target date/venues from JRDB retained Raw / BAC-derived metadata only;
2. acquire RaceNote with `as_of_exclusive = target_date`;
3. validate Reader View round-trip;
4. generate and freeze **v0.1 control marks**;
5. independently generate and freeze **v0.2 candidate marks + optional ☆ + short comments**;
6. freeze betting policies before HJC;
7. only then acquire HJC / target result;
8. settle both prediction versions and both trio policies;
9. compare prediction quality separately from betting economics.

No target result, final target odds/popularity, Web result, or post-target history may be read before both prediction versions are frozen.

## 11. Evaluation metrics

Do not judge v0.2 only by total return.

Prediction metrics:

- ◎ win capture
- ◎ top2 / top3 capture
- top-5 mark coverage of winner / top2 / top3
- ○ vs ▲ top2 capture
- axis-correct / opponent-miss rate
- distance-risk flag outcomes
- pace/style-fit promoted vs downgraded horse outcomes
- mark changes from v0.1 and whether changed races improve

Betting metrics:

- quinella ◎-○ / ◎-▲ contribution
- trio Policy A vs B
- value/disagreement candidate contribution
- payout concentration / tail dependence
- block stability

Comment-quality audit:

- concrete race-specific evidence present;
- risk explicitly stated when material;
- no unsupported generic claim;
- user can understand why the horse is buyable or avoidable.

## 12. Promotion rule

This candidate must not replace v0.1 based on the existing 219R because those races informed its design.

Promotion requires new untouched blind samples.

At minimum, assess:

- whether v0.2 changes marks often enough to matter;
- whether changed marks improve axis capture rather than merely shifting payouts;
- whether distance / pace / frame-style judgments show repeatable value across independent blocks;
- whether the user-facing short comments remain consistent and evidence-grounded.

Until then:

```text
v0.1 = control
v0.2 = candidate
```
