# Training Pattern Stage 2b — Evidence

Date: 2026-09-11
Status: **DEVELOPMENT-PERIOD VALIDATION COMPLETE**
Scope: Theme B incremental validation against confirmed Training Edge v0.1 baseline. This document does not authorize production deployment and does not treat 2024-2025 as unopened holdout.

## 1. Evidence identity

- Protocol: `horse-racing/jrdb/docs/Training_Pattern_Stage2b_Protocol_20260911.md`
- Analyzer: `horse-racing/jrdb/src/analyze_jrdb_training_stage2b.py`
- Workflow: `.github/workflows/jrdb_training_stage2b_issue.yml`
- GitHub Issue: `#846` — `[JRDB_TRAINING_STAGE2B] training-pattern-stage2b-20260911-a1`
- Actions run ID: `34507502943`
- Frozen analyzer source SHA: `58797eddbe5d04d55a7de83d8f8473a4fd7c06cb`
- Workflow head SHA: `5ea62c14a2961624b2bbc28976c5eeade6591c8a`
- Run conclusion: `success`
- Artifact ID: `10165030176`
- Artifact name: `jrdb-training-stage2b-training-pattern-stage2b-20260911-a1-34507502943`
- Artifact digest: `sha256:3e1bd66f1b12d873ba61d7a363d7682f2958b68163de82c10d6a1eccc19b61cc`
- Artifact size: `32,602` bytes
- Artifact created: `2026-09-10T17:35:16Z`
- Artifact scheduled expiration: `2026-10-10T17:35:15Z`

Workflow exits:

- FETCH: `0`
- AUDIT: `0`
- ANALYZE: `0`

## 2. Temporal and holdout guard

Stage 2b used the development-only Training Research Lite.

- Eligible 2013-2023 rows: `214,833`
- OOT test rows 2018-2023: `112,766`
- 2018: `19,012`
- 2019: `17,322`
- 2020: `19,045`
- 2021: `18,975`
- 2022: `18,108`
- 2023: `20,304`
- Maximum selected year: `2023`
- Selected 2024-2025 rows: `0`

The 2024-2025 outcomes were already opened and consumed by Training Edge v0.1 and were not used for Stage 2b selection, fitting or evaluation.

## 3. Model definitions

- **M0**: confirmed Training Edge v0.1 development baseline: JRDB processed training fields + current rest bucket + same-horse vertical `final_self_pct`.
- **M1**: M0 + generic rotation/training-process facts.
- **M2**: M0 + strictly-prior shrinkage-regularized trainer-pattern effects.
- **M3**: M0 + generic B + trainer-pattern effects.
- **M4**: M3 + predeclared same-horse vertical × B interactions.

All families used the frozen Stage 2b protocol and annual walk-forward testing for 2018-2023.

## 4. Pooled OOT results

| Model | Spearman | Δ vs M0 | RMSE | Top-bottom mean spread | Δ spread | Positive Δ years | Stage2b decision |
|---|---:|---:|---:|---:|---:|---:|---|
| M0 | 0.1990277 | — | 0.0869222 | 0.0543114 | — | — | confirmed baseline |
| M1 | **0.2165464** | **+0.0175187** | **0.0866624** | **0.0589593** | **+0.0046479** | **6/6** | **B_CORE_CANDIDATE** |
| M2 | 0.1991295 | +0.0001018 | 0.0869205 | 0.0545511 | +0.0002397 | 4/6 | **B_AUXILIARY_ONLY** |
| M3 | **0.2168032** | **+0.0177755** | **0.0866576** | **0.0595908** | **+0.0052794** | **6/6** | **B_CORE_CANDIDATE** |
| M4 | **0.2168202** | **+0.0177925** | **0.0866578** | **0.0588057** | **+0.0044944** | **6/6** | **B_CORE_CANDIDATE** |

## 5. Annual Spearman increment vs M0

| Year | M1 | M2 | M3 | M4 |
|---:|---:|---:|---:|---:|
| 2018 | +0.012686 | -0.000341 | +0.012676 | +0.012792 |
| 2019 | +0.016172 | -0.000163 | +0.016045 | +0.015957 |
| 2020 | +0.022763 | +0.000167 | +0.023088 | +0.022966 |
| 2021 | +0.019843 | +0.000218 | +0.020188 | +0.020067 |
| 2022 | +0.022488 | +0.000104 | +0.022948 | +0.023564 |
| 2023 | +0.011657 | +0.000542 | +0.012224 | +0.011878 |

M1, M3 and M4 improved M0 in every OOT test year. M2 was near zero and reversed slightly in 2018-2019.

## 6. Complexity comparison

The extra gain beyond M1 was very small:

- M3 minus M1 pooled Spearman: `+0.0002568`
- M4 minus M3 pooled Spearman: `+0.0000170`
- M3 improves top-bottom mean spread vs M1 by about `+0.0006315`
- M4 does not improve the top-bottom mean spread over M3.

Therefore the Stage 2b evidence supports the generic rotation/training-process block as the substantive B signal. Strictly-prior trainer-pattern history and explicit A×B interaction terms add little aggregate predictive value relative to their additional complexity.

## 7. Named trainer-pattern diagnostics

Named trainer patterns were retained only as interpretability diagnostics. Some discovery patterns survived temporal validation, including trainer × course, trainer × effort, trainer × training type, trainer × training-course type and trainer × course × rest combinations.

However the generic trainer-pattern model M2 added only `+0.0001018` pooled Spearman over M0. This is the controlling aggregate evidence: named trainer lore must not be promoted into the core index merely because individual retrospective patterns appear plausible.

## 8. Controller interpretation

The Stage 2b evidence supports the following development decision:

```text
B_GENERIC_ROTATION_TRAINING_PROCESS = RETAIN_FOR_NEXT_DEVELOPMENT_CYCLE
B_TRAINER_PATTERN_HISTORY = AUXILIARY_ONLY
B_EXPLICIT_A_X_B_INTERACTIONS = DO_NOT_REQUIRE_FOR_CORE
2024_2025_REUSED_AS_UNOPENED_HOLDOUT = false
PRODUCTION_DEPLOYMENT = NOT_AUTHORIZED_BY_STAGE2B_ALONE
```

The preferred core representation of Theme B is the M1 feature block because it captures almost all of the observed B increment with substantially lower complexity than M3/M4.

Any next index version that includes B must be separately versioned from confirmed Training Edge v0.1 and should receive genuine forward confirmation on races not used to design it.
