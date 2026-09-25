# RaceNote Gen0.3 72-race semantic evidence loss analysis

Date: 2026-09-26
Sample:
- 2026-07-25: 36 races
- 2026-07-26: 36 races
Total: 72 races

Forecast profile:
`DayRehearsal-v0.1`

## 1. Goal

This analysis asks a narrower question than overall forecast accuracy:

`Why does the current system often place the eventual winner inside the candidate cluster, but fail to select that horse as ◎?`

The focus is the information lost when DayRehearsal-v0.1 compresses evidence into coarse ordinal states:

```text
Data Trend state
→ RaceReview state
→ Ability lexicographic tie-break
```

No ranking rule is changed in this document.

## 2. Candidate cluster versus axis

Across 72 races:

- ◎ wins: 11 / 72
- actual winner in forecast top3: 31 / 72
- actual winner in forecast top5: 45 / 72

There were therefore 34 races in which:
- ◎ did not win;
- but the eventual winner was already forecast in ranks 2-5.

These 34 races are the highest-value sample for understanding:
`candidate cluster → single axis`

### Direct Pairwise comparison already existed

Among these 34 races:

- 29 races had a direct Pairwise comparison between ◎ and the eventual winner.
- only 5 did not.

The decisive lane for those 29 direct comparisons was:

- DATA_TREND: 12
- RACEREVIEW: 9
- ABILITY_ANCHOR: 6
- UNCERTAINTY: 2

This means the dominant failure mode was not failure to discover the winner.

In most useful-cluster misses, the system had already compared the eventual winner directly against ◎ and selected the wrong side.

The main research target is therefore Pairwise semantic interpretation.

## 3. Coarse Data Trend state is useful, but too dominant

Among the 61 races where ◎ did not win:

Axis Data Trend state:
- SUPPORTIVE: 49
- NEUTRAL_OR_UNKNOWN: 10
- MIXED: 2

Winner Data Trend state:
- SUPPORTIVE: 17
- MIXED: 14
- NEUTRAL_OR_UNKNOWN: 25
- OPPOSED: 5

There were 32 misses where:
- ◎ was SUPPORTIVE;
- the eventual winner was not SUPPORTIVE.

In 21 of those 32 races, the eventual winner was superior to ◎ in at least one of:
- RaceReview coarse state;
- Ability typical;
- Ability latest;
- Ability peak.

Interpretation:

`SUPPORTIVE` is clearly informative.
Eventual winners with SUPPORTIVE Trend had a mean forecast rank of 2.54 and 88.5% were already in the forecast top5.

Therefore Data Trend priority should not be discarded.

However, the current DayRehearsal rule effectively treats:

`SUPPORTIVE > MIXED > NEUTRAL > OPPOSED`

as a hard gate.

That can suppress a horse with weaker coarse Trend state even when the RaceReview or Ability evidence materially challenges the Trend advantage.

Future Pairwise logic should permit evidence-content comparison across lanes rather than treating the coarse Trend state as an almost absolute ordering gate.

## 4. The most important compression loss: same state, different content

There were 12 axis misses where ◎ and the eventual winner had both:
- the same Data Trend coarse state;
- the same RaceReview coarse state.

In these cases DayRehearsal-v0.1 necessarily fell heavily toward Ability or UNCERTAINTY.

But the underlying Trend and RaceReview contents were often materially different.

### Example: 2026-07-25 新潟8R

Frozen:
- ◎ ハルノアラシ
- actual winner ロケットパンチ
- winner frozen rank: 2
- direct decisive lane: ABILITY_ANCHOR

Both horses:
- Data Trend = SUPPORTIVE
- RaceReview = MIXED

Ability:
- ハルノアラシ typical 39 / latest 45 / MAD 6
- ロケットパンチ typical 35 / latest 46 / MAD 1

Data Trend content:
- ハルノアラシ SAME_DISTANCE top3 delta: +13.7pt
- ロケットパンチ SAME_DISTANCE top3 delta: +50.0pt

RaceReview transferability:
- ハルノアラシ exact surface-distance count: 1
- ロケットパンチ exact surface-distance count: 2

The current rule reached Ability because the two coarse states were tied, then preferred the higher typical median.

