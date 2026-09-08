# RaceNote v0.1 vs v0.2 Prospective Blind Comparison Protocol

## 1. Status

**PREREGISTERED PROSPECTIVE COMPARISON**

This protocol defines the next validation stage after the 219-race v0.1 historical blind development sample.

The 219 races are now treated as **development / diagnostic data** for v0.2 design and must not be reused as proof that v0.2 is superior.

Models:

- Control: `provisional_handoff_v0.1_unweighted`
- Candidate: `RaceNote_Prediction_Handoff_v0_2_Candidate.md`

Betting policies:

- Quinella baseline: ◎-○ / ◎-▲
- Trio A: current 6-ticket ◎ axis flow
- Trio B: 5-ticket `◎ -> ○▲ -> ○▲△1△2`

## 2. Primary question

Does the suitability-first v0.2 candidate improve prediction quality on **new untouched races** without simply overfitting the known 219-race payouts?

Secondary questions:

1. Does explicit distance evidence/risk handling improve ◎ selection?
2. Does course-frame-running-style / pace-position evaluation improve ranking when v0.2 differs from v0.1?
3. Does the separate ☆ value/disagreement flag identify useful opponents without forcing a longshot into ▲?
4. Is trio Policy B materially different from Policy A prospectively?
5. Are the short comments specific enough for a human bettor to understand and challenge the recommendation?

## 3. Target sample

### 3.1 Initial prospective block

Target approximately **72 races (two full JRA days)** as the first v0.1-v0.2 comparison block.

If operationally convenient, extend to 108-144 races before any promotion decision.

### 3.2 Venue diversity preference

When choosing target dates from retained JRDB Raw/BAC metadata, prefer venue families underrepresented in the 219-race development sample, especially when available:

- 中山
- 阪神
- 小倉
- 函館

This is a diversity preference, not a performance filter.

Do not select dates because a known winner/result seems favorable to the candidate logic.

### 3.3 Target discovery source

Use retained JRDB Raw / BAC or BAC-derived RaceNote race metadata only for date/venue/class/grade discovery.

Do not use Web/JRA result pages/search engines for historical target selection.

Existing contamination exclusions remain excluded.

## 4. Freeze sequence

For each target date:

```text
Raw/BAC target discovery
 -> RaceNote acquisition
 -> Reader View round-trip validation PASS
 -> v0.1 control prediction freeze
 -> v0.2 candidate prediction + ☆ + short-comment freeze
 -> betting-policy freeze
 -> HJC acquisition
 -> deterministic settlement
 -> comparison report
```

No target-date HJC/result/final odds/final popularity/Web result/post-target history may be accessed before **both prediction versions** are frozen.

## 5. Required frozen output per race

### v0.1

- ◎
- ○
- ▲
- △1
- △2
- confidence A/B/C
- source semantic SHA

### v0.2

- ◎
- ○
- ▲
- △1
- △2
- optional ☆ value/disagreement candidate
- confidence A/B/C
- race-shape short comment
- ◎ short comment
- principal risk
- source semantic SHA

Additionally record whether v0.2 changed any of the following relative to v0.1:

- ◎
- top 3 ordering
- selected five horses
- confidence

## 6. v0.2 reasoning audit fields

For each v0.2 race, record compact internal labels:

- `ability_gate`
- `frame_style_fit`
- `pace_position_fit`
- `distance_evidence`
- `surface_going_fit`
- `condition_signal`
- `pedigree_support`
- `uncertainty_flags`
- `value_disagreement_flag`

Recommended qualitative vocabulary:

### ability_gate
- core
- competitive
- borderline
- unproven

### fit fields
- positive
- neutral
- negative
- unknown

### distance_evidence
- same_distance_strong
- same_distance_usable
- nearby_distance_usable
- indirect_only
- insufficient
- contradictory

These labels are for auditability, not fixed numeric scoring.

## 7. Primary evaluation metrics

### Prediction

Compare v0.1 and v0.2 on:

- ◎ win rate
- ◎ top2 rate
- ◎ top3 rate
- selected-five winner capture
- selected-five top3 coverage
- ○ / ▲ contribution to top2 capture
- changed-◎ race outcomes
- changed-top3-order race outcomes

Most important diagnostic:

> On races where v0.2 differs from v0.1, which version is more often directionally correct?

Do not let unchanged races dominate the interpretation.

### Suitability sub-audits

For v0.2 changes attributable to:

- distance evidence/risk;
- frame/style fit;
- pace/position fit;
- condition/training;
- pedigree support;

record whether the promoted/downgraded horse actually improved the relevant finish-position comparison.

No single small subgroup may be promoted into a production rule without replication.

## 8. Betting evaluation

For both prediction versions, calculate:

### Quinella
- ◎-○
- ◎-▲
- two-ticket total

### Trio Policy A
Six tickets:

- ◎○▲
- ◎○△1
- ◎○△2
- ◎▲△1
- ◎▲△2
- ◎△1△2

### Trio Policy B
Five tickets:

- ◎○▲
- ◎○△1
- ◎○△2
- ◎▲△1
- ◎▲△2

Compare:

- investment
- payout
- hit races
- hit rate
- return rate
- incremental ROI of ◎△△
- payout concentration

No policy change is accepted merely because one block has the highest ROI.

## 9. ☆ value/disagreement evaluation

The ☆ flag is not required every race.

When present, evaluate:

- finish position
- whether it entered top2/top3
- whether it was already ○/▲/△
- available pre-target market rank / disagreement context
- whether a hypothetical ◎-☆ quinella would have hit
- whether substituting ☆ into a baseline ticket would improve or damage result

This remains diagnostic in the first prospective block.

Do **not** automatically add an extra real-money ticket from ☆ during this stage.

## 10. Short-comment quality review

Each v0.2 output must be understandable to the final human bettor.

Audit whether the comment answers:

1. Why is ◎ strong enough?
2. Why does today's course / frame / pace / distance suit or not suit it?
3. What is the main way the bet can fail?
4. Why are ○ and ▲ different from ◎?
5. If ☆ exists, what concrete evidence makes it value-like rather than merely unpopular?

Failure examples:

- generic index-only justification;
- unsupported course stereotype;
- vague `展開が向く` without explaining position/pace;
- ignoring a known distance contradiction;
- calling a horse value solely from low popularity.

## 11. Interpretation discipline

The first 72-race prospective block is evidence, not final proof.

Possible outcomes:

### A. v0.2 clearly improves prediction-layer metrics

Continue candidate unchanged into another independent block before promotion.

### B. v0.2 changes many marks but does not improve

Diagnose which suitability layer is overactive. Do not tune using payouts first.

### C. v0.2 rarely changes v0.1

The procedure is not materially different enough; inspect whether ability consensus still dominates qualitative judgment.

### D. prediction improves but betting ROI does not

Treat this as a betting-layer problem, not prediction failure.

### E. betting improves without prediction improvement

Do not claim prediction improvement. Diagnose ticket construction separately.

## 12. Promotion gate

Do not replace v0.1 after a single favorable day or G1.

Before promotion, require at least:

- independent prospective blind blocks;
- meaningful number of v0.1-v0.2 disagreement races;
- no evidence that one narrow venue/class explains all gain;
- stable short-comment audit quality;
- documented handling of distance / pace / frame-style uncertainty.

Until promotion:

```text
v0.1 = authoritative control
v0.2 = experimental candidate
219R = development/diagnostic sample
new races only = v0.2 validation sample
```
