# Issue #2232: historical parent identities and ancestor graphs

The fixed 2026 KYI cohort contains 10,680 horses and 39,543 declared entries; actual starts, cancellations and the time of same-day publication are unconfirmed. All 39,543 declaration profiles remain available at calendar-day granularity. All parent IDs below were resolved from profiles available on the date, using exact-only matching and the existing strict sex, year, lineage, candidate uniqueness and dam/BMS guards. No undated alias is used.

| Role | Resolved entries | UNKNOWN entries | Resolved rate |
|---|---:|---:|---:|
| sire | 28,164 | 11,379 | 71.223731% |
| dam | 29,869 | 9,674 | 75.535493% |
| broodmare sire | 21,222 | 18,321 | 53.668159% |

The v0.3 reader reported all these parent IDs as UNKNOWN. The above counts are thus the increases over v0.3 for this denominator. The parent ID differences from the current static table are 0 sire, 346 dam and 0 BMS entries; the dated result takes precedence, and no static ID is used to resolve history.

Maximum observed sire/dam ancestor depths 0, 1, 2, 3, 4, 5 occur in 2,966, 2,568, 20,448, 13,075, 486 and 0 declarations respectively. Zero means no resolved path, not proof of missing ancestry. The BMS is dam-sire at depth 2; all graph nodes are reevaluated at the same date. `summary.json` and `independent_verification.json` provide annual/daily and monthly breakdowns, and first-entry-per-horse counts; the Drive artifact contains the complete day-level and row-level paths, source provenance and guards.

A strict date-inclusive result may include records distributed after the actual race time because that time is not known. Annual history remains the selected annual snapshot only. As-of dates after the observed daily coverage are rejected. No CURRENT, production or other application is changed.
