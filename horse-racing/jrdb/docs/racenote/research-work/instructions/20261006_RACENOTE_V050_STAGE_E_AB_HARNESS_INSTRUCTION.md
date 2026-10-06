# RaceNote v0.4.6 vs v0.5.0 — Stage E Clean-Blind A/B Harness Instruction

Status: **READY FOR EXECUTION**  
Date: 2026-10-06  
Purpose: implement a durable same-BTDAY / same-clean-evidence A/B harness  
Production impact: **ZERO**

## 1. Objective

Implement a dedicated research harness that allows one reserved BTDAY and one
canonical clean Reader preparation to be used for **two independent forecast
lanes**:

- Lane A: `RaceNote-Human-Context-Reader-0.4.6-candidate`
- Lane B: `RaceNote-Human-Context-Reader-0.5.0-candidate`

Both lanes must use the same:

- selection id / BTDAY id;
- target date;
- race roster;
- source PACI / Analysis generation;
- clean pre-race evidence;
- RRDB contract;
- target-result / target-market firewall state.

The only intended experimental difference is the Reader presentation surface.

Do **not** run a prediction A/B during Stage E. Stage E builds and validates the
harness only.

## 2. Canonical prerequisites

Read before implementation:

1. `docs/racenote/BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md`
2. `docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_4_6_CANDIDATE.md`
3. `docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_5_0_CANDIDATE.md`
4. `src/racenote_reader_v050.py`
5. `src/racenote_save_venue_batch_v046.py`
6. `src/racenote_bind_venue_batches_v046.py`
7. `src/racenote_freeze_prepared_forecast.py`
8. `src/racenote_stage_btday_archive.py`
9. Stage D report and tests.

Stage D has already established that 0.5.0 is a parallel presentation-only
candidate and is structurally ready for clean-blind A/B.

## 3. Experimental independence is mandatory

A/B validity requires more than using the same date.

The two model-authored forecast lanes must not see one another's marks, prose,
decision traces, boundary alternatives, or authored files before both are
frozen.

### Required operating rule

Create the A/B session first on a shared clean base.

Then start two **separate Cloud tasks / chat threads** from the same declared
A/B base commit:

```text
shared BTDAY + clean Reader
          |
          +--> lane A task/branch: v0.4.6 authoring -> lane Freeze
          |
          +--> lane B task/branch: v0.5.0 authoring -> lane Freeze
```

Do not merge Lane A forecast artifacts into main before Lane B is frozen.
Do not merge Lane B forecast artifacts into main before Lane A is frozen.

Each lane instruction / runner must explicitly reject the sibling lane as an
authoring input.

After both freezes exist, a separate deterministic integration/evaluation step
may combine the lane artifacts.

## 4. Reuse one reserved BTDAY

Do not draw a second date for Lane B.

Stage E must support this flow:

```text
reserve BTDAY once
-> prepare canonical clean v0.4.6 Reader once
-> seal A/B session manifest
-> derive v0.5.0 normal Reader deterministically from the same clean files
-> independently author A and B
-> independently freeze A and B
-> only then permit comparison / result opening
```

The shared session must prove that the race/date source is identical between
the lanes.

## 5. A/B session manifest

Implement a deterministic session initializer.

Suggested module:

`src/racenote_ab_session.py`

Suggested session root:

`backtests/BTDAY-XXXX/ab/`

Required session manifest:

`backtests/BTDAY-XXXX/ab/ab_session.json`

At minimum record:

- ab_session_version
- selection_id
- target_date
- session_id
- base_main_sha
- source prepare request identity
- clean Reader manifest SHA-256
- complete race roster
- complete original clean Reader file hashes
- expected venue set
- RRDB contract
- market_blind=true
- target_market_opened=false
- result_opened=false
- lane definitions
  - lane_a logic version = v0.4.6
  - lane_b logic version = v0.5.0
- sibling-forecast-input forbidden=true
- status = SESSION_SEALED

The session initializer must not choose horses or create predictive text.

## 6. Candidate Reader derivation

Under the A/B session, create a deterministic 0.5.0 Reader projection from the
same original clean Reader files.

Suggested locations:

```text
ab/
  shared/
    reader_manifest.json
  v046/
    reader/  (reference/or immutable copy of canonical clean Reader)
  v050/
    reader/
    reader_manifest.json
```

It is acceptable for v046 to reference the canonical `forecast_prep/reader/`
rather than duplicate it, provided hashes are revalidated.

For every race, the v050 manifest must bind:

- original clean Reader filename
- original clean Reader SHA-256
- source semantic SHA
- derived v050 normal-view SHA-256
- candidate version

The model-facing v050 input must be **normal_view only**.

The provenance sidecar may be retained for audit but must not be included in
normal model input.

## 7. Lane-specific authoring storage

Use separate immutable paths.

Suggested:

```text
ab/
  v046/
    authored_decisions/
    frozen/
  v050/
    authored_decisions/
    frozen/
```

Do not reuse the existing production-path
`authored_decisions/<venue>.json` for both lanes.

Every authored venue file must include or be bound to:

- session_id
- selection_id
- target_date
- lane id
- logic version
- reader manifest SHA
- complete venue card

The model-authored Decision Core semantics remain:

