# RaceNote v1 — Evidence Note Design

Status: Phase 1 design baseline
Date: 2026-09-28

## 1. Definition

RaceNote is a **pre-race evidence note for GPT forecasting**.

Its purpose is to let a GPT model reason about one race without needing to:
- re-parse JRDB fixed-length files,
- re-query historical warehouses,
- re-scrape race-day facts,
- reconstruct RaceReview history,
- or infer basic race/horse context from fragmented inputs.

RaceNote **does not forecast**.

It must not contain:
- ◎○▲△,
- a final horse ranking,
- a universal evidence hierarchy,
- a numeric "forecast score",
- a deterministic "buy / do-not-buy" decision,
- or a pre-written conclusion that one horse is better than another.

The Forecast layer will consume one RaceNote and reason about that race independently.

---

## 2. Design principles

### 2.1 Evidence completeness before forecast cleverness

RaceNote should make relevant evidence easy to read and compare.

The builder may:
- normalize source fields,
- join historical records,
- aggregate descriptive statistics,
- compute as-of-safe summaries,
- flag missing data,
- preserve source provenance.

The builder should not:
- decide which evidence must dominate,
- collapse heterogeneous evidence into one ranking,
- or turn uncertainty into a forced ordering.

### 2.2 One race is one self-contained note

A RaceNote file represents exactly one race.

It should contain:
1. race context,
2. race-day facts,
3. Trend context,
4. field-level context,
5. every runner,
6. runner histories and evidence,
7. provenance / coverage / limitations.

### 2.3 Facts and interpretations are separated

Three levels are allowed.

#### Level A — Source facts
Examples:
- class,
- distance,
- frame,
- jockey,
- recent finish,
- IDM,
- RaceReview time-class equivalent,
- track condition.

#### Level B — Descriptive evidence
Examples:
- same-distance record,
- recent class sequence,
- named-race frame statistics,
- local-context jockey statistics,
- repeated above-class RaceReview observations.

These may be generated deterministically.

#### Level C — Forecast judgment
Examples:
- "this horse is the most reliable",
- "trend should override ability",
- "this is the best bet",
- mark assignment.

Level C is prohibited inside RaceNote.

---

## 3. Top-level structure

```text
RaceNote v1
├─ metadata
├─ race
├─ race_day
├─ trend_context
├─ field_context
├─ runners[]
├─ coverage
└─ provenance
```

---

## 4. metadata

Required:
- schema_version
- generated_at
- target_date
- as_of
- note_kind = EVIDENCE_NOTE
- result_visibility = HIDDEN
- market_visibility = HIDDEN by default
- source_snapshot identifiers

The note must be reproducible enough to identify which source snapshot generated it.

---

## 5. race

Race identity and conditions.

Required where available:
- date
- venue
- race_no
- race_name
- surface
- distance_m
- course_layout
- turn
- race_type
- class
- grade
- weight_rule
- age/sex restrictions
- field_size
- course rail setting when available (A/B/C etc.)
- meeting identifier / meeting day when available
- special/newcomer/steeplechase flags

No forecast interpretation belongs here.

---

## 6. race_day

Independent race-day facts.

Examples:
- weather
- official track condition
- cushion value / moisture if a trusted source is available
- publication timestamp
- source

Race-day facts must be:
- pre-result,
- timestamped,
- source-attributed.

---

## 7. trend_context

Trend is descriptive race context, not a ranking rule.

### 7.1 named_race

Used when a stable named-race history exists.

Examples:
- 有馬記念
- 札幌記念
- ポルックスS

The preferred sample is:
- same named race,
- under comparable race conditions.

The note must preserve:
- included editions,
- excluded editions and reason when applicable,
- sample counts,
- observed statistics,
- source period.

A small sample is not discarded merely because it is small.

### 7.2 local_context

Used especially for ordinary/condition races.

Example context:
- 中山
- 芝1600m
- 2勝クラス
- 秋開催
- Bコース
- comparable meeting progression

