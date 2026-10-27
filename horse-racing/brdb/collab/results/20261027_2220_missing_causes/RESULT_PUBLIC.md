# Issue #2220 — static-unjoined KYI cause audit

Scope: 2026-01-04–2026-10-25 KYI declared entries; cancellations/actual starts are UNKNOWN.

Upstream denominator: 10,680 horses / 39,543 entries; RESEARCH joins 6,886; static missing 3,794 horses / 10,016 entries.

| Primary reason | Horses | % of 3,794 |
|---|---:|---:|
| DAILY_UKC_PRESENT_OUTSIDE_104_OVERLAY | 3,794 | 100.0000% |
| PROFILE_DATE_OR_SELECTION_GUARD | 0 | 0.0000% |
| ANNUAL_VALID_PROFILE_NOT_IN_BASE_REVIEW_REQUIRED | 0 | 0.0000% |
| NOT_FOUND_IN_SCANNED_ANNUAL_OR_DAILY_UKC | 0 | 0.0000% |
| UNKNOWN_INPUT_GAP | 0 | 0.0000% |
| UNKNOWN_PARSE_FAILURE | 0 | 0.0000% |
| UNKNOWN_BUILD_DISCREPANCY | 0 | 0.0000% |

Input scans: annual 27/27 ZIPs; daily 91/91 ZIPs. Target ID matches: annual 0; daily 3,794.

When all targets have valid daily source profiles outside the overlay, the measured primary cause is the 104-ID overlay scope. Annual nonappearance does not imply that daily UKC lacks pedigree facts. The reason table above, including zero/UNKNOWN categories, controls the conclusion.

Source-supported static recovery potential: +3,794 horses / +10,016 entries, bringing a future extended candidate to 10,680/10,680 horses (100.0000%) and 39,543/39,543 entries (100.0000%). This is a source audit, not a completed candidate build.

A conditional single-latest-profile snapshot could add 3,794 race-date-safe entries. Earlier dated raw-source evidence exists for 10,016 missing entries; using it would require a separately implemented historical/profile-history reader. Do not equate static potential or dated-source evidence with availability through the current Reader.

The conditional latest-snapshot calculation preserves existing annual and 104-overlay profiles and appends only the newly found targets. Replacing existing profiles with newer daily observations would require a separate audit. Date comparisons are inclusive; intra-day publication timing remains unverified.

The prior 292 as-of-only blocked entries of already-joined horses are outside this static missing cohort.

## Monthly active-cohort missingness

| Month | Missing horses / active horses | Missing entries / entries |
|---|---:|---:|
| 202601 | 484/3,472 (13.9401%) | 566/3,982 (14.2140%) |
| 202602 | 485/3,475 (13.9568%) | 560/4,021 (13.9269%) |
| 202603 | 546/3,613 (15.1121%) | 643/4,237 (15.1758%) |
| 202604 | 594/3,383 (17.5584%) | 665/3,743 (17.7665%) |
| 202605 | 701/3,889 (18.0252%) | 851/4,763 (17.8669%) |
| 202606 | 903/3,241 (27.8618%) | 992/3,589 (27.6400%) |
| 202607 | 1,060/3,264 (32.4755%) | 1,224/3,746 (32.6749%) |
| 202608 | 1,404/3,905 (35.9539%) | 1,688/4,777 (35.3360%) |
| 202609 | 1,113/2,823 (39.4261%) | 1,255/3,137 (40.0064%) |
| 202610 | 1,374/3,171 (43.3302%) | 1,572/3,548 (44.3067%) |

Within this fixed snapshot, entry missingness rises from 14.2140% in January to 44.3067% through October 25. This supports a descriptive late-period coverage decline; it is not a causal claim that being a new horse removes UKC data. All classified targets still have daily UKC evidence.

## Birth year / declared new-race class

| Source birth year | Missing horses |
|---|---:|
| 2019 | 1 |
| 2020 | 1 |
| 2021 | 2 |
| 2022 | 15 |
| 2023 | 1,580 |
| 2024 | 2,195 |

| First scanned BAC class | Missing / cohort horses |
|---|---:|
| A1 | 2,875/2,876 (99.9652%) |
| OTHER | 919/7,804 (11.7760%) |

A horse can be active in several months; these horse counts are non-additive. First-appearance month groups are disjoint. BAC A1/A2 identifies a declared new/unraced race class, not an independently confirmed debut. Birth years come only from consistent, valid exact-ID UKC birth dates. New-race and birth-year composition is descriptive evidence, not an asserted causal explanation.

Annual nonappearance is limited to the verified 1999–2025 archive inventory. Dates after 2026-10-25 and archives outside the inventory are unverified. Profile quality, sentinel dates, conflicts and input gaps remain explicit evidence flags; no name rescue is used.

The annual scan encountered 3 source IDs outside the numeric KYI identity domain. They are retained in anomaly evidence without normalization and do not interrupt the exact target-ID scan.

Next research build inputs: the same SHA-pinned 27 annual ZIPs and all 91 PACI UKC members, with the 104-ID inclusion cap removed. Under the preserved-profile assumption the master would have 132,652 profiles. A separate immutable generation build, parent-resolution/regression audit and explicit research reader validation are still required.

Detailed artifacts: 3,794-row CSV/JSON, raw-record/source SHA provenance, source-observation JSONL/CSV, entry evidence, monthly/first-month/new-class/birth-year/race-type cross tables, unknown list, run/test logs and manifest. Execution is local managed runtime; no new generation, CURRENT change or production publication is part of this analysis.
