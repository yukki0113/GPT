# RaceNote v0.5.4 Candidate — Contextual Evidence and Reader-Facing Prose

Status: **PROMOTED CURRENT — NEW v0.5.4 FREEZES ONLY / EXISTING v0.5.3 FREEZES IMMUTABLE**
Date: 2026-10-15
Logic ID: `RaceNote-Human-Context-Reader-0.5.4-candidate`
Contract revision: `v054-authored-prose-r2`\nLegacy verification support: `v054-context-evidence-r1`
Predecessor: `RaceNote-Human-Context-Reader-0.5.3-candidate` / `v053-boundary-safety-r2`

## 1. Objective and invariant

Keep the protected ordinary-five, win-first ◎, independent asymmetric ▲, and narrowly gated one-horse boundary exchange from v0.5.3 r2. Improve the **interpretation of the evidence already consulted**, not the size of the candidate pool or the ability-score arithmetic.

Every decision remains individually authored from a complete, sealed, as-of-exclusively market-blind Reader. Target race outcomes, target final odds/popularity/payout, and post-Freeze reinterpretation are prohibited.

A v0.5.3 record is never upgraded in place. v0.5.4 authoring requires its own versioned Reader manifest, contract revision, Decision Core, prose, immutable Freeze, and result-consulted barrier. Any rerun of a previously examined race is a diagnostic counterfactual, not clean-blind validation.

## 2. Evidence hierarchy and responsibilities

Preserve `DATA / TRENDS > RACEREVIEW >= ABILITY`. Neither SRB nor KYI hidden-value forms an additive scoring lane.

- DATA / TRENDS: existing race and condition evidence.
- RACEREVIEW: past horse performance plus **source-race** context, including RRDB v0.5 and SRB leader laps.
- ABILITY: existing supported ability and repeatability evidence.
- `JRDB_HIDDEN_VALUE_CONTEXT`: attention, disagreement, corroboration and contradiction only; **not** automatic inclusion, promotion, ▲ allocation or confidence elevation.

Identical underlying evidence must not be counted twice because it appears in both RRDB and SRB. Distinguish an RRDB predicate from SRB's descriptive details. A signal without its supporting historical race or a verified join is not equivalent to a fully supported signal.

## 3. Source-race lap interpretation

Use `jrdb_race_lap_reader.RaceLapReader` through its JSON-compatible consumer API. Batch lookup by the **historical source race key**. Never implement Parquet/DuckDB-specific SQL in RaceNote.

SRB is race-level, leader-based, post-race evidence, **not individual-horse sectional timing**. Join to the horse's historical run before interpreting `race shape × corner position × last3F × result/gap`. Reject source dates on or after the prediction date. Missing data remains missing; do not synthesize a pace label. `NO_LAPS` is unavailable, not neutral evidence. Do not reinterpret partial first segments as comparable full 200m splits.

Pay particular attention to front runners surviving sustained fast pace, strong finishes against an unfavorable shape, slow-race closing times that may flatter, where the pace rose, and whether the entire race decelerated late. These are **contextual hypotheses** to be supported with a horse-specific historical run, not automated score boosts.

No uncalibrated fixed front-/rear-loaded threshold or direct mark from a race-level shape value is permitted. Use the calibrated RRDB predicate wherever RRDB already owns one.

## 4. RRDB v0.5

Required semantics: `rrdb-recommendation-signals-v0.5`; lookback 730 days; grades disabled; signals are separate evidence, not votes.

| Signal | Decision role |
|---|---|
| `TIME_CLASS_PLUS1` | Historical clock/class evidence; validate current-condition transfer |
| `FRONT_SURVIVE_GAP05` | Historical front-survival predicate; SRB shape may clarify the burden without applying a second automatic threshold |
| `REAR_HIGH_LAST3F90` | RRDB already requires historical SRB `early_late_delta_sec <= frozen_q20(surface × distance_bucket)`; do not reimplement the gate |
| `HV02_Q85_Q90` | Historical stronger-than-finish clock evidence; not ability-point credit |
| `COURSE_PROFILE_FIT` | **Current-condition** fit only for LARGE × LONG_STRAIGHT; not a source-run performance signal |

RRDB missing/failure must be distinguished from signal absence. Failed SRB coverage for REAR follows RRDB's own fail-closed semantics and does not invalidate other signals. Avoid parallel independent RRDB reclassification.

## 5. KYI hidden-value context

### Reference previous runs

`reference_previous_raw` denotes up to two back-indices. Decode digits 1–5 against KYI `previous[]` result/race keys; a non-resolvable reference is visible as unresolved, never silently guessed. These reference runs do not replace the normal recent-five evaluation or invent older history. They identify 1–2 **already available runs to revisit**, particularly when the primary is not the immediately previous start. Provider selection is an attention hint, not ground truth.

### Longshot and ticket fields

`longshot_type` (especially A1/A2), `longshot_index` disagreement with ordinary measures, and `ticket_index/mark` may trigger a targeted recheck. The latter is betting/market-sensitive composite information; keep it separate from win-ability evidence. No "A1 => ▲", automatic rescue, vote count, or score uplift. A corroboration requires a **different, concrete, current-condition-relevant** source-run or horse-level reason. Do not treat source popularity group as evidence of future profitability.

