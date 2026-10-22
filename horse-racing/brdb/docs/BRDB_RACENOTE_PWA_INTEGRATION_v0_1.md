# BRDB → RaceNote / Newspaper / PWA Integration v0.1

Status: PHASE 3 DESIGN/HANDOFF CLOSED — NOT INTEGRATED OR DEPLOYED
Date: 2026-10-22

## Ownership

- BRDB: canonical pedigree Reader + frozen Blood Review v0.1 + display handoff.
- RaceNote: independently produces as-of-exclusive P2 evidence; no reimplementation in PWA.
- Newspaper: exact identity join to daily horse entries, emits addon and source_status.
- Kenshow_Labo PWA: displays the published addon and its statuses in a blood-detail dialog.
- Momotaro: out of scope by default; must not automatically inherit private BRDB addon.

No current Pages, Release, daily job, newspaper layout, or RRDB state changes in Phase 3A.

## Stable review/handoff

Producer `horse-racing/brdb/src/brdb_newspaper_handoff.py` accepts only `brdb-review-v0.1` and projects:

```json
{
  "contract_version": "brdb-newspaper-handoff-v0.1",
  "status": "AVAILABLE",
  "display_available": true,
  "detail": {
    "horse_id": "...",
    "status": "AVAILABLE",
    "facts": {},
    "classification": {},
    "review": {},
    "coverage": {},
    "confidence": "DESCRIPTIVE_ONLY",
    "provenance": {}
  }
}
```

It rejects scores, inferred regional type, unsupported versions/statuses and mismatched/missing horse IDs. Full-field projection requires an exact requested cohort including unavailable rows. It does not perform a name join or a historical query.

## Proposed Newspaper placement

On each exact matched horse:

```text
horse.addons.brdb = project_review(review)
```

The Newspaper join must match the authoritative race identity and horse_id, not horse name. If the current Newspaper horse object lacks canonical horse_id, correct the upstream identity path before adding the addon. Do not infer identity by textual name.

Day/race `source_status.brdb` must distinguish `READY / PARTIAL / ERROR / NOT_PROVIDED` and include generation/schema/review-version provenance. A BRDB failure is an optional-addon failure and must not destroy PACI/base or other addons.

## Proposed PWA detail view

- Kenshow_Labo: add a `血統詳細` affordance with the existing shared dialog.
- Show sire/dam/BMS, official sire/BMS line, as-of-safe descriptive sire/BMS P2 starts/wins/top3 rates and sample size, coverage and reason when unavailable.
- No score, regional label, suitability verdict, or condition inference in Javascript.
- If addon missing, leave the existing newspaper display intact.
- If `AS_OF_UNVERIFIED`, do not display withheld identity/P2 from another path.
- Reuse existing dialog lifecycle and CSS conventions; do not alter the mark positions or Edge lane.
- Preserve mobile 360/390/430px, existing sticky and scroll behavior.
- Do not project to Momotaro without a separately approved scope.

## Deferred implementation / independent release gates

1. Verify actual canonical Newspaper JSON horse identifier, daily addon merge layer, and all downstream publisher/reader entrypoints. Add an exact-key BRDB merge adapter with field cardinality audit.
2. Wire RaceNote authoritative P2 `adapt_racenote_bundle` → `BloodReviewEngine` → `project_field` in a sidecar producer. Use canonical CURRENT pin.
3. Validate one full authoritative race with 9 entries and unavailable statuses preserved; verify no output leaking race finish/odds.
4. Add Newspaper addon reader/merge unit tests for absent/error/old payload, duplicate/missing identities and other-addon non-regression.
5. Add private Kenshow_Labo-only modal, rendering tests and manual small-screen check.
6. Run full `JRDB PWA Pages` only after explicit production-cutover decision. Verify actual hosted Pages and current package; keep production untouched before that.

**Phase 3 is closed at the design/handoff boundary.** The items above are deferred to a separately authorized integration/release project; they are not part of Phase 3 completion. No Newspaper merger, UI, daily workflow, Release, Pages, or Momotaro changes are authorized by this document. Before any future deployment, the user must review and approve the exact blood-detail fields, wording, status/coverage presentation, absence of predictive claims, personal-vs-shared PWA scope, and real-device screenshots. Preparation and design alone do not grant publication permission.
