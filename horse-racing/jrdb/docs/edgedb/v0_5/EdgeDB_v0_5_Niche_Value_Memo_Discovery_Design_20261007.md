# EdgeDB v0.5 — Niche Value Memo Discovery Design

Date: 2026-10-07  
Status: DESIGN DRAFT / RESEARCH RESET  
Scope: JRDB Central Racing EdgeDB research  
Production impact: NONE  
Predecessor: v0.4 High-Order Cross / Observe-only cohort  
Primary goal: discover concise, currently useful betting-decision memos that help RaceNote or a human handicapper notice overlooked positive/negative conditions.

---

## 1. Why v0.5 exists

v0.4 successfully built:

- deterministic candidate generation;
- high-order cross evaluation;
- parent comparison;
- pre-race-safe matching;
- frozen observe-only cohorts;
- unified EdgeDB Query;
- Newspaper/PWA serving boundary.

However, live PWA inspection showed that the scientific definition of "Edge" remained too broad.

Examples of undesirable outputs:

- one horse receives both "sire × left-turn 2000m" and "sire × turf 2000m";
- turf->turf, dirt->dirt, same-distance-band conditions produce large numbers of ordinary signals;
- many conditions are statistically describable but not useful as betting-decision prompts;
- the system behaves more like a condition-statistics enumerator than a "market-overlooked niche memo finder".

v0.5 therefore resets the research objective.

The key question is no longer:

> Which multidimensional conditions are statistically incremental?

The v0.5 question is:

> Which short, understandable pre-race conditions still show useful recent betting value or meaningful positive/negative race outcomes, especially where the market may not fully reflect the condition, and are therefore worth surfacing as a decision memo?

Examples of desired form:

- ミッキーアイル産駒は芝ワンターンで狙い
- ドゥラメンテ産駒は距離延長で狙い
- キズナ産駒は初ダートで狙い
- ○○産駒は初ブリンカーで注意
- 東京芝○○mは○枠でプラス / マイナス

These are not standalone automatic betting systems.

They are evidence prompts for:

- RaceNote automatic prediction;
- human comparison between two candidates;
- re-checking a popular horse with multiple negative signals;
- finding a longshot worth reviewing.

---

## 2. Fundamental separation: occurrence statistics vs betting returns

This is a hard design rule.

### 2.1 Performance / occurrence lane

This answers:

> How often did the condition produce a good or bad race outcome?

Examples:

- n
- wins
- places
- win_rate
- place_rate
- fail_rate
- parent-relative place-rate delta
- year distribution
- unique race days

This lane describes occurrence / racing performance.

### 2.2 Betting-return lane

This answers:

> What happened financially if the qualifying runners were backed historically?

Examples:

- win_return_sum
- place_return_sum
- win_roi
- place_roi
- 2024 win/place ROI
- 2025 win/place ROI
- popularity-band ROI diagnostics
- highest-priced hit
- longshot hit count

This lane describes betting return.

### 2.3 These lanes must not be conflated

A condition can be:

- low-frequency but valuable as a longshot discovery memo;
- high hit-rate but already fully priced by the market;
- poor as a blind-buy strategy but still useful as a secondary decision signal;
- statistically noisy but worth reviewing because it has produced a rare market miss.

Therefore:

- no automatic rejection solely because ROI excluding the largest hit falls below 100;
- no automatic rejection solely because one large payout contributes strongly;
- no automatic acceptance solely because ROI is above 100;
- no requirement that all qualifying horses be profitable when blindly purchased.

Top1/top3 contribution remains diagnostic only.

A historical longshot success may be exactly the evidence v0.5 is intended to preserve.

---

## 3. Canonical time windows

### 3.1 Discovery window

Primary discovery:

- 2024-01-01 through 2025-12-31

This is the canonical search population for the first v0.5 generation.

Reason:

- market awareness changes quickly;
- course biases become public knowledge;
- sire trends decay;
- race programming and horse populations change;
- recent ROI is more relevant to "is this still overlooked?" than decade-long ROI.

### 3.2 Historical context window

Background only:

- 2022-01-01 through 2023-12-31

This window does not define membership.

It is used to classify freshness:

- NEWLY_EMERGING
- PERSISTENT
- DECAYING
- OLD_ONLY
- MIXED

Example:

```
2022-23 place ROI 82
2024    place ROI 118
2025    place ROI 142
=> RECENTLY_EMERGING candidate
```

