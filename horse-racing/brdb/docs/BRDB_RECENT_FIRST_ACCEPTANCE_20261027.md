# BRDB 血統データ受入基準 — Recent-first v0.1

Status: USER PRIORITY CONFIRMED / COVERAGE BY RACE-YEAR NOT YET MEASURED
Date: 2026-10-27
Scope: Research and acceptance design, no CURRENT/PWA/News cutover

## Required quality priorities

1. **Must: recent 1–2 years/current**. Recent race entries (2024–2026, with 2026 source verification pending) must have dependable horse_id-based sire/dam/BMS facts, sire/BMS lineage codes and mapped official line names, missing status and profile-as-of provenance. Do not require complete 3–5-generation ancestors. Confirm actual race-entry cohort with JRDB canonical entry keys, not only UKC birth year or latest profile year.
2. **Must next: about 10 racing seasons (2016–2025)**. Support as-of-safe pedigree facts and historical joining to JRDB race results for backtests and condition-specific frequency analysis. Inventory coverage **by race year** and by role, with denominators unique entrants and starts separately. Guard against future-profile leakage, repeated starts and later taxonomy knowledge.
3. **Older ancestor/historical horses**. Official lineage and reviewed geographic pedigree-root type (US/European/etc.) are sufficient. Unknown/ambiguous stays UNKNOWN. Do not insist on full recursive canonical 5-generation IDs or attempt fuzzy name matching to fill them.

## Required coverage report contract

For each actual race year 2016..2026 where inputs available:
- `entries_total` / `unique_horses`
- `horse_id_join_matched`, `sire_name_present`, `dam_name_present`, `bms_name_present`
- `sire_line_mapped`, `bms_line_mapped`
- `sire_parent_id_resolved`, `dam_parent_id_resolved`, `bms_parent_id_resolved` (diagnostics only, not required)
- `official_family_taxonomy_mapped`, `regional_root_verified`, `regional_root_unknown`
- `historical_asof_verified`, `asof_unverified`, `source_generation`, `date_filter_version`.
Calculate rates using exact denominators; distinguish a field's factual presence from canonical parent identity resolution. Only make 2026 claims after confirming access to 2026 UKC/entry feeds.

Do not compare all-master unresolved counts to a recent-field cohort; they answer different questions. Also distinguish archive-year UKC horse IDs from actual racing entrants.

## Sentinel release gate

- 27-year candidate `9ad752020bd5801b` must not be adopted: eight `99999999` source observations were previously selected as latest.
- Fixed builder version 0.2.0 quarantines `99999999`, tracks provenance, rejects invalid calendar dates; generation identity incorporates builder version.
- Issue #2172 FAILED before building candidate due a Python SyntaxError. Fixed syntax at commit `deb487501b595dc427159c7545614b996cb68dd2`; retry [Issue #2205](https://github.com/yukki0113/GPT/issues/2205) is validation pending at document creation.
- Test suite, candidate audit, sentinel zero-in-output, 8 horse fallback, immutable manifest, and recent 2016–2026 annual field coverage are separate checks. A generic generation PASS is not automatically the recent-field acceptance PASS.
- BRDB CURRENT `eeca93556584a5b8`, PWA, Newspaper and review-v0.1 remain unchanged until separately approved.
