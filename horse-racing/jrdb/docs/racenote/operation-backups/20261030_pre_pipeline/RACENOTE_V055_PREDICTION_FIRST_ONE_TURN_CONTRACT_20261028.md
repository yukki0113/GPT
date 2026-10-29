# RaceNote r6 — prediction-first one-turn operating contract (2026-10-28)

## Decision
Do not pursue model orchestration, autonomous model fan-out, or Work/Codex allowance-heavy execution. Preserve the aspiration of 36R/day in one Chat turn, but do not claim it can be guaranteed. Maximize the fraction of available conversational reasoning used for LLM reading and independently authoring every runner.

## Deterministic pre-turn operations (outside forecast context)
1. Resolve canonical T1 READY for a single selected BTDAY and verify sealed session / clean blind.
2. Enumerate immutable prediction checkpoints in `horse-racing/jrdb/llm_checkpoints/BTDAY-NNNN/prediction/` and validate each against the original Reader.
3. Build a **short control manifest** only: selection_id, session_id, count, missing ordered [venue,race_no], next race path, verified Reader hash, expected checkpoint path, stage and blocking errors. Never insert an all-race Reader, machine rankings, marks, or Confidence in the control manifest.
4. Supply only the next *one race* lossless Reader payload to the model. All fields remain available: do not truncate/summarize historical evidence silently.
5. After LLM authors that race, existing canonical validator must pass. Save exactly one immutable GitHub checkpoint and return only status + commit SHA; do not echo the complete JSON into chat again. A failed validation stops and reports actionable errors, not a machine-generated prediction.
6. Repeat while the current Chat turn and model context allow. A context limit is not success: return precise committed checkpoints / missing roster, no invented completion.
7. When all 36 immutable decisions exist, deterministic assemble + preflight + submit-gate; commit only one `incoming/llm_decisions.json` under the selected canonical root to `main`. Wait for verified persisted Prediction Freeze.
8. LLM re-reads **each frozen honmei** and independently assigns A/B/C/Z and a race-specific reason. Per-race confidence checkpoints may be needed; do not infer grades from marks, heuristic scores, or odds.
9. Assemble, submit and verify Confidence Freeze; only then report TURN2_COMPLETE and sync Batch Controller.

## What may be optimized mechanically
- CLI orchestration of download/hash/parse/schema validation, immutable file persistence, coverage and stage status.
- Avoid rereading all checkpoint contents into the LLM context: read them in validation code, report hashes/counts only.
- Avoid loading unchanged readers again, run-specific notebook/chat narration, long GitHub logs and repeated docs.
- Cache immutable reader ZIP **bytes** by session + SHA (not a lossy Reader projection).
- Use narrowly scoped GitHub commit operations rather than entire PR re-review on every race.

## Not allowed
- Automated mark selection, contender filtering, recommendation/prose drafting, Confidence grading, results/target market access.
- Lossy Reader optimization presented as unchanged evidence.
- Marking any race complete based only on a JSON file existing; verify canonical core and its bound Reader.
- Replacing the current LLM with an API, background Work agent or Codex fan-out without separate approval.

## Reality check
BTDAY-0136's Reader was measured at approximately 1.92M token-proxy tokens for 36R. Even perfect mechanical orchestration does not make this fit in a single finite model context. One-turn completion remains an unproven stretch objective. Prefer durable partial completion over false claims, and keep user interaction to one request per attempt whenever feasible.

## Current BTDAY-0136 checkpoint state
4 persisted races as of the time of this plan: 中山01, 中山03, 中山07, 阪神09; remaining 32. PR #2225 is draft; canonical T1/Freeze untouched. Refresh GitHub branch before relying on the count.
