# RaceNote r6 T1 Orchestrator — operating contract (2026-10-29)

## Purpose

One entrypoint to make exactly one historical BTDAY usable for CLEAN BLIND T2:
**selection / reservation → pinned immutable shared T1 → 36 race ZIPs → Actions Artifact**.

No LLM prediction, no Confidence grading, no results, odds, payout or Freeze operations.

## Entry points

GitHub Actions: **RaceNote r6 T1 Orchestrator** → Run workflow.
- `NEXT` (default): choose one unused eligible **2025** Historical Warehouse date via the existing canonical picker, reserve it and execute T1. If a selected unstarted BTDAY exists, reuse it instead of reserving again.
- `EXISTING`, `selection_id=BTDAY-0138`: if T1 is already committed and verified, reuse it and regenerate only the transport ZIP. If selected and not yet started, run T1. If another T1 request already exists, report that state without making a duplicate.
- `STATUS`, `selection_id=BTDAY-0138`: inspect canonical committed T1 in read-only mode (does not start T1 or create ZIP).
- `T2_ONLY`: no T1 action. The separate T2/Freeze remains untouched.

From a connected GitHub writer, instead create **one** new file on `main`, e.g.
`horse-racing/jrdb/backtests/requests/orchestrator/start-0139-01.json`,
with exactly this JSON:
```json
{"mode":"NEXT","selection_id":null}
```
For a known ready day use `{"mode":"EXISTING","selection_id":"BTDAY-0138"}`.
Do not reuse a request filename: new requests must be new commits and unique paths.
A matching push on main starts the *same* orchestration workflow, not an independent T1.

## Contract / safety

1. Only one orchestrator runs at a time (`concurrency`, no cancellation).
2. A newly selected day is committed to the pool and immutable `selection.json` on main.
3. The caller explicitly invokes the existing reusable shared T1 workflow with `selection_id` and the **pinned SHA of the reservation commit**. Bot-push chaining is not required.
4. Shared T1 writes the immutable canonical T1 root and pushes it to main; its initial code is pinned, while Git rebases only for target-path coexistence.
5. After T1 succeeds, orchestration checks out main, packages clean-blind race ZIPs and uploads an artifact named `racenote-orchestrator-BTDAY-NNNN`.
6. The whole workflow is green only if all required jobs succeed, including transport; the caller must check the final artifact and SHA manifest. A T1-only success is not T1 Orchestrator success.
7. Existing T1 is *never* overwritten. Partially-created canonical targets fail closed. A separately requested T1 does not trigger duplicate generation.
8. The controller only supports the historical archive year **2025** until the shared T1 year support changes.
9. T2 and the two-phase Freeze remain independent. An orchestrator error must not change the current T2's canonical data. The pipeline can start T1 immediately before beginning LLM predictions; only check results after Confidence Freeze.

## Important limits / outstanding validation

- Offline regression tests exercise NEXT, EXISTING, STATUS, T2_ONLY and idempotency; they do not create production new BTDay selections.
- Following merge, test STATUS and EXISTING against a previously committed T1 **before** first production NEXT, then separately verify the full new-date T1 execution.
- The GitHub Actions workflow completion and the uploaded ZIP artifact are the source of truth for transport readiness; `STATUS` only assesses local canonical T1 state, not artifact retention.
- Current artifact retention is 7 days. Use EXISTING to reissue ZIP when expired.
- No unattended ChatGPT monitoring after a conversation reply. GitHub Actions independently processes the queued T1 until terminal status.
