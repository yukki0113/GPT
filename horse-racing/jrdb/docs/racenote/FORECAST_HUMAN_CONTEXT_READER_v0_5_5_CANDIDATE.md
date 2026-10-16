# RaceNote v0.5.5 Candidate — Lean Reader / Lean Decision Core / Win Confidence

Status: **CURRENT CANDIDATE FOR NEW CLEAN-BLIND RUNS**  
Logic ID: `RaceNote-Human-Context-Reader-0.5.5-candidate`  
Contract revision: `v055-win-confidence-lean-reader-r2`

## 1. Purpose

v0.5.5 keeps the established v0.5.4 evidence sources and horse-selection semantics while reducing both sides of T2 work:

1. the model-facing Reader is a deterministic lean projection;
2. the persisted Decision Core contains only irreducible forecast judgments;
3. A/B/C means confidence that ◎ wins the race.

The goal is to reduce repeated context and repeated authored prose without replacing horse-race reasoning with a score or model-generated summary.

## 2. Evidence boundary

### 2.1 Bound source evidence

The pre-result evidence sources remain the same as v0.5.4:

- clean RaceNote / forecast_prep;
- RRDB v0.5;
- KYI supplemental context;
- historical RaceLap / SRB context.

These sources remain bound by hashes and as-of rules. Target result, target final market and payout information remain unavailable until Freeze verifies.

### 2.2 Model-facing Reader

T2 does **not** read the former verbose enriched presentation.

For each race it reads the complete bound **v0.5.5 Lean Model Reader**:

`v055-lean-model-reader-r2`

This projection is deterministic field selection. It does not use an LLM to summarize or preselect horses.

The model Reader keeps:

- race conditions and race trends;
- runner identity;
- primary/secondary/context evidence blocks;
- compact recent runs;
- compact older history and historical profile;
- RaceReview conclusions;
- current training/condition context;
- pedigree identity and one pedigree-stat representation;
- compact RRDB signals;
- compact historical RaceLap shape;
- minimal KYI provider-reference hints.

The model Reader removes or consolidates:

- repeated provenance and policy text;
- RaceReview copies of source-run facts already present in recent runs;
- duplicated sire/broodmare-sire statistics;
- verbose history-coverage metadata;
- repeated RRDB contract/provenance fields;
- repeated RaceLap archive/member/policy metadata;
- hidden-value fields already represented in normal evidence;
- historical final odds/popularity that are not needed for current-race reasoning.

Complete source evidence remains reproducible from the sealed source assets. The lean Reader is the sole T2 model input.

Evidence priority remains:

`DATA / TRENDS > RACEREVIEW >= ABILITY`

No additive score, signal count, IDM-gap rule or deterministic ranking may replace model judgment.

## 3. Candidate and mark selection

### 3.1 Ordinary five

Select five horses under the ordinary race scenario before considering an outside challenger.

### 3.2 ◎ and ○

◎ and ○ must come from the ordinary five.

◎ is the horse judged most likely to **win** the race, not the safest horse to place.

○ is the second principal winning route. No separate persisted ◎-vs-○ essay is required.

### 3.3 External challenger and ▲

Search at most one horse outside the ordinary five for a genuinely asymmetric winning route.

The challenger may attack only the lowest-ranked ordinary horse that is not ◎ or ○.

KEEP is the default. Admit only when current evidence is sufficient to replace that fixed boundary horse.

If admitted, the challenger becomes ▲. Otherwise ▲ is chosen from the retained non-anchor ordinary horses.

Route diversity is a tie-breaker only.

## 4. Win confidence

`honmei_win.confidence` means:

> **confidence that ◎ wins this race**

It does not mean confidence that ◎ merely finishes ahead of ○.

- **A** — high confidence that ◎ wins.
- **B** — ◎ is the preferred winner, but meaningful winning alternatives or risks remain.
- **C** — ◎ is selected, but win confidence is low because the race is materially uncertain.

Confidence is a whole-race judgment. Fixed IDM gaps, A5/A7, pairwise distance and signal counts do not assign A/B/C.

The prediction freezes:

- why ◎ can win;
- the main reason ◎ may fail to win;
- A/B/C.

Pairwise ◎>○ and IDM-gap diagnostics are downstream research only.

## 5. Lean Decision Core

Each race persists:

- `venue`, `race_no`
- `marks`: ◎ ○ ▲ △ △
- `candidate_selection`
  - ordinary five
  - external challenger
  - excluded horse
  - KEEP / ADMIT / no-challenger
  - one boundary reason
- `honmei_win`
  - `evidence`
  - `main_risk`
  - `confidence`
- `shot_case.case`
- `rrdb_refs`
- `reader_facing_reason`

The following are not persisted:

- race-wide authored summary;
- four separate mainline essays;
- separate ○ essay;
- separate ◎-vs-○ ranking essay;
- duplicated challenger/boundary essays;
- fixed mode strings;
- per-race prose-authorship metadata;
- prediction-time A5/A7 fields.

## 6. Reader-facing output

Normal display is:

- ◎ ○ ▲ △ △
- confidence A/B/C
- one short reader-facing note

The note is model-authored from the completed race judgment. It has no fixed sentence count or fixed character target and must not be constructed by a deterministic template.

## 7. Freeze and result unlock

Lifecycle:

```text
T1_SEALED
  -> AUTHORING_IN_PROGRESS
  -> AUTHORING_COMPLETE
  -> FORMAT_AUDIT_COMPLETE
  -> FROZEN_WITH_CONFIDENCE
  -> RESULT_UNLOCKED
  -> RESULT_EVALUATED
```

The Freeze already contains win confidence. There is no separate normal `confidence_pre_result.json` authoring stage.

Before result unlock, the frozen handoff must verify:

- `status=FROZEN_CLEAN_BLIND`
- `confidence_frozen=true`
- `confidence_meaning=HONMEI_WIN_CONFIDENCE`
- `result_opened=false`
- `target_market_opened=false`

## 8. Evaluation

Primary confidence evaluation:

1. ◎ win rate;
2. ◎ single-win return;
3. ◎ top-2 / top-3 as supporting diagnostics;
4. winner-in-five;
5. downstream ◎-○ / ◎-▲ betting-layer performance.

Pairwise ◎>○ remains optional diagnostic analysis.

## 9. Revision boundary

r1 and older v0.5.x frozen assets remain immutable reproduction evidence.

A session initialized under r1 must not be rewritten in place to r2 because the model Reader projection changed. New work uses a newly initialized r2 session.
