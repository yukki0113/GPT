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
| M4 Stallion master / ancestry work ③-A/B/C, ④ | research partial completion | remaining identities and verified edges, no inferred cross |
| M5 Condition research D3 | accepted retrospective description [#2599](https://github.com/yukki0113/GPT/pull/2599) | causal/conditional suitability not demonstrated |
| M5-D4 Non-scoring supplemental sidecar | real PACI full-field E2E accepted [#2603](https://github.com/yukki0113/GPT/pull/2603); exact PACI user-side pre-off availability accepted in #2619 | provider release timestamp remains independently unknown; D3 remains AS_OF_UNVERIFIED |
| M6 Predictive-value study | **BLOCKED** [#2395](https://github.com/yukki0113/GPT/issues/2395) | immutable pre-off-time pairs, results and independently supported as-of |
| M7 Integrated Blood Review promotion | **not accepted** | versioned new contract, integration tests, qualified interpretations |
| M8 RaceNote / PWA handoff | **not authorized** | M7 acceptance plus consumer-contract regression |

## Prioritized next work
1. **P0: D4 real PACI full-field E2E (research-only).** Use existing JRDB PACI Reader and canonical `horse_id`; validate full roster, one-to-one mapping, source generation/SHA, conditions and all missingness. Execute on fixed real PACI cohort and repeat for identical output bytes. Do **not** import post-race D3 observations into a historical target or mark observations as predictive.
2. **P0: race-day provenance.** Separate date-level availability and actual release/off-time attestation; retain UNKNOWN when intraday timing or source revisions cannot be verified. A post-2026-11-01 research demonstration is not proof of a genuine pre-race feature snapshot.
3. **P1: integrated review contract.** Keep frozen `brdb-review-v0.1` and `brdb-integrated-blood-review-v0.2-candidate` unchanged until a separately reviewed, versioned upgrade. D4 `supplemental_insights` is a **separate** sidecar; no automatic positive/negative factors, confidence, score, marks or PWA disclosure.
4. **P1: ancestor identity debt.** Stage3B [#2430](https://github.com/yukki0113/GPT/pull/2430): five unconfirmed identities, 10/40 missing 2nd/3rd-generation name slots and 36 label differences. Stage4 [#2597](https://github.com/yukki0113/GPT/pull/2597): 150 source-observed maternal slots, only two ID-verified DD direct positions. Treat name paths and canonical IDs separately.
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
