# RaceNote v0.5.5 Candidate — Single-Day Runbook

Status: **CURRENT CANDIDATE / NEW v0.5.5 SESSIONS**  
Logic: `RaceNote-Human-Context-Reader-0.5.5-candidate`  
Revision: `v055-win-confidence-lean-reader-r2`

## 1. Prepare market-blind source

Use the canonical forecast preparation path with RRDB v0.5 enrichment.

Required preconditions:

```text
market_blind=true
stripped_at_input_bind=true
result_opened=false
target_market_opened=false
```

Use the existing KYI supplemental bundle and verified RaceLap Parquet. v0.5.5 r2 changes presentation to the model, not the underlying evidence sources.

## 2. Initialize the sealed Lean Model Reader

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py init \
  --prep-root <operation-root>/forecast_prep \
  --root <operation-root>/v055 \
  --base-main-sha <exact source-main SHA> \
  --evidence-bundle <operation-root>/v054_inputs/kyi_bundle.json \
  --race-lap-parquet <verified-lap-store>/race_lap.parquet
```

Initialization binds the source evidence and writes one model-facing Reader per race using:

`v055-lean-model-reader-r2`

The projection is deterministic. It removes repeated provenance and duplicate representations but does not author summaries, scores, candidates or marks.

The Reader manifest records, per race:

- full enriched presentation byte size before projection;
- model Reader byte size;
- reduction percentage;
- Reader projection version.

## 3. Author each race

Read the **complete bound Lean Model Reader for that race**.

Do not reopen or reconstruct the verbose source presentation during normal T2 authoring. The lean Reader is the intended complete model input.

Author:

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
    "main_risk": "...",
    "confidence": "A"
  },
  "shot_case": {
    "case": "..."
  },
  "rrdb_refs": [],
  "reader_facing_reason": "..."
}
```

For a five-runner race use `NO_EXTERNAL_CHALLENGER`, null challenger/excluded fields and an empty boundary reason.

A/B/C is assigned in the same race judgment and means confidence that ◎ wins.

Do not calculate pairwise grades, A5/A7 or IDM-gap gates during authoring.

## 4. Checkpoints and restart

3–4 races are a practical checkpoint size only.

A restart resumes from:

- sealed Lean Reader;
- immutable saved venue/chunk artifacts;
- neutral progress state.

Neutral helpers may track identity, paths, hashes and progress. They must not select marks, confidence, boundary decisions or prose.

## 5. Preflight and validation

Before Freeze:

1. read `src/racenote_decision_core_v055.py`;
2. read `src/racenote_v055_authoring_quality.py`;
3. validate the authored card;
4. correct only genuine pre-result schema/evidence issues.

Do not introduce deterministic prediction logic to satisfy the validator.

## 6. Save, Freeze and verify

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py save \
  --root <operation-root>/v055 \
  --decisions <operation-root>/v055/incoming/<venue>.json

python horse-racing/jrdb/src/racenote_v055_single_day.py freeze \
  --root <operation-root>/v055

python horse-racing/jrdb/src/racenote_v055_single_day.py verify \
  --root <operation-root>/v055
```

Do not open target results before verify succeeds.

Required frozen state:

```text
status=FROZEN_CLEAN_BLIND
confidence_frozen=true
confidence_meaning=HONMEI_WIN_CONFIDENCE
result_opened=false
target_market_opened=false
```

## 7. Result evaluation

After result unlock report:

- total ◎ win / top2 / top3;
- winner-in-five and top3 capture;
- A/B/C counts;
- A/B/C ◎ win rates;
- A/B/C ◎ single-win return when HJC payout data are available.

Pairwise ◎>○, IDM gaps, debut/obstacle grouping and old A5/A7-style analysis may be recomputed later as diagnostics.

## 8. Existing r1 session

Do not mutate an already initialized r1 session into r2. If T2 was started under r1 and results remain unopened, preserve that r1 work as abandoned/reproduction material and initialize a fresh r2 session from the same clean pre-result sources.
