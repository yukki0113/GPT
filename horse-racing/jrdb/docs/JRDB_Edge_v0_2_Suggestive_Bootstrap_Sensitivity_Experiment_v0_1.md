# JRDB Edge v0.2 SUGGESTIVE Bootstrap Sensitivity Experiment v0.1

Status: **EXPERIMENT SPEC / NO SERVING CHANGE**  
Established: 2026-09-10

## Purpose

Measure whether the SUGGESTIVE channel support observed with the existing 400-sample race-date cluster bootstrap is stable when bootstrap sampling is increased.

This study does not expand the q band, recover additional rejected candidates, or alter ACTIVE/Registry/Matcher semantics.

## Frozen Full baseline

Source: Issue `#827`, run `34442743305`, Full 2010-2025.

The baseline research output contains:

- q-band selected candidates: 1,015
- baseline-supported candidates: 519
- baseline-supported channels: 540
- baseline bootstrap samples: 400

Frozen identity hashes, calculated from sorted newline-delimited keys:

```text
supported edge_id set SHA-256:
a65138340b905f5bd5650ca773346a3262dcd5a62e0bc823e1e5de0d2cea86f4

supported edge_id|channel set SHA-256:
bbe29fd342b6a6e9a833612390e4ab39da19b55b2cd9503e26211a5d6fe589b5
```

The Full sensitivity audit must reproduce these baseline identities before interpretation.

## Population

Only channels that were already directional-CI supported in the frozen 400-sample baseline are re-evaluated.

Therefore this is a **retention/stability study**, not a second opportunity for baseline-non-supported channels to become SUGGESTIVE.

No candidate is selected because of a known sire, course, racing maxim, or desired downstream example.

## Method

For every baseline-supported channel:

1. resolve the same `edge_id` / `candidate_id` against the rebuilt Registry and temporal audit,
2. verify the stored nominal p-value matches recomputation from the Feature Mart,
3. verify the channel remains in the original `0.05 < q <= 0.10` research band,
4. rerun the same race-date cluster bootstrap with the same deterministic candidate-derived seed,
5. increase bootstrap samples from 400 to **2,000**,
6. re-evaluate only the same channel and same signal direction,
7. record whether directional CI support is retained.

No FDR/q recalculation, q threshold retuning, signal direction change, or effect threshold change is authorized.

## Why 2,000

The first sensitivity step uses 2,000 samples as a fivefold increase over the 400-sample research baseline while keeping runtime practical for the existing Full Actions pipeline.

This number is an experiment setting, not yet a permanent serving contract. The result determines whether 400 is operationally stable enough or whether production SUGGESTIVE publication needs a higher bootstrap count or another stability rule.

## Outputs

- `edge_suggestive_bootstrap_sensitivity.jsonl`
- `edge_suggestive_bootstrap_sensitivity_audit.json`
- `edge_suggestive_bootstrap_sensitivity_audit.md`

Audit dimensions:

- retained/lost candidate count,
- retained/lost channel count,
- family,
- template,
- polarity,
- performance/value channel.

## Acceptance sequence

1. Implement sensitivity audit without Registry mutation.
2. Run focused synthetic tests.
3. Run 2025-only real-data smoke.
4. Confirm sensitivity outputs are created and the ordinary Edge pipeline remains successful.
5. Run Full 2010-2025 sensitivity build.
6. Verify Full baseline candidate/channel hashes equal the frozen #827 identities.
7. Analyze retention and losses before choosing the production SUGGESTIVE bootstrap policy.

No Matcher or serving change is authorized by this experiment.