If KYI extraction is not available or a field is blank, record missing coverage; continue without fabricating hidden-value signals.

## 6. Decision sequence

**A — Race model.** Interpret the whole Reader as before, integrating source-run structures into the historical performance narratives and distinguishing past conditions from today's anticipated pace.

**B — Ordinary five.** Form and order five horses under the ordinary race scenario, before external-challenger search. Use reference-run and hidden-value prompts only to verify that important evidence was not missed. No automatic inclusion.

**C — ◎/○.** Choose the two best winning routes within the ordinary five using `WIN_FIRST_NOT_PLACE_FIRST`. The pairwise ranking must cite concrete comparative support. A/RRDB/SRB/KYI source overlap does not create independent support merely by duplication.

**D — One external challenger.** Search for a genuinely asymmetric win route; never reinterpret a KYI longshot flag as an independent winning route.

**E — Fixed boundary.** Apply v0.5.3 r2 exactly: keep ◎ and ○, challenge only the lowest ordinary-ranked non-anchor, KEEP by default, ADMIT only on direct sufficient current-condition evidence. Route novelty is a tie-breaker, not a promotion criterion. Under KEEP choose ▲ from retained non-anchor horses; under ADMIT the admitted challenger is ▲.

**F — Confidence.** A/B/C remains *pairwise certainty that ◎ outranks ○*, not the predictability or completeness of the five-horse set. More signals do not mechanically mean A. Study A purification separately; do not silently replace existing A/B/C policy or betting BP2 in v0.5.4.

## 7. Decision Core and short newspaper prose

Record race model, win cases, ranking reason, one external-challenger case, fixed boundary decision, non-▲ mainline cases, and ▲ single-shot case exactly once. Keep trace links to source-run identities and evidence provenance, including whether RRDB/SRB/KYI influenced **attention only**, **corroborated**, **contradicted**, or **contributed to the final decision**.

`reader_facing_reason` is a **reader-facing compression** of the already-authored Decision Core, not another forecast pass. It must be authored separately for each race by the same model authoring that race's Decision Core. Use 2–3 natural sentences, usually around 100–150 Japanese characters where supported. Convey (1) ◎'s most distinctive concrete reason, (2) what decides ◎ versus ○, and optionally (3) ▲'s genuine alternate winning route. Do not merely enumerate marks or repeat templates. Omit △ enumeration unless vital.\n\n**Programmatic short-comment generation is prohibited.** A workflow, Python helper, formatter, string template, mark-plan expander, or other deterministic process must not construct `reader_facing_reason` from horse number, latest finish, IDM, running style, marks, or other fields. Workflows may validate, save, Freeze and verify a model-authored venue JSON, but may not manufacture its prose or Decision Core. Prediction runtime must not contain a fallback prose generator.\n\nFor r2, every Decision Core must carry `reader_facing_reason_authorship` with `mode=MODEL_AUTHORED_PER_RACE`, `programmatic_template=false`, and a `basis` containing at least `honmei_win_case` and `ranking_reason`. This is provenance/operation metadata, not permission to auto-compose those fields.

**Forbidden in newspaper prose and authoring path**: `sealed Reader`, `ordinary five`, `r2`, `boundary KEEP`, model plumbing, unsupported specifics, market-sensitive hidden-value index values. Never reopen all horses to generate prose. If the recorded core lacks the facts for a good explanation, record the deficiency and correct it **before** Freeze with the original decision author; do not invent a better story afterward.

## 8. Research and release gates

Version all upstream RRDB contracts, SRB dataset/Reader generation, KYI parser/projection, and evidence-availability statuses. Test source-run joins, `source_date < target_date`, partial-lap and missing-value fail-closed cases, deterministic input identity, and absence of target result/market leakage.

Stage implementation:
1. KYI neutral parsing / reference resolution and SRB historical reader-context integration;
2. RRDB v0.5 binding and one source-run evidence view; missing/duplicate audit;
3. v0.5.4 Decision Core + independent prose quality validation;
4. sealed representative **diagnostic** cases comparing 0.5.3 vs 0.5.4 interpretation, with no post-result retroactive promotion;
5. new untouched race-day Freeze and clean-blind evaluation.

Compare ordinary-five capture, ◎/○/▲, KEEP/ADMIT, confidence distribution, unsupported claims, and prose specificity; settlement and wagering policies remain separate. The current forecast pointer may reference v0.5.4 after the promotion gate passes. Existing v0.5.3 sessions and Freezes remain reproducible through their own versioned contracts.

## 9. Source handoffs

- `RaceNote_SRB_RaceLap_Usage_Handoff_20261015.md`
- `RRDB_v0_5_Signal_Summary_for_RaceNote_20261015.md`
- `RaceNote_KYI_HiddenValue_Research_20261015.md`

The handoffs inform this cohesive rewrite; the v0.5.3 r2 boundary invariants remain the predecessor contract.