versus:

```
2022-23 place ROI 148
2024    place ROI 101
2025    place ROI 67
=> DECAYING / likely market saturation or regime loss
```

### 3.3 OOS / operational validation

2026 is not part of initial discovery.

Use 2026 for:

- historical blind replay;
- true-forward when available;
- live PACI matching;
- PWA collision/presentation review.

Past 2026 race dates may be used as HISTORICAL_BLIND_REPLAY if the pre-race/result separation contract is respected.

---

## 4. Candidate generation remains market-blind

Popularity, odds and payout must not define the candidate population.

Forbidden in candidate definition:

- popularity
- win odds
- place odds
- "5th favorite or worse"
- "10x or higher"

Allowed after candidate membership is frozen:

- ROI
- payout
- popularity-band diagnostics
- market expectation comparison
- longshot hit counts

This keeps:

> "condition is interesting"

separate from:

> "condition happened to select expensive runners".

---

## 5. v0.5 initial search template families

v0.5 does not start from arbitrary depth-2-to-6 cross enumeration.

It starts from explicitly meaningful human-readable template families.

### T1. Course × frame

```
venue × surface × distance × frame
```

Example:

- 東京 × ダート × 1600m × 8枠

Purpose:

- find current course biases;
- detect whether famous biases still retain betting value;
- allow positive and negative signals.

Frame representation should support exact frame first.
A broader INNER / MIDDLE / OUTER variant may be evaluated separately, not emitted redundantly.

### T2. Sire × course

```
sire × venue × surface × distance
```

Example:

- ミッキーアイル × 東京 × 芝 × 1600m

This is a primary v0.5 family.

Optional semantic course derivatives may later include:

- turf one-turn;
- dirt one-turn;
- two-turn;
- straight course.

These must be canonical derived features, not ad-hoc display labels.

### T3. Sire × meaningful distance change

```
sire × DISTANCE_EXTEND
sire × DISTANCE_SHORTEN
```

Do not include SAME_BAND.

Initial change semantics:

- EXTEND
- SHORTEN

Do not split immediately into many meter buckets.
Only add magnitude if the broad transition is demonstrably heterogeneous and a later expansion is justified.

### T4. Sire × surface switch

```
sire × TURF_TO_DIRT
sire × DIRT_TO_TURF
```

Also treat first-surface events as distinct templates:

- sire × FIRST_DIRT
- sire × FIRST_TURF

Do not include:

- TURF_TO_TURF
- DIRT_TO_DIRT

in the initial v0.5 search space.

Continuity states are ordinary context, not Edge candidates by default.

### T5. Sire × first blinkers

```
sire × FIRST_BLINKERS
```

This is intentionally niche.

Small support alone must not automatically remove it.
It should retain explicit MICRO/SMALL support labels.

### T6. Sire × surface × going

Initial form:

```
sire × surface × going_bucket
```

Initial going buckets:

- GOOD
- SOFT_OR_WORSE

Where:

- turf/dirt condition mappings must be canonical JRDB mappings;
- "稍重以上" is treated as a semantic bucket only if source codes are consistent.

Do not initially split into 良 / 稍重 / 重 / 不良 separately unless distribution review justifies it.

---

## 6. Optional derived semantic features

The following are allowed only as canonical pre-race features.

### 6.1 One-turn / two-turn

A course topology lookup should map:

```
venue + surface + distance (+ course variant if required)
-> ONE_TURN / TWO_TURN / STRAIGHT / OTHER
```

This allows:

- sire × turf × ONE_TURN

without needing to list every venue-distance combination.

It is specifically intended to discover memo forms such as:

> 芝ワンターンはミッキーアイル

### 6.2 First-surface

FIRST_DIRT / FIRST_TURF must mean true career-first surface exposure as known before the target race.

Do not approximate it from only the immediate previous race.

### 6.3 First blinkers

FIRST_BLINKERS must mean first known use before the target race.

Do not confuse:

- wearing blinkers today
- returning to blinkers
- first-time blinkers

---

## 7. Search depth policy

v0.5 prioritizes semantic templates, not raw depth.

The initial canonical search is limited to the template families above.

Do not automatically add arbitrary extra dimensions such as:

- age
- sex
- jockey
- trainer
- class
- frame
- going
- venue

to every candidate.

A candidate may be expanded only when:

1. the base template is already interesting;
2. there is a specific semantic reason to test one additional dimension;
3. the child meaning remains understandable as one sentence;
4. the new dimension materially changes the evidence.

Examples of justified later expansion:

- sire × distance extension -> perhaps surface-specific if turf and dirt behave oppositely;
- sire × course -> perhaps frame if a plausible interaction is visible;
- sire × first dirt -> perhaps age if first-dirt behavior is strongly age-dependent.

Depth is not a score.

Shorter explanations are preferred when they explain the same evidence.

---

## 8. Candidate metrics

Every candidate must retain raw metrics, not only a final score.

### 8.1 Support and occurrence

- n
- wins
- places
- win_rate
- place_rate
- misses
- unique_horses
- unique_race_days
- 2024 n/wins/places
- 2025 n/wins/places
- historical-context 2022-23 n/wins/places

### 8.2 Return

- win_return_sum
- place_return_sum
- win_roi
- place_roi
- 2024 win/place ROI
- 2025 win/place ROI
- 2022-23 context ROI

### 8.3 Market-miss evidence

Calculated only after candidate population freeze.

At minimum:

- hit count at 5th favorite or worse
- hit count at 8th favorite or worse
- hit count at 10th favorite or worse
- highest finishing longshot popularity
- largest win payout
- largest place payout
- popularity distribution
- average/median popularity diagnostic
- ROI by broad popularity band

Suggested broad diagnostic bands:

- 1-4
- 5-7
- 8+

These bands are evaluation diagnostics only, never candidate conditions.

### 8.4 Jackpot diagnostics

Retain:

- top1 return contribution
- top3 return contribution
- ROI excluding top1
- ROI excluding top3

But these fields must not automatically invalidate a candidate.

The purpose is to tell the consumer:

> this memo has one large historical success

not:

> remove the large success and pretend it never happened.

---

## 9. Minimum support

v0.5 must avoid n=1/2 style noise while preserving niche conditions.

Initial support classes:

- MICRO: n=5-9
- SMALL: n=10-19
- MEDIUM: n=20-49
- LARGE: n>=50

n < 5:

- do not publish as an Edge candidate;
- may remain in raw research audit.

This reflects the intended use:
a 1/5 longshot hit can still be meaningful as a memo candidate, while 1/2 is too weak for serving.

Support class is evidence context, not a direct acceptance rank.

---

## 10. Positive and negative Edge lanes

v0.5 explicitly supports both.

### 10.1 Positive Edge

Question:

> Does this condition give a reason to upgrade or re-check a horse?

Evidence can include:

- elevated recent win/place ROI;
- positive place-rate shift;
- repeated longshot hits;
- recent improvement vs historical context;
- meaningful parent/context improvement.

A positive Edge does not mean "blindly bet every qualifier".

### 10.2 Negative Edge

Question:

> Does this condition give a reason to downgrade or re-check a horse?

Evidence can include:

- poor recent performance;
- low recent win/place ROI;
- worse place rate than a natural parent/context;
- repeated failures under the condition;
- clear recent deterioration.

Negative condition generation remains market-blind.

Its usefulness is especially high when a current horse is popular, but current popularity is not needed to define the negative Edge.

---

## 11. Parent/context comparison

v0.5 keeps parent comparison, but changes its role.

It is diagnostic and semantic, not a universal statistical gate.

Examples:

```
ミッキーアイル overall
vs
ミッキーアイル × turf one-turn
```

```
ドゥラメンテ overall
vs
ドゥラメンテ × distance extend
```

```
東京ダ1600 overall
vs
東京ダ1600 × frame 8
```

Keep:

- parent n
- parent place rate
- parent win/place ROI
- delta place rate
- delta win/place ROI
- longshot-hit delta where meaningful

The child need not beat every parent metric.

The purpose is to answer:

> Does the added condition tell us something more specific than the broad fact?

---

## 12. Freshness / saturation classification

This is a central v0.5 concept.

Use:

- 2022-23 context
- 2024
- 2025

to classify direction.

Initial labels:

- EMERGING
- CURRENT
- DECAYING
- OLD_ONLY
- VOLATILE
- INSUFFICIENT_HISTORY

Example interpretation:

### EMERGING

Recent ROI/value materially stronger than 2022-23.

### CURRENT

Useful in 2024-25 without obvious collapse in 2025.

### DECAYING

Earlier value strong, 2025 materially weaker.

