# BRDB M7 × RaceNote × JRDB Newspaper: actual consumer input/output contract audit (2026-11-18)

Status: **SOURCE CONTRACTS AUDITED / RESEARCH-ONLY IDENTITY PREFLIGHT IMPLEMENTED / NO NEWSPAPER OR RACENOTE PRODUCTION INTEGRATION**.

Tracker: [BRDB M7 #2628](https://github.com/yukki0113/GPT/issues/2628). M6 independent scientific blocker: [#2395](https://github.com/yukki0113/GPT/issues/2395), OPEN/BLOCKED.

## 1. Source-of-truth inspection

These are **actual main source/code/schema** boundaries; neither the earlier BRDB design handoff nor an invented hypothetical payload is substituted for production behavior:

| Boundary | Main canonical file | Observed contract |
|---|---|---|
| RaceNote authoritative daily bundle | `horse-racing/jrdb/src/build_racenote_daily.py`, `horse-racing/jrdb/schema/racenote_bundle_schema_v1_0.json`, `src/racenote_reader_view.py` | PACI → official RaceNote bundle (schema `1.0`, `race`, `metadata`, `horses`), reversible Reader View. **Not a Newspaper prediction-handoff CSV.** |
| RaceNote BRDB descriptive P2 lane | `horse-racing/brdb/src/brdb_racenote_p2_adapter.py` | `adapt_racenote_bundle` requires exact full cohort of canonical `basic.horse_id` and explicit P2 provenance/as-of; it is separately validated and does not produce M7 prediction. |
| RaceNote prediction → Newspaper | `horse-racing/jrdb/docs/RaceNote_Newspaper_Output_Contract_v0_1.md`, `horse-racing/jrdb/src/jrdb_newspaper_merge_external.py` | CSV `date,venue_code,venue,race_no,race_key,horse_no,horse_name,mark,prediction_rank,confidence,race_short_comment,model_version,source_semantic_sha256` and optional `horse_short_comment`; **no canonical horse_id**. `load_racenote(..., sparse_marks=True)` supports marks rank 1..5 only. |
| Newspaper base generation | `horse-racing/jrdb/src/jrdb_newspaper_build.py`, `src/jrdb_newspaper_day_build.py` | PACI Common Reader; `horses[].key.horse_id = KYI blood_registration_no or null`; `key.horse_no` required, base field count from BAC. Addon dict contains `eval`, `racenote_prediction`, `keibailuka` (and optional other existing addons from separate merge). |
| Newspaper bundle output schema | `horse-racing/jrdb/schema/jrdb_pwa_newspaper_race_schema_v0_1.json` | `schema_version=0.1`, `bundle_kind=jrdb_pwa_newspaper_race`; `race.race_key,date,venue_code,venue,race_no` required; `horses[].key.horse_no` required; **`key.horse_id` optional and `null` permitted**. `addons.additionalProperties=true` but this does **not** mean BRDB has been integrated. |
| Newspaper external merge | `horse-racing/jrdb/src/jrdb_newspaper_merge_external.py` | `merge_day` accepts Eval, Iluka, RaceNote prediction, RRDB recommendation, **not BRDB**. Actual RaceNote join is `(venue_code,race_no,horse_no)` plus exact horse_name/date/race_key/venue. `addons.racenote_prediction`, `race_notes.racenote_short_comment`, `metadata.source_status.racenote_prediction` are prediction-specific and not a BRDB contract. |
| Newspaper source state | `metadata.source_status` plus daily manifest `source_status` | Existing `racenote_prediction` source-specific `READY` may mean **all five sparse prediction selections** merged, not complete 18-horse coverage. Cannot infer BRDB full-field safety from this status. |
| Frozen BRDB Newspaper handoff v0.1 | `horse-racing/brdb/src/brdb_newspaper_handoff.py` | Accepts only `brdb-review-v0.1`, emits `brdb-newspaper-handoff-v0.1`. It rejects M7 v0.3/preview; handoff not wired to the live external merger. |
| BRDB M7 research | `horse-racing/brdb/src/brdb_m7_research_consumer_preview.py` + accepted [M7 real E2E](BRDB_M7_REAL_FIELD_E2E_ACCEPTANCE_20261117.md), [④ detail](BRDB_M7_RELATIVES_DETAIL_RESEARCH_CONTRACT_v0_1_20261117.md) | Full 18-horse `horse_id` + `horse_no` canonical cohort, no rank/probability/score; ③④ remain `AS_OF_UNVERIFIED`. No publication authorization. |

The 2026-10-22 [design/handoff](BRDB_RACENOTE_PWA_INTEGRATION_v0_1.md) explicitly defers the live Newspaper/PWA addon join, device rendering, and release. Its proposed `horses[].addons.brdb` and `source_status.brdb` are **not** evidence of implemented production code.

## 2. Actual 2026-11-15 comparison

Accepted BRDB PACI target: `PACI261115.zip`, Tokyo 12R, race `05265412`, **18 entrants**. The previously accepted M7 private integrated v0.3 is 18/18; integrated v0.3 SHA `96129fdd70155cea98e07e1a5725116e6d2ade7dc3ee9f8ddf1c8a625655774f`.

Actual committed RaceNote file: `horse-racing/jrdb/newspaper/incoming/RaceNote_20261115_PWA_Prediction_Sparse_v056.csv`. CSV source has **180 prediction rows in total (36 races × 5 marked horses)**. Race `05265412` has **5 rows** (horse numbers `18,1,9,3,10`; ranks 1–5). The header does **not** contain `horse_id` and thus cannot serve as a BRDB full-field source or canonical blood registration number join. Matching the selected five horse numbers does **not** prove safe identity for the other thirteen horses. The same day’s `RaceNote_20261115_PWA_Social_Handoff_v056.json` is a separate social handoff contract, not the Newspaper CSV merger input.

**Important distinction:** `racenote_prediction` is a prediction/mark surface; RaceNote P2 historical pedigree evidence is a separately provenance-guarded lane and must not be confused with v0.5.6 sparse predictions.

## 3. Blocking seams and required behavior

| Gate | Current observed state | Required before any addon implementation |
|---|---|---|
| Canonical identity | Newspaper base has optional nullable `key.horse_id`; ordinary `validate_bundle` checks horse-number uniqueness, not canonical ID uniqueness | Enforce 8-digit `horse_id`, non-null, unique and exact `(horse_no,horse_id)` equality with M7 **for every entrant**. Never join BRDB by name, rank or selected prediction rows. |
| Race context | `date,race_key,venue_code,venue,race_no,surface,distance_m` available from base | Validate exact race_key, date, venue_code, surface enum mapping, distance, and full field size. No implicit code translation beyond canonical known surface map. |
| Source separateness | Prediction CSV rank1..5 accepted as sparse; addon namespace owned by existing merger | Do not overwrite `addons.racenote_prediction` or `race_notes`, `rrdb_recommendation`, Eval, Iluka, PWA marks. BRDB addon requires its own separately reviewed namespace/ownership policy. |
| Source status | No live BRDB state registration | Explicit independent `source_status.brdb`, provenance, expected/resolved counts and policy for `PARTIAL`/`ERROR`/`NOT_PROVIDED` would be a **future versioned integration change**. A ready prediction source is not a BRDB-ready source. |
| Research safeguards | `AS_OF_UNVERIFIED`, non-scoring | Remain ③④ unverified, preserve `SOURCE_UNAVAILABLE` and zero-start nulls; no positive/negative suitability, score, odds, mark, rank, probability or confidence promotion. |
| Consumer acceptance | Newsp. `addons.additionalProperties=true`, but no registered BRDB producer/merger/display | **Schema allowance is not functional acceptance**. Validate real Newspaper package, per-source non-regression and chosen user-visible wording, and obtain explicit production authorization before PWA or Newspaper modification. |

## 4. Implemented audit-only preflight

New `src/brdb_m7_consumer_boundary_audit.py` is **strictly read-only**. It accepts a pre-existing, actual-shape Newspaper race bundle plus the research-only M7 preview and checks:

1. supported exact Newspaper v0.1 and M7 preview research contracts, frozen source SHA references;
2. full race, surface, distance and field-size agreement;
3. every `(horse_no, horse_id)` present, 8-digit, unique, sorted and **exactly matching**;
4. `jrdb_base` READY, no pre-existing `addons.brdb` or `metadata.source_status.brdb`;
5. ①② descriptive status only, ③④ unverified/unavailable; no score, rank, probability, or suitability verdict;
6. no mutation of either input; returns an **aggregate-only** SHA/coverage receipt labeled `IDENTITY_BOUNDARY_PASS_RESEARCH_ONLY`, with explicit open gates and `production_authorized=false`.

It does **not** perform the actual BRDB merge, create or inject a Newspaper addon/source_status, convert v0.3 to frozen v0.1, or touch an online consumer.

Test file `tests/test_brdb_m7_consumer_boundary_audit.py` validates the actual `_runner_row` source projection against the current Newspaper Draft2020-12 JSON Schema, runs the actual `load_racenote` on the 2026-11-15 sparse CSV, verifies the frozen v0.1 handoff refuses M7 research, checks no BRDB input exists in current `merge_day`, and tests fail-closed identity/as-of/namespace/prediction guard cases. The CI workflow also executes the existing actual JRDB Newspaper builder/merger regressions and frozen BRDB P2/Newspaper regressions.

## 5. Interpretation / graduation decision

**Current conclusion: only identity-level research preflight is suitable for acceptance**, not a production bridge. A future authorizing decision must review the exact display fields and wording, every horse status, optional addon failure behavior, complete real Newspaper package regression and real-device preview. Production CURRENT, RaceNote, Newspaper, Kensho_Labo/Momotaro and PWA remain untouched. M6 #2395 remains OPEN/BLOCKED.

Research M7 can proceed independently; as-of-unsafe blood evidence must not silently become a predictive score or production mark.
