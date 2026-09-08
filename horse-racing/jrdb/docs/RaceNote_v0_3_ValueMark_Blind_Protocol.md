# RaceNote v0.3 Value-Mark Blind Protocol

## Status

**PROSPECTIVE CANDIDATE / RESULT-BLIND UNTIL FREEZE**

This protocol tests the user's proposed mark semantics without changing the already-tested v0.2 axis score.

## 1. Control and candidate

### v0.2 control

Use the tested v0.2 score unchanged. Pure score order becomes:

`◎ / ○ / ▲ / △1 / △2`

### v0.3 candidate

First compute the exact same v0.2 pure top-five order `P1..P5`.

- `◎ = P1`
- `○ = P2`
- `▲` is a value-oriented role selected only from `P3..P5`
- the two remaining horses are printed as `△1 / △2` in their original pure-score order

If no justified value candidate exists, use:

- `▲ = P3` as an orthodox third-ranked horse
- `△1 = P4`
- `△2 = P5`

Thus v0.3 does **not** change the five-horse candidate set, ◎, or ○. It tests whether moving a justified value horse from pure rank 4/5 into ▲ improves the ticket mapping while retaining the orthodox third-ranked horse inside the trio structure.

## 2. Value eligibility for ▲

To avoid fitting a new rule to the already-settled 144R, reuse the already-tested v0.2 `☆` disagreement rule, restricted to pure ranks P3..P5.

For each P3..P5 horse:

1. read pre-target `base_win_rank` only;
2. compute `market_gap = base_win_rank - min(pure_prediction_rank, ability_rank)`;
3. compute `support = PaceStyleFit + DistanceFit + FrameFit`;
4. require `market_gap >= 3`;
5. require `support >= 1.45`.

If multiple horses qualify, choose:

1. largest market gap;
2. then largest support.

Target-race final odds/popularity remain prohibited before freeze.

If none qualifies, ▲ remains the orthodox P3 horse.

## 3. Confidence

Keep the tested v0.2 confidence rule unchanged for this block.

- A: v0.2 score gap to second >= 0.07, ◎ distance evidence is neither insufficient nor contradictory, and ◎ PaceStyleFit >= 0.45
- C: score gap < 0.018, or ◎ distance evidence is insufficient/contradictory
- B: otherwise

Confidence is frozen before HJC and evaluated after settlement as a purchase-decision aid.

Primary calibration checks:

- ◎ win/top2/top3 by A/B/C
- win/place return by A/B/C
- quinella/trio return by A/B/C
- race counts and payout concentration by A/B/C

No confidence threshold becomes a purchase rule from this block alone.

## 4. User-facing output

Use `RaceNote_User_Facing_Prediction_Output_v0_3_Candidate.md` with:

- `レース短評` first line: `自信度：A/B/C`
- one concise race-shape / upset-risk sentence when useful
- ◎ comment: buy reason + meaningful caution
- ○ comment: support + why below ◎ / reversal condition when identifiable
- ▲ comment: value reason; if no value role, explicitly say it is an orthodox evaluation slot
- `△ x,y` only; left is △1, right is △2

Raw IDM/total values may be used internally but are not mechanically copied into the standard short comment.

## 5. Frozen betting comparisons

All are 100-yen unit diagnostics unless the active betting contract specifies otherwise.

### Quinella

- `Q2_v0.2`: ◎-○ / ◎-pure▲
- `Q2_v0.3`: ◎-○ / ◎-value▲
- `Q4`: ◎ to all four other top-five horses (diagnostic)

### Trio

- Policy A: six tickets using ◎ plus every pair among ○/▲/△1/△2
- Policy B: five tickets excluding only `◎△1△2`

Because v0.3 can change role labels without changing top-five membership, Policy A is membership-invariant while Policy B can change which single combination is excluded.

## 6. Primary questions

1. Does v0.2 axis quality continue to hold on another untouched block?
2. Does v0.3 improve quinella `◎-▲` economics and/or Q2 total without degrading hit capture excessively?
3. Does moving pure P3 to △ preserve trio performance as intended?
4. Is A/B/C confidence meaningfully calibrated?
5. Are short comments concise, evidence-grounded, and useful as purchase-decision support?

## 7. Blind order

1. choose untouched dates from BAC/Archive identity metadata only;
2. acquire RaceNote with target date excluded;
3. validate Reader View;
4. compute v0.2 pure order;
5. compute v0.3 role reassignment;
6. freeze marks, confidence, comments, and betting policies;
7. only then acquire HJC;
8. normalize HJC into `result_cache/`;
9. settle v0.2 and v0.3;
10. treat any newly discovered betting rule as post-hoc until validated on another untouched block.