### OLD_ONLY

Historical context strong, 2024-25 weak.

### VOLATILE

Large year-to-year reversal.

These are descriptive labels.

Do not force a candidate to have two profitable years.
A strong 2025 after a weak 2024 may be exactly the trend being sought.

---

## 13. "Market overlooked" evaluation

v0.5 does not define market-overlooked as:

> ROI > 100 for all qualifiers forever.

Instead, after condition membership is frozen, evaluate evidence such as:

- recent aggregate win/place ROI;
- number of medium/longshot hits;
- popularity-band outcomes;
- whether value concentrates only in favorites;
- whether the candidate still produced high-payout hits in 2024-25;
- freshness vs 2022-23.

A condition can be useful even if aggregate blind-buy ROI < 100, if it has produced meaningful market misses that can help a second-stage handicapper.

Conversely, a famous bias with high hit rate but recent ROI collapse may be considered saturated.

No single metric defines "market overlooked".

---

## 14. Redundancy and semantic dominance

This is a mandatory v0.5 stage.

The system must not present:

- sire × turf 2000
- sire × left-turn 2000
- sire × Tokyo turf 2000

as three independent memos if they represent substantially the same historical population/evidence.

### 14.1 Exact/nested redundancy

Compare candidate runner sets.

Store:

- overlap count
- Jaccard similarity
- subset/superset relation
- metric deltas

### 14.2 Semantic dominance rule

Prefer the broader/simple condition when it explains essentially the same evidence.

Prefer the narrower condition only if the added dimension materially changes:

- return profile;
- occurrence profile;
- longshot evidence;
- freshness.

### 14.3 Display cluster

Retain all raw candidates in research storage.

Create a display cluster with:

- representative memo
- suppressed redundant candidate IDs
- reason for suppression

No evidence is deleted.

---

## 15. Memo quality / explainability

Every served Edge must be expressible as one short sentence.

Examples:

- ドゥラメンテ産駒は距離延長でプラス
- キズナ産駒は初ダートで狙い
- ミッキーアイル産駒は芝ワンターンでプラス
- 東京ダ1600mは8枠が近年マイナス

Avoid machine-facing output such as:

- surface_transition=1->1
- distance_change_bucket=SAME_BAND
- sire_line_code=1206

If a condition cannot be converted into a concise human memo, it is not presentation-ready.

---

## 16. Research labels

Research candidates should be categorized without collapsing all evidence into one score.

Suggested labels:

- NICHE_VALUE_POSITIVE
- NICHE_VALUE_NEGATIVE
- LONGSHOT_EVIDENCE
- CURRENT_BUT_LOW_SUPPORT
- EMERGING
- DECAYING
- SATURATED_OR_PRICED
- REDUNDANT
- WEAK
- INSUFFICIENT

A candidate may have multiple labels.

Example:

```
NICHE_VALUE_POSITIVE
LONGSHOT_EVIDENCE
MICRO
EMERGING
```

This is more informative than one scalar rank.

---

## 17. No universal "top1 exclusion" rejection

v0.4 heavily emphasized jackpot dependence.

v0.5 changes this policy.

Top1/top3 exclusion is retained for transparency, but:

- jackpot dependence is not an automatic failure;
- a single high-priced success may be valuable evidence;
- the memo can be labelled ONE_BIG_HIT / LONGSHOT_EVIDENCE;
- RaceNote/human consumers decide how much weight to give it.

Example:

```
n=5
places=1
best hit = 10th favorite, place payout 810
place ROI = 162
place ROI ex top1 = 0
```

This is not automatically "worthless".

It means:

> very low support, one meaningful market miss, high uncertainty.

That is a valid research memo state.

---

## 18. Initial discovery workflow

### R0 — Feature feasibility audit

Verify exact availability and leakage safety for:

- venue
- surface
- distance
- frame
- sire
- course topology (one-turn/two-turn)
- distance extend/shorten
- turf<->dirt
- first dirt / first turf
- first blinkers
- going bucket
- result/payout/popularity fields for post-freeze evaluation

Produce a compact availability report.

### R1 — Build canonical 2024-25 mart

Create a v0.5 discovery mart containing only required fields plus result/evaluation fields.

Separate:

- pre-race candidate features
- post-race outcome/value features

Use Parquet / DuckDB canonical tooling.

### R2 — Evaluate six template families

Run T1-T6.

Do not run arbitrary high-order enumeration.

