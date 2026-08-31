# JRDB PWA Index Phase A implementation status v0.1

## Scope

Phase A establishes a Raw-direct, time-aware longitudinal SQLite for the independent-index project.

Implemented files:

- `schema/jrdb_index_base_schema_v0_1.sql`
- `src/build_jrdb_index_base_from_raw.py`
- `tests/test_build_jrdb_index_base_from_raw.py`
- `docs/README_build_jrdb_index_base.md`

## Architecture decision

The research base is intentionally separate from Analysis Lite / Stats Mart / Fact Lite / RaceNote. Analysis Lite remains the compact production analysis layer; Index Base preserves detailed SED/CHA/CYB/UKC material required by RunPerf / Ability / Edge research.

Availability is explicit:

- PRE_RACE: BAC / KYI / CHA / CYB / dated UKC observation
- CURRENT_RESULT: SED race/result context
- BAC-missing historical race headers reconstructed from SED are marked `CURRENT_RESULT_FALLBACK` and are not valid pre-race evidence.

## Synthetic validation

`tests/test_build_jrdb_index_base_from_raw.py` currently covers seven synthetic parser/integration cases.

Status: **7 / 7 PASS**.

This is not a substitute for the full 2010-2025 Raw build.

## Acceptance gate before Phase B

Run the builder against canonical external 2010-2025 Raw storage and audit at minimum:

1. SQLite integrity check
2. race / runner counts by year
3. BAC vs SED race coverage and `CURRENT_RESULT_FALLBACK` count
4. KYI vs SED horse-key match rate
5. previous-result-key resolution rate
6. CHA / CYB coverage by year and effective `available_from`
7. UKC as-of profile coverage and duplicate/change behavior
8. null/invalid distribution for time, first/last 3F, weight, body weight, corners, track condition
9. duplicate business keys / non-identical duplicate detection
10. source ZIP manifest and SHA-256 preservation

Only after this audit passes should Phase B start fitting ExpectedTime / DayTrackBias / RunPerf candidates.