The class level is a major context key.

If the narrow sample is sparse, supporting samples should expand while preserving race class as long as practical.

For a 2勝クラス race, fallback should prefer comparable 2勝クラス races, not OP+.

### 7.3 base_context

A broader comparator.

Purpose:
- show whether the local trend agrees with,
- differs from,
- or contradicts broader course tendencies.

The base sample must not overwrite the local sample.

### 7.4 fallback policy by race class

#### Named OP / graded race
1. same named race under comparable conditions
2. comparable OP+ races at the same venue/course/distance/meeting context
3. broader comparable OP+ context

This is useful for:
- newly created graded races,
- long interruptions,
- venue-replacement periods,
- material course renovations.

#### Ordinary / class race
1. same named special race if the identity is genuinely comparable
2. same class + venue + surface + distance + meeting/local context
3. same class + venue + surface + distance
4. same class + nearby comparable course context

Do not jump to OP+ solely to increase sample size.

### 7.5 trend dimensions

Candidate dimensions:
- popularity buckets from historical races
- frame / draw
- running style
- age
- sex
- sire / pedigree group
- jockey
- previous-race class
- previous-race distance
- previous-race finish
- weight/handicap where relevant

Every statistic should expose:
- numerator/denominator or starts,
- period/editions,
- sample size,
- return/payoff statistics when legitimately available,
- missingness.

No statistic gets an automatic priority rank.

---

## 8. field_context

Field-level facts that help GPT understand the race as a whole.

Examples:
- field size
- declared running-style distribution
- pace-relevant composition
- class distribution / unusual class movers
- age distribution
- newcomers
- first-time surface/distance cases
- layoff distribution

Allowed:
- descriptive labels such as "many front-runners" if the derivation is explicit.

Not allowed:
- "pace will definitely collapse"
- "closers should be preferred"
- horse ranking.

---

## 9. runners

Every runner must be present.

Each runner should contain the following families.

### 9.1 identity
- horse_no
- frame_no
- horse_name
- sex
- age
- weight
- jockey
- trainer
- stable
- horse_id / stable source identifiers

### 9.2 current_entry
Current race facts:
- assigned weight
- jockey change
- equipment
- rest interval
- condition/training fields
- JRDB improvement/training arrows
- special notes/tokki codes
- body/leg/equipment comments where available

These are facts/context only.

### 9.3 recent_runs

Do not reduce recent runs to only a median.

For each recent run preserve enough context to read **how comparable that performance is to today's race**:
- date
- venue
- race name
- class / grade
- surface
- distance
- course layout when available
- track condition
- field size
- frame / horse number where available
- jockey
- weight
- finish
- margin
- running style / positions
- IDM / ability-related source fields
- odds/popularity only if the future forecast mode explicitly permits market data; hidden by default
- RaceReview references/observations

This is essential for contextual reads such as:
- G2 1st → G3 4th → G3 1st,
- G1 loss that may not represent today's class,
- repeated same-class placings,
- class-rise breakthrough,
- a high-grade performance earned at a materially different venue/distance from today's target,
- a slightly lower raw Ability performance earned under conditions much closer to today's race.

Race class/grade must therefore never be detached from venue, surface and distance when GPT reads a past performance.

Example:
- 天皇賞（春）G1 at Kyoto 3200m,
- 阪神大賞典 G2 at Hanshin 3000m,
- 宝塚記念 G1 at Hanshin 2200m,
- 金鯱賞 G2 at Chukyo 2000m,
- 京都記念 G2 at Kyoto 2200m,

are not interchangeable evidence for a target such as Sapporo 2000m merely because they are all graded races.

RaceNote should preserve these contexts and let the Forecast layer judge their relevance.

### 9.4 ability_history

Ability is evidence, not a rank.

