# Controller status — Existing-Horse Ability v0.1 — 2026-09-03

## Predictive decision

`PASS_STRONG`

Frozen candidate:

```text
ElasticNet
recent_decay=D070
distance_bandwidth=200m
aptitude_shrink_k=0
jockey_shrink_k=0
alpha=0.01
l1_ratio=0.5
```

2024-2025 temporal confirmation run `33720247812` passed all technical gates.

Primary deltas versus A0_D070:

- 2024: `+0.017550366255286942`
- 2025: `+0.01776975122981478`
- equal-year mean: `+0.01766005874255086`

## Materialization status

Predictive specification is frozen and accepted as production-candidate.

Official materialization is **not yet accepted** pending rerun after the semantics-preserving metadata correction documented in `Existing_Horse_Ability_v0_1_Materialization_Metadata_Correction_20260903.md`.

Issue #321 / run `33722753208` successfully generated all 781,161 rows and 569,234 existing-horse scores, but its annual model snapshots omitted only the metadata name of the already-present constant-zero 22nd feature column. It is classified `INVALID_TECHNICAL_METADATA`.

Do not retune or reopen candidate selection during the corrected materialization rerun.

Debut/no-scored-history Ability remains a separate workstream.
