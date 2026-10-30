# Issue #2230 actual 2026 KYI audit

Generation `5279af0bd8226cde`; 10,680 unique declared horses and 39,543 declared entries, January 4–October 25, 2026. This measures calendar-day inclusion; same-day distribution time and confirmed starts are unknown.

| Method | Available declarations | Rate |
|---|---:|---:|
| Static latest snapshot | 39,543 | 100% |
| v0.2 latest-only, as-of | 33,029 | 83.526794% |
| v0.3 historical, as-of | 39,543 | 100% |

History adds 6,514 declarations (16.473206 percentage points). Annual snapshot contributes 29,131, historical daily 6,514, latest daily 3,898. All 39,543 input history rows were semantically validated; all 3,898 additions, including the 104 preserved profiles, match the latest profile on its selected observation date. Future selected profile dates and observation dates were checked against every as-of date: zero leaks. This result is conditional on same-day observations being available before the actual race time, which was not established.

All three parent names and both official lineage codes are present and mapped in every available entry for each method. Historical parent IDs are deliberately UNKNOWN for every entry and every role; current static relation IDs are not reused. The summary contains per-role static and latest resolved/unknown counts. This limits graph coverage; no name-only inference is made. Annual profiles before the selected snapshot are unsupported.

Ten selection tests pass (including ordering, duplicate, conflict, invalid JSON/hash, future and changed-parent profiles). Complete row results, run logs, source and checksums are in the approved Drive artifact. No CURRENT or production writes.