Preserve:
- run-level Ability/IDM values,
- recent sequence,
- optional descriptive summaries such as latest / median / peak / dispersion,
- class/grade attached to each value,
- venue attached to each run-level value,
- surface attached to each run-level value,
- distance attached to each run-level value.

The class context **and target-condition context** must not be lost when summarizing Ability.

A peak Ability earned in a G1 at 3200m and an only slightly lower Ability earned in a G2 at 2000m should remain distinguishable to the Forecast layer when today's race is 2000m.

RaceNote does not decide which is superior; it preserves enough context for GPT to make that judgment.

### 9.5 horse_history

Descriptive historical records:
- career
- same surface
- same venue
- same exact distance
- relevant distance ranges
- comparable class where available
- course-specific history where available

Expose starts/wins/top2/top3 and sample size.

Do not encode "SUPPORTIVE" as a forecast conclusion.

### 9.6 racereview

Reuse stable RaceReview observations.

Preserve run references and contextual fields such as:
- declared class
- time-class equivalent
- adjusted time delta
- pace shape
- last3f information
- position changes
- trouble indicators

Deterministic observation tags may be included if they remain descriptive, e.g.:
- TIME_ABOVE_DECLARED_CLASS
- RESULT_UNDERRATES_TIME
- FASTEST_LAST3F

But do not collapse them into a horse rating.

### 9.7 population_context

Relevant descriptive historical context for:
- jockey
- sire
- trainer/stable if available
- frame
- running style
- other stable population dimensions

Context should be attached to the target race conditions and expose sample size.

### 9.8 data_gaps

Per-runner missingness must be visible.

Examples:
- no prior runs
- insufficient RaceReview history
- no same-distance history
- new surface
- missing training data

Missingness is information; do not silently substitute a neutral value.

---

## 10. Newcomer and steeplechase handling

Phase 1 does not define separate forecasting logic.

However, RaceNote must explicitly identify:
- newcomer / debut races,
- steeplechase races,
- evidence families that are unavailable by construction.

This prevents the Forecast layer from pretending that ordinary recent-form evidence exists.

A future phase may add specialized evidence families, but the main schema should remain extensible.

---

## 11. Market and consensus boundary

Core RaceNote v1 is market-hidden by default.

Hidden from the core note:
- current odds
- current popularity
- current JRDB consensus/prediction marks
- Training Edge
- EdgeDB match
- RL-derived final indices
- results

Historical popularity/odds may be used inside historical Trend analysis because they describe past race outcomes, not the current market.

If a future Forecast mode intentionally wants current market/value context, it should be attached as a separate supplement after the evidence-only forecast boundary, not silently mixed into core RaceNote.

---

## 12. Provenance and as-of safety

Every derived family should be traceable.

At minimum preserve:
- source name
- source snapshot / file
- as_of cutoff
- query period
- transformation version

Historical queries must be exclusive of the target race result.

---

## 13. Reader-oriented output

Canonical storage format:
- JSON

Human/GPT reader format:
- Markdown or structured text rendered from the same JSON.

The reader view should prioritize:
1. race context,
2. Trend context,
3. full runner list,
4. concise runner summaries,
5. expandable detailed histories.

The reader view must not introduce forecast interpretations absent from the canonical JSON.

---

## 14. Explicit non-goals

RaceNote v1 does not:
- rank runners,
- select candidates,
- choose ◎,
- assign ○▲△,
- decide betting tickets,
- optimize ROI,
- implement a universal race thesis,
- or decide how much one evidence family should outweigh another.

Those are Forecast-layer responsibilities.

---

## 15. Phase 1 acceptance criteria

Phase 1 is complete when:

1. a canonical schema exists;
2. the schema can represent normal races, newcomers and steeplechases without pretending missing evidence exists;
3. no forecast/ranking fields are part of the contract;
4. named/local/base Trend can coexist without one overwriting another;
5. fallback Trend preserves class context;
6. recent-run class/grade context survives into the note;
7. source/as-of provenance is mandatory;
8. a validator can reject obvious forecast leakage fields.
