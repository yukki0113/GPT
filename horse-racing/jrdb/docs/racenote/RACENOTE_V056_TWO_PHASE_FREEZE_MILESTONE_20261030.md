# RaceNote v0.5.6 — Common pipeline to Two-Phase Freeze milestone

Status: IMPLEMENTATION TARGET (not an executed PASS). Owner: RaceNote research/implementation. Branch PR #2246.

## Boundary

One common v0.5.6 forecast engine for both BTDAY and FORWARD. **No mode split in model judgment or freeze phases**. Only after confirmed persisted Prediction and Confidence Freezes:
- BTDAY -> after required cohort/result guard, official post-freeze JRDB results / assessment (not a second forecast).
- FORWARD -> separate newspaper editorial pass using sealed pre-race RaceNote + frozen prediction + shared prediction_audit_comment + frozen Confidence review -> PWA formatting/submission (outside this milestone).
- No automated marks, confidence, or rationales; LLM independently authors both phases.
- v0.5.5 r6 paths and historical Freeze remain immutable/reproducible.

## Milestone gates (M1–M7)

| Gate | Deliverable | Machine-checkable acceptance | State |
|---|---|---|---|
| M1 | v056 session/contract/versioned schema, execution mode enum BTDAY/FORWARD | version mismatch fails closed; v055 remains supported; root-specific SHA / sources cannot cross | NOT DONE |
| M2 | prediction authoring via bound Reader, one race per LLM decision, Decision Core + common prediction_audit_comment | all runners considered; 36/36 roster where applicable; legacy comment prose constraints NOT incorrectly applied | NOT DONE |
| M3 | separate Prediction Freeze workflow and record/hand-off commit | canonical main persisted frozen records + verified SHA + immutable repeat rejection; confidence not yet authored | NOT DONE |
| M4 | separate independently LLM-authored Confidence A/B/C/Z with structured review | frozen ◎ exact match; positive win case, rival comparison and defeat scenario; mandatory Z only for existing special races | PARTIAL: isolated gates only |
| M5 | separate Confidence Freeze workflow and commit | confidence_frozen records/hand-off + Turn2 summary on main; no results/target market until appropriate seal | NOT DONE |
| M6 | clean-blind E2E and interrupted/replay/mismatch regressions | positive two-phase 1-day BTDAY fixture and FORWARD common-phase fixture; failure injection; no cross-generation writes; show run URL / commit SHA | NOT DONE |
| M7 | new-run routing/runbook/current pointer cutover | config, workflows, T1, T2, CLI reference v056; v055 historical replay still works; rollback documented | NOT DONE |

M1–M5 must run through a **single shared pipeline**; mode-specific model prompts or divergent Freeze record formats are not permitted unless purely conditional mandatory metadata. M6 must include FORWARD **through the second Freeze**, not newspaper or PWA.

## Contract invariants

- Phase 1 output: marks, full Decision Core, `prediction_audit_comment` shared across both modes; no Confidence.
- Phase 2 output: confidence grade + `confidence_review`, identity anchored to frozen honmei; no mark changes.
- Phase 3 (future, FORWARD only): `forward_newspaper_comment`; entirely skipped by BTDAY. This phase does not mutate frozen SHA and only consumes pre-race source.
- Keep operational mode (`PIPELINE` vs `T2_ONLY`, which controls next T1 prefetch) separate from forecast execution mode (`BTDAY` vs `FORWARD`).
- Do not use v055 runtime tools with changed contract labels as though they were v056-ready.
- README links marked v056 current only after confirmed M6 and M7; until then v055 r6 remains active.
- Tests must be executed and their actual results recorded; added unit test files without run evidence are not PASS.

## Next implementation sequence

1. Inventory exact src/schema/workflow entrypoints and tests from current main.
2. Wire new v056 session/record validators, using existing v055 shared data readers without violating semantic contract.
3. Add isolated v056 prediction and confidence Freeze entrypoints and start-to-end gates, using the supported GitHub connector/Actions route.
4. E2E rehearsal on clean-blind historical fixture: Prediction/Confidence fully persisted, no post-freeze result opening.
5. Commit live pointer/docs changes only after gates passed. Then proceed to forward editorial/PWA separately.
