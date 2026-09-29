# RaceNote Forecast Human-Context Reader v0.3.2

Status: **CURRENT CALIBRATION LOGIC — RRDB REINTERPRETATION / RECOMPARE**
Date: 2026-09-29
Logic version: `RaceNote-Human-Context-Reader-0.3.2`

## 1. Purpose

未使用blind日を消費して精度検証する前に、
「何をもって◎を選ぶ予想なのか」を固めるためのcalibration logic。

v0.1 / v0.2で見られた、
RaceNote内の数値を実質的な総合スコアとして並べる挙動から離れ、
人力予想教師データで観測された **race-context-first / flexible evidence**
の判断様式を直接参照する。

このversionはまだ採用Forecast logicではない。
まず予想の軸を安定させるためのcalibration candidateである。

## 2. Mandatory human forecast evidence

Every forecast execution must read:

`racenote/evidence/human_forecast_evidence_202301.md`

This evidence is a few-shot reasoning reference, not a deterministic rulebook.

Preserve these principles:

1. ◎ is not highest generic score / highest win probability by definition.
   - ◎ = 「今回、自分なら一番買いたい馬」。
2. Race-level context comes first.
3. Evidence importance changes by race.
4. Concern does not automatically veto ◎.
5. A race may have no obvious safe axis, yet still require a chosen ◎.
6. Recent form is contextual:
   opponent strength / class / course / race content matter.
7. Do not copy historical examples literally.

## 3. Hard anti-mechanical rules

The following are forbidden as the primary selection mechanism:

- sorting by one aggregate / total / 総合 value
- adding RaceNote numeric fields into an implicit score
- choosing the largest Ability / Training / Stable / Trend value
- making a draft full-field numeric order before understanding the race
- explaining an already numeric-sorted list after the fact

Numeric values may support a judgment only **after** the race thesis and horse
comparison have been formed.

If the same marks would be produced merely by sorting one or more visible
numeric fields, the forecast must be reconsidered before Freeze.

## 4. Prediction sequence

### Step A — Read the race, not the horses first

Write a short `race_model` before selecting any horse:

- what kind of race is this?
- what is likely to separate the field?
- what evidence lane is especially meaningful here?
- what evidence lane is likely noisy / secondary?

No horse may be assigned ◎ at this step.

### Step B — Read every runner as a case

For each runner, extract only concise contextual notes:

- case_for: why this horse can be bought *in this race*
- case_against: why it may fail *in this race*
- context_hook: which race-model point matters most

Do not assign a numeric score.

### 4.1 Pedigree evidence

When RaceNote exposes `pedigree` / `pedigree_context`, treat it as one
contextual evidence lane.

Especially relevant when:
- newcomer / no prior race history
- lightly raced horse
- first meaningful distance change
- first surface / weak direct suitability evidence

Read:
- sire identity
- broodmare sire identity
- target venue + surface + exact-distance historical context
- target-relevant distance-range context
- starts / wins / top3 / sample-size band

Rules:
- pedigree is not a fixed-weight lane;
- no pedigree-only ◎;
- small-n is retained but interpreted with its sample size;
- do not turn a percentage into an automatic "suitable / unsuitable" label;
- if direct race evidence is strong, pedigree may remain secondary;
- if direct race evidence is absent, pedigree may become more informative,
  but uncertainty remains.

### 4.2 RaceReviewDB / Next-Watch evidence

When RaceNote exposes `racereview`, it must be reviewed before marks are
finalized.

Read RRDB as prior-run interpretation, not as a score.

Especially useful for:
- result understated by adjusted performance / last-3F;
- trouble or position recovery hidden by the finishing position;
- apparent good form aided by pace / position;
- repeated historical patterns;
- frozen Next-Watch S/A matches.

Rules:
- S/A never automatically becomes ◎ / ○ / ▲;
- NO_MATCH is neutral, not negative;
- no fixed RRDB weight exists;
- a strong current-condition mismatch may outweigh RRDB history;
- evidence from the same source run appearing in both `recent_runs` and
  `racereview` is one corroborated story, not two votes;
- raw trouble scores are descriptive and must not be interpreted as calibrated
  severity unless their RRDB contract says so.

### 4.2.1 RRDB reinterpretation / recompare

RRDB's primary role is to answer:

> Should the horse's visible prior result be taken at face value?

Use RRDB in two steps.

#### Step 1 — Reinterpret the prior run

For each relevant prior run, decide whether RRDB changes the meaning of the
visible result:

- `UPGRADE`: the finish likely understates the content;
- `DOWNGRADE`: the finish likely overstates the content;
- `CONFIRM`: RRDB supports the visible interpretation;
- `NEUTRAL`: RRDB adds no material interpretation.

This is not a score and does not directly assign a mark.

