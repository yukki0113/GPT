# RaceNote v0.5.0 Stage E — Clean-Blind A/B Harness Report

Date: 2026-10-06  
Instruction: `20261006_RACENOTE_V050_STAGE_E_AB_HARNESS_INSTRUCTION.md`  
Decision: **READY_FOR_DUAL_THREAD_PILOT**  
Production impact: **ZERO**

## Implemented

| File | Role |
|---|---|
| `src/racenote_ab_session.py` | Seals one shared clean preparation, request identity, race and horse roster, original Reader hashes, Stage C policy/binding hashes and RRDB contract; deterministically derives v0.5.0 normal Reader files and their manifest. |
| `src/racenote_ab_lane.py` | Saves complete immutable venue Decision Core wrappers under distinct v0.4.6/v0.5.0 paths; validates each against its own lane Reader; creates a lane-specific frozen wrapper and handoff. |
| `src/racenote_ab_freeze_barrier.py` | Revalidates both frozen lanes and writes the barrier only after both are complete and clean. Exposes `require_barrier` for a future result/market evaluation entry point. |
| `tests/test_racenote_ab_harness.py` | Synthetic positive and negative structural tests. |
| `docs/racenote/RACENOTE_CLEAN_BLIND_AB_RUNBOOK_v0_1.md` | Exact separate-thread and branch operating procedure. |
| This report | Stage E result and next action. |

No live race was predicted, no BTDAY was reserved, and no target result or target market was opened.

## Contracts and evidence binding

`ab/ab_session.json` has version `racenote-ab-session-0.1` and status `SESSION_SEALED`. Its deterministic session id binds the selection id, target date, preparation base SHA, prepare-request SHA and PACI/Analysis identity, original clean Reader manifest SHA, complete race/horse roster, expected venues, RRDB v0.3 contract, Stage C policy SHA and 73-row v0.5 binding SHA. The session requires `market_blind=true`, `target_market_opened=false`, `result_opened=false` and a sibling-input prohibition. It refuses to overwrite an existing session.

The v0.4.6 lane references the original `forecast_prep/reader/` and rechecks every file hash. The v0.5.0 lane materializes only `normal_view` JSON under `ab/v050/reader/`. Its manifest binds original filename/hash, source semantic hash, derived normal hash and `RaceNote-Human-Context-Reader-0.5.0-candidate`. The provenance sidecar is not placed in the model-facing directory. The loader re-derives each candidate normal view from the original clean file to detect tampering.

Each lane's `authored_decisions/<venue>.json` binds the session id, selection/date, lane id, logic id, lane Reader manifest hash, original clean manifest hash, complete venue card and individual Decision Core hashes. Authoring input is accepted only from that lane's `incoming/<venue>.json`; a sibling lane path is rejected. The saver and freezer reuse the existing v0.4.6 `validate_core` semantics for five unique marks, four mainline cases, independent ▲, △2 boundary, sparse RRDB refs and prose. For v0.5.0 the validator sees an identity/RRDB adapter built from **candidate normal view**, not the original evidence or provenance.

The research Freeze uses wrapper version `racenote-ab-lane-frozen-0.1`, with explicit v0.4.6 or v0.5.0 logic id, `validator_status=PASS` and `FROZEN_CLEAN_BLIND`. This is a dedicated Stage E lane wrapper; it does not label a v0.5.0 record as a v0.4.6 research record and does not modify the ordinary Freeze implementation. `ab/ab_freeze_barrier.json` is written only when both full lane wrappers validate against the same sealed session, original clean manifest, race/horse roster and pre-result firewall. A future evaluator must call `require_barrier`, which rechecks the current bytes rather than trusting a stale PASS file.

Example session tree:

```text
backtests/BTDAY-XXXX/
  forecast_prep/reader/                   # one canonical clean source
  ab/
    ab_session.json
    shared/reader_manifest.json
    v046/reader_manifest.json
    v046/authored_decisions/<venue>.json
    v046/frozen/{records.json,lane_handoff.json}
    v050/reader_manifest.json
    v050/reader/<race>.json               # normal_view only
    v050/authored_decisions/<venue>.json
    v050/frozen/{records.json,lane_handoff.json}
    ab_freeze_barrier.json                # only after both lane Freezes
```

## Independence and ordinary BTDAY compatibility

The two forecast tasks must start in fresh Cloud threads from the **same committed session base**, on separate branches. Each task receives only its own Reader contract and is instructed not to inspect sibling branches, authored/frozen files, marks, prose or traces. Neither prediction PR may merge before both lanes are frozen. A third non-authoring task imports the immutable lane artifacts and runs the barrier. Code enforces separate input/output paths, source hashes, lane logic ids and frozen manifests; it cannot prove what a model saw outside the declared task input. The separate-thread operating rule is therefore mandatory.

Existing `racenote_save_venue_batch_v046.py`, `racenote_bind_venue_batches_v046.py`, `racenote_freeze_prepared_forecast.py`, the permanent v0.4.6 prepare/finalize workflows and the one-lane archive route were not modified. The repository's current logic configuration file was not changed. It currently names v0.4.2 in `current_logic_version` and v0.4.6 in `prospective_research_candidate`; the Stage E harness changes neither field.

## Validation

- `python -m py_compile` on the three new modules and test file: PASS.
- `python -m unittest` on the new harness tests plus the v0.4.6 validator, Stage D Reader, older BTDAY A/B and Freeze preflight tests: **26 tests passed** (11 new harness tests and 15 existing tests).
- Synthetic tests cover one preparation/session, identity and original hashes common to both lanes, deterministic normal-only v0.5 Reader, sibling authoring rejection, sibling artifact rejection as Reader input, separate authored paths, incomplete/invalid venue rejection, explicit v0.5 Freeze identity, one-lane barrier failure, session/hash/roster/result/sibling tamper failure, both-lane PASS, stale-barrier rejection and unchanged current configuration.

## Limits and next action

This stage has not run two model forecasts or evaluated outcomes. The Freeze is a dedicated A/B research wrapper with Decision Core validation; it is not a production forecast record or a replacement for the ordinary v0.4.6 finalizer. Human authoring independence still depends on fresh isolated tasks and the branch instructions. The session's `base_main_sha` is the preparation revision; after committing the sealed session, the resulting commit SHA must be recorded as the common base for both authoring tasks.

**Next action:** authorize and reserve one unused BTDAY for a separate dual-thread pilot. Prepare and commit one clean session, then start isolated v0.4.6 and v0.5.0 Cloud tasks from its exact shared commit. Keep both forecast branches unmerged until both are frozen. Run a third integration task and require a PASS barrier before any result/market opening.
