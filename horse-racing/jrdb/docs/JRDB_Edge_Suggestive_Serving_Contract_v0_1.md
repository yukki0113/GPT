# JRDB Edge SUGGESTIVE Serving Contract v0.1

Status: **DESIGN SPEC / SERVING NOT ENABLED**  
Established: 2026-09-10

## 1. Purpose

Define how lower-confidence but still potentially useful Edge evidence may be surfaced to downstream consumers without weakening the existing ACTIVE statistical contract.

This contract is motivated by the Full 2010-2025 SUGGESTIVE bootstrap study in Issue `#827`, run `34442743305`.

The core design rule is:

> Statistical confirmation and serving eligibility are separate concerns.

`ACTIVE` remains the high-confidence Registry state. SUGGESTIVE evidence does not promote a `REJECTED` Edge to ACTIVE and does not change Registry lifecycle semantics.

## 2. Non-goals

This contract does **not**:

- loosen ACTIVE `q<=0.05`,
- loosen the existing directional bootstrap-CI requirement,
- redefine temporal validation,
- convert SUGGESTIVE evidence into an index score,
- automatically decide bets or final predictions,
- expose every REJECTED Edge,
- use known racing heuristics as hand-picked acceptance targets.

## 3. Evidence model

Evidence is channel-specific. Performance and Value must never be collapsed into one undifferentiated confidence label.

For each matched Edge, consumers receive independent evidence levels:

```text
performance_evidence_level = CONFIRMED | SUGGESTIVE | NONE
value_evidence_level       = CONFIRMED | SUGGESTIVE | NONE
```

Signal direction remains independently represented by the existing fields:

```text
performance_signal = POSITIVE | NEGATIVE | NEUTRAL
value_signal       = POSITIVE | NEGATIVE | NEUTRAL
```

Meaning:

- `CONFIRMED`: the channel passed the existing production Statistical Guard for an ACTIVE Edge.
- `SUGGESTIVE`: the channel did not satisfy the ACTIVE q gate, but satisfied the predeclared SUGGESTIVE research gate and directional bootstrap support.
- `NONE`: the channel is neutral, failed its applicable evidence gate, or is not eligible for serving.

Registry `status` remains separately visible. A SUGGESTIVE Edge therefore normally has:

```text
registry_status = REJECTED
serving_evidence = SUGGESTIVE on one or both channels
```

This is intentional. `REJECTED` means “not statistically confirmed under the ACTIVE Registry contract”; it does not mean “all information must be hidden from advisory serving.”

## 4. CONFIRMED channel rule

For normal ACTIVE Registry Edges:

```text
performance_evidence_level = CONFIRMED
    iff registry_status == ACTIVE
    and edge_statistical_guard.performance_stat_pass == true

value_evidence_level = CONFIRMED
    iff registry_status == ACTIVE
    and edge_statistical_guard.value_stat_pass == true
```

An ACTIVE Edge may therefore be:

- performance CONFIRMED only,
- value CONFIRMED only,
- both channels CONFIRMED.

Full #827 confirms this distinction is material:

| ACTIVE channel state | Edge count |
|---|---:|
| Performance only confirmed | 2,062 |
| Value only confirmed | 269 |
| Both confirmed | 241 |

No consumer should infer that both channels are confirmed merely because `status=ACTIVE`.

## 5. SUGGESTIVE channel rule

A channel is eligible to become SUGGESTIVE only when all of the following are true:

```text
final Registry status = REJECTED
temporal_status = ACTIVE
statistical_status = WATCH
channel signal != NEUTRAL
0.05 < channel q-value <= 0.10
same channel directional race-date cluster bootstrap CI excludes zero
```

The Full #827 research stage uses 400 bootstrap samples with deterministic candidate-derived seed.

Candidate-level inclusion is not itself a serving fact. Serving is channel-specific.

For example, if only Value clears the research bootstrap gate:

```text
performance_evidence_level = NONE
value_evidence_level       = SUGGESTIVE
```

The candidate must not be presented as though its performance effect were SUGGESTIVE.

## 6. Current research evidence

Full #827 produced:

- temporal-ACTIVE statistical rejects: 3,667
- q-band selected candidates: 1,015
- selected channels: 1,066
- directional-CI supported channels: 540
- candidates with at least one supported channel: 519

Supported candidates by family:

| Family | Supported |
|---|---:|
| PEDIGREE | 445 |
| TRANSITION | 47 |
| COURSE | 22 |
| HUMAN | 4 |
| RECENT | 1 |

Supported candidate composition:

