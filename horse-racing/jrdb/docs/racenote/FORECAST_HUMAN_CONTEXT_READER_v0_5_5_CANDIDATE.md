# RaceNote v0.5.5 Candidate — Lean Reader / Prediction Freeze / Confidence Review

Status: **CURRENT CANDIDATE FOR NEW CLEAN-BLIND RUNS**  
Logic ID: `RaceNote-Human-Context-Reader-0.5.5-candidate`  
Contract revision: `v055-prediction-freeze-confidence-review-r4`

## 1. Purpose

v0.5.5 r4 keeps the r3 horse-selection logic, Lean Model Reader and editorial short-comment policy, but separates two judgments that must not be frozen at the same moment:

1. **Forecast judgment** — ◎ ○ ▲ △ △ and the reasons for those marks.
2. **Win-confidence judgment** — how strongly the already frozen ◎ should be supported as the winner / single-win axis.

The prediction is frozen first. Confidence is reviewed afterward while the target result and target market are still closed. This gives confidence research a legitimate reconsideration stage without allowing the prediction itself to move.

## 2. Evidence boundary

The underlying pre-result evidence sources remain unchanged:

- clean RaceNote / forecast_prep;
- RRDB v0.5;
- KYI supplemental context;
- historical RaceLap / SRB context.

T2 reads the complete bound `v055-lean-model-reader-r2`. The projection remains deterministic field selection; it does not summarize, rank or preselect horses.

No target result, payout or target final-market information may be opened before both prediction Freeze and confidence Freeze verify.

Evidence priority remains:

`DATA / TRENDS > RACEREVIEW >= ABILITY`

No additive score, signal count or fixed IDM-gap rule may replace model judgment.

## 3. Forecast judgment

### 3.1 Ordinary five

Select five horses under the ordinary race scenario before considering an outside challenger.

### 3.2 ◎ and ○

◎ and ○ must come from the ordinary five.

◎ is the horse judged most likely to **win** the race, not the safest horse to place.

○ is the second principal winning route.

### 3.3 External challenger and ▲

Search at most one horse outside the ordinary five for a genuinely asymmetric winning route.

The challenger may attack only the lowest-ranked ordinary horse that is not ◎ or ○. KEEP is the default; admit only when current evidence is sufficient to replace that fixed boundary horse.

If admitted, the challenger becomes ▲. Otherwise ▲ is chosen from the retained non-anchor ordinary horses.

Route diversity is a tie-breaker only.

## 4. Lean Decision Core

For r4 each race persists:

- `venue`, `race_no`
- `marks`: ◎ ○ ▲ △ △
- `candidate_selection`
- `honmei_win.evidence`
- `honmei_win.main_risk`
- `shot_case.case`
- `rrdb_refs`
- `reader_facing_reason`

**A/B/C is not part of the r4 Decision Core.**

The Decision Core therefore answers:

> Who is the forecast winner, why can that horse win, and what is the principal risk?

It does not answer how strongly that frozen ◎ should later be backed.

## 5. Reader-facing note

The short note remains editorial rather than a Decision Core summary:

> **write the one point from this race that is most useful for a reader to notice.**

It may focus on ◎'s winning case, its risk, pace/position, ▲, uncertainty, or another race-specific point. It need not enumerate ○/▲ or every marked horse.

The note is for an ordinary racing reader, not for the audit layer. Internal evidence may support the judgment, but **must be translated into ordinary racing language before it appears in `reader_facing_reason`**. Do not expose internal metric/plumbing labels such as `IDM`, `RRDB`, `SRB`, `KYI`, `調教指数`, `状態指数`, Reader/Decision-Core terminology, hashes, or missing-value tokens such as `None`.

Examples:

- NG: `IDM64.0と調教・状態のバランスが最上位。`
- OK: `近走内容はこの組み合わせでも上位。追い切りの気配も悪くなく、流れに乗れれば勝ち切りまで。`
- NG: `IDM差が大きい。`
- OK: `近走内容では一枚上と見た。`

