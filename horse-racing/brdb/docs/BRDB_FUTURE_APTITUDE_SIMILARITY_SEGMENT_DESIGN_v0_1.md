# BRDB 将来拡張設計 v0.1 — 血統タイプ・類似血統・条件抽出

Status: DESK DESIGN / FEASIBILITY REVIEW ONLY — NOT IMPLEMENTED OR APPROVED FOR PRODUCTION
Date: 2026-10-22
Owner: horse-racing/brdb/
Related: `BRDB_REVIEW_CONTRACT_v0_1.md`, `BRDB_ANCESTOR_CROSS_SIMILARITY_v0_1.md`, RaceNote P1/P2 and JRDB Analysis / EdgeDB research.

## 0. Decision

All three requested concepts are implementable in stages, but **observed conditional performance, pedigree descriptors, and predictive aptitude are distinct objects**:

1. **Type / aptitude** (sire line, geographic lineage, turf/dirt, going, speed/power) — descriptive line + historical conditional evidence immediately feasible; assigning geographic roots and speed/power labels requires a versioned and reviewed taxonomy and validation.
2. **Similar-pedigree search → aptitude** — sire/BMS feature overlap viable in a limited research mode; exact 3–5 generation similarity blocked by coverage. Incomplete ancestor graphs must not be ranked as complete likeness.
3. **Compound pedigree cohort query** (Sunday sire line × US-root maternal side × condition) — first research priority, using available sire-line/BMS-line codes and historical results, subject to canonical definitions and post-selection validation.

No scoring/marks/PWA/Newspaper/CURRENT cutover authorized. `brdb-review-v0.1` remains unchanged.

## 1. Shared architecture

```text
BRDB canonical pedigree facts + lineage_code_master
   ├── reviewed classification dictionary (future, versioned)
   ├── observed ancestor graph (partial)
JRDB Analysis canonical historical starts/results (as-of-filtered)
   └── normalized condition dimensions and outcome facts
         ↓
BRDB cohort query (identity/exposure/date/policy)
         ↓
BRDB descriptive performance mart (counts, reference rates, uncertainties)
         ↓
optional similarity evidence / aptitude hypotheses
         ↓
research Review v0.2 candidate (separate contract)
         ↓
human approval before any shared PWA publication
```

One canonical conditional-performance statistics engine underlies all three features; no surface/distance/race-condition predicates are recreated in PWA or within separate similarity logic. Full-source immutable analysis remains separate from portable consumer projections.

## 2. Classification / 国籍型・タイプ

### 2.1 Independent attributes

- `sire_line_code` / `broodmare_sire_line_code`: JRDB official lineage codes and labels. **Never assume codes themselves denote nationality.**
- `sire_family_tag`: e.g. Sunday-line category, only if explicitly mapped and versioned with evidence; not inferred from horse-name substring.
- `regional_ancestry_tag`: separately reviewed pedigree-cultural/root grouping such as Japanese-developed, US-root, European-root; **not** country of horse birth, registration, ownership, or farm location.
- `maternal_side_tag`: based on BMS line when only BMS available; this is **BMS-line proxy**, not verified maternal 5-generation composition.
- `speed_power_hypothesis`: distinct **unvalidated hypothesis** and never a canonical pedigree fact. Distinguish `early_speed`, `sustained_speed`, `stamina`, `going_response` rather than equating turf=dry=speed or dirt=power.
- `surface` (turf/dirt), `going` (turf and dirt condition separately), `distance_band`, `venue`, `course`: target/observed race conditions, not pedigree.

### 2.2 Example classifier dictionary

```json
{
  "taxonomy_version": "brdb-type-taxonomy-proposal-v0.1",
  "lineage_code": "<official JRDB code>",
  "family_tag": "SUNDAY_LINE",
  "regional_ancestry_tag": "UNKNOWN",
  "regional_basis": null,
  "definition_source": "REVIEW_REQUIRED",
  "approved": false
}
```

No nationality is allocated without reviewed source/version. Multiple historical origins in a single family require a multi-label or proportion-based tag with explicit `UNKNOWN` rather than one forced category. Regional taxonomy and type scores are not currently implemented.

## 3. Compound condition extraction / pedigree segments (recommended first)

### 3.1 Query contract (proposal)

