# RaceNote v1.1-P Target Selection Freeze — 2026-07-04 / 07-25 / 07-26

Status: **TARGETS SELECTED BEFORE TARGET RESULT ACQUISITION**

Established: 2026-09-09

## Selection boundary

- design: `RaceNote_v1_1_PolarityAxis_Prediction_Design_Candidate.md`
- design commit used as deterministic seed: `783e57512450bed99ee6315596fc569cf8ebe07b`
- settled v1.0 dates excluded: 2026-08-09 / 08-15 / 08-22
- Edge development/backfill dates excluded: 2026-09-05 / 09-06
- 2026-07-18 / 07-19 excluded because they already appear in Eval project material
- exact-date repository search found no existing use for 2026-07-04 / 07-05 / 07-11 / 07-12 / 07-25 / 07-26
- target HJC / SED / result / final odds / final popularity consulted: `false`

## Deterministic selection

Candidate dates:

```text
20260704
20260705
20260711
20260712
20260725
20260726
```

Selection procedure: seed a deterministic PRNG from SHA-256 of the design commit string and sample
three dates without replacement, then sort chronologically.

Selected dates:

```text
20260704
20260725
