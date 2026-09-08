# RaceNote v0.1 vs v0.2 Blind Freeze — 2025-06-28

**FROZEN BEFORE TARGET-DATE RESULT / HJC ACQUISITION**

- target selection: RaceNote Archive `expected_race_index.json` identity metadata only
- target venues: 函館 / 福島 / 小倉, 36 races
- Reader View v0.1 round-trip: **36/36 PASS**
- control: `provisional_handoff_v0.1_unweighted`, same prospective implementation as 2025-03-01/02
- candidate: `RaceNote_Prediction_Handoff_v0_2_Candidate.md`, unchanged from first prospective block
- betting policies frozen: quinella `◎-○ / ◎-▲`; trio A=6-ticket ◎ axis; trio B=5-ticket formation excluding only `◎△1△2`
- `☆ value/disagreement`: diagnostic only, no extra ticket
- target result / HJC / final target odds-popularity / Web result lookup before freeze: **false**

## Prediction payload commitment

The complete 2025-06-28/29 prediction payload contains every v0.1/v0.2 mark, confidence, v0.2 ☆, race-shape comment, ◎/○/▲ comments, risk comment, audit labels, and source semantic SHA.

- local payload: `predictions_20250628_29_v01_v02.json`
- complete payload SHA-256: `5e857cfbb7f8fc6db5c736e7d7ca85fdd48eba98b36100f2db52bd3515886752`
- canonical 2025-06-28 slice SHA-256: `77fbb0196b3b0b081ee722b2bce9f324d0aaea376c5c3dbfa2bfc6372ee9bf29`
- generation script SHA-256: `31a0000a88de3f8288f5c01535133dbe9104f274da8109815c22652e8d78bbd7`
- v0.1 vs v0.2 ◎ differs in the combined 72-race block: 16 races

This cryptographic commitment is the authoritative pre-result freeze. The readable settlement report may reproduce the marks/comments after HJC, but any reproduced payload must match the SHA values above.