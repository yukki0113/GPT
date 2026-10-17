# RaceNote v0.5.5 Candidate — Single-Day Runbook

Status: **CURRENT CANDIDATE / NEW v0.5.5 SESSIONS**  
Logic: `RaceNote-Human-Context-Reader-0.5.5-candidate`  
Revision: `v055-prediction-freeze-confidence-review-r4`

## 1. Prepare market-blind source

Use the canonical forecast preparation path with RRDB v0.5 enrichment.

Required preconditions:

```text
market_blind=true
stripped_at_input_bind=true
result_opened=false
target_market_opened=false
```

Use the existing KYI supplemental bundle and verified RaceLap Parquet.

For normal **forward** operation, RaceLap must come from the canonical forward-current asset defined by
`RACENOTE_V055_FORWARD_EVIDENCE_OPERATION_DESIGN_v0_1.md`.

Forward T1 must not:

- fetch annual historical SED archives;
- scan a historical daily SED date range;
- rebuild RaceLap from raw history.

Before Reader seal, require:

```text
analysis.period_to < target_date
race_lap.period_to < target_date
race_lap.period_to == analysis.period_to
```

The exact RaceLap Parquet SHA-256 is still bound into the v0.5.5 session, so reuse of the canonical current asset does not weaken input immutability.


RaceLap is exposed to the model through the common Reader contract, not through
consumer-side Parquet SQL. PACI recent runs retain their canonical `race_key`;
the daily RRDB/RaceNote enrichment performs one batch lookup and attaches:

```text
horses[].recent_runs[].race.race_key
  -> RaceLapReader.get_race_contexts(...)
  -> recent_runs[].race_structure
       source = JRDB_RaceLapReader_v0.1
       coverage
       lap_shape
       srb_context
       policy
       provenance
```

`lap_shape` is source-race context, not an individual-horse sectional or an
additive score. Missing RaceLap coverage is represented explicitly as
`coverage.status=NOT_FOUND`; target-date or future source rows fail closed.

## 2. Initialize the sealed Lean Model Reader

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py init \
  --prep-root <operation-root>/forecast_prep \
  --root <operation-root>/v055 \
  --base-main-sha <exact source-main SHA> \
  --evidence-bundle <operation-root>/v054_inputs/kyi_bundle.json \
  --race-lap-parquet <verified-lap-store>/race_lap.parquet
```

T2 reads the complete bound `v055-lean-model-reader-r2` for each race.

## 3. Author the prediction

Author the forecast without A/B/C:

```json
{
  "venue": "中山",
  "race_no": 1,
  "marks": [12, 2, 7, 16, 11],
  "candidate_selection": {
    "ordinary_five": [12, 2, 7, 16, 11],
    "external_challenger_horse_no": 5,
    "excluded_horse_no": 5,
    "decision": "KEEP_ORDINARY_FIVE",
    "boundary_reason": "..."
  },
  "honmei_win": {
    "evidence": "...",
    "main_risk": "..."
  },
  "shot_case": {
    "case": "..."
  },
  "rrdb_refs": [],
  "reader_facing_reason": "..."
}
```

A/B/C must not be inserted into the r4 Decision Core.

The short note is editorial: write the single race-specific point most useful to the reader. Do not routinely summarize all marks.

## 4. Save prediction checkpoints

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py save \
  --root <operation-root>/v055 \
  --decisions <operation-root>/v055/incoming/<venue>.json
```

Repository-backed authored venue files remain recovery checkpoints. They are immutable once saved.

## 5. Prediction Freeze

After every expected venue is present:

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py freeze \
  --root <operation-root>/v055

python horse-racing/jrdb/src/racenote_v055_single_day.py verify-prediction \
  --root <operation-root>/v055
```

Required state:

```text
status=PREDICTION_FROZEN_CLEAN_BLIND
confidence_frozen=false
confidence_pending=true
result_opened=false
target_market_opened=false
```

From here onward, do not alter marks, Decision Core or short comments.

Do not open target results or target market.

## 6. Confidence Review

Now review the already frozen ◎ horses as a separate judgment.

Meaning:

- **A** — ◎を勝ち馬・単勝軸として積極的に支持できる。
- **B** — ◎が最有力だが、有力な逆転候補または主要リスクがありAほど強く買わない。
- **C** — ◎は固定済みの本命だが、勝ち馬選定そのものへの確信が低い。

A does not mean near-certainty. Plausible upset routes do not automatically demote A to B.

There is no A quota and no target grade distribution.

Create a complete review array:

```json
[
  {
    "venue": "中山",
    "race_no": 1,
    "honmei": 12,
    "confidence": "A",
    "reason": "現級での直接実績が一段上で、主要リスクを考慮しても単勝軸として積極的に支持できる。"
  }
]
```

The `honmei` value must exactly match the frozen ◎.

Save the draft:

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py save-confidence \
  --root <operation-root>/v055 \
  --confidence <operation-root>/v055/incoming/confidence.json
```

Before Confidence Freeze, `confidence_review.json` is deliberately replaceable. Re-read the frozen prediction, reconsider A/B/C boundaries, edit the incoming review and run `save-confidence` again as needed.

This is the formal pre-result reconsideration stage.

## 7. Confidence Freeze

When the review is settled:

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py freeze-confidence \
  --root <operation-root>/v055

python horse-racing/jrdb/src/racenote_v055_single_day.py verify \
  --root <operation-root>/v055
```

Final required state:

```text
Prediction:
  PREDICTION_FROZEN_CLEAN_BLIND

Confidence:
  CONFIDENCE_FROZEN_CLEAN_BLIND
  confidence_frozen=true
  confidence_meaning=HONMEI_WIN_CONFIDENCE

Both:
  result_opened=false
  target_market_opened=false
```

Only after final `verify` succeeds may result evaluation begin.

## 7.1 Completion report to the forecast execution thread

After Prediction Freeze, Confidence Freeze, and final `verify` succeed, keep the chat completion report compact.

The canonical frozen artifacts already contain the full race-by-race marks, comments, and Confidence review. Therefore, the normal completion report must summarize only:

- race / frozen counts;
- Prediction / Confidence final statuses;
- A/B/C counts;
- prediction / confidence hashes;
- `result_opened=false`;
- `target_market_opened=false`;
- material technical observations, if any.

Do **not** print the full card of ◎ ○ ▲ △ △, short comments, or per-race Confidence back into the conversation after successful completion.

Only reproduce a full or partial marks table when the user explicitly asks to see it.

This is a conversation-volume control only. It does not reduce or alter any repository artifact, Freeze record, handoff, or downstream publication requirement.

## 8. Result evaluation

After result unlock report:

- total ◎ win / top2 / top3;
- winner-in-five and top3 capture;
- A/B/C counts;
- A/B/C ◎ win rate;
- A/B/C ◎ single-win return when HJC payout is available.

Pairwise ◎>○, IDM gaps, debut/obstacle grouping and old A5/A7-style analysis remain downstream diagnostics.

## 9. Existing r1/r2/r3 sessions

Do not migrate an existing frozen r1/r2/r3 session into r4. Their embedded confidence remains part of their historical Freeze.

r4 applies only to newly initialized sessions.