That discarded:
- the much larger condition-specific top3 delta;
- slightly higher latest Ability;
- much lower Ability dispersion;
- more exact surface-distance review overlap.

This does not prove ロケットパンチ should always be ranked above ハルノアラシ.

It proves that the evidence necessary to make that semantic decision existed, but the rehearsal author did not compare it.

### Example: 2026-07-25 札幌3R

Frozen:
- ◎ メイショウノヴァス
- actual winner ヤマメイッカ
- winner frozen rank: 2
- decisive lane: ABILITY_ANCHOR

Both:
- Trend = SUPPORTIVE
- RaceReview = MIXED

メイショウノヴァス:
- typical 39
- latest 30
- distance-range top3 delta +3.3pt
- exact surface-distance RaceReview count 0

ヤマメイッカ:
- typical 35
- latest 42
- SAME_DISTANCE top3 delta +30.0pt
- exact surface-distance RaceReview count 1

Again, the fixed Ability lexicographic rule selected typical median first and did not semantically weigh the contrast between:
- historical central level;
- latest level;
- direct condition evidence;
- review transferability.

### Example: 2026-07-26 新潟5R

Frozen:
- ◎ アンバサダネージュ
- actual winner ショコラキュイ
- winner frozen rank: 2
- decisive lane: ABILITY_ANCHOR

Both:
- Trend = SUPPORTIVE
- RaceReview = MIXED

アンバサダネージュ:
- typical 38
- latest 38
- MAD 10
- SAME_DISTANCE top3 delta +40.0pt

ショコラキュイ:
- typical 36
- latest 40
- MAD 0
- SAME_DISTANCE top3 delta +66.7pt

The current author again selected the higher typical median.

The winner carried a different evidence shape:
- lower historical central level;
- higher latest;
- much greater consistency in the available Ability history;
- larger same-distance top3 uplift.

The relevant question is not which numeric field should become a new fixed score.

The relevant question is whether the Pairwise reader understands the meaning of those differences.

## 5. Rank-2 winner sample isolates the final decision problem

There were 15 races where the actual winner was frozen exactly at rank 2.

The direct ◎ versus winner decisive lane was:

- ABILITY_ANCHOR: 6
- RACEREVIEW: 5
- DATA_TREND: 4

### Ability-decided rank-2 misses

In all 6 Ability-decided misses:
- ◎ had the higher typical median.

But:
- the eventual winner had the higher latest Ability in 4 / 6;
- the eventual winner had the larger maximum positive Trend top3 delta in 3 / 6.

This is a strong diagnostic of the rehearsal author implementation.

DayRehearsal-v0.1 currently compares Ability lexicographically with typical median first.

The sample suggests that:
`typical historical level`
and
`current/latest condition`
must be interpreted as different concepts rather than one fixed ordering tuple.

No weight change should be made from six races alone.

But future semantic Pairwise reading should explicitly explain:
- baseline level;
- recent level;
- peak ceiling;
- dispersion/stability;
- whether current condition-specific evidence supports trusting latest improvement or historical typical level.

## 6. RaceReview state should not be an ordinal horse rating

The current rehearsal author orders coarse states roughly as:

`HIDDEN_STRENGTH > MIXED > ... > FRAGILE_FORM`

This is useful as a temporary authoring shortcut, but it is not semantically correct as a universal horse ranking.

The rank-2 winner sample alone includes cases where:
- an eventual winner with FRAGILE_FORM beat an axis with INSUFFICIENT;
- eventual winners with MIXED beat axes with HIDDEN_STRENGTH.

This is expected because RaceReview states describe the character of prior-run evidence, not a scalar ability score.

Future Pairwise reading should use:
- actual primary-positive codes;
- actual concern codes;
- repeatability;
- contradiction;
- target-condition transferability;
- exact surface/distance overlap;
- pace-shape context.

A HIDDEN_STRENGTH label without target transferability should not automatically outrank a MIXED horse whose positive evidence transfers directly to today's condition.

Likewise FRAGILE_FORM is not an automatic dismissal if the concern is not expected to repeat under today's setup.

## 7. Proposed semantic reading model — not yet an implementation change

The next Pairwise generation should reason within each lane before comparing lanes.

