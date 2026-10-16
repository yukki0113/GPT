# RaceNote v0.5.5 Candidate — Single-Day Runbook

Status: **CURRENT CANDIDATE / NEW v0.5.5 SESSIONS**
Logic: `RaceNote-Human-Context-Reader-0.5.5-candidate`
Contract: `FORECAST_HUMAN_CONTEXT_READER_v0_5_5_CANDIDATE.md`
Revision: `v055-win-confidence-lean-r1`

## 1. Prepare market-blind source

Use the existing canonical forecast preparation path with RRDB v0.5 enrichment.

Required preconditions:

```text
market_blind=true
stripped_at_input_bind=true
result_opened=false
target_market_opened=false
```

Use the same verified KYI supplemental bundle and RaceLap Parquet sources used by the v0.5.4 evidence projection. v0.5.5 does not add a new evidence source.

## 2. Initialize the sealed Reader

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py init \
  --prep-root <operation-root>/forecast_prep \
  --root <operation-root>/v055 \
  --base-main-sha <exact source-main SHA> \
  --evidence-bundle <operation-root>/v054_inputs/kyi_bundle.json \
  --race-lap-parquet <verified-lap-store>/race_lap.parquet
```

The upstream KYI supplemental schema remains the existing v0.5.4 supplemental format because the evidence projection itself is unchanged.

Initialization writes the sealed v0.5.5 Reader, manifest, evidence snapshot and session identity.

## 3. Author each race

Read the complete bound Reader for the race.

Author only the v0.5.5 Lean Decision Core:

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
    "evidence": "...why ◎ can win...",
    "main_risk": "...largest reason ◎ may fail to win...",
    "confidence": "A"
  },
  "shot_case": {
    "case": "...why ▲ has a distinct winning route..."
  },
  "rrdb_refs": [],
  "reader_facing_reason": "..."
}
```

For a five-runner race, use `NO_EXTERNAL_CHALLENGER`, null challenger/excluded fields and an empty boundary reason.

### Confidence

Assign A/B/C during this same authoring pass.

A/B/C expresses only confidence that ◎ wins. Do not calculate pairwise grades, A5/A7 or IDM-gap gates during authoring.

### Checkpoints

3–4 race model-authored chunks remain a practical recovery unit, not a prediction rule. A restart resumes from persisted chunks and the sealed Reader.

A neutral workspace may contain identity, Reader path/SHA and compact neutral facts, but it must not preselect marks, confidence, boundary decisions or prose.

## 4. Preflight once

Before the first save/Freeze execution:

1. read `src/racenote_decision_core_v055.py`;
2. read `src/racenote_v055_authoring_quality.py`;
3. validate the complete authored card once;
4. correct only genuine pre-result schema/evidence issues.

Do not build deterministic code that authors or fills prediction meaning.

## 5. Save, Freeze and verify

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py save \
  --root <operation-root>/v055 \
  --decisions <operation-root>/v055/incoming/<venue>.json

python horse-racing/jrdb/src/racenote_v055_single_day.py freeze \
  --root <operation-root>/v055

python horse-racing/jrdb/src/racenote_v055_single_day.py verify \
  --root <operation-root>/v055
```

A verified Freeze contains confidence already. There is no separate confidence-authoring stage.

Do not open results until verify succeeds and the frozen day handoff confirms:

```text
status=FROZEN_CLEAN_BLIND
confidence_frozen=true
confidence_meaning=HONMEI_WIN_CONFIDENCE
result_opened=false
target_market_opened=false
```

## 6. Result evaluation

After result unlock, report at minimum:

- total ◎ win / top2 / top3;
- winner-in-five and top3 capture;
- A/B/C counts;
- A/B/C ◎ win rates;
- A/B/C ◎ single-win return when HJC payout data are available.

Optional diagnostics may recompute IDM gaps, ◎>○ pairwise outcomes, debut/obstacle groups or historical A5/A7-style thresholds from the frozen Reader and results. Those diagnostics do not alter the frozen prediction.
