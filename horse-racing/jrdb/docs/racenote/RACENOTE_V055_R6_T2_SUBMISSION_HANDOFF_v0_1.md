# RaceNote r6 T2 Submission and Freeze handoff (candidate)

## Components

- `racenote_v055_racezip_delivery.py`: read-only ZIP of T1 evidence.
- `racenote_v055_race_draft_assemble.py`: assemble LLM-authored per-race JSON into canonical draft with r6 preflight.
- `racenote_v055_r6_turn2_checkpoint.py`: inspect committed canonical phase state, fail closed.
- `racenote_v055_r6_submit_gate.py`: inspect canonical state and draft, then emit target filename and SHA-256 for one-file `main` commit.

## Prediction

1. Run checkpoint on a T1-ready BTDAY. Require `next_action=LLM_PREDICTION_AUTHORING`.
2. LLM independently reads EVERY runner and writes one race-specific JSON object per file. Code must not author marks or justifications.
3. Assemble full roster with `--phase prediction` and `--output` into **a temporary path**. Draft source is not committed to the BTDAY root.
4. Run submit gate `--phase prediction --draft <temp>`. Confirm `READY_TO_SUBMIT`, payload SHA, session ID, race count, exact target path.
5. Use GitHub connector to commit **only** `<root>/incoming/llm_decisions.json` to `main`, with the exact gate-approved draft; do not commit per-race temp files. A wrong-root or multi-root commit is forbidden.
6. Existing `racenote_v055_llm_prediction_freeze.yml` triggers on push. Confirm successful workflow **and committed frozen/day_handoff.json**, with canonical verify_freeze. Do not proceed just because Actions ran.
7. Resume checkpoint. Only `LLM_CONFIDENCE_REVIEW` allows next phase.

## Confidence

1. Independently re-review the **committed frozen** honmei. Write one per-race confidence draft. Mandatory Z for special race types.
2. Assemble with `--phase confidence`, run submit gate. Commit only `<root>/incoming/llm_confidence.json` to `main`.
3. Confirm `racenote_v055_llm_confidence_freeze.yml` success, committed `confidence_frozen/day_handoff.json`, `turn2_summary.json`, SHA links, and `TURN2_COMPLETE`.
4. Re-run canonical Batch Controller inspect/sync. No automatic result/target-market unlock.

## Idempotency / interruption

- Existing `incoming/llm_decisions.json` -> `WAIT_PREDICTION_FREEZE`; never resubmit automatically. Failures require deliberate diagnosis.
- Prediction frozen -> never edit predictions. Confidence is separate.
- Confidence submitted -> `WAIT_CONFIDENCE_FREEZE`.
- Both frozen + TURN2 summary -> `BATCH_SYNC_STATUS`.
- Code cannot ensure GitHub commit success; read canonical `main` after every change.
- Nothing in this plan runs the LLM asynchronously or guarantees all 36R fit in one model turn.
- Never open results, target-market values, payouts or settle before cohort seal.

## Test limitations

The submit-gate regression currently tests syntax and invalid draft / invalid phase rejection only. The full positive path depends on LLM-authored complete r6 payload and persisted Freeze; neither has yet been executed. Draft PR must not be merged as though an end-to-end test had passed.
