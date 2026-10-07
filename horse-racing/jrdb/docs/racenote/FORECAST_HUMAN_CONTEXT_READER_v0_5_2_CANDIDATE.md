# RaceNote v0.5.2 Candidate — Protected Candidate Set / Aggressive Role Assignment

Status: **RESEARCH CANDIDATE — CLEAN-BLIND v0.5.1 vs v0.5.2 VALIDATION REQUIRED**  
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

No production/current pointer changes are made by this candidate.
