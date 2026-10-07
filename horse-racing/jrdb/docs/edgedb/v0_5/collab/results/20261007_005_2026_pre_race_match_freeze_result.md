# 20261007_004 — 2026 Pre-Race Match Freeze

Status: PARTIAL — match freeze created for available canonical PACI dates  
Recommendation: `PARTIAL_PRE_RACE_COVERAGE`  
Production impact: NONE

## Scope and boundary

This is a result-blind Turn 2 freeze using the exact 1,620 Turn 1 candidates. It does not join 2026 outcomes or use finish, payout, popularity, odds, post-race performance, or 2026 result-side Analysis fields. Turn 3 has not started.

The first full replay revealed that an explicit blank KYI blinker code had been treated as missing. The corrected run distinguishes blank (inactive) from null/conflicting (UNKNOWN); the earlier run and artifact are superseded.

## A. Input provenance

- Cohort: `horse-racing/jrdb/config/edgedb/v0_5/frozen/v05_positive_value_frozen_cohort.json`
- Cohort SHA-256: `a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9`
- Turn 1: run `37598903743`, artifact `11471917437`; 1,620 candidate objects parsed and consumed, with zero unsupported condition keys. No candidates were regenerated.
- 2026 PACI inventory: canonical Drive folder `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`, snapshot 2026-10-07. Drive listed 84 PACI files. Actions run `37608655008` downloaded 79 files; PACI dates unavailable for matching were `2026-05-10`, `2026-05-16`, `2026-05-31`, `2026-08-01`, and `2026-10-03`.
- The matching population is built with the existing `build_jrdb_edge_current_facts.py` BAC/KYI/UKC parser. It projects race date/key, race-horse key, horse ID/no, venue, surface, distance, frame, sire, and pre-race transitions into an allowlisted schema.
- 2026 chronology: run `37604723913`, artifact `11474018960`, digest `sha256:23080e983350cd61255d229315855cab29a492eef62e3ae1df6c88bbe164c516`. Only SED `race_key`, `horse_no`, `blood_registration_no`, and `race_date` were read. Its 84-day history contains 36,706 starts; 2,156 SED rows could not join to available PACI facts and remain UNKNOWN for PACI-derived history attributes.
- Historical source: accepted Warehouse generation `jrdb_normalized_warehouse_v1_2010_2025_g20260921`, run `37592837881`, artifact `11468713930`, digest `sha256:fb28c17889cf2a9028b58e1bac3164b89a0b4c66eadfb5d3dba19d1ace88499a`. The manifest and all 32 annual SED/KYI partitions were verified.
- Source code commit: `08610fa29fa412b504491f6adb30536e13263584`.

## B. Pre-race coverage

| Measure | Result |
|---|---:|
| First matched race date | 2026-01-04 |
| Latest matched race date | 2026-10-04 |
| PACI race days matched | 79 |
| PACI races | 2,502 |
| PACI runners | 34,550 |
| SED chronology days / starts | 84 / 36,706 |
| PACI dates unavailable | 2026-05-10, 2026-05-16, 2026-05-31, 2026-08-01, 2026-10-03 |

The 79 fact dates are an exact subset of the SED chronology. The five unavailable PACI dates are omitted rather than fabricated. Their SED starts are preserved as unresolved chronology; later history flags remain UNKNOWN when affected.

Monthly coverage and match counts (audit-only):

| Month | Fact rows | Match rows |
|---|---:|---:|
| 2026-01 | 3,982 | 1,268 |
| 2026-02 | 4,021 | 1,280 |
| 2026-03 | 4,237 | 1,347 |
| 2026-04 | 3,743 | 1,353 |
| 2026-05 | 3,419 | 1,093 |
| 2026-06 | 3,589 | 1,273 |
| 2026-07 | 3,746 | 1,397 |
| 2026-08 | 4,314 | 1,327 |
| 2026-09 | 3,137 | 979 |
| 2026-10 | 362 | 110 |

## C. Matching schema and leakage audit

The matcher uses the exact frozen `conditions` object and exact equality. Unsupported condition keys fail closed. Its fact allowlist contains race identity, horse identity/no, venue, surface, distance, frame, sire, distance change, surface transition, FIRST_DIRT, FIRST_TURF, FIRST_BLINKERS, and going bucket.

| Check | Status |
|---|---|
| Result fields absent from matching schema | PASS |
| Payout fields absent | PASS |
| Popularity absent | PASS |
| Odds absent | PASS |
| Post-race fields absent | PASS |
| 2026 Analysis fields read | NONE |
| Canonical pre-race going bucket available | NO — all 34,550 matching facts are UNKNOWN for going |

Historical Warehouse columns read were SED identity/key/date/surface/distance and KYI identity/key/blinker code. Those values derive chronology and pre-race conditions only; result and market fields are not selected or passed to the matcher.

## D. History audit

All flags use strictly earlier dates; target and future rows cannot enter prior history. Chronology violations: **0**.

| Flag | TRUE | FALSE | UNKNOWN |
|---|---:|---:|---:|
| FIRST_DIRT | 2,554 | 31,909 | 87 |
| FIRST_TURF | 2,379 | 32,094 | 77 |
| FIRST_BLINKERS | 909 | 33,470 | 171 |

The history index includes 781,161 2010–2025 Warehouse starts and all 36,706 SED chronology starts from 2026. Distance-change and surface-transition facts are unresolved for 5,112 matching rows. UNKNOWN never satisfies a TRUE-only candidate condition.

## E. Cohort and match diagnostics

- Candidate count: **1,620**
- Cohort SHA: exact match to the frozen digest above
- Unsupported condition count: **0**
- Match rows: **11,427** across **10,019** unique runners
- Runner density: 0 matches = 24,531; 1 = 8,718; 2 = 1,204; 3+ = 97
- Maximum matches on one runner: **4**
- Family counts: T1 3,361; T2 5,585; T3 837; T4 1,511; T5 133

These diagnostics did not change candidate membership, conditions, or match logic.

## F. Freeze fingerprints and artifacts

- Pre-race fact SHA-256: `526516f9e5a1f46d96de6484e68a9b04237f6f5d6ac2f80f0c34ad380e5ef5c0`
- Match SHA-256: `fbc6258626e9f407990639b1bcb3cfaad3b7d83666aee418c754d74f79240cf4`
- Daily fact/match fingerprints: 79 rows in `v05_2026_match_counts_by_day.csv` within the Actions artifact.
- Corrected Actions run: `37608655008`; artifact `11477465151`, `edgedb-v05-2026-match-freeze-pr-1895`; digest `sha256:d892b0f5262b864c313ef7ff27c4fff65d103e704d392ddef4b6122d71d5d246`; expires 2027-01-05.
- The row-level fact and match Parquet files remain in that Actions artifact and are not committed to Git.

## G. Recommendation

`PARTIAL_PRE_RACE_COVERAGE`

The canonical source path is usable and produced a non-empty, result-blind match freeze, but five PACI dates are unavailable and the canonical pre-race builder does not supply going. Preserve this partial boundary for review; do not start Turn 3 until the missing coverage and going-field limitation are addressed. Production remains unchanged.