| Support composition | Candidates |
|---|---:|
| Performance only | 326 |
| Value only | 172 |
| Both | 21 |

This concentration is evidence that a single candidate-level `SUGGESTIVE=true` flag is insufficient.

## 7. Serving profiles

Target v0.2 serving profiles are defined as follows.

### CONFIRMED_ONLY

Backward-compatible behavior.

- serve ACTIVE Edge matches only,
- expose channel-specific CONFIRMED/NONE labels,
- do not include SUGGESTIVE rows.

This corresponds to the existing production behavior conceptually.

### STANDARD

Target ordinary advisory behavior after acceptance testing.

- serve ACTIVE CONFIRMED evidence,
- additionally serve prequalified SUGGESTIVE evidence,
- preserve `registry_status` separately,
- clearly expose evidence level per channel,
- do not numerically add SUGGESTIVE and CONFIRMED evidence.

This profile is intended to fulfill the EdgeDB product goal: surface useful pre-race tendencies while communicating their evidence strength.

### RESEARCH_ALL

Explicit research-only profile.

- may include PROVISIONAL/WATCH/other requested states,
- must never be selected implicitly by ordinary consumers,
- must remain visibly distinct from STANDARD output.

During migration, existing v0.1 matcher behavior stays unchanged. STANDARD becomes the default only in the v0.2 serving path after its implementation and acceptance tests pass.

## 8. Publication architecture

The existing `edge_registry_active.jsonl` remains backward-compatible and must not be silently repurposed to include REJECTED rows.

SUGGESTIVE serving requires a separately traceable publication artifact derived from:

- `edge_registry.sqlite`,
- `edge_statistical_guard`,
- `edge_suggestive_bootstrap_research.jsonl`,
- the matching Registry version / build provenance.

Recommended v0.2 publication shape:

```text
edge_registry_active.jsonl              # existing compatibility asset
edge_registry_suggestive.jsonl          # only serving-eligible SUGGESTIVE rows
edge_serving_catalog_v0_2.jsonl         # optional unified consumer input
```

A SUGGESTIVE publication row must preserve at least:

```text
edge_id
candidate_id
registry_status
family
template_id
polarity
conditions
display_text
performance_signal
value_signal
performance_evidence_level
value_evidence_level
performance_q_value
value_q_value
performance_ci_low / high
value_ci_low / high
sample_n
unique_horses
unique_races
place_rate
place_roi
baseline_place_rate
performance_lift
redundancy_group_id
specificity
registry_version
research_version
bootstrap_samples
```

Publication must fail closed if Registry/research identity or stored/recomputed evidence does not match.

## 9. Exact matching remains unchanged

SUGGESTIVE evidence uses the same canonical current facts and exact condition matcher as ACTIVE evidence.

No fuzzy matching, approximate sire names, alternative distance buckets, or guessed previous runs are introduced.

Current leakage boundaries remain unchanged.

A condition that cannot be resolved pre-race does not match.

## 10. Redundancy and overlapping evidence

Matcher raw output must preserve all exact matches. Evidence must not be deleted merely because another related Edge also matches.

However, presentation and downstream aggregation must prevent obvious double counting.

The existing Statistical Guard `redundancy_group_id` is the canonical first-level grouping key.

Full #827 SUGGESTIVE candidates show why this matters:

- 519 supported candidates occupy 487 redundancy groups,
- 26 groups contain multiple supported candidates,
- those groups contain 58 supported candidates total,
- collapsing blindly to one row per group would remove 32 rows,
- 56 redundancy groups contain both ACTIVE and SUGGESTIVE evidence,
- those overlaps involve 76 SUGGESTIVE candidates and 85 ACTIVE candidates.

Rules are therefore:

1. Match first, group second. A related Edge that does not match the current runner is irrelevant to presentation grouping.
2. Raw `edge_matches[]` preserves every matched Edge and its channel evidence.
3. Grouping is channel-specific. Performance evidence must not suppress Value evidence and vice versa.
4. Within the same matched `redundancy_group_id` and channel:
   - CONFIRMED evidence has presentation precedence over SUGGESTIVE evidence in the same direction.
   - among same-level / same-direction evidence, the most specific matching Edge is PRIMARY; less-specific related Edge rows are SECONDARY.
   - opposite directions are not silently collapsed. They are retained and flagged as a conflict.
5. `strength_score`, ROI, lift, q-values, or confidence values are never summed across overlapping Edges.
6. Consumers may display only PRIMARY rows in compact UI, but raw provenance must retain SECONDARY/conflicting rows.

This grouping rule is a presentation/aggregation contract, not a statistical reclassification.

## 11. Required output fields

