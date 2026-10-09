# EdgeDB v0.5 in the personal Newspaper PWA

Status: PRODUCTION / 2026-10-09

The daily `JRDB Newspaper Day Build via Issue` Action is the production entrypoint. It builds the audited PACI base day, resolves canonical Analysis, attaches the existing `STANDARD` EdgeDB Query, then runs the v0.5 addon once for every runner using the same PACI and canonical Analysis current generation. It retains the v0.2 `special_memos` data for compatibility, while the public `newspaper.html` removes its former display column. The public display consumes only `horse.addons.edge_v05.candidate_ids` and each race's `edge_v05_candidates` dictionary. It does not evaluate Edge conditions or sort candidates in the browser.

The v0.5 candidate inventory is the frozen 1,620-candidate cohort. The checked-in `config/edgedb/v0_5/frozen/v05_2026_oos_eval_artifact.zip` is an immutable copy of Actions artifact `11478468034`, SHA-256 `f10034cf6d2d730dcb3d76b6c9be41c90d36e61e49c94b70ab7458f296eb9f13`. The builder verifies this digest, membership, and the CSV fingerprint against the frozen manifest. This avoids depending on an expiring Actions artifact during daily runs. Canonical Analysis remains the same bundle verified by generation ID and manifest SHA before the STANDARD Query step; no additional Analysis copy or source is introduced.

Current production coverage is: T1 supported, T2 supported, T3 supported when the prior link resolves exactly, and T4 surface transition supported when the prior link resolves exactly. T4 first-use is not connected, T5 first blinkers is not connected, and T6 going has no pre-race going source. Those unavailable features remain unknown and cannot light up. The source status is `PARTIAL` when these constraints are present. A v0.5 source or join error produces `edge_v05=ERROR` in the day and race manifests and keeps the PACI base, STANDARD Edge, and other addons. The page shows an empty v0.5 Edge cell for missing or error status.

The production column is a standalone `rowspan=2` Edge header after the mark group and before history. The legacy special memo header and cells are removed from the rendered table. A horse with at least one candidate shows `○`, opening the candidate details. The first two candidates are visible; remaining candidates remain in a disclosure. The 2026 tier and historical ROI are explanatory data, not a forecast or recommendation.

The frozen OOS evaluation includes races through 2026-10-04. The builder refuses a target day on or before that date to avoid retrospective leakage. Therefore v0.5 production applies only to post-endpoint daily packages; historical 2026-10-04 remains ineligible for v0.5 retrofit.

The v0.5 production PWA integration was merged in PR #1903 (merge commit `f739f186ba20df65d7076654e7528d8b205e5df0`). Daily operation must use the existing day-build workflow and existing frozen cohort/matcher/addon path; do not recreate the matcher in chat-side Python or derive missing features heuristically.

## Daily audit and publication

After day build, inspect at least:

```text
audit status
race count
venue codes
history coverage
completeness
source_status
edge_v05.state
matched_runner_count
signal_count
missing_join_count
extra_join_count
```

Normal exact-join expectation:

```text
missing_join_count = 0
extra_join_count = 0
```

A zero matched-runner count is not automatically an error, although a full normal meeting with zero matches should trigger input/matcher/status investigation.

Publication is complete only after the canonical day-package is published by the formal `JRDB Newspaper Current Publish`, the downstream `JRDB PWA Pages` full-site deployment succeeds, and the public Newspaper page is checked. The Release alone is not the completion boundary.

## PWA troubleshooting order

If the Edge column alone is empty, inspect in this order:

```text
day manifest source_status.edge_v05
-> race metadata.source_status.edge_v05
-> horse.addons.edge_v05
-> edge_v05_candidates
-> candidate_ids / dictionary key consistency
-> newspaper-edge-v05.js
```

If the Edge column itself is absent, inspect the static shell, `newspaper-edge-v05.js`, `newspaper-edge-v05.css`, asset query versions, and Service Worker cache.
