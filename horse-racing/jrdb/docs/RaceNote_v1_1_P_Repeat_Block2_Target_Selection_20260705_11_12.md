# RaceNote v1.1-P Repeat Block 2 Target Selection — 2026-07-05 / 07-11 / 07-12

Status: **TARGETS FROZEN BEFORE TARGET RESULT ACQUISITION**

Established after settlement of the first 108-race v1.1-P block.

## Decision carried forward

The first blind block decision is `REPEAT_UNCHANGED`.

The following prediction rule remains frozen without modification:

- `BaseGood - HorseGood <= 0.04` axis eligibility guard;
- ACTIVE performance Edge only;
- one-family-vote correlation control;
- polarity collapse to NEGATIVE / NEUTRAL / POSITIVE;
- challenger must have strictly higher polarity than BaseAxis;
- tie break by higher frozen v0.2 Good, then lower horse number;
- preserve relative order of the remaining four marks;
- Value Edge remains shadow-only;
- no Edge magnitude is added to Good.

No threshold or aggregation rule was tuned from the first block result.

## Target-selection rule

The original pre-result candidate pool frozen before the first block was:

```text
20260704
20260705
20260711
20260712
20260725
20260726
```

The first block used `20260704 / 20260725 / 20260726`.

Block 2 therefore uses the deterministic complement of that already-frozen
candidate pool, without a new random draw:

```text
20260705
20260711
20260712
```

This avoids adding a post-result researcher degree of freedom.

## Leakage audit before freeze
