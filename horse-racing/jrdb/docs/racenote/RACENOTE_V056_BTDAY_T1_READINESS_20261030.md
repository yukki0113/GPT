# RaceNote v0.5.6 BTDAY T1 readiness — pre-BTDAY integration check

Status: **PRE-FLIGHT ONLY / NOT PRODUCTION ACTIVE** (2026-10-30). v0.5.5 r6 remains the current main operation until reviewed activation.

## Entry points added on PR #2246

- T1 shared workflow: `.github/workflows/racenote_v056_btday_turn1_shared.yml`.
- Expected trigger, **only after PR merge and approval**: a *new* `horse-racing/jrdb/backtests/requests/BTDAY-NNNN.v056-turn1` file on main, for an already committed eligible `selection.json`. Do not send a v055r6 request.
- Session builder: `src/racenote_v056_single_day.py init`; canonical root `horse-racing/jrdb/backtests/BTDAY-NNNN/YYYYMMDD/v056`.
- LLM authoring bundle: `src/racenote_v056_authoring_bundle.py`.
- Read-only T1 transport: `src/racenote_v056_racezip_delivery.py`.
- T2 two-phase entrypoint: `src/racenote_v056_turn2_two_phase.py`; separate `.github/workflows/racenote_v056_llm_prediction_freeze.yml`, `racenote_v056_llm_confidence_freeze.yml`.

## Required green gates before real BTDAY

1. PR CI syntax/unit tests pass and exact v056 source/workflow paths are validated.
2. Existing selection must be 2025 historical Warehouse, CLEAN BLIND and satisfy current shared T1 source constraints.
3. T1 must commit `v056/session.json`, `reader_manifest.json`, `reader/`, `authoring_bundle/manifest.json`, `operation_handoff.json` to main with v056 session identity and SHA integrity.
4. T1 ZIP transport must prove complete roster and manifest SHA. Pre-race source is sole permitted data.
5. Prediction input must contain one LLM-authored v056 Decision Core including `prediction_audit_comment` per race. Freeze must be committed and reverified from main before Confidence.
6. Confidence input must reference frozen ◎ and include `confidence_review`; Freeze committed and reverified from main.
7. Report exact Workflow IDs, source SHA, frozen artifacts, and any failure. Neither T1 readiness nor unit test green implies two-phase E2E PASS.

## Known limitations

- v056 direct shared T1 is separate from the older v055 T1 Orchestrator NEXT/EXISTING; **do not use the v055 Orchestrator as a v056 dispatcher**. A v056-specific NEXT/STATUS/EXISTING orchestration path still requires implementation/review before it becomes default.
- The T1/Reader path has not yet run on a real v056 BTDAY in CI; no live result evaluation has been authorized.
- FORWARD PACI input preparation and post-freeze newspaper/PWA export are outside this current BTDAY-readiness gate.
- Legacy v055 roots, workflows, historical Freeze and market/result protections must remain untouched.
