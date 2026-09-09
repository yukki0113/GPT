# JRDB Edge Contract v0.1

Status: **FROZEN FOR PHASE1 SHADOW USE**
Frozen: 2026-09-09

## 1. Baseline

Phase1 baseline is Issue `#572`, run `34299375131`, request `phase1-003-full-2010-2025-d`, 2010-2025, registry version `phase1-003-research-2010-2025-d`.

Recorded result: Feature Mart 781,161 rows / eligible 773,811 / candidates 67,438 / temporally validated 6,239 / stored 2,912 / final ACTIVE 1,111 / PROVISIONAL 51 / WATCH 1,750 / integrity `ok`. All workflow exit codes were `0`.

This is research/shadow evidence only. Phase1 does not automatically add Registry Edge to the independent index score.

## 2. Leakage boundary

Conditions must be decidable before the target race. Allowed: current pre-race BAC/KYI/profile facts, strict-prior KYI-linked previous races, as-of-exclusive historical aggregates. Forbidden: target finish/abnormal result, final odds/popularity, payout, final target track condition unavailable pre-race, later races/profile observations.

## 3. Candidate identity and canonical fields

Complexity is fixed to `1 Anchor + 0..2 Modifiers`; free numeric-threshold search is disabled. Canonical Matcher fields are:

```text
venue_code surface_code distance_m turn_code frame_zone
sire_name sire_line_code broodmare_sire_name broodmare_sire_line_code
jockey_code trainer_code distance_change_bucket surface_transition frame_transition
```

String-coded JRDB identifiers remain strings; leading zeros are significant.

Canonical buckets, matching `build_jrdb_edge_feature_mart.py`:

```text
frame_zone: 1-3 INNER / 4-6 MIDDLE / 7-8 OUTER
current_distance - prev1_distance:
  <=-400 LARGE_SHORTEN; <=-200 SHORTEN; <200 SAME_BAND; <400 EXTEND; otherwise LARGE_EXTEND
surface_transition: <prev surface_code>-><current surface_code>
frame_transition: <prev frame_zone>-><current frame_zone>
```

Changing bucket semantics requires a contract/template version bump and revalidation.

## 4. Phase1 exploration and baselines

Enabled catalog is `config/jrdb_edge_candidate_templates_v0_1.json`: COURSE course×frame; PEDIGREE sire×turn×distance, sire×surface×distance, sire-line×turn×distance; TRANSITION sire×distance-change, sire×surface-transition, sire×frame-transition.

HUMAN remains disabled until a horse-quality-adjusted residual baseline exists. RECENT has no enabled Phase1 template.

Baseline modes are `same_anchor` and `same_anchor_with_prev1`. Statistical testing compares the candidate subset with its **complement inside the same Anchor**, not with a baseline containing the candidate itself.

## 5. Temporal and statistical validation

Policy source is `config/jrdb_edge_validation_policies_v0_1.json`. Candidates route by Anchor nature:

- STRUCTURAL: calendar-block stability
- LIFECYCLE: relative lifecycle segments
- DYNAMIC: rolling windows + review/expiry
- EMERGING: WATCH/PROVISIONAL accumulation path

Performance and Value remain separate. Negative Edge means persistent baseline-relative underperformance, not merely ROI below 100%.

Statistical guard is frozen to: hypothesis family = template id; Benjamini-Hochberg FDR separately by template and signal; ACTIVE `q<=0.05`; PROVISIONAL `q<=0.10`; race-date cluster bootstrap (default 400); confidence interval must support the signal direction without crossing zero. Temporal ACTIVE/PROVISIONAL clearing neither signal is downgraded to WATCH.

## 6. Registry and publication

Schema: `schema/jrdb_edge_registry_schema_v0_1.sql`. Core entities are `edge_registry_meta`, `edge_definition`, `edge_metric_snapshot`, `edge_validation_event`, plus statistical-guard records created by the guard implementation.

Expected publication package:

```text
edge_registry.sqlite
edge_registry_active.jsonl / .csv
edge_registry_audit.json
edge_statistical_guard.jsonl / _audit.json
edge_registry_summary.json / .md
manifest.json   # dedicated publication manifest; workflow integration is the next package
```

Generated large assets are not committed to Git.

## 7. Pre-race Matcher

Implementation: `src/jrdb_edge_matcher.py`.

Input is a flattened leakage-safe current runner fact using the canonical fields above, with optional `race_date`, `race_key`, `race_horse_key`, `horse_id`, `horse_no`. Upstream adapters derive canonical transition/bucket values; Matcher does not reinterpret raw offsets.

Matching is exact across every Anchor and Modifier. Default served state is ACTIVE. Other live states require explicit research/shadow opt-in. Expired records are never served. An unexpired record past `next_review_at` is returned with `evidence.review_due=true`.

Output is compatible with Newspaper `edge_matches[]`:

```text
edge_id display_text polarity status strength_score confidence_band registry_version evidence
```

Matcher owns only Edge match output and does not mutate RaceNote, Eval, Newspaper JRDB base, keibailuka or independent-index namespaces.

## 8. Change control

A version bump + revalidation is mandatory for changes to leakage rules, canonical bucket semantics, enabled template shape, baseline semantics, temporal thresholds, multiple-testing family/q gates, or bootstrap/CI gate semantics. Display wording and transport may evolve without redefining statistical meaning if `edge_id`, conditions, registry version and evidence remain traceable.