- exactly five unique marks;
- ◎ ○ ▲ △1 △2;
- four mainline cases;
- one independent ▲ case;
- final △2 vs strongest excluded alternative/null;
- sparse RRDB refs;
- natural reader-facing prose.

Do not mechanically copy decisions from the sibling lane.

## 8. 0.5.0 freeze compatibility

Extend research Freeze support so v0.5.0 can be frozen as its own logic cohort.

Do **not** repoint current production logic.

Prefer one of these safe approaches:

1. introduce a dedicated 0.5.0 research record schema and register it in the
   freeze validator; or
2. introduce an explicit A/B lane record wrapper that preserves the existing
   Decision Core but identifies v0.5.0 unambiguously.

Whichever is chosen, the final artifact must not falsely claim to be v0.4.6.

The freeze must validate the Reader input used by its lane:

- v046 record binds to the original clean Reader;
- v050 record binds to the derived 0.5.0 normal Reader and the corresponding
  original clean source hash/session manifest.

## 9. Shared Freeze barrier

Implement a deterministic barrier/checker.

Suggested module:

`src/racenote_ab_freeze_barrier.py`

Before target result/market may be opened, it must verify both lanes:

- complete expected race roster;
- complete venue set;
- Validator PASS;
- market blind;
- result not opened;
- five marks per race;
- correct lane logic id;
- common session id;
- common target date;
- common original clean Reader manifest hash;
- all expected race identities equal;
- sibling lane was not used as input;
- both statuses are `FROZEN_CLEAN_BLIND`.

Only then write:

`ab/ab_freeze_barrier.json`

with:

`status = BOTH_LANES_FROZEN_CLEAN_BLIND`

No evaluation code may proceed without this barrier.

## 10. Branch / task isolation contract

Stage E must document an operating procedure for actual A/B runs.

Recommended procedure:

### Step 1 — session preparation

On main:

- reserve BTDAY once;
- prepare clean evidence;
- create/commit the sealed A/B session;
- record the exact base commit.

### Step 2 — lane tasks

Start two fresh Cloud tasks from that exact base:

- Task A receives only the v0.4.6 lane instruction and shared evidence.
- Task B receives only the v0.5.0 lane instruction and shared evidence.

Create separate branches.

The task prompts must tell Codex:

- do not inspect sibling A/B branches;
- do not inspect sibling authored/frozen files;
- do not use prior marks/prose as inputs;
- use only shared clean evidence plus the lane's Reader contract.

### Step 3 — no early merge

Keep both prediction PRs unmerged until both lane freezes are complete.

### Step 4 — integration

A third non-authoring task may then inspect both frozen branches/artifacts and
create the combined barrier/integration artifact.

### Step 5 — results

Only after the combined barrier is PASS may result/market evaluation begin.

## 11. Existing BTDAY compatibility

Do not break the current one-lane v0.4.6 prospective route.

Existing:

- prepare request
- v046 venue save
- v046 bind
- v046 finalize
- v046 archive

must keep working unchanged for ordinary BTDAY validation.

A/B must be an additive research lane.

## 12. Tests

Add deterministic tests covering at minimum:

1. one prepare can initialize one A/B session;
2. both lanes bind to the same target date / selection id / race roster;
3. original clean Reader hashes are identical/common;
4. v050 Reader derives deterministically from the original clean Reader;
5. v050 model input excludes provenance;
6. sibling authored/frozen data is not accepted as Reader input;
7. v046 and v050 authored files can coexist without path collision;
8. v050 freeze identifies itself as v0.5.0, not v0.4.6;
9. barrier fails when only one lane is frozen;
10. barrier fails on race roster/hash/session mismatch;
11. barrier passes only when both independent lanes are complete and clean;
12. current production pointer remains v0.4.6;
13. existing v0.4.6 tests remain green.

Use synthetic fixtures for destructive/negative tests.

Do not open target results.

## 13. Required deliverables

At minimum create:

### Implementation

- A/B session initializer
- deterministic v050 Reader session materialization
- lane-specific authoring/binding/freeze support
- both-lanes Freeze barrier
- tests

### Documentation

Create:

`docs/racenote/RACENOTE_CLEAN_BLIND_AB_RUNBOOK_v0_1.md`

The runbook must explain exactly how the user should operate the two separate
forecast threads/tasks.

### Stage E report

Create:

`docs/racenote/research-work/reports/20261006_RACENOTE_V050_STAGE_E_AB_HARNESS_REPORT.md`

Report:

- implemented modules
- schemas/contracts
- test results
- compatibility with ordinary v0.4.6 BTDAY
- how independence is enforced
- known limitations
- example session tree
- production impact
- exact next action

## 14. Stage E decision

Choose exactly one:

- `READY_FOR_DUAL_THREAD_PILOT`
- `REVISE_AB_HARNESS`
- `AB_HARNESS_NOT_VIABLE`

Do not actually perform the pilot during Stage E.

## 15. Commit / PR discipline

Stage E is incomplete unless durable Git artifacts exist.

- work on a dedicated branch;
- include only Stage E-related changes;
- run the relevant tests;
- create a PR against latest main;
- do not change the current prediction pointer;
- do not merge prediction artifacts;
- return commit SHA, PR, changed files, test summary and Stage E decision.

## 16. Production impact

Must remain **ZERO**.

This harness is research infrastructure only. The active prospective prediction
logic remains v0.4.6 until a later explicit promotion decision after clean-blind
A/B evidence.
