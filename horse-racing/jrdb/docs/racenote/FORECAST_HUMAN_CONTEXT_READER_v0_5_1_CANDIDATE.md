# RaceNote v0.5.1 Candidate — Protected Mainline / Six-to-Five Compression

Status: **RESEARCH CANDIDATE — CLEAN-BLIND THREE-WAY VALIDATION REQUIRED**  
Date: 2026-10-07  
Logic ID: `RaceNote-Human-Context-Reader-0.5.1-candidate`

## 1. Why v0.5.1 exists

Across BTDAY-0049 through BTDAY-0054 (180 races), v0.5.0 repeatedly showed two different effects that must be separated.

1. The v0.5.0 `normal_view` can recover useful horses that v0.4.6 leaves outside the five marks.
2. The v0.5.0 five-role compression can degrade the assignment of ◎ / ○ / ▲ and can churn the lower boundary, especially △2.

The research conclusion is therefore **not** to undo the v0.5.0 Reader projection. v0.5.1 keeps the same model-facing `normal_view` bytes as v0.5.0 and changes only the decision procedure used to compress candidates into five public marks.

Prediction accuracy and betting return remain separate evidence channels. A longer-priced ▲ is not a success unless it contributes to the intended ◎-anchored return profile.

## 2. Invariants carried from v0.5.0

v0.5.1 uses:

- the same clean Reader source;
- the same Stage C feature policy and v0.5.0 binding;
- the same deterministic `normal_view`;
- no provenance in normal model input;
- no target result, final odds, final popularity or payout before Freeze;
- five final public roles: ◎ ○ ▲ △1 △2;
- sparse material RRDB v0.3 citations;
- natural reader-facing prose;
- independent clean-blind authoring.

The Reader change from v0.5.0 to v0.5.1 is identity-only. If the v0.5.0 and v0.5.1 model-facing Reader bytes differ for the same sealed session, the session is invalid.

## 3. Decision procedure

### Step A — form the race model

Read the complete v0.5.x `normal_view` field and state what decides the race. Do not begin by assigning marks.

### Step B — build the ordinary five before searching for ▲

Choose an ordered ordinary five:

```text
ordinary_five = [anchor_◎, anchor_○, support_A, support_B, support_C]
```

This is the five-horse set that would be carried forward on ordinary race-strength / repeatability / shape grounds **without using an external asymmetric candidate to force a vacancy**.

The first two positions are protected anchors for the rest of the compression step.

### Step C — search outside that five for one external asymmetric challenger

Choose exactly one horse outside `ordinary_five` as `external_challenger_horse_no` when the race has six or more runners. The challenger must have a distinct upside / winning route that is not merely “the next horse in ordinary rank”. Price, popularity and target-day market information are unavailable and must not be inferred.\n\nFor an exactly five-runner field there is no external horse to compare. Use `NO_EXTERNAL_CHALLENGER`, keep the full ordinary five, and assign ▲ from the three ordinary support horses.

### Step D — compare six to five explicitly

The candidate pool is the union of the ordinary five and the one external challenger.

There are only two legal outcomes:

#### ADMIT_CHALLENGER

- the challenger enters the final five;
- the challenger is ▲;
- ◎ and ○ remain the first two ordinary anchors;
- the challenger may displace only one of `support_A / support_B / support_C`;
- the displaced horse is recorded explicitly.

#### KEEP_ORDINARY_FIVE

- the challenger is excluded;
- all five ordinary horses remain;
- ◎ and ○ remain the first two ordinary anchors;
- ▲ is assigned from the three ordinary support horses as the strongest remaining asymmetric case.

This is intentionally different from v0.5.0. The system must not create an external ▲ first and then silently rebuild the rest of the five around it.

## 4. v0.5.1 Decision Core extension

The existing v0.4.6-compatible fields remain, with one additional required object:

```json
"candidate_compression": {
  "ordinary_five": [1, 2, 4, 5, 6],
  "external_challenger_horse_no": 3,
  "external_challenger_case": "...",
  "excluded_horse_no": 6,
  "decision": "ADMIT_CHALLENGER",
  "reason": "..."
}
```

Mechanical validation enforces:

- five unique `ordinary_five` Reader horses;
- one external challenger not already in the five;
- ◎ = `ordinary_five[0]`;
- ○ = `ordinary_five[1]`;
- final five = six-candidate pool minus `excluded_horse_no`;
- an admitted challenger cannot displace ◎ or ○;
- an admitted challenger must be ▲;\n- `KEEP_ORDINARY_FIVE` must exclude the external challenger;\n- an exactly five-runner field must use `NO_EXTERNAL_CHALLENGER` with null challenger/excluded fields;
- final marks remain exactly five unique Reader horses.

The validator does **not** mechanically score the racing evidence. The model remains responsible for the racing judgment.

## 5. Initial validation design

The first two new unused BTDAYs should use three isolated lanes from one sealed preparation:

- v046 — original complete clean Reader;
- v050 — current `normal_view` and v0.5.0 decision procedure;
- v051 — byte-identical `normal_view` and v0.5.1 protected-mainline compression.

Do not let any authoring lane inspect sibling marks, prose or frozen artifacts.

The first two trials are intended to answer whether changing only the compression procedure:

- reduces unnecessary ◎ changes;
- preserves v0.5.0's useful new-candidate discovery;
- reduces old △2 complete-drop frequency;
- improves ▲ top-3 / winning contribution without collapsing its asymmetric character;
- improves ◎-▲ quinella / exacta contribution;
- protects trio capture;
- does so without using result or market information.

After the first two three-way BTDAYs, the initial v0.5.1 validation phase is complete. For prospective work after 2026-10-07, use the v0.5.1 vs v0.5.2 two-lane profile defined in `RACENOTE_CLEAN_BLIND_V051_V052_AB_RUNBOOK_v0_1.md`. v0.4.6 remains a retrospective historical baseline rather than a required prospective authoring lane.

## 6. Production boundary

This candidate does not change the production/current pointer. It is research-only until prospective clean-blind evidence supports promotion.
