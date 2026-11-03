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

## Verified T5 outcome — 2026-11-03

- **Git/CI: PASS.** T5 docs and CI repair [PR #2345](https://github.com/yukki0113/GPT/pull/2345) merged to `b6af2530c0cad225cf14a97539c2298485e6f8c9`. PR Common Reader [41632167186](https://github.com/yukki0113/GPT/actions/runs/41632167186) and T4 audit [41632167068](https://github.com/yukki0113/GPT/actions/runs/41632167068) both PASS; main Common Reader [41632408445](https://github.com/yukki0113/GPT/actions/runs/41632408445) PASS.
- **Follow-up Pages CI correction: PASS.** The first post-merge Pages [41632408437](https://github.com/yukki0113/GPT/actions/runs/41632408437) surfaced a deleted test filename. [PR #2346](https://github.com/yukki0113/GPT/pull/2346) migrated the Pages gate to retained `test_retired_training_asset_boundary.py`; regression audit PASS and merged as `066e6cb1b43a78b7a3386cfd6c231a9555c08dd6`.
- **Main full-site Pages: PASS.** [Run 41633046397](https://github.com/yukki0113/GPT/actions/runs/41633046397): focused tests, Prepare Pages artifact, Upload Pages artifact, Deploy to GitHub Pages **all SUCCESS**. Pages environment URL `https://yukki0113.github.io/GPT/`. The deployed artifact includes the current Newspaper Release, passes SHA/size/manifest validation and retired-source scrub, and includes independent Momotaro Newspaper Release.
- **PACI-only source day: PASS as day build, not as post-cutover Current publish.** [Issue #2338](https://github.com/yukki0113/GPT/issues/2338) reports [run 41450479244](https://github.com/yukki0113/GPT/actions/runs/41450479244), 2026-11-01, 24/24R, 318 runners, 1059 resolved histories, `audit_status=PASS`. The independently queried `jrdb-newspaper-current` Release metadata last updated 2026-10-31 16:17 UTC, before the Phase 2 merger; a fresh PACI-only production Current publication cannot be claimed from that evidence.
- **User PWA acceptance (2026-11-03): REPORTED PASS.** The user checked the PWA and reported `動作問題ありません` (no operational problems). This is direct user feedback, not an independently reproduced HTTP/device or per-surface inspection. The user did not separately specify personal versus Momotaro screens, offline/sync cases, or inspected addon fields; do not infer those individual checks as complete. No Drive data or old immutable revisions were changed.

## Acceptance gates — verified results

- [x] T5 PRs merged with related CI and T4 retirement audit PASS.
- [x] Main Pages run: focused tests, preparation, upload and deployment PASS.
- [x] PACI-only synthetic and real 2026-11-01 day build audit PASS (24R/318 runners; **not** the same as Current Publish).
- [ ] Newly published post-Phase-2 PACI-only Current Release verified end-to-end with its own source identity, SHA/size and source_status.
- [x] User-reported PWA basic operational check on 2026-11-03: no problems observed (scope not specified).
- [ ] Separate personal and Momotaro UI/addon/retired-field checks documented individually if required for formal acceptance.
- [ ] iOS real-device UI/offline/sync verification, if required by the operating team.

**T5 Git/CI/Pages cutover complete; user-reported PWA basic operation also PASS. Fresh post-cutover Current publication and any separately required per-surface/offline/sync verification remain pending. Do not declare T7 final retirement or delete T6 Drive sources based solely on a Pages run or general PWA feedback.**
