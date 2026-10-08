# RaceNote v0.5.2 Candidate — Protected Candidate Set / Aggressive Role Assignment

Status: **PROMOTED BASELINE — PROSPECTIVE v0.5.1 vs v0.5.2 A/B COMPLETE AT BTDAY-0057..0060**  
Date: 2026-10-07  
Logic ID: `RaceNote-Human-Context-Reader-0.5.2-candidate`

## 1. Why v0.5.2 exists

v0.5.0 and v0.5.1 exposed a useful trade-off.

- v0.5.0 showed the desired attacking character: ◎ could be chosen for a stronger win route rather than mere safety, and ▲ could represent a genuinely asymmetric route outside ordinary ranking. That character produced meaningful upside in ◎ win, ◎→▲ exacta and trifecta settlement.
- v0.5.0 also allowed role assignment to destabilize the five-horse candidate set, especially the lower boundary.
- v0.5.1 repaired that structural weakness with an explicit ordinary-five plus six-to-five compression, but the protected anchors can make the forecast flatter than intended.

v0.5.2 therefore keeps **v0.5.1 candidate-set protection** while restoring **v0.5.0-style attacking role assignment**.

Prediction accuracy and betting return are separate evidence channels. A higher hit rate alone is not the objective, and a longer-priced horse alone is not a success. The intended profile is to preserve enough candidate-set stability to avoid wasteful churn while allowing ◎ and ▲ to create materially asymmetric payout routes.

## 2. Reader invariants

v0.5.2 uses a byte-identical model-facing `normal_view` to v0.5.0 and v0.5.1.

There is no new evidence surface. v0.5.2 changes only judgment procedure.

The lane must not read target result, target-day final odds/popularity/payouts, or sibling-lane forecasts before Freeze.

## 3. Decision procedure

### Step A — form the race model

Read the complete normal_view and state what decides the race. Do not start from public marks.

### Step B — build the ordinary five as a protected candidate set

Choose five horses that deserve to survive on ordinary ability, repeatability, race shape and pre-race context **before creating any vacancy for an external shot**.

Record them as:

```text
ordinary_five = [ordinary_rank_1, ordinary_rank_2, ordinary_rank_3, ordinary_rank_4, ordinary_rank_5]
```

Unlike v0.5.1, these positions are **not protected public ◎/○ roles**. They record the ordinary/repeatability ordering only.

### Step C — aggressively assign ◎ and ○ inside the ordinary five

Choose ◎ and ○ from the ordinary five only.

◎ must be selected under:

`WIN_FIRST_NOT_PLACE_FIRST`

The question is not “which horse is safest to hit the board?” but “which horse has the clearest realistic route to winning this race?”

It is legal and expected for ◎ to differ from `ordinary_five[0]` when another ordinary-five horse has a more decisive win route. Do not manufacture contrarianism; the re-ranking needs a concrete race-shape / ability / condition case.

○ is the next strongest mainline win/contender route after ◎.

This is the deliberate v0.5.0 inheritance: **candidate membership remains stable, but ranking inside that set may be aggressive.**

### Step D — search outside the ordinary five for exactly one asymmetric challenger

When there are six or more runners, choose one external horse whose route is not merely “sixth best”.

The required mode is:

`ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK`

The challenger should represent a distinct route such as a pace monopoly, collapse setup, latent class jump, condition-driven rebound or another materially different winning path.

Do not use or infer target-day price/popularity. “Likely to be a longshot” is not evidence.

### Step E — six-to-five compression

Compare the ordinary five plus challenger.

#### ADMIT_CHALLENGER

- challenger enters as ▲;
- audited ◎ and ○ remain fixed;
- challenger may displace one ordinary-five horse other than ◎ or ○;
- the displaced horse must be explicit.

#### KEEP_ORDINARY_FIVE

- challenger is excluded;
- all ordinary-five horses remain;
- ▲ is chosen from the three ordinary-five horses other than ◎ and ○.

#### NO_EXTERNAL_CHALLENGER

Only for exactly five runners.

## 4. Required role audit

In addition to `candidate_compression`, v0.5.2 requires:

