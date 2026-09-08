# RaceNote v0.2 vs v0.3 Blind Freeze Manifest — 2025-08-02/03/09/10

**FROZEN BEFORE TARGET-DATE RESULT / HJC ACQUISITION**

## Scope

- dates: 2025-08-02, 2025-08-03, 2025-08-09, 2025-08-10
- venues: 中京 / 新潟 / 札幌
- races: 144
- target selection source: RaceNote Archive expected_race_index.json (BAC/Analysis identity metadata only)
- Reader View round-trip: 144/144 PASS
- target result / HJC / final target odds-popularity / Web result consulted before freeze: **false**

## Frozen logic

- v0.2 axis/order logic: unchanged from `RaceNote_v0_2_Tested_Implementation_Spec_144R.md`
- v0.3 value-role logic: unchanged from the 2025-07-26/27 first blind block
  - ◎ / ○ unchanged from pure v0.2 order
  - reuse preregistered value/disagreement eligibility
  - candidate restricted to pure ranks P3-P5
  - if eligible, chosen candidate becomes ▲ and remaining pure-ranked horses retain their relative order as △1 / △2
  - no tuning from July results
- confidence A/B/C: unchanged
- user-facing comments: same output contract; comments included in frozen payload
- betting policies: v0.2 Q2=◎-○/pure▲; v0.3 Q2=◎-○/value▲; Q4 diagnostic; trio A6/B5

## Cryptographic freeze

The complete local prediction payload contains all 144 races, including:

- v0.2 marks
- v0.3 marks
- confidence
- value-role flags and pure ranks
- race short comments
- ◎ / ○ / ▲ comments
- RaceNote source semantic hashes

Raw serialized payload SHA-256:

`e3e484707a7027c9c6b74fb24c452aa92c7f14213314603ef8f6947f23a34158`

Per-date canonical payload hashes:

| Date | Races | Value-role used | Actual role-order changes | SHA-256 |
|---|---:|---:|---:|---|
| 2025-08-02 | 36 | 15 | 9 | `b38997d22e3a1644d4c3e80981f83a3ee4baf6b0db56881f16d229c0c8cbb552` |
| 2025-08-03 | 36 | 15 | 11 | `45de116f74e7252e4c2fb535b33dc8628de47dcfeb67caee0df8393ba5513884` |
| 2025-08-09 | 36 | 17 | 13 | `a8ce2bcf7b484531d2bda1f64cb9b28be0ef0b8a65eebf932dd0da05f96618a5` |
| 2025-08-10 | 36 | 16 | 12 | `1156d082ff6ea554187e7a7aee38b22fd7092bc305ea14351ab0c790f6a2a3c4` |

Totals:

- value-role used: 63 / 144
- actual v0.2→v0.3 role-order changes: 45 / 144
- confidence distribution: A 30 / B 70 / C 44

The full payload must not be altered after this commit; any later publication/settlement payload must match the frozen SHA above.