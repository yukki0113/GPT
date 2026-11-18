# BRDB M7 × actual PACI Newspaper full-field research preflight and addon non-interference — 2026-11-18

**Decision: REAL-PACI FULL-FIELD CANONICAL ID MATCH PASS; NON-RACENOTE ADDON NON-INTERFERENCE PASS; STRICT NEWSPAPER ALL-DAY JSON SCHEMA BLOCKED BY EXISTING DEFECTS; NO PRODUCTION AUTHORIZATION.**

- BRDB M7 tracker [#2628](https://github.com/yukki0113/GPT/issues/2628): OPEN. Independent M6 scientific blocker [#2395](https://github.com/yukki0113/GPT/issues/2395): OPEN/BLOCKED.
- Earlier [source-contract audit](BRDB_M7_RACENOTE_NEWSPAPER_CONSUMER_CONTRACT_AUDIT_20261118.md) established a strict research-only identity checker and a synthetic test. **This new audit adds real PACI-derived Newspaper JSON versus private M7 JSON, and actual existing RaceNote source merging.**
- Scope: read/audit and offline reconstruction **only**. No additive BRDB producer/merger, source_status change, forecast, BRDB CURRENT, Newspaper current publish, PWA/Pages/Personal/Momotaro mutation.

## Input source, authorization and audit mode

The **historically published immutable 2026-11-15 Newspaper day-package could not be found** in the connected Drive search or existing current Release (the available mutable current release asset was dated 2026-11-14). We therefore did **not** claim to inspect an already-published daily package.

Instead, using the existing **canonical source code** and the identical full official PACI input, we **reconstructed a new Newspaper 2026-11-15 daily JSON** privately, then ran the unmodified production `merge_day` against the real, previously committed, source-authenticated sparse RaceNote forecast CSV. This supplies real source-to-source validation, not published-revision equivalence.

| Input | Identity / fixed provenance |
|---|---|
| PACI official bytes | `PACI261115.zip`, SHA256 `3c80e70a74a13874a82b7f7cf4c5f9415d6abbf186ec0ccfa1d2842e51a7b050`. |
| M7 research consumer preview | Private Library `/BRDB/M7/m7_research_consumer_preview.json`, raw SHA256 `a86cd81d9b1dd9f0cfb094bc327e2739080da15e6c2c003c7cb15686f2e20a1d`; canonical JSON SHA256 `bad84a4cceca76f4bf368f653595b0fa0f9bf8b229c9a66f4cdd6eeb37f68f89`. No score/rank/probability, `prediction_safe=false`, `production_authorized=false`. |
| Actual committed RaceNote | `horse-racing/jrdb/newspaper/incoming/RaceNote_20261115_PWA_Prediction_Sparse_v056.csv`, raw SHA256 `4db5fd8fb02719ce0658cdaa16e135f6d4d3d691b46caf6906e95c872619ca20`. |
| Source code | Exact GitHub commit `1a7e09b20fdcb42e5a8220906d338c139925bdab` transported through public-source/fixture-only [fallback #2635](https://github.com/yukki0113/GPT/issues/2635), [Actions run 44213659000](https://github.com/yukki0113/GPT/actions/runs/44213659000). Nine archived source/fixture files checked against SHA manifest. No private horse data included in transport. |
| Newspaper real builder | Unmodified `horse-racing/jrdb/src/jrdb_newspaper_day_build.py::build_day`, `jrdb_newspaper_build.py` plus `jrdb_raw.Parser`, *Analysis overlay disabled* (the normal PACI-only base). |
| Existing live merger | Unmodified `horse-racing/jrdb/src/jrdb_newspaper_merge_external.py::merge_day` with `racenote_sparse_marks=True`. |

## Real execution and measured reconciliation

1. `build_day(PACI261115.zip, "20261115", private_day_dir, revision=1)` produced **36 races, 505 horses**, valid race-key/fixed-source identities and output bundles. This is **newly reconstructed** rather than a published historical revision.
2. `merge_day(private_day_dir, private_merged_dir, revision=2, racenote_csv=<actual v056 CSV>, racenote_sparse_marks=True)` returned **PASS**, with 36/36 races and **180/180** marked horses, no unmatched entries.
3. For **Tokyo12R, `05265412`, 2026-11-15, 芝2000m**, the actual reconstructed Newspaper base and the actual merged Newspaper bundle each matched the **private full-field M7 preview exactly 18/18** by `(horse_no, eight-digit canonical blood_registration_no)`. All race identity/date/venue/surface/distance checks passed. The five real RaceNote selections remained the exact horse numbers **1, 3, 9, 10, 18**; remaining 13 horses still have M7 review identity.
4. The frozen `brdb_m7_consumer_boundary_audit.audit_newspaper_boundary` was run on **both** real base and real merged JSON; both reported `IDENTITY_BOUNDARY_PASS_RESEARCH_ONLY` with `canonical_id_matches=18`. The original Newspaper JSON and M7 preview semantic SHA were identical before and after the read-only checks.
5. Full-day exact before/after equality after excluding only the merger-owned `racenote_prediction` addon field: **all 505/505 horse core/other addons unchanged**. Non-RaceNote `metadata.source_status` **36/36 unchanged**. Race notes excluding the merger-owned `racenote_short_comment`: **36/36 unchanged**. **No `addons.brdb` or `metadata.source_status.brdb` was created.** This is namespace non-interference, not approved BRDB addon production integration.
6. On actual Tokyo12R merged JSON, malformed horse ID, missing ID, horse number, missing entry, surface, forged BRDB addon/source-status, and prediction-safe promotion were separately tampered. **8/8 real-data negative probes were rejected** by the existing fail-closed M7 auditor.
7. The target **base** JSON validated against the current Newspaper Draft2020-12 schema with **0 errors**. The same target after approved sparse RaceNote merge produced **13 schema errors**, exclusively missing the `racenote_prediction` key for 13 unselected horses. Therefore **full schema acceptance is not PASS**.

## Pre-existing Newspaper schema drifts — separate mandatory repair gates

**Defect A [#2637](https://github.com/yukki0113/GPT/issues/2637): sparse RaceNote addon omission vs required schema.** The current merger deletes `addons.racenote_prediction` for all horses, and only reinserts it for the 5 selected horses per race. Current `jrdb_pwa_newspaper_race_schema_v0_1.json` requires that property in every `addons` object. Across 36 real races, **325 unselected horses** are missing a schema-required property. The current sparse merger succeeded and all 180 selected prediction records were correctly consumed; **schema validity nevertheless fails in all 36 merged race bundles**. A product policy must choose between explicit `null` and versioned optionality, with consumer regression, before any production fix.

**Defect B [#2638](https://github.com/yukki0113/GPT/issues/2638): historical `horse_no=0`.** One Tokyo11R (`05265411`) base historical record `horses[17].history[0].horse_no=0` violates minimum `1` in the same schema. It is present before the BRDB audit or external addons. Its meaning requires canonical Reader/source investigation; do not fabricate a horse number or automatically alter history.

| Scope | Raw Draft2020-12 errors |
|---|---:|
| 36-race reconstructed Newspaper base | 1 (Tokyo11R history) |
| 36-race Newspaper after real sparse RaceNote merge | 326 (325 missing keys + same history) |
| Tokyo12R **before** merger | 0 |
| Tokyo12R **after** merger | 13 (sparse required-key drift) |
| Real M7 canonical ID preflight Tokyo12R, before + after | 18/18 each PASS |
| Other addon fields/core compared across full day | 505/505 identical |
| Other source states / other race notes | 36/36 each identical |

The two defects are **existing JRDB Newspaper schema/merger behaviors**, not caused by M7. No production repairs were made in this task.

## Private artifacts, hashes and readback

Uploaded **three new, private** files to personal Library `/BRDB/M7/`: `newspaper_05265412_base.json` (real PACI reconstructed), `newspaper_05265412_merged.json` (same after real 2026-11-15 v056 sparse predictions), `m7_real_newspaper_consumer_receipt.json` (aggregate-only). Each was materialized back independently from Library; **all byte SHA256 readbacks PASS**.

- Private target base file SHA256: `6a31af6fd5f94f29e4dcc4bdec195dc6fc2f31de18456328c045e1edc5d71557`.
- Private target merged file SHA256: `2538897a36bd958dab690370469055ea2454929b68d3f85325a1fd075484cba9`.
- Private receipt SHA256: `ade37b8115f7b13dbb5ac763a4a1adb42a98359445ac213a2e8ddd9532806e5e`.
- Base target canonical semantic SHA256: `bb552963f5a2b38a487661ad4269ac04bd61ec1b17ff15d8601e9906ed7618e6`.
- Merged target canonical semantic SHA256: `15cf700822b56ed44cf79e32e1605499aaa05e52e122c7e8cec4148f9d9f4154`.

All per-horse and full-day source/generated data remain private/local; **no private per-horse output was committed to public Git**. The existing committed sparse CSV was only used as previously public official-workflow input.

## Research regression acceptance and next gates

- [PR #2636](https://github.com/yukki0113/GPT/pull/2636) adds an auditable allowlist source/fixture handoff and synthetic 18-horse regression using the **actual** existing sparse RaceNote CSV and canonical Newspaper `_runner_row` + `merge_day`, with populated Eval/Iluka/RRDB sentinel namespaces. It checks 18-horse M7 read-only preflight, other addon/source-state non-interference and explicitly preserves awareness of the 13 sparse schema violations. Synthetic test is a regression; the **real 36-race execution above is independent local evidence**.
- **Research gate ACCEPTED:** real PACI ↔ M7 all 18 IDs and source-owned non-interference.
- **Strict consumer-schema gate BLOCKED:** pre-existing #2637 / #2638, plus no production BRDB merge namespace, no display wording/device approval, no independently verified historical as-of. No hidden promotion.
- **Still not done:** comparison with the *original historically published* 2026-11-15 immutable Newspaper package; production consumer integration, BRDB source-status registration, PWA display and explicit graduation.

M6 #2395 stays OPEN/BLOCKED, M7 #2628 stays OPEN. No production changes.

## Verified CI, main readback and disposition — 2026-11-18

- [PR #2636](https://github.com/yukki0113/GPT/pull/2636) successfully merged; merge commit `be35598ebbe4159a2716992ff2bca512f275f465`.
- [BRDB research CI run 44215290154](https://github.com/yukki0113/GPT/actions/runs/44215290154) **completed/success** (new real public sparse input + 18-horse synthetic noninterference test suite and existing BRDB regressions).
- [Repository cross-workstream CI run 44215290228](https://github.com/yukki0113/GPT/actions/runs/44215290228) **completed/success**.
- **Source-real result** is the separate local 36-race canonical PACI execution documented above; **CI fixture is intentionally synthetic** and does not imply private PACI was available to public CI.
- The research-only all-horse join gate is **PASS**, non-RaceNote addon non-interference **PASS**, and **strict after-merge Newspaper schema gate remains BLOCKED** by separately filed [#2637](https://github.com/yukki0113/GPT/issues/2637) and [#2638](https://github.com/yukki0113/GPT/issues/2638).
- Private target base, target merged and receipt were independently read back from Library `/BRDB/M7/` and all exact raw file SHA256 fingerprints matched. No production publication.