#### Step 2 — Return to the current race and recompare

After reinterpretation, compare the horse again in the **target race context**.

RRDB may move ◎ / ○ / ▲ / △ when:
- two candidates are otherwise close and RRDB becomes a genuine tie-breaker;
- a poor-looking recent result is reinterpreted upward and the horse already
  owns relevant direct evidence for today's conditions;
- a good-looking recent result is reinterpreted downward and another candidate
  has comparable or stronger current-condition evidence;
- direct evidence is weak / stale / internally inconsistent and RRDB resolves
  that uncertainty.

RRDB should not move marks when:
- one horse has clearly stronger current-condition evidence and RRDB only adds
  generic hidden/fragile context;
- Next-Watch S/A is the only reason;
- hidden_strength / fragile_form is the only reason;
- the reinterpretation has no clear relevance to today's course / distance /
  pace / class / running setup.

Important:
- there is no "RRDB may never overturn direct evidence" rule;
- there is also no "RRDB should cause mark changes" target;
- strong direct evidence raises the burden of proof, but does not make a horse
  immune to reinterpretation;
- old relevant direct evidence may become newly important when RRDB explains
  why recent finishes look worse than the underlying run;
- same-run recent comment + RRDB remain one evidence story, not two votes.

A useful mental model:

```text
visible past result
  -> RRDB reinterpretation
  -> revised understanding of that horse
  -> current-race comparison
  -> marks
```

The mark change is caused by the **revised current-race comparison**, not by
the RRDB label itself.

Each forecast trace must state:
- whether RRDB was available;
- that it was reviewed;
- whether it changed the decision;
- cited horse/run when used;
- why it was not used when available but non-decisive.

### Step C — Form a candidate cluster

Select typically 3–5 candidates.

For each candidate state:
- plausible winning / strong-running path
- main vulnerability
- evidence that is actually discriminating vs merely descriptive

### Step D — Choose ◎ by comparative judgment

Ask:

> If I had to buy one horse in this specific race, which horse's positive case
> remains most convincing after accounting for the race model and its own main
> weakness?

Then compare ◎ directly with ○ and ▲.

The answer may favor:
- the strongest horse,
- the best-suited horse,
- the horse with the most repeatable setup,
- a horse whose recent result underrates its content,
- or another context-specific case.

There is no universal hierarchy.

### Step E — Marks

- ◎ = 今回、自分なら一番買いたい馬
- ○ = ◎と最後まで比較した対抗
- ▲ = 上位を逆転できる第三候補
- △ = candidate clusterの残り

Full-field order is **not used to select ◎**.
If ranking output is needed for evaluation, create it only after marks are fixed.

## 5. Required calibration trace

Each race must preserve:

- `human_principles_used`: 1–3 principle IDs from the teacher evidence
- `race_model`
- `primary_question`: this race's central forecasting question
- `candidate_cases`: 3–5 concise candidate case summaries
- `main_vs_second`
- `main_vs_third`
- `why_not_numeric_leader`:
  - if ◎ is not the obvious numeric leader, explain why;
  - if ◎ is also the numeric leader, explain why the judgment would still hold
    without relying on that numeric rank.
- `strongest_counter`
- `reversal_condition`
- `rrdb_evidence`:
  - available
  - reviewed
  - used_in_decision
  - cited horse refs / decision roles when used
  - reason_not_used when not used

Private chain-of-thought is not required; these are concise auditable summaries.

## 6. Calibration phase

Current project status is **CALIBRATION_HOLD**.

Do not consume a new unused eligible PACI day while this hold is active.

Allowed development material:

- human forecast evidence
- already-used BTDAY-0001 dates:
  - 2026-02-08
  - 2026-05-23
- already-used BTDAY-0002 dates:
  - 2026-03-08
  - 2026-04-26
- already ineligible / result-exposed dates for explicit DEV replay

Calibration replay is not blind performance evidence and must not be counted in
Forecast hit-rate promotion metrics.

Use a small representative set, normally 6–12 races, rather than another full
two-day 48–72R turn.

Goal of calibration:
- predictions no longer collapse into numeric sorting
- race_model materially differs by race
- candidate comparisons are specific
- teacher principles are visibly reflected
- user can understand why the marks were chosen

Only after the Research thread explicitly clears calibration may the project
resume random unused two-day blind turns.

## 7. Missing evidence

If a desired human-style judgment needs evidence absent from RaceNote:
- do not invent it;
- record the gap;
- make the best forecast from available evidence;
- treat repeated gaps as RaceNote research input.

Do not change RaceNote schema during a calibration replay.

## 8. Result discipline

Calibration is for forecast behavior, not result optimization.

Do not use target results to decide whether a calibration forecast "looks human".
Result-aware tuning resumes only after the forecast axis is accepted and clean
blind research is restarted.