```json
{
  "schema_version": "brdb-segment-query-v0.1",
  "pedigree_filters": {
    "sire_family_tag": "SUNDAY_LINE",
    "bms_regional_tag": "US_ROOT"
  },
  "race_filters": {
    "surface": "dirt",
    "going": "muddy",
    "distance_band_m": [1400, 1800],
    "venue": null,
    "target_date": "YYYY-MM-DD"
  },
  "as_of_exclusive": true,
  "min_unique_horses": 30,
  "min_starts": 100
}
```

This is an **illustrative non-executable request**, not an implemented filter or a statistical acceptance threshold. All query dimensions must be normalized using JRDB canonical definitions and independently tested. No free-text ancestry inference.

### 3.2 Descriptive aggregation

Output (candidate):

`segment_key, taxonomy_version, conditions, as_of_exclusive, unique_horses, starts, wins, top3, win_rate, top3_rate, median/uncertainty intervals, baseline_cohort_count, baseline_rate, lift_vs_baseline, result_asof, source_generation, coverage, status`.

Unit of counting is **start** for starts/wins/top3. Also record unique horses, sire groups, and years to avoid treating repeated starts/related progeny as independent replication.

Comparison baseline must match year, venue/course, surface, distance band, going, age/class where sample permits. Baseline definition must be pinned before comparing. A raw 20% win rate does not mean a bloodline is strong if the corresponding field/population baseline is higher or confounded by favorite status.

Odds-adjusted ROI is optional **research-only**, with payout availability/source, stakes and look-ahead price policy verified. Do not infer profitability from win rate or retrospective odds without payout contract.

### 3.3 Discovery → validation gates

- Discovery cohort and later chronological out-of-sample cohort strictly separated. Explore hypotheses on training dates only; test registered predicates without modification on held-out dates.
- Count all candidate combinations tested; require multiple-comparison control or confirmatory holdout to avoid winner's curse.
- Exclude target result and any races at or after the target date from review computation; cohort labels/taxonomy versions must be obtainable by the target as-of.
- Distinguish systematic concentration by a few sire families, repeat horses, class/venue preferences, time regime and popularity.
- Report confidence/uncertainty; sparse segments must be `INSUFFICIENT_EVIDENCE` rather than ranked.
- Preset thresholds must be measured/calibrated and stored as versioned research policy before any `STRONG` / aptitude claim.
- Keep EdgeDB `PEDIGREE_CROSS_5Y_MIXED_OBSERVE_ONLY` **research-only**; do not reuse its measured outcomes as proof for new BRDB cohorts.

### 3.4 Example outputs (not claims)

- “父系=SUNDAY_LINE、母父系代理=US_ROOTの芝1800m重馬場は、対象期間XXX走/YY頭、複勝率ZZ%。比較母集団は…。”
- With too few starts or unverified taxonomy: “傾向の判定不可（分類未確定／標本不足）。”

These are descriptions, not recommendations or certified bloodline truths.

## 4. Aptitude / 芝ダ・道悪・速度パワー

Recommended staged view:

- **Stage A (descriptive)**: `sire × surface × distance`, `BMS × surface × distance`, going, venue from RaceNote P2/Analysis. Existing P2 specifically offers exact/distance-range aggregates and `track_condition_scope=all_conditions`; it is **not** already a going-specific classifier.
- **Stage B (conditional evidence)**: group/taxonomy x condition mart, matched baseline and temporal held-out validation; observable affinity by surfaces/distance/going.
- **Stage C (hypothesis)**: early/late pace, speed/stamina/power proposed proxies only after availability of standardized, as-of-safe pace and sectional/historical dimensions. Race result, margin or speed index cannot be silently equated with an inherited physiological trait.
- **Stage D (review)**: `aptitude_evidence` with separate `description`, `historical_effect`, `uncertainty`, `provenance`; no 0–100 composite, PWA category color, or mark without independent acceptance.

A tag “US-root” must not automatically imply dirt/power or vice versa.

## 5. Similar pedigree search

### 5.1 Two levels

**Level L1, possible with existing facts**: exact canonical sire name / sire-line code / BMS name / BMS-line code and optionally approved family tags. Filter/search these dimensions; preserve name provenance and enforce `horse_id` for result identities. This gives "pedigree-feature resemblance", **not full genealogical similarity**.