Each v0.2 match should eventually expose:

```json
{
  "edge_id": "...",
  "display_text": "...",
  "polarity": "POSITIVE",
  "registry_status": "ACTIVE or REJECTED",
  "performance_evidence_level": "CONFIRMED | SUGGESTIVE | NONE",
  "value_evidence_level": "CONFIRMED | SUGGESTIVE | NONE",
  "redundancy_group_id": "...",
  "specificity": 0,
  "presentation_role": "PRIMARY | SECONDARY | CONFLICT",
  "evidence": {}
}
```

The evidence object must retain the exact matched conditions and the applicable p/q/CI provenance when available.

Consumers must not infer evidence level from display wording or polarity.

## 12. Consumer interpretation

Recommended semantics:

### CONFIRMED

“Historical evidence cleared the current production statistical contract.”

### SUGGESTIVE

“Historical evidence repeatedly points in this direction and passed the lower-confidence research bootstrap gate, but did not clear the ACTIVE multiple-testing threshold.”

SUGGESTIVE must not be described as statistically confirmed, proven, guaranteed, or an independent replication.

Performance and Value wording must remain separate:

- Performance evidence: tendency to outperform/underperform the same-anchor complement in placing outcome.
- Value evidence: tendency for return to outperform/underperform the same-anchor complement.

A performance-positive / value-none Edge must not be called a profitable betting Edge.

## 13. Numerical use

No automatic additive score is authorized.

Forbidden without a separate calibration contract:

```text
CONFIRMED = +N points
SUGGESTIVE = +M points
sum all Edge strength_score
sum all ROI lifts
```

EdgeDB v0.2 serving remains evidence delivery, not final prediction calibration.

Any later numeric aggregation must be validated with TRUE_FORWARD data and must account for overlapping/redundant matches.

## 14. Sensitivity gate before STANDARD activation

The #827 400-sample bootstrap is sufficient to justify further development, but not yet sufficient to enable STANDARD production serving.

Reason: a material portion of supported performance channels are close to the zero boundary. The Full audit found 206 of 347 supported performance channels with the directional CI bound within 0.005 of zero.

Before STANDARD is enabled, run a predeclared sensitivity study that:

1. re-evaluates the same frozen 1,015 candidate set,
2. increases bootstrap sample count without changing q-band or candidate selection,
3. measures support-state stability at channel level,
4. reports flips by family/template/channel,
5. does not retune thresholds based on desired examples.

No known sire, course, or racing maxim is an acceptance target.

The sensitivity study decides whether 400 bootstrap samples are operationally stable enough or whether a larger count is required for SUGGESTIVE publication.

## 15. Acceptance sequence

Implementation proceeds in this order:

1. Freeze this serving contract.
2. Run bootstrap-sample sensitivity on the frozen #827 candidate population.
3. Decide production bootstrap sample count / stability rule.
4. Implement SUGGESTIVE publication builder as a separate sidecar/unified serving catalog.
5. Add v0.2 matcher evidence fields and channel-specific grouping.
6. Keep v0.1 matcher and active export backward-compatible.
7. Run focused synthetic regression tests.
8. Run 2025 real-data current-matching smoke.
9. Run Full publication non-regression audit.
10. Only after all acceptance checks pass, switch the v0.2 ordinary serving profile to STANDARD.

Until step 10, Matcher production behavior remains ACTIVE-only.

## 16. Change control

A contract version bump and revalidation are mandatory for changes to:

- SUGGESTIVE q band,
- required temporal status,
- bootstrap direction rule,
- bootstrap sample/stability rule after it is frozen,
- performance/value evidence semantics,
- STANDARD profile eligibility,
- overlap suppression/grouping semantics that affect consumer-visible PRIMARY evidence.

Display wording may evolve without a statistical version bump if evidence identity, conditions, levels, and provenance remain traceable.

## 17. Related evidence

- `docs/JRDB_Edge_v0_2_Suggestive_Bootstrap_Experiment_v0_1.md`
- `docs/JRDB_Edge_v0_2_Suggestive_Bootstrap_Full_Audit_20260910.md`
- `docs/JRDB_Edge_Contract_v0_1.md`
- `docs/JRDB_Edge_Current_Matching_v0_1.md`
- `docs/JRDB_Edge_Consumer_Integration_v0_1.md`
- `src/research_jrdb_edge_suggestive_bootstrap_v0_1.py`
- `src/jrdb_edge_matcher.py`
- `src/jrdb_edge_matcher_v0_2.py`

This contract does not authorize RaceNote prediction logic changes. It defines EdgeDB serving semantics only.
