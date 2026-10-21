# RaceNote v0.5.5 r6 — two-phase Turn2 operation

Status: implementation candidate; applies to **new r6 sessions only**.

## Boundary

The LLM independently reads every runner in every lossless authoring bundle and authors the complete Decision Core and independently worded short note. Deterministic workflows may validate, save, freeze, verify, and commit, but **must never select runners, marks, challenger admission, Confidence grades, or prose**.

## Prediction phase

1. After T1, LLM authors every race and writes valid UTF-8 JSON array to `<root>/incoming/llm_decisions.json`.
2. Commit that file to `main` using the exact daily or BTDAY root.
3. Permanent `racenote_v055_llm_prediction_freeze.yml` resolves one approved root and calls `racenote_v055_turn2_two_phase.py --phase prediction`.
4. Preflight validates sealed session and complete race coverage; existing canonical save, authoring-quality and Prediction Freeze validators remain authoritative.
5. Runner commits verified `frozen/`, venue checkpoints and `prediction_phase_summary.json` into the same root.
6. Confirm `PREDICTION_FROZEN_CLEAN_BLIND` is **committed** before reviewing Confidence. An in-runner Freeze without a successful push is not complete.

## Confidence phase

1. LLM **re-reads the frozen ◎** independently and assigns A/B/C or mandatory Z for special races, with a race-specific reason.
2. LLM writes `<root>/incoming/llm_confidence.json` and commits it to `main`.
3. Permanent `racenote_v055_llm_confidence_freeze.yml` checks Prediction Freeze, compares every honmei with the frozen Decision Core, and calls canonical Confidence save / Freeze / verify.
4. Runner commits `confidence_frozen/` and `turn2_summary.json`.
5. Only after successful push report `TURN2_COMPLETE`.

## Approved roots

- `horse-racing/jrdb/daily/YYYYMMDD/v055_day/v055`
- `horse-racing/jrdb/backtests/BTDAY-NNNN/YYYYMMDD/v055`

Push changes for **one root per commit**. No temporary per-date workflow is required.

## Failures / retry

Malformed UTF-8, malformed JSON, missing/duplicate races, incorrect frozen honmei, unsupported root/session, and existing immutable Freeze fail closed. Full semantic checks reuse the canonical modules; failed preflight/freeze never initiates result or target-market access.

The workflow job output identifies the failing stage; a failed runner may contain ephemeral partial files, but only a **successfully committed and verified** Freeze is authoritative. After fixing an incoming draft, recommit the file to retrigger the correct phase. Do not change an already frozen Prediction. Avoid Base64/gzip transport.

## Compatibility

The previous combined `racenote_v055_turn2_finalize.py` stays unchanged for historical reproducibility. Its workflow is **manual-only and non-r5**; new r6 sessions must use the two separate workflows.

## Regression checks before merge

- Normal fresh r6 Prediction → persisted frozen Prediction → LLM Confidence → persisted frozen Confidence.
- Broken JSON (including extra suffix), missing race, duplicate race, wrong frozen ◎, non-r6 input and frozen-stage replays all fail closed.
- Both daily and BTDAY roots resolve; unapproved roots fail.
- No result or target market is opened.
- Runner commit writes exactly within the selected operation root.