**Level L2, blocked until verified ancestors**: ancestor-ID path signatures with generations (e.g. 3×4), unique/weighted overlap, paternal/maternal path distinction, relatedness/coefficient candidate. Existing Phase 4 graphs use resolved JRDB parent IDs only. The accepted 2025 coverage audit finds zero complete depth-2..5 graphs; a partial Jaccard=1 can mean both horses share only one observed ancestor. Ranking across such incomplete graphs is misleading.

### 5.2 Candidate query/output

Input: `target_horse_id, as_of_date, mode=L1|L2, context, max_results`.

Return `matched_horse_id, matched_features, unmatched_features, coverage, profile_observed_as_of, similarity_measure, similarity_comparable, match_evidence_version`. No name-only identity join; approved horse name is display-only.

Never calculate winner aptitude from a resemblance alone. For “similar horses in this race condition performed well”, first:
1. define reference peers only from as-of-safe features;
2. exclude the target horse, duplicated starts and future performances;
3. aggregate peers' prior same-condition performance;
4. compare to matched baseline / uncertainty;
5. report comparison support and coverage.

Do not conflate the target's own prior races, descendant/sibling results, and related-bloodline evidence.

## 6. Historical leakage and semantics

- Blood identity source: pinned BRDB CURRENT as facts; for retrospective predictions require historical profile_data_date <= target date. Current-only profiles cannot be retroactively assumed available.
- Historical outcomes source: JRDB Analysis canonical with `race_date < target_date`. Never allow same-race results, post-race popularity, returns or any target labels in pre-race feature rows.
- Taxonomy and model versions: definition release/effective timestamps, hindsight-free generation and lineage provenance.
- At evaluation time, all preprocessing, peer choice, parameter tuning and segment selection occur on historical train data only.
- Each response separates `fact`, `segment_observation`, `hypothesis` and `validated_prediction`; claims require independent backtest and quality gates.
- Missing dam identity, lineage, unknown provenance or a partial ancestry path must remain UNKNOWN and never be imputed via substring/fuzzy matching.

## 7. Build order and provisional feasibility

| Module | Dependency | Current assessment |
| --- | --- | --- |
| normalized condition dictionary and observation mart | existing Analysis and official dimensions | HIGH; research implementation can start without new UKC |
| sire-line / BMS-line compound filters | UKC pedigree fact, lineage_code_master, Analysis | HIGH, after exact definitions and historical join audit |
| going-specific historical aggregation | Analysis going columns verified before use | LIKELY; requires source/schema check |
| family/country-root taxonomy | reviewed official codes + external pedigrees as needed | PARTIAL; no automatic country classification |
| speed/power labels | outcome/pace proxies and out-of-sample calibration | RESEARCH ONLY |
| L1 similar-feature search | current sire/BMS facts | HIGH, with as-of gating |
| L2 3–5 generation similarity | verified parent ID graph and extended ancestry | BLOCKED BY COVERAGE |
| similarity → predicted aptitude | stable peers + condition mart + OOS tests | NOT YET VALIDATED |
| user-facing PWA | approved Review contract and full UI review | EXPLICITLY DEFERRED |

## 8. Independent acceptance milestones

1. Freeze source inventory: exact Analysis surface/going/distance/class/date/horse_id and results fields, sample scope, lifetime/historical coverage; align IDs with BRDB.
2. Freeze taxonomy **proposal**, with UNKNOWN/NOT_SUPPORTED and mapping governance; test accepted Sunday and US-root examples before use.
3. Implement a read-only, historical-safe segment query PoC and baseline comparison; retrospective placebo/time-shift tests.
4. Create matched comparison and chronological holdout report for one pre-registered segment, including sample counts and uncertainty.
5. Add L1 exact-feature similarity with identity/as-of tests; do not enable L2 ranking on partial graphs.
6. Only then propose new separately versioned Review contract `brdb-review-v0.2-candidate`; leave v0.1 untouched.
7. Shared PWA view/release only after user explicitly approves display fields/wording/screenshots/scope.

**No new UKC download, official JRDB site access, production CURRENT update, PWA UI modification, or predictive capability is claimed by this design.**
