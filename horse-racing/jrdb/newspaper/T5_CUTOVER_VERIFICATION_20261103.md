# EdgeDB decommission — T5 Git/current operation readiness (2026-11-03)

> Dated snapshot, not a dynamic current pointer. Re-check latest main, current Releases, Actions and Pages before production assertions.

## Boundary
- T1 PR #2339, T2 PR #2341, T3 PR #2343, T4 PR #2344 merged. Starting main `d549a20ec1b39f07bffb981eb70846b000440ea1`.
- Phase 3 inventory/audit: `PHASE3_AUDIT.md`, Issue #2334; archive `../archive/retired-edge-training/`.
- T5 repairs current operating docs and CI prerequisites. T6 Drive source deletion and T7 final closure remain **out of scope**.
- Preserve Analysis Parquet, JRDB Reader, RaceNote/Eval/RRDB/Fact Lite/Stats Mart, immutable revisions and Releases, archived research, `jrdb_newspaper_retired_sources.py`, and retired-source tests.

## Baseline observations
- T4 audit [run 41569400606](https://github.com/yukki0113/GPT/actions/runs/41569400606): SUCCESS.
- Pages [run 41569560253](https://github.com/yukki0113/GPT/actions/runs/41569560253): FAILURE at PWA focused tests before artifact/upload/deploy; Momotaro test could not import `jrdb_newspaper_retired_sources`.
- Common Reader [run 41569560213](https://github.com/yukki0113/GPT/actions/runs/41569560213): FAILURE from reference to removed `test_racenote_v11p_true_forward_day.py`.
- Newspaper Current Release assets last updated 2026-10-31 16:17 UTC; timestamp alone is not proof of a post-Phase-2 PACI-only production publish. Git-tracked `publish/current.json` is an older sample.

## T5 changes
- Set shared JRDB source path for all PWA focused-test commands; do not remove failing tests or retirement guard.
- Remove only deleted RaceNote test filename from Common Reader CI; preserve active suites.
- Update current README/CONTEXT/HANDOFF/WORKFLOW/DEPLOYMENT_TRIGGER to PACI-only; retain independent addons and archive boundary.

## Acceptance gates — verify after PR and main merge
- [ ] T5 PR CI and T4 retirement audit PASS.
- [ ] T5 PR merged after review.
- [ ] Main Pages run: tests, artifact preparation, upload, deploy PASS.
- [ ] Actual PACI-only Current source verified (date/revision, races/headcount, source_status and SHA/size).
- [ ] Individual/Momotaro public surfaces: EdgeDB/Training Edge absent; Eval/RaceNote/RRDB/keibailuka/history retained.
- [ ] Device-specific behavior confirmed separately or explicitly unverified.

Do not infer a pending gate from an old run, synthetic test, or release timestamp.
