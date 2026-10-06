# RaceNote Forecast Human-Context Reader v0.5.0 Candidate

Status: **RESEARCH CANDIDATE — NOT PRODUCTION**  
Date: 2026-10-06  
Logic id: `RaceNote-Human-Context-Reader-0.5.0-candidate`  
Stage D decision: **READY_FOR_CLEAN_BLIND_A_B**

## Purpose and boundary

The candidate projects the same validated, market-blind RaceNote Reader View v0.1 used by v0.4.6 into a different information surface. The existing v0.4.6 Reader, current pointer, extraction, normalization, prediction semantics and freezing workflow remain unchanged. This candidate has no production route or prediction prompt.

The command is:

```bash
python horse-racing/jrdb/src/racenote_reader_v050.py <clean-reader.json> \
  --output <candidate.json> \
  --policy horse-racing/jrdb/docs/racenote/research-work/results/stage_c/reader_feature_policy_v0_5_candidate.json
```

The Stage C policy is the authority. `config/racenote_reader_v050_binding.json` binds all 73 policy IDs to exact normalized source paths. The transformer validates binding against the Stage C policy when `--policy` is supplied. The candidate is deterministic for the same input and binding.

## Output contract

```text
candidate_version
input_view_version
source_semantic_sha256
normal_view
  tier_legend: P=PRIMARY, S=SECONDARY, C=CONTEXT_ONLY
  shared_context
  race
  horses[]
    identity
    evidence
      ABILITY / PACE_POSITION / TRAINING_CONDITION /
      SUITABILITY / CONNECTIONS / MARKS
      P / S / C -> feature_id -> source value
    other_context (all clean non-policy runner evidence)
provenance
  source_metadata
  policy_binding_version
  horses[]
    horse_no
    detail[]: feature_id, source_family, source_path,
              value, reason, primary_representation
    missing_feature_ids
    missing_features[]: source_path and absent/null/empty_string state
    divergence
```

Only `normal_view` is the default model-facing candidate. `provenance` is a separate inspectable sidecar, not a second independent vote. A later A/B runner must pass only `normal_view` as normal evidence and may expose provenance on demand for audit or an explicitly justified detail request.

## Presentation rules

- **ABILITY:** IDM is primary. Information and longshot indices support it in the same block. JRDB class appears when both the source value and race class are present. Total index and parent marks remain in detail.
- **PACE_POSITION:** Late index is primary. Front, pace and position numeric indices are secondary. Supplied ranks and projected orders move to detail; projected margins form the normal trajectory. Lane, start and late-break remain in detail until an explicit relevance gate is defined.
- **TRAINING_CONDITION:** KYI training is primary; CHA last clock and CYB condition are secondary. CYB training is the normal workout representation, with CHA total in detail. If both values differ, both are retained and a divergence note is emitted. No equality is inferred when one source is missing.
- **SUITABILITY and CONNECTIONS:** Fit fields appear only when populated and race-relevant. Jockey index appears once; expected top-two rate stays in detail. Stable index is secondary.
- A populated `CONTEXT_ONLY` field is hidden from normal view by default. Explicit gates allow jockey index and CYB training index as the required normal representations; distance fit when race distance is known; turf/dirt fit on the matching surface; heavy-track fit when the race condition is heavy; and JRDB class when race class is known. Other context fields remain in detail until a deterministic gate is justified.
- Other clean pre-race context, including race trends, runner identity, history, pedigree, stats and RRDB context, remains available. Stage C fields that are hidden or irrelevant to the present race remain in provenance.

The tiers are presentation roles, never numerical weights or mechanical votes. Missing values are omitted from normal evidence and recorded as absent, null or empty string in provenance. No correlated feature is filled in for a missing source.

The transformer rejects direct target market/result fields and does not consume target-race results, final odds, final popularity or payouts. Historical past-run facts already present in the clean Reader remain context. No re-prediction occurs in Stage D.

## Comparison and compatibility

The separate `normal_view` is compared with the compact JSON encoding of the clean v0.4.6 input. The full candidate includes provenance and is therefore larger; normal-view savings are modest. The Stage D report records fixture-level counts and method.

The active `config/racenote_forecast_logic_current.json` pointer stays at v0.4.6. No v0.4.6 file is modified. This spec authorizes only a later clean-blind, same-evidence A/B study, subject to its own instruction and audit.