Translation is semantic, not cosmetic: merely removing the metric name while retaining a day-wide fill-in-the-blanks template is not acceptable. Each race must independently choose the one reader-useful point. Obvious variable-substitution templates across a card are a quality failure even when every sentence is grammatically valid.

There is no sentence-count target and no character-count target. Validation remains an accident guard only; it may reject internal terminology and structural template repetition, but must not prescribe which racing point the model chooses.

## 6. Prediction Freeze

After all races pass format/quality audit, freeze the prediction.

For r4 the prediction handoff is:

`status=PREDICTION_FROZEN_CLEAN_BLIND`

and must show:

- `confidence_frozen=false`
- `confidence_pending=true`
- `result_opened=false`
- `target_market_opened=false`

After this Freeze, marks, Decision Core, short comments and their evidence bindings are immutable.

This Freeze is deliberately **not** sufficient for result unlock.

## 7. Confidence Review

Confidence Review starts only after Prediction Freeze verifies.

The review sees the already frozen ◎ and asks:

> **How strongly can this ◎ be supported as the winner / single-win axis?**

The grades are:

- **A — ACTIVE WIN SUPPORT**  
  ◎ has a clear enough winning advantage that it can be actively backed as the main win bet. A does not require near-certainty and does not require the absence of plausible upset routes.

- **B — PREFERRED BUT CONTESTED**  
  ◎ is the preferred winner, but comparison with credible alternatives or the principal risk is strong enough that the win bet should not receive A-level support.

- **C — LOW WIN CONVICTION**  
  ◎ remains the frozen forecast winner, but confidence in the winner selection itself is low.

There is **no target A rate** and no quota. The purpose is not to manufacture A races; it is to avoid defining A so strictly that only near-certain races qualify.

Pairwise ◎>○, A5/A7, fixed IDM gaps and signal counts remain diagnostic only.

### 7.1 Reconsideration is allowed

Before Confidence Freeze, the confidence draft may be rewritten.

For example, B may be reconsidered as A when the reviewer concludes that the frozen ◎ is sufficiently strong to back actively under the operational A definition.

This is not a forecast rewrite: ◎ and every prediction field are already frozen and cannot change.

### 7.2 Confidence artifact

Each confidence record contains only:

- `venue`
- `race_no`
- frozen `honmei`
- `confidence`: A / B / C
- concise `reason`

The artifact is bound to the Prediction Freeze SHA.

## 8. Confidence Freeze and result unlock

Lifecycle:

```text
T1_SEALED
  -> AUTHORING_IN_PROGRESS
  -> AUTHORING_COMPLETE
  -> FORMAT_AUDIT_COMPLETE
  -> PREDICTION_FROZEN_CLEAN_BLIND
  -> CONFIDENCE_REVIEW
  -> CONFIDENCE_FROZEN_CLEAN_BLIND
  -> RESULT_UNLOCKED
  -> RESULT_EVALUATED
```

Result unlock requires final verification of both immutable layers.

The confidence handoff must show:

- `status=CONFIDENCE_FROZEN_CLEAN_BLIND`
- `confidence_frozen=true`
- `confidence_meaning=HONMEI_WIN_CONFIDENCE`
- prediction Freeze SHA binding
- `result_opened=false`
- `target_market_opened=false`

## 9. Evaluation

After result unlock evaluate at minimum:

1. total ◎ win / top2 / top3;
2. winner-in-five and top3 capture;
3. A/B/C counts;
4. A/B/C ◎ win rates;
5. A/B/C ◎ single-win return when HJC payout is available.

Downstream ◎-○ / ◎-▲ betting strategies remain a separate betting layer.

## 10. Revision boundary

Existing r1/r2/r3 sessions and Freezes remain immutable reproduction evidence. Their embedded confidence must not be rewritten or extracted into a synthetic r4 artifact after results are known.

Only newly initialized r4 sessions use the two-stage Prediction Freeze / Confidence Freeze lifecycle.