```json
"role_assignment": {
  "honmei_horse_no": 4,
  "second_horse_no": 1,
  "honmei_win_case": "ordinary rankでは1が僅かに上だが、4は主導権を取った時の勝ち切り経路が最も明確。",
  "second_case": "1は能力と再現性が高く、4が作る主線の次位として残す。",
  "honmei_selection_mode": "WIN_FIRST_NOT_PLACE_FIRST",
  "shot_selection_mode": "ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK",
  "ranking_reason": "複勝圏の安全性ではなく勝率側を優先して4を◎へ再順位付けした。"
}
```

The validator checks structure and identity. It does not mechanically score racing evidence.

## 4.1 Research-oriented reasoning capture — prose-only revision 2026-10-08

This revision changes **how the already-made judgment is recorded**, not the
decision procedure in Steps A-E. Use the same normal_view, ordinary-five
selection, WIN_FIRST_NOT_PLACE_FIRST ◎/○ choice, one independent ▲ challenger,
six-to-five compression and final mark assignment. Do not run another ranking
pass, add thresholds, change the model-facing Reader, or select marks to improve
the research labels. The record remains
`RaceNote-Human-Context-Reader-0.5.2-candidate`.

Once the five marks and the actual reasons are decided, keep the **existing
Decision Core fields** but make the reasoning genuinely discriminative:

- `race_model`: name the concrete condition that defines today's main race
  scenario (position, pace, class, course or condition), and, **where material**,
  which plausible departure from that scenario would threaten the main line.
  Do not invent alternative scenarios just to fill a checklist.
- `role_assignment.honmei_win_case`: specify why ◎ can *win*, rather than
  merely place, with one or more concrete pre-race observations. If the path
  depends on a particular pace/position/smooth trip, state that dependency
  plainly instead of declaring confidence.
- `role_assignment.second_case` and `ranking_reason`: preserve the real
  distinction between ◎ and ○. State the decisive **reason for ◎ over ○**
  when one exists; if both are very close, record the actual tie-break and
  residual uncertainty without pretending the gap is clear. Do not force
  ordinary rank 1 to be ◎.
- `boundary_review.reason`: explain the real final △2 vs closest excluded
  alternative comparison using their contrasting evidence when a meaningful
  alternative exists. Say when the margin is thin, if it truly is. Keep the
  original `alternative_horse_no` meaning; no newly selected runner or
  manufactured sixth candidate is allowed.
- `candidate_compression.reason`: keep the independent challenger admission
  or rejection rationale specific to that horse's alternative win path.
  Do not replace the six-to-five audit with a confidence judgment.
- `single_shot_case` and `mainline_cases`: retain their original roles and
  actual supporting race evidence. Do not impose new ordering or scoring.

**Evidence specificity:** writing "most reproducible", "clear winning path",
"stable second", or "better boundary" without the race-specific observation
does not record a useful comparison. Replacing horse names or numbers in a
shared sentence is not a genuine reason. When the evidence is ambiguous, say
so; do not fabricate a neat contrast, hidden doubt, objective probability or
post hoc winning condition.

**Output boundaries:** do not add A/B/C, confidence percentages, numeric
scores, extra schema keys, required subheadings, or artificial sentence
templates. `reader_facing_reason` remains one compact, natural race comment
under `FORECAST_READER_FACING_PROSE_v0_1.md`, not a transcript of the audit
fields. Keep all existing validation, hashes, Freeze and market/result
firewalls unchanged.

Before saving each venue, compare its race explanations for identical or
near-identical wording after replacing horse names, numbers and venue names.
If a repeated passage conceals materially different reasoning, repair the
prose **only**, using already-seen clean Reader evidence. Do not revise the
horse selection, introduce evidence after Freeze, or force variation where
the evidence really is the same.

For analysis, preserve a separate annotation/output-policy cohort:
records authored using this guidance can be compared with older v0.5.2
FROZEN records for **mark/outcome metrics**, but differences in prose quality
must not be treated as pre-existing features of the older cohort. Use the
existing `base_main_sha` / authored-session provenance to distinguish
generations; do not backfill or rewrite historical frozen Decision Cores.

