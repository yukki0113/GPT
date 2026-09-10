# JRDB Edge SUGGESTIVE Serving Contract v0.2

Status: **DESIGN FROZEN / IMPLEMENTATION IN PROGRESS / SERVING NOT ENABLED**  
Established: 2026-09-10  
Supersedes: `JRDB_Edge_Suggestive_Serving_Contract_v0_1.md`

## 1. Purpose

Define the v0.2 serving contract that separates statistical confirmation from advisory serving eligibility while preserving the existing ACTIVE Registry contract.

The evidence model is channel-specific. Performance and Value are never collapsed into one undifferentiated Edge confidence label.

```text
performance_evidence_level = CONFIRMED | SUGGESTIVE | NONE
value_evidence_level       = CONFIRMED | SUGGESTIVE | NONE
```

Registry lifecycle state remains independent:

```text
registry_status = ACTIVE | PROVISIONAL | WATCH | DECAYING | REJECTED
```

A SUGGESTIVE Edge normally remains `registry_status=REJECTED`. SUGGESTIVE is a serving evidence classification, not a Registry promotion.

## 2. Non-goals

This contract does not:

- loosen ACTIVE `q<=0.05`;
- loosen the production Statistical Guard;
- redefine temporal validation;
- convert REJECTED rows to ACTIVE;
- expose every REJECTED row;
- turn historical ROI/lift into an additive prediction score;
- automatically decide marks, bets, or final predictions;
- use known racing maxims as hand-picked acceptance targets.

The legacy `edge_registry_active.jsonl` and v0.1 matcher behavior remain backward-compatible.

## 3. CONFIRMED evidence

For an ACTIVE Registry Edge:

```text
performance_evidence_level = CONFIRMED
    iff registry_status == ACTIVE
    and performance_stat_pass == true

value_evidence_level = CONFIRMED
    iff registry_status == ACTIVE
    and value_stat_pass == true
```

An ACTIVE Edge may therefore carry Performance only, Value only, or both confirmed channels.

Full 2010-2025 v0.2 data contains:

- Performance CONFIRMED channels: `2,303`;
- Value CONFIRMED channels: `510`;
- ACTIVE Edge rows: `2,572`.

Consumers must not infer that both channels are confirmed merely from `registry_status=ACTIVE`.

## 4. SUGGESTIVE evidence — frozen v0.2 rule

A channel is eligible for SUGGESTIVE serving only when all conditions below are true:

```text
final Registry status = REJECTED
temporal_status = ACTIVE
statistical_status = WATCH
channel signal != NEUTRAL
0.05 < channel q-value <= 0.10
same-channel 2,000-sample race-date cluster bootstrap CI excludes zero
in the preregistered signal direction
```

Direction rule:

```text
POSITIVE -> CI low > 0
NEGATIVE -> CI high < 0
```

The 400-sample research bootstrap is not production-eligible. It remains screening/research evidence only.

No additional post-hoc q threshold or CI-margin threshold is introduced from the sensitivity result.

## 5. Basis for the 2,000-sample rule

Full sensitivity study:

- Issue: `#833`
- run_id: `34457918449`
- artifact: `jrdb-edge-registry-v02-suggestive-bootstrap-sensitivity-full-2010-2025-a-34457918449`
- baseline 400-supported candidates: `519`
- baseline 400-supported channels: `540`
- 2,000-sample retained candidates: `437`
- 2,000-sample retained channels: `454`

Channel retention:

| Channel | 400-supported | 2,000 retained | Retention |
|---|---:|---:|---:|
| Performance | 347 | 275 | 79.25% |
| Value | 193 | 179 | 92.75% |
| Total | 540 | 454 | 84.07% |

Because the 400->2,000 attrition is material, especially for Performance, v0.2 ordinary SUGGESTIVE serving uses 2,000 bootstrap samples as the fixed operational definition.

This does not mean 2,000 samples prove asymptotic convergence. Any future change to this sample count requires a contract version bump and revalidation.

## 6. Publication architecture

SUGGESTIVE serving is published separately from the legacy ACTIVE export.

Target artifacts:

```text
edge_registry_active.jsonl              # existing compatibility asset; unchanged semantics
edge_registry_suggestive.jsonl          # only v0.2 SUGGESTIVE-eligible rows
edge_serving_catalog_v0_2.jsonl         # ACTIVE CONFIRMED + SUGGESTIVE unified consumer input
edge_suggestive_publication_audit.json  # provenance / integrity / counts / hashes
```

The publication builder consumes:

```text
edge_registry.sqlite
edge_suggestive_bootstrap_sensitivity.jsonl
```

The builder is fail-closed. For each SUGGESTIVE channel it must verify against the Registry that:

- Edge ID and candidate ID match;
- family/template identity matches;
- final status is still REJECTED;
- temporal status is still ACTIVE;
- statistical status is still WATCH;
- signal matches;
- stored q-value matches sensitivity input;
- q remains inside `(0.05, 0.10]`;
- sensitivity bootstrap sample count is exactly `2000`;
- the retained 2,000-sample CI excludes zero in the correct direction.

The builder must never mutate `edge_registry.sqlite`.

## 7. Required publication fields

Each serving row preserves at least:

```text
edge_id
candidate_id
registry_status
status                         # compatibility alias preserving actual Registry status
family
anchor_type
anchor_name
validation_class
policy_id
polarity
performance_signal
value_signal
conditions
display_text
specificity
strength_score
confidence_band
sample_n
unique_horses
unique_races
win_rate
place_rate
win_roi
place_roi
baseline_place_rate
performance_lift
performance_p_value
performance_q_value
value_p_value
value_q_value
redundancy_group_id
registry_version
performance_evidence_level
value_evidence_level
```

