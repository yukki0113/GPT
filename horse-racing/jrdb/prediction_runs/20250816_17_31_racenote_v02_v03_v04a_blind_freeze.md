# RaceNote v0.2 / v0.3 / v0.4a Blind Freeze — 2025-08-16 / 08-17 / 08-31

## Status

**AUTHORITATIVE CRYPTOGRAPHIC FREEZE BEFORE TARGET HJC / RESULT ACQUISITION**

- random candidate pool: 2025-08-16 / 2025-08-17 / 2025-08-30 / 2025-08-31
- excluded 2025-08-23 / 08-24 because results were already known
- fixed random seed: `20260908`
- selected: **2025-08-17 / 2025-08-16 / 2025-08-31**
- venues each day: 中京 / 新潟 / 札幌
- total races: **108**
- RaceNote acquisition only; target HJC/result/final odds-popularity/Web result consulted before this freeze: **false**

## Frozen candidates

- v0.2: documented-spec-compatible reconstructed pure ranking control
- v0.3: unchanged old value-role selector shadow
- v0.4a: P3-defense selector frozen in `RaceNote_v0_4a_PreResult_Activation_Calibration_20250816_17_31.md`
- confidence: unchanged v0.3 protocol A/B/C rule
- comments: standard RaceNote short-comment contract
- Q2: `◎-○ / ◎-▲` per selector
- Q4: `◎` to all four top-five opponents
- trio A6 / B5 retained

## Full-payload cryptographic commitment

The canonical JSON contains all 108 race identities, v0.2/v0.3/v0.4a marks, confidence labels, value-role flags, comments, and source semantic hashes.

- canonical prediction payload SHA-256: **`4c249aefc6011a60d0ed890950872eff515a5873d269b45948b4db62398782f3`**
- rendered detailed freeze SHA-256: `8e03722be9ff7ca5b03622dfebe996e4876d3a75825238c2a7e4d3ab3fbe5881`

The exact payload may be archived after settlement; its SHA must match the commitment above.

## Pre-result activation audit

Original v0.4 was pathologically strict at 1/108 = 0.9%, so only activation frequency was used to perform the preregistered pre-result calibration to v0.4a.

v0.4a final activation:

- total: **11/108 = 10.2%**
- 2025-08-17: 5/36
- 2025-08-16: 3/36
- 2025-08-31: 3/36
- promoted pure P4: 11
- promoted pure P5: 0

Old v0.3 actual P4/P5 role changes for shadow comparison:

- 2025-08-17: 10/36
- 2025-08-16: 7/36
- 2025-08-31: 7/36
- total: 24/108 = 22.2%

Confidence distribution:

- A: 24
- B: 44
- C: 40

No further threshold/model changes are permitted after this freeze.

## Runtime reproducibility limitation

The exact one-off v0.2 generator used in the earliest prospective blocks was not retained. Before any target HJC acquisition, the implementation was reconstructed from the frozen tested specification and checked against the immediately preceding 2025-08-02/03/09/10 pre-result freezes:

- v0.2 exact ordered top-five: 134/144 = 93.1%
- v0.2 same top-five membership: 141/144 = 97.9%
- old v0.3 exact marks: 132/144 = 91.7%

This limitation is frozen before target results and applies to interpretation of this block. It must not be concealed or corrected using target outcomes.