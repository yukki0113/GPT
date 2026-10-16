# RaceNote v0.5.5 Candidate — Lean Win-Confidence Forecast Contract

Status: **CURRENT CANDIDATE FOR NEW CLEAN-BLIND RUNS**
Logic ID: `RaceNote-Human-Context-Reader-0.5.5-candidate`
Contract revision: `v055-win-confidence-lean-r1`

## 1. Objective

v0.5.5 keeps the established RaceNote horse-selection model while reducing the amount of model-authored state that must be generated, validated and frozen for every race.

The forecast has three jobs:

1. select five horses without allowing role assignment to destabilize the candidate set;
2. assign ◎ / ○ / ▲ with ◎ chosen for winning rather than placing;
3. state how confident the model is that ◎ wins the race.

The persisted forecast contains only judgments that cannot be reconstructed later from the sealed Reader. Derived diagnostics such as IDM gaps, pairwise ◎>○ distance, debut/obstacle flags, A5/A7 thresholds or result metrics are not part of the prediction record. They may be recomputed during research.

## 2. Evidence

Each race is authored after reading the complete sealed, market-blind Reader.

Evidence priority remains:

`DATA / TRENDS > RACEREVIEW >= ABILITY`

RRDB v0.5, historical SRB race-lap context and KYI hidden-value context remain contextual evidence. They do not create additive scores, automatic promotions, automatic ▲ assignments or automatic confidence grades.

Target results, final target odds, final target popularity and target payouts must remain unopened until the immutable prediction Freeze verifies successfully.

## 3. Candidate and mark selection

### 3.1 Ordinary five

Select and order five horses under the ordinary race scenario before searching for an outside challenger.

### 3.2 ◎ and ○

◎ and ○ are the first two marks within that ordinary five.

◎ is selected under a win-first objective: choose the horse judged most likely to win the race, not the horse judged safest to place.

○ is the second winning route. No separate persisted pairwise-ranking essay is required.

### 3.3 One external challenger

Search at most one horse outside the ordinary five for a genuinely asymmetric winning route.

The external challenger may challenge only the lowest-ranked ordinary horse that is not ◎ or ○.

Default decision is KEEP. Admit the challenger only when current-condition evidence is sufficient to replace that fixed boundary horse.

If admitted, the challenger becomes ▲. If kept out, ▲ is selected from the retained non-anchor ordinary horses.

Route novelty is a tie-breaker, not an automatic promotion rule.

## 4. Win confidence

`honmei_win.confidence` means:

> **confidence that ◎ wins this race**

It does not mean confidence that ◎ finishes ahead of ○.

- **A** — the model has high confidence that ◎ wins.
- **B** — ◎ is the preferred winner, but meaningful winning alternatives or risks remain.
- **C** — ◎ is still the selected winner, but the race is materially uncertain or close enough that win confidence is low.

Confidence is a model judgment based on the whole race. No fixed IDM-gap threshold, signal count or deterministic score can assign A/B/C.

The frozen record keeps:
- the main evidence for ◎ winning;
- the main risk to ◎ winning;
- A/B/C.

Those three fields are the prospective research record. Pairwise ◎>○, IDM gaps, A5/A7 and similar diagnostics are evaluated later and are not prediction-time requirements.

## 5. Lean Decision Core

Every race persists exactly these semantic items:

- `venue`, `race_no`
- `marks`: ◎, ○, ▲, △, △
- `candidate_selection`
  - ordinary five
  - external challenger
  - excluded horse
  - KEEP / ADMIT / no-challenger decision
  - one boundary reason when a challenger exists
- `honmei_win`
  - `evidence`
  - `main_risk`
  - `confidence`
- `shot_case.case`: why ▲ has a distinct winning route
- `rrdb_refs`: only RRDB horses that actually informed the final judgment
- `reader_facing_reason`: short reader-facing note

The following v0.5.4 fields are not part of the v0.5.5 Decision Core:

- race-wide authored summary;
- four separate mainline horse essays;
- separate ○ case;
- separate ◎-vs-○ ranking essay;
- duplicated external-challenger and boundary essays;
- fixed selection-mode strings;
- per-race prose-authorship metadata.

The Reader remains complete. Only the newly authored persistence layer is reduced.

## 6. Reader-facing output

Normal RaceNote display is:

- ◎ ○ ▲ △ △
- confidence A/B/C
- one short reader-facing note

The note is model-authored from the same completed race judgment. It need not restate the audit fields, mention every mark or follow a fixed sentence count. It must not expose internal contract/plumbing terms or be generated from a deterministic template.

## 7. Freeze and result unlock

A verified v0.5.5 Freeze already includes win confidence inside each Decision Core.

Therefore there is no separate `confidence_pre_result.json` authoring stage in normal v0.5.5 operation.

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

The frozen day handoff must state:

- `confidence_frozen=true`
- `confidence_meaning=HONMEI_WIN_CONFIDENCE`
- `result_opened=false`
- `target_market_opened=false`

before results may be opened.

## 8. Evaluation

Primary confidence evaluation is by confidence grade:

1. ◎ win rate;
2. ◎ single-win return when payout data are evaluated;
3. ◎ top-2 / top-3 as supporting diagnostics;
4. five-horse winner capture;
5. later betting-layer evaluation of ◎-○ / ◎-▲ combinations.

Pairwise ◎>○ remains an optional diagnostic only.

Betting strategy is downstream from the forecast contract. v0.5.5 does not hard-code stake sizing or ticket construction.