### DATA_TREND

Do not compare only:
`SUPPORTIVE vs MIXED`

Read:
- which condition produced the signal;
- SAME_DISTANCE / SAME_SURFACE / SAME_VENUE relevance;
- direction;
- win delta and top3 delta separately;
- sample-size band;
- redundant signals from the same condition family;
- whether the evidence describes winning upside or only in-the-money stability.

This is important for future ◎ / ○ roles:
- high win delta can support ◎ upside;
- high top3 delta can support ○ stability;
- they should not be collapsed into the same SUPPORTIVE label.

### RACEREVIEW

Read:
- hidden-strength reason itself;
- fragile-form reason itself;
- repeated versus one-off evidence;
- RESULT_UNDERRATES_TIME / RESULT_OVERRATES_TIME context;
- pace-position-aided/against context;
- fastest-last3F context;
- move-then-fade context;
- exact target surface/distance transferability;
- contradiction.

Do not turn HIDDEN_STRENGTH / MIXED / FRAGILE_FORM into a fixed numeric ranking.

### ABILITY

Read different roles:
- typical median = historical baseline;
- latest = current expression;
- peak = ceiling;
- minimum = downside;
- MAD = stability/volatility.

Do not always use:
`typical > latest > peak > stability`

The semantic reader should decide which Ability dimension is relevant to the specific comparison.

### RACE STRUCTURE / SCENARIO

Continue to treat historical position as context, not today's fixed position.

Use scenario evidence to ask:
- which horse is more vulnerable if pace differs;
- which horse has multiple ways to remain competitive;
- whether one horse's upside depends on a narrower race shape.

Do not convert ROBUST into confidence.

## 8. Relationship to the new mark concept

The current findings fit the intended mark roles.

### ◎ — Forecast Best

◎ should remain the final result of the complete semantic race prediction.

It may be:
- the obvious high-index favorite;
- or a horse that Data Trend / RaceReview / race structure justifies placing above the high-index favorite.

The purpose is not to force value or popularity.

### ○ — Stability Partner

The same semantic evidence can be read with a different question:

`Which candidate is most reliable as the companion to ◎?`

Potential evidence:
- high typical Ability;
- stable MAD;
- strong top3-oriented condition Trend;
- transferable RaceReview evidence;
- low scenario fragility.

This explains why ○ should not simply be frozen rank 2.

### ▲ — Upside Partner

Ask:

`Which candidate can produce a materially better outcome than its baseline ranking suggests?`

Potential evidence:
- strong win-oriented Trend;
- hidden-strength review;
- prior result understating performance;
- favorable scenario interaction;
- improving latest Ability;
- later, workout evidence.

This explains why ▲ should not simply be frozen rank 3.

## 9. Design conclusion

The 72-race analysis does not support replacing RaceNote's evidence hierarchy with a numeric scoring model.

It supports making the Pairwise reader more semantic.

The current pipeline already has much of the necessary raw information.

The information loss occurs when that evidence is compressed into:

```text
SUPPORTIVE > MIXED > NEUTRAL
HIDDEN_STRENGTH > MIXED > FRAGILE_FORM
typical > latest > peak > MAD
```

and those ordinal shortcuts decide the boundary.

The target architecture should become:

```text
General Evidence
  ↓
Candidate cluster
  ↓
Content-aware Pairwise semantic reading
  - Trend meaning
  - RaceReview meaning
  - Ability role
  - Scenario dependence
  ↓
Forecast Best = ◎
  ↓
separate Mark Policy
  - ○ Stability Partner
  - ▲ Upside Partner
```

The goal is not:
`more complex scoring`

The goal is:
`read the evidence the way a data-driven human handicapper would read it.`

## 10. Next implementation step

Before changing production ranking rules:

1. add a semantic Pairwise research layer that exposes the full comparison contents;
2. run it retrospectively over the same 72 frozen races without using results as inputs;
3. produce proposed ◎ ordering and ○ / ▲ role candidates;
4. compare the proposed rules against the already-open result set;
5. only promote a rule if it improves out-of-sample rehearsal behavior rather than fitting individual winners.

The existing DayRehearsal-v0.1 must remain preserved as the control baseline.
