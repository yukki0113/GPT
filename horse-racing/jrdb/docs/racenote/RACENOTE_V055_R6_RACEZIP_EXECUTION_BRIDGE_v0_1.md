# RaceNote r6 One-turn execution bridge — Stage 1

Status: transport verified, execution coordination design (not yet implemented).
Date: 2026-10-28.
PR: #2225.

## Verified transport
- Read-only T1-ready BTDAY-0136 (2025-03-02, 36R).
- PR CI run: https://github.com/yukki0113/GPT/actions/runs/40618976838
- Artifact ID: 12786775750
- Artifact is an outer Actions ZIP containing `test-btday-0136.zip`. That inner ZIP contains `index.json` and 36 `races/<venue>/<NN>.json`.
- GitHub connector `fetch_workflow_run_artifacts` -> `download_workflow_artifact` -> local ZIP: confirmed.
- SHA-256 on all 36 race entries: PASS; clean blind flags PASS.
- No T2, no Freeze, no market/results opened.

## Proposed contract for the next stage
Existing canonical workflow remains unchanged:
1. Detect canonical Batch Controller next_action. If PICK, dispatch canonical picker only; if T1, dispatch existing shared T1 request route. Do not recreate T1 for already prepared days.
2. Await the committed `READY_FOR_V055_AUTHORING` handoff. The independent read-only ZIP delivery workflow publishes an artifact.
3. Locate the matching artifact by exact selection ID and successful run, download and verify inner ZIP `index.json`, each entry hash, clean blind flags, session ID and 36R complete roster. Never assume an Artifact created implies canonical T1 completion.
4. LLM reads ALL runners of each race and authors its Decision Core. Store local per-race checkpoints; do not publish partial prediction payloads into the immutable target root.
5. Assemble exact full roster into the current `incoming/llm_decisions.json` schema, validate, and commit only the one root to `main`. Await `PREDICTION_FROZEN_CLEAN_BLIND` and successful commit/push.
6. LLM independently reviews every frozen honmei, preserving A/B/C/Z definitions. Commit `incoming/llm_confidence.json` to the same root. Await verified `CONFIDENCE_FROZEN_CLEAN_BLIND`, `TURN2_COMPLETE` and successful commit/push.
7. Batch Controller sync/status. Do not seal a cohort until its configured stop condition is met. Never unlock results or market automatically.

## Failure / idempotency
- State is reconstructed from committed canonical artifacts, not conversation claims or transient job statuses.
- Frozen prediction records are immutable; retries start from current `next_action` and never rewrite an already frozen phase.
- If a turn ends without T2 completion, report selection ID, committed stage, workflow URL and next action; never claim asynchronous LLM work.
- The action/artifact is a transport capability, NOT a background LLM, and does not make 36R reasoning fit in one turn by itself.

## Outstanding verification
- After merging the PR, verify push-triggered ZIP delivery on a newly generated clean-blind T1 and manual dispatch on an existing sealed day.
- Runtime cost, context pressure and reasoning quality for 36R sequential authoring remain unproven.
- Confirm r6 current schemas before coding draft uploader / checkpoint bridge; respect single-root-per-commit and frozen SHA constraints.
