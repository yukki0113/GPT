# Issue #2214 — immutable research candidate (aggregate report)

Status: **full build and local verification PASS**. CURRENT was not switched.
Date: 2026-10-27 JST. Source main: `1462a2f499bc318b4bc01d48a79d0b9f0204d9b1`.

The exact 27 annual UKC archives rebuilt the existing research baseline
`c73cf76ad930b5f0` with 128,754 unique horses. The fixed 91 daily PACI ZIPs
and original UKC members were rechecked by size, SHA-256, member list, and
record count. Their exact-ID observations agreed with the prior 108-row audit.

Research candidate `8fe45a6e2c6ccf53` has 128,858 unique horses: 104 additions
and the four unmatched IDs remain absent. It retains 396 source observations
for the additions. Annual pedigree fact rows compare equal; annual parent
relation changes: 0. Daily parent ID resolution: sire 77/104, dam 81/104,
broodmare sire 60/104. The remaining relations are explicit unknowns. Two
horses have non-pedigree semantic history differences, recorded for review.

All 104 additions returned by both individual and batch research queries with
father, mother, broodmare sire names, official lineage codes, and provenance.
At 2025-12-31 the as-of reader returned zero additions. Five-generation
ancestor checks reached depth 0/1/2/3 for 7/3/53/41 horses respectively;
deeper resolution is not asserted.

Full BRDB test suite: 69 passed. A second full candidate build produced the
same generation ID and byte-identical outputs. The private artifact contains
the complete manifest, all input and output SHA-256 values, row-level audit,
observation history, relation differences, verification report, and test log.
Its approved `blood_review` Drive folder location is shared in the task chat.

This candidate has no CURRENT pointer and no automated production exposure.