## 5. What v0.5.2 must not become

v0.5.2 is not:

- “pick a popular horse for ◎ and a random longshot for ▲”;
- a fixed-weight score;
- a requirement to change ◎ from ordinary rank 1;
- a requirement to admit the challenger;
- an attempt to maximize ▲ top-3 rate;
- an attempt to maximize raw hit rate at the expense of payout shape.

A flat forecast that raises hit rate while removing the asymmetric payout route is not automatically an improvement.

## 6. Evaluation priority

The prospective test is v0.5.1 vs v0.5.2.

Evaluate prediction and settlement separately.

Prediction:
- ◎ win / top-2 / top-3;
- ▲ win / top-3;
- winner-in-five;
- average actual top-3 captured;
- ordinary-five coverage before compression;
- challenger admission and displacement outcomes.

Settlement:
- ◎ win and place;
- quinella ◎-○ / ◎-▲;
- exacta ◎→○ / ◎→▲;
- trio;
- trifecta.

The central v0.5.2 question is:

> Can v0.5.2 recover v0.5.0's win-first / asymmetric payout character without reintroducing v0.5.0's candidate-boundary damage?

## 7. v0.4.x status

v0.4.6 remains preserved as a historical baseline and can be used retrospectively. It is no longer required as a prospective authoring lane for the new v0.5.1 vs v0.5.2 experiment.

## 8. Baseline promotion — 2026-10-07

The prospective v0.5.1 vs v0.5.2 comparison is complete for BTDAY-0057 through BTDAY-0060, 132 races total.

Promotion evidence is intentionally split into prediction and settlement channels.

Prediction:
- v0.5.1 ◎ wins: 32/132 = 24.2%
- v0.5.2 ◎ wins: 35/132 = 26.5%
- v0.5.1 ◎ top-2: 50.0%
- v0.5.2 ◎ top-2: 44.7%
- v0.5.1 ◎ top-3: 61.4%
- v0.5.2 ◎ top-3: 56.1%
- v0.5.1 winner-in-five: 71.2%
- v0.5.2 winner-in-five: 70.5%

The lower top-2/top-3 rate is not treated as an automatic regression because the v0.5.2 objective is win-first asymmetric settlement rather than place-first flattening.

The v0.5.2 role audit changed ◎ away from ordinary_five[0] in 52 races. Across those re-ranks:
- finish improved in 31 races;
- finish worsened in 21 races;
- 11 additional ◎ wins were created;
- 6 ordinary-rank-1 wins were lost;
- net ◎ win creation: +5.

Settlement over the same 132 races:
- ◎ win ROI: v0.5.1 60.8% / v0.5.2 69.2%
- ◎-○ quinella ROI: 48.8% / 61.4%
- ◎-▲ quinella ROI: 90.0% / 83.8%
- ◎→○ exacta ROI: 33.9% / 72.1%
- ◎→▲ exacta ROI: 54.0% / 76.2%
- combined ◎→○▲ exacta ROI: 43.9% / 74.2%
- trio ROI: 54.3% / 69.5%
- trifecta ROI: 34.0% / 84.8%

BTDAY-0060 supplied the clearest asymmetric day-level evidence, including positive v0.5.2 ROI in the combined quinella, both exacta routes, trio and trifecta while prediction top-2/top-3 rates were lower than v0.5.1.

Decision:
- v0.5.2 is promoted to the current RaceNote forecast baseline.
- v0.5.1 remains preserved as the historical structural-safety baseline.
- the v0.5.1/v0.5.2 A/B harness remains available for audit/reproduction but is no longer required for ordinary prospective operation.
- future improvements should preserve the v0.5.2 candidate-set protection and WIN_FIRST_NOT_PLACE_FIRST role behavior unless new prospective evidence justifies replacing them.

## 9. Current operation

Ordinary BTDAY and forward daily use should use the single-day v0.5.2 path documented in:

`RACENOTE_V052_SINGLE_DAY_RUNBOOK_v0_1.md`

The A/B path remains historical/research infrastructure and is not the default operational route.
