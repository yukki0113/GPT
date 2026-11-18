# BRDB milestone reconciliation — 2026-11-16 (JST)

Status: **management audit / no production promotion**. Repository `yukki0113/GPT`, source of truth `main`. This document inventories completed scope and remaining gates; it does **not** assert all Blood Review development is finished.

## Scope and status definitions
- **Accepted research work** means implementation, tested behavior and documented historical evidence within a frozen cohort; it does not authorize prediction or operational use.
- **Research-only** results retain `prediction_safe=false` / `AS_OF_UNVERIFIED` until separately proven.
- The M0–M8 headings below are **management grouping**, not GitHub native Milestones nor a redefinition of the numbered ①–⑥ delivery sequence.
- GitHub Issue closure below refers to the **original Issue's bounded deliverable**, not elimination of all descendants or related scientific questions.

## Legacy open-Issue reconciliation (close candidates)

| Issue | Accepted evidence on main | Closure boundary |
|---|---|---|
| [#2212](https://github.com/yukki0113/GPT/issues/2212) | merged [#2213](https://github.com/yukki0113/GPT/pull/2213); 108 fixed IDs, 2025 annual UKC aggregate 109 members/47,239 rows; 2026 91 PACI ZIP/39,543 UKC rows; FOUND 104 / NOT_FOUND_IN_SCANNED 4, row-level artifact validated | 2025 PACI **container** inventory not included; 2026 observations do not prove 2025 as-of |
| [#2214](https://github.com/yukki0113/GPT/issues/2214) | merged [#2215](https://github.com/yukki0113/GPT/pull/2215); immutable 104-horse addition, 128,858 horses, 70 tests, deterministic rebuild and Drive readback | performed in managed runtime; GitHub Actions run evidence not claimed; later superseded by #2229 |
| [#2218](https://github.com/yukki0113/GPT/issues/2218) | merged [#2219](https://github.com/yukki0113/GPT/pull/2219); 91 ZIP, fixed 10,680 horses / 39,543 KYI declarations, static/as-of distinctions and complete audit | KYI declarations are **not confirmed actual starts**; period ends 2026-10-25 |
| [#2220](https://github.com/yukki0113/GPT/issues/2220) | merged [#2221](https://github.com/yukki0113/GPT/pull/2221); 3,794 missing horses and 10,016 declarations attributable to the 104-ID-only overlay (not missing UKC source) | cause-only audit; build performed later in #2229 |
| [#2223](https://github.com/yukki0113/GPT/issues/2223) | merged [#2229](https://github.com/yukki0113/GPT/pull/2229); generation `5279af0bd8226cde` with 132,652 unique horses; fixed 2026 KYI static join 100%; 22-file byte-identical rebuild | selected-latest **race-date** safe 33,029/39,543; static completeness is not temporal correctness or production CURRENT |
| [#2230](https://github.com/yukki0113/GPT/issues/2230) | merged [#2231](https://github.com/yukki0113/GPT/pull/2231); point-in-time history Reader v0.3, day-level source profile 39,543/39,543, no future profile leak; later as-of-parent research [#2233](https://github.com/yukki0113/GPT/pull/2233) | intraday availability unverified; annual history limited; historical parent resolution was separate #2233 |

Original audit outputs and SHA references remain linked in their corresponding PR/Issue; do not change existing accepted numbers.

## Milestone overview (management grouping)

| Area | Status | Next gate |
|---|---|---|
| M0 Source inventory / contract | bounded work complete | keep source/identity provenance |
| M1 CURRENT / Reader foundation | operational baseline implemented | no unapproved CURRENT pointer revision |
| M2 Blood Review v0.1 | frozen | preserve schema/contract |
| M3 Research pedigree generation | accepted for fixed cohort | static != as-of; as-of reader remains research-only |
| M4 Stallion master / ancestry work ③-A/B/C, ④ | research partial completion; Stage3B root identities 50/50 reviewed; 36 label differences classified | 29 no-ID alias-review rows (21 pairs), 10/40 missing gen2/gen3 names, old-ancestor IDs; no inferred cross |
| M5 Condition research D3 | accepted retrospective description [#2599](https://github.com/yukki0113/GPT/pull/2599) | causal/conditional suitability not demonstrated |
| M5-D4 Non-scoring supplemental sidecar | real PACI full-field E2E accepted [#2603](https://github.com/yukki0113/GPT/pull/2603); exact PACI user-side pre-off availability accepted in #2619 | provider release timestamp remains independently unknown; D3 remains AS_OF_UNVERIFIED |
| M6 Predictive-value study | **BLOCKED** [#2395](https://github.com/yukki0113/GPT/issues/2395) | immutable pre-off-time pairs, results and independently supported as-of |
| M7 Integrated Blood Review promotion | v0.3 candidate and **real PACI 18-horse research E2E accepted**; **production promotion not accepted** | qualified interpretation rules, non-lossy ④ numeric contract review, consumer-contract regression and explicit graduation |
| M8 RaceNote / PWA handoff | **not authorized** | M7 acceptance plus consumer-contract regression |

## Prioritized next work
1. **P0 COMPLETE: D4 real PACI full-field E2E (research-only).** PR #2603 merged: fixed real PACI field 18/18 BAC/KYI/UKC, exact committed PACI tests, frozen D3 SHA replay and byte-identical D4 sidecar. Research-only / AS_OF_UNVERIFIED / no-score boundaries remain.
2. **P0 COMPLETE for the selected PACI snapshot: race-day user-side provenance.** PR #2619 merged: the exact SHA-pinned PACI bytes were present in canonical Drive 18h53m22s before scheduled post. Provider publication time remains `UNKNOWN_NOT_ATTESTED`; D3 historical as-of remains unchanged.
3. **P1 COMPLETE for research contract composition:** v0.3 candidate is accepted on `main`; frozen `brdb-review-v0.1` and v0.2 candidate remain unchanged, and D4 attaches only as `supplemental_research` / `supplemental_insights`. Real 18-horse full-field research E2E is now accepted separately (see 2026-11-17 addendum); production M7 remains unaccepted pending qualified interpretation rules, consumer regression and explicit graduation.
4. **P1: ancestor identity debt.** Five Stage3B root holds are resolved (50/50 roots reviewed; Henny Hughes remains JBIS source-only with no inferred JRDB ID). The former 36 label-difference rows are now classified: 7 already carry canonical identity evidence and are label-only discrepancies; 29 rows / 21 pairs still require explicit alias review with no canonical ID. Also open: 10/40 missing 2nd/3rd-generation name slots, old-ancestor person IDs and additional verified edges. Stage4 [#2597](https://github.com/yukki0113/GPT/pull/2597) remains source-observed research; treat name paths and canonical IDs separately.
5. **P2: M6 prospective scientific gate.** Maintain [#2395](https://github.com/yukki0113/GPT/issues/2395) OPEN/BLOCKED. [#2408](https://github.com/yukki0113/GPT/pull/2408) was conditional retrospective evidence, not a true frozen prospective comparison. [#2410](https://github.com/yukki0113/GPT/pull/2410) closed unmerged as draft; do not treat it as main production implementation. JRDB provider-equivalence **reported by user** is a usable assumption for labeled retrospective research, not independent pre-off-time evidence.

## Non-negotiable boundaries
- JRDB canonical ID only; no name fallback or guessed JRDB/JBIS crosswalk.
- Source and scoring separate; historical result-based research must not become pre-race features implicitly.
- Research outputs must remain `research_only=true`, `prediction_safe=false`, `AS_OF_UNVERIFIED` where applicable.
- BRDB CURRENT, RaceNote, Newspaper, PWA and frozen review v0.1 are unchanged in this reconciliation.
- Read actual main README/CONTEXT/WORKFLOW and repository Git policy before the next implementation. Reuse `horse-racing/jrdb/` and `tools/data-storage/`; no duplicate parser/storage layer.

## Audit anchors
- [Stage3C #2432](https://github.com/yukki0113/GPT/pull/2432), [Stage4 #2597](https://github.com/yukki0113/GPT/pull/2597), [D3 #2599](https://github.com/yukki0113/GPT/pull/2599), [D4 #2601](https://github.com/yukki0113/GPT/pull/2601).
- D4 E2E verified 103 tests, synthetic 3-horse research field and 17 observations, **not** real PACI race.
- Existing M6 blocker issue: [#2395](https://github.com/yukki0113/GPT/issues/2395).

## 2026-11-17 M7 real-field E2E addendum

- [Accepted audit](BRDB_M7_REAL_FIELD_E2E_ACCEPTANCE_20261117.md), tracker [#2628](https://github.com/yukki0113/GPT/issues/2628): 2026-11-15 real PACI `05265412`, all 18 horses, exact ①②③④ canonical research modules with D4 attachment. **Research E2E PASS**, two independent entire-chain runs, identical v0.2/v0.3 byte SHA and private Library readback.
- v0.2 SHA `9ffef59d343f07a2fcacda24c8e8e0650c6c1f3d3c7e38c6f06838c7b051c0b3`; v0.3 SHA `96129fdd70155cea98e07e1a5725116e6d2ade7dc3ee9f8ddf1c8a625655774f`; 19 local source-exact tests PASS and [#2630](https://github.com/yukki0113/GPT/pull/2630) merged with CI PASS. Private outputs reside in Library `/BRDB/M7/`, not Git.
- ④ mother-root verified for 13/18 horses; unresolved 5. The frozen v0.2 schema cannot losslessly carry per-relative scoped counts without a baseline: relation identity facts only are carried, and raw ④ research output retained privately. ③ and ④ remain `AS_OF_UNVERIFIED`; no suitability score or predicted confidence.
- **Remaining M7:** qualified interpretation, optional new explicit non-lossy ④ representation, consumer contract regression, explicit user-authorized production graduation. BRDB CURRENT, RaceNote, PWA, Newspaper unchanged. **M6 #2395 OPEN/BLOCKED** remains independent.

## 2026-11-17 M7 ④ detail + qualified consumer preview addendum

- Accepted [M7 ④ non-lossy research contract](BRDB_M7_RELATIVES_DETAIL_RESEARCH_CONTRACT_v0_1_20261117.md) via [PR #2633](https://github.com/yukki0113/GPT/pull/2633): immutable v0.3 unchanged, ④ 75 canonical relatives × 5 conditions = 375 observations (zero-start `top3_rate=null` retained for 285), 18/18 field integrity and exact source metadata preservation.
- The separate **research-only consumer preview** maps ①② coverage to descriptive-sample labels, keeps ③④ `AS_OF_UNVERIFIED`, never emits suitability judgement, positive/negative factor, score/rank/probability, or publishes to the Newspaper/PWA. Frozen `brdb_newspaper_handoff.project_review` rejects new candidate data by contract. This is an explicit **boundary regression**, not actual RaceNote consumer integration.
- Local 37/37 M7 tests PASS; [BRDB Actions 44052284944](https://github.com/yukki0113/GPT/actions/runs/44052284944) PASS and [cross-repository Actions 44052285021](https://github.com/yukki0113/GPT/actions/runs/44052285021) PASS. Separate two-run real-field detail and preview SHA match; non-public results in Library `/BRDB/M7/` verified by SHA readback.
- **M7 remains OPEN**: consumer live-contract integration acceptance, exact user-reviewed display wording and fields, independent as-of qualification and explicit graduation are still pending. **M6 #2395 remains OPEN/BLOCKED**. CURRENT, frozen v0.1/v0.2/v0.3, RaceNote, PWA, Newspaper not modified.

## 2026-11-18 M7 actual RaceNote/Newspaper consumer I/O audit

- [Source audit](BRDB_M7_RACENOTE_NEWSPAPER_CONSUMER_CONTRACT_AUDIT_20261118.md) accepted by [PR #2634](https://github.com/yukki0113/GPT/pull/2634). A read-only strict `(horse_no,horse_id)` full-field preflight was implemented and tested against actual Newspaper builder/merger code, real 2026-11-15 RaceNote sparse prediction CSV, and frozen BRDB v0.1/P2 boundaries.
- The 2026-11-15 RaceNote sparse prediction handoff for Tokyo12R `05265412` contains **5 selected horses**, compared with M7 research's **18 field horses**. The CSV has no canonical `horse_id`. Newspaper base has `key.horse_id` but the current schema permits missing/`null` and no BRDB addon is registered in the actual merger. Therefore neither `racenote_prediction=READY` nor the permissive `addons` schema establishes full-field BRDB acceptance.
- 27 new targeted tests, existing JRDB Newspaper base+merger and frozen BRDB v0.1/P2 regressions passed in [BRDB CI 44212243392](https://github.com/yukki0113/GPT/actions/runs/44212243392); independent [repository regression 44212243355](https://github.com/yukki0113/GPT/actions/runs/44212243355) PASS. Audit, test, workflow and source read back from `main`.
- **M7 consumer source-contract audit = PASS; research-only identity preflight = PASS on synthetic Newspaper bundles and real RaceNote sparse file; live BRDB consumer integration = NOT IMPLEMENTED.** Next independent gate is actual same-day 18-horse Newspaper bundle↔M7 private research preview match, then a separately reviewed addon contract and display acceptance. Do not automatically publish.
- M6 [#2395](https://github.com/yukki0113/GPT/issues/2395) remains OPEN/BLOCKED; M7 [#2628](https://github.com/yukki0113/GPT/issues/2628) remains OPEN. Frozen v0.1/v0.2/v0.3, BRDB CURRENT, RaceNote, Newspaper and PWA production untouched.


## 2026-11-18 M7 real Newspaper JSON 18-horse identity and non-interference

- [Accepted source-real audit](BRDB_M7_REAL_NEWSPAPER_IDENTITY_ADDON_NONINTERFERENCE_20261118.md) / [PR #2636](https://github.com/yukki0113/GPT/pull/2636): exact PACI261115 reconstructed with canonical Newspaper day builder (36 races / 505 horses), actual v056 sparse RaceNote merged 180/180, Tokyo12R `05265412` real source M7 preview `(horse_no,horse_id)` exact **18/18** before and after merge, research-only gate PASS.
- **Noninterference:** all 505/505 horse core and non-RaceNote addon fields unchanged; other `source_status` 36/36 unchanged; other race notes 36/36 unchanged. No BRDB addon/status injected; original source and preview unchanged under read-only audit. Private Library `/BRDB/M7/` base+merged target JSON and audit receipt SHA readback PASS.
- [BRDB CI 44215290154](https://github.com/yukki0113/GPT/actions/runs/44215290154) and [repository CI 44215290228](https://github.com/yukki0113/GPT/actions/runs/44215290228) both PASS; exact main code/readback verified. CI uses synthetic full-field inputs plus the already-committed actual sparse CSV; actual PACI 36-race execution was private/local.
- **Strict existing Newspaper JSON Schema gate BLOCKED**: [#2637](https://github.com/yukki0113/GPT/issues/2637) missing required `racenote_prediction` addon for 325 non-selected horses (13 in Tokyo12R); [#2638](https://github.com/yukki0113/GPT/issues/2638) one Tokyo11R historical `horse_no=0`. New real PACI base target passes schema, after sparse merge target has 13 violations. Existing root causes; no unapproved builder/schema fix.
- Historical immutable 2026-11-15 **published** Newspaper package not acquired; result applies to new canonical-source reconstruction only. **M7 research-only identity/namespace gate PASS but consumer full schema and display/production promotion not accepted.** M7 #2628 remains OPEN, M6 #2395 OPEN/BLOCKED. CURRENT/RaceNote/Newspaper/PWA untouched.


## 2026-11-18 Newspaper sparse and overseas ZED 00 semantics audit

- [Canonical JRDB source and PWA display audit](../../jrdb/newspaper/SPARSE_RACENOTE_AND_OVERSEAS_HISTORY_SEMANTICS_AUDIT_20261118.md), [PR #2639](https://github.com/yukki0113/GPT/pull/2639): the active sparse RaceNote mode is exactly top-five selections per race, not 18-horse negative scoring; its existing omission conflicts with required-nullable addon schema (#2637). The unique historical `horse_no=0` is present as `00` in overseas ZED for 2026-02-14 Saudi 1351 Turf Sprint, sixth-place Fortune Time (#2638); the precise JRDB vendor field semantics remain **NOT INDEPENDENTLY DOCUMENTED**.
- Read-only deep-copy candidate on authentic reconstructed PACI261115 day (36/505): **325 missing-RN→null + 1 historical overseas-zero→null**, strict Draft2020-12 errors **326→0**, all 180 actual selected RaceNote marks unchanged. Existing Personal PWA v4/v5 display functions (standard/compact and source states) and Momotaro automatic projection respond equivalently to the candidate. This is **not** real-device or published-revision acceptance.
- [BRDB Actions 44217735239](https://github.com/yukki0113/GPT/actions/runs/44217735239) PASS; [repository regression 44217735235](https://github.com/yukki0113/GPT/actions/runs/44217735235) PASS. Private aggregate what-if receipt in Library `/BRDB/M7/` with SHA `2537ab5ab306c3578c9125d6f8e1a759520bfbf110b198293a809ab8081ff84e`, readback PASS. Production Newspaper merger/builder/schema/PWA/CURRENT unchanged.
- **M7 #2628 OPEN**: independent full consumer schema + accepted display wording/device checks + production authorization still pending; **M6 #2395 OPEN/BLOCKED** remains separate. JRDB issues #2637/#2638 stay OPEN until an explicitly reviewed production change.


## 2026-11-18 M6 year-file equivalence policy reset (user-directed)

- [Formal project decision](BRDB_M6_HISTORICAL_EQUIVALENCE_POLICY_DECISION_20261118.md): **accept JRDB 2016–2025 annual pedigree files as equivalent for retrospective BRDB pedigree research**, in line with the user's report of provider equivalence. Historical byte-for-byte original ZIP or release timestamp authentication is **no longer a blocking prerequisite**. This is a project research assumption/acceptance, not an invented provider-signed proof.
- **M6 historical research accepted with stated limits**: exact-source 2021–2025 five-year walk-forward on 235,700 entries / 17,239 races, research baseline log loss 0.26121709072530674 and blood-added 0.2608869015289739 (Δ -0.0003301891963328283). Existing regression and sensitivity results stay unchanged, not an ROI or actual RaceNote lift claim.
- 481,503/481,627 pedigree candidates joinable (124 unavailable, documented nonblocking exclusion). No fabricated records, no calendar-time or leakage assumptions retroactively rewritten.
- Split **historical M6-R research acceptance** from the *different* **M6-P real RaceNote incremental-effect claim**, which lacks prospective same-race paired probability outputs. That latter validation may be pursued separately but must not hold hostage already completed pedigree research or M7 descriptive reference display. No production forecast-score use authorized.
- This postdates earlier “M6 BLOCKED by historical as-of evidence” text in the dated reconciliation. For the historical-year-file acceptance decision, this **2026-11-18 addendum supersedes that blocker**; other original numerical audit observations remain immutable. No CURRENT, RaceNote, Newspaper, or PWA changes.