Output all candidates with n>=5 and required metrics.

### R3 — Freshness/context evaluation

Attach:

- 2022-23 metrics
- 2024 metrics
- 2025 metrics
- freshness labels

### R4 — Market diagnostic enrichment

After candidate membership is frozen, attach:

- popularity bands
- longshot hit counts
- largest payouts
- market-miss diagnostics

No candidate definition may change in this stage.

### R5 — Redundancy clustering

Collapse near-equivalent/nested memos for presentation.

Preserve raw candidates.

### R6 — Human review shortlist

Produce a compact shortlist, ideally grouped by:

- course
- sire-course
- transition
- equipment
- going

For each memo show enough evidence for human review.

### R7 — 2026 historical blind replay

Freeze selected memo definitions.

Replay 2026 race dates using only pre-race facts before joining results.

Measure:

- match frequency
- positive/negative usefulness
- longshot hits
- collision density
- redundancy after live matching
- PWA readability

### R8 — OBSERVE_ONLY publication

Only after review.

v0.5 enters EdgeDB manifest first as OBSERVE_ONLY.

No automatic STANDARD promotion.

---

## 19. Initial shortlist display metrics

For each candidate/memo, show at minimum:

```
memo
support_class
n
wins / places
win ROI / place ROI
2024 place ROI
2025 place ROI
2022-23 context place ROI
5+ popularity hits
8+ popularity hits
10+ popularity hits
largest place payout
parent/context delta
freshness label
redundancy cluster
```

Do not hide the raw n/hit counts behind a score.

---

## 20. PWA presentation target

The final PWA should not display every raw candidate.

Per horse, present only non-redundant memo representatives.

Initial target:

- 0-3 positive memos
- 0-3 negative memos

This is a presentation target, not a research cap.

If five raw conditions collapse to one semantic memo, display one.

Example:

```
＋ キズナ産駒は初ダートで狙い
－ ○○産駒は道悪ダートで近年不振
```

Tapping the memo may show:

- n
- recent ROI
- hit counts
- notable longshot history
- freshness
- source generation

---

## 21. RaceNote integration principle

v0.5 Edge remains a secondary evidence lane.

RaceNote may later use:

- positive memo count/type
- negative memo count/type
- support class
- freshness
- longshot evidence

but must not treat:

- place ROI 150 = automatic score +X

without a separate RaceNote policy decision.

EdgeDB provides evidence.
RaceNote owns prediction weighting.

---

## 22. Success criteria

v0.5 succeeds if it can produce a compact library of memos that:

1. are understandable in one sentence;
2. come from pre-race conditions;
3. emphasize 2024-25 current value;
4. distinguish occurrence statistics from betting returns;
5. preserve meaningful one-off longshot evidence instead of deleting it;
6. avoid ordinary continuity conditions such as turf->turf, dirt->dirt, same-distance-band;
7. identify both positive and negative conditions;
8. reduce semantic duplication before PWA display;
9. can be matched automatically from PACI through `edgedb-query/v1`;
10. are useful as decision prompts rather than automatic blind-buy rules.

Success is not:

- every candidate having ROI > 100;
- every year being profitable;
- every candidate being statistically significant;
- maximum search depth;
- maximum number of signals;
- maximizing historical backtest profit.

---

## 23. Explicit non-goals

v0.5 does not attempt:

- automatic bet portfolio construction;
- optimizing staking;
- fitting popularity/odds thresholds into candidate definitions;
- exhaustive 5-6 dimension mining;
- suppressing all low-support conditions;
- making top1-exclusion profitability mandatory;
- replacing RaceNote;
- promoting v0.4 or v0.5 automatically to STANDARD.

---

## 24. First implementation decision

Before any large aggregation, implement only enough to answer:

> Can the six T1-T6 template families over 2024-25 produce memo-like candidates resembling the historical TARGET-style discoveries?

The first v0.5 execution should therefore be a compact prototype.

Do not reuse v0.4's 47,371-template exhaustive catalog as the starting point.

Reuse:

- Feature Mart / canonical data access
- transition derivation where valid
- EdgeDB Query serving infrastructure
- result query / Analysis / Warehouse access
- data-storage Parquet/DuckDB tools

Replace:

- broad high-order candidate search
- automatic jackpot rejection emphasis
- presentation of overlapping raw conditions
- ordinary continuity transitions as first-class Edge candidates.