SUGGESTIVE rows additionally preserve channel-specific 2,000-sample evidence:

```text
suggestive_evidence.performance/value:
  signal
  p_value
  q_value
  ci_low
  ci_high
  bootstrap_samples = 2000
```

CONFIRMED rows preserve the existing Statistical Guard CI provenance separately.

## 8. Serving profiles

### CONFIRMED_ONLY

Backward-compatible behavior.

- serve ACTIVE rows only;
- expose channel-specific CONFIRMED/NONE labels;
- do not include SUGGESTIVE rows.

### STANDARD

Target ordinary v0.2 advisory behavior after acceptance testing.

- serve ACTIVE CONFIRMED evidence;
- serve the separately published SUGGESTIVE channels;
- preserve actual Registry status;
- never describe SUGGESTIVE as statistically confirmed;
- do not numerically add CONFIRMED and SUGGESTIVE evidence.

### RESEARCH_ALL

Explicit research-only behavior. It may expose additional states, but it is never the implicit ordinary consumer profile.

STANDARD remains disabled until implementation and acceptance checks pass.

## 9. Exact matching and leakage boundary

SUGGESTIVE uses exactly the same canonical current facts and exact condition matching as ACTIVE.

No fuzzy matching, guessed previous race, approximate sire name, alternative distance bucket, or post-race information is introduced.

Current-race facts remain pre-race only. SED result, finish, payout, final odds, final popularity, and later-dated history remain forbidden in current matching.

## 10. Redundancy / presentation contract

Raw matching preserves every exact match. Presentation may suppress duplicate-looking rows but cannot erase provenance.

`redundancy_group_id` is the first-level grouping key.

Rules:

1. Match first, group second.
2. Grouping is channel-specific.
3. Same group + same channel + same direction:
   - CONFIRMED has precedence over SUGGESTIVE;
   - same evidence level uses higher specificity as PRIMARY;
   - remaining rows become SECONDARY.
4. Opposite directions are not silently collapsed; they are marked CONFLICT.
5. Strength, ROI, lift, q-value, or confidence values are never summed across overlapping Edge rows.
6. Compact consumers may display PRIMARY rows only, but raw matched provenance remains available.

Full 2,000-sample sensitivity population contains `437` SUGGESTIVE candidates in `411` redundancy groups, including overlaps with ACTIVE evidence. Therefore this presentation rule is part of the serving contract, not optional UI polish.

## 11. Consumer wording

Recommended interpretation:

### CONFIRMED

Historical evidence cleared the current production statistical contract.

### SUGGESTIVE

Historical evidence points repeatedly in this direction and passed the lower-confidence 2,000-sample bootstrap serving gate, but did not clear the ACTIVE multiple-testing threshold.

Performance and Value wording remain distinct:

- Performance: tendency to outperform/underperform the same-anchor complement in placing outcome.
- Value: tendency for return to outperform/underperform the same-anchor complement.

A Performance-positive / Value-NONE Edge must not be described as a profitable betting Edge.

## 12. Numerical use

No automatic additive score is authorized.

Forbidden without a separate calibration contract:

```text
CONFIRMED = +N points
SUGGESTIVE = +M points
sum Edge strength_score
sum ROI/lift across matched Edges
```

EdgeDB serving remains evidence delivery. Numeric aggregation requires separate TRUE_FORWARD calibration and explicit redundancy handling.

## 13. Implementation sequence

The sensitivity threshold research is complete. Remaining activation work is implementation/acceptance:

1. freeze this v0.2 contract;
2. implement the sidecar SUGGESTIVE publication builder;
3. publish `edge_registry_suggestive.jsonl` and `edge_serving_catalog_v0_2.jsonl` with audit hashes;
4. implement channel-specific evidence fields in the v0.2 matcher;
5. implement channel-specific redundancy presentation roles;
6. keep v0.1 matcher and `edge_registry_active.jsonl` backward-compatible;
7. run focused synthetic regression tests;
8. run 2025 real-data current-matching smoke;
9. run Full publication non-regression audit;
10. only after all checks pass, enable v0.2 STANDARD serving.

Until step 10, ordinary production behavior remains ACTIVE-only.

## 14. Change control

A contract version bump and revalidation are mandatory for changes to:

- SUGGESTIVE q band;
- required temporal status;
- bootstrap sample count;
- directional CI rule;
- performance/value evidence semantics;
- STANDARD eligibility;
- redundancy grouping rules that change consumer-visible PRIMARY evidence.

Display wording may evolve without a statistical version bump if evidence identity and provenance remain traceable.

## 15. Related

- `docs/JRDB_Edge_Suggestive_Serving_Contract_v0_1.md`
- `docs/JRDB_Edge_v0_2_Suggestive_Bootstrap_Full_Audit_20260910.md`
- `docs/JRDB_Edge_v0_2_Suggestive_Bootstrap_Sensitivity_Full_Audit_20260910.md`
- `docs/JRDB_Edge_Current_Matching_v0_1.md`
- `docs/JRDB_Edge_Consumer_Integration_v0_1.md`
- `src/research_jrdb_edge_suggestive_bootstrap_v0_1.py`
- `src/research_jrdb_edge_suggestive_bootstrap_sensitivity_v0_1.py`

This contract defines EdgeDB serving semantics only. It does not authorize changes to RaceNote prediction logic.
