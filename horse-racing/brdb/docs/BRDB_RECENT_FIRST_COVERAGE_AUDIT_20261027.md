# BRDB Recent-first 基本血統の充足率監査（2026-10-27）

Status: UKC ANNUAL COHORT PASS / REAL KYI ENTRANT COHORT IN EXECUTION
Research generation: `c73cf76ad930b5f0`; no CURRENT switch.

## Scope and denominator

The 2016–2025 annual cohort audit uses unique horse IDs recorded in each `UKC_YYYY.zip`. **This does not mean entrants who raced that year** and horse IDs may appear across annual archives. Do not add annual rows to make a unique-horse denominator.

Run [#2208](https://github.com/yukki0113/GPT/issues/2208) / [40433329593](https://github.com/yukki0113/GPT/actions/runs/40433329593) PASS. Source version `f45e9256332d9a8b0542773fc2e3c837528006ac`, report `output/annual_ukc_cohorts_2016_2025.json`.

| UKC year | unique horse IDs | joined | all sire/dam/BMS names | both official sire/BMS lines mapped | selected profile newer than that year's end |
|---|---:|---:|---:|---:|---:|
| 2016 | 11,183 | 11,183 | 11,183 | 11,183 | 6,645 |
| 2017 | 11,277 | 11,277 | 11,277 | 11,277 | 6,652 |
| 2018 | 11,398 | 11,398 | 11,398 | 11,397 | 6,656 |
| 2019 | 11,557 | 11,557 | 11,557 | 11,557 | 6,845 |
| 2020 | 11,702 | 11,702 | 11,702 | 11,702 | 6,929 |
| 2021 | 11,567 | 11,567 | 11,567 | 11,567 | 6,850 |
| 2022 | 11,557 | 11,557 | 11,557 | 11,557 | 6,912 |
| 2023 | 11,720 | 11,720 | 11,720 | 11,720 | 6,841 |
| 2024 | 11,786 | 11,786 | 11,786 | 11,783 | 6,835 |
| 2025 | 11,818 | 11,818 | 11,818 | 11,818 | 0 |

These rates establish official pedigree *facts* availability in the pinned 27-year candidate, not historical as-of readiness. Future-updated profiles are only a diagnostic; their race-date validity still requires explicit proof or historical state reconstruction.

## Actual entrants: independent audit

KYI normalized warehouse 2023, 2024, 2025 Parquet sourced from `horse-racing/jrdb/config/warehouse_drive_index_kyi_v1.json`, pinned separately in `horse-racing/brdb/config/public_drive/kyi_2023_2025_research_inputs_v0_1.json`.

- Real-entry audit implementation: `horse-racing/brdb/src/audit_brdb_kyi_recent_cohorts.py`.
- Run: [#2209](https://github.com/yukki0113/GPT/issues/2209). Needs actual artifact readback before any coverage claim.
- Per year: KYI entry rows, distinct horse IDs, BRDB ID join, all three names, both official lineage mappings, later-than-year-end current profile counts. Does *not* assert retrospective safe features.
- 2026 cannot be called covered by this 2010–2025 warehouse; acquire a separately verified 2026 current entry source.

## Action gates

1. Confirm KYI dataset key/schema, #2209 success, genuine unique entry denominators.
2. Expand matching join audit from 2023–2025 to 2016–2025, preserving exact archive-year and race-date distinction.
3. For historical backtests, use dated observations and strict `data_date <= historical race date` (with explicit same-day/source policy), never unguarded selected latest profile from 2025.
4. Review high-frequency mismatches by horse ID and lineage source code. UNKNOWN != NO ancestry.
5. Country/region-root taxonomy and Storm Cat/Halo ancestor-presence filters remain independent; neither is a prerequisite to P0/P1 basic pedigree.
6. No current generation swap, PWA deploy, Newspaper integration or scoring authorization.

## Actual 2023–2025 KYI entrants: accepted result

Run [#2209](https://github.com/yukki0113/GPT/issues/2209) / [40433677343](https://github.com/yukki0113/GPT/actions/runs/40433677343) PASS; report `output/kyi_2023_2025_coverage.json`, source commit `e37557723f28487a1f4b0c5a5cde723219fd0dc6`.

| KYI archive year | entry rows | unique horse IDs | BRDB matched | all 3 names | sire and BMS codes mapped | selected profiles newer than year-end |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 47,672 | 11,720 | 11,720 (100%) | 11,720 | 11,720 | 6,841 |
| 2024 | 47,181 | 11,786 | 11,786 (100%) | 11,786 | 11,783 | 6,835 |
| 2025 | 47,884 | 11,930 | 11,822 (99.0947%) | 11,822 | 11,822 | 0 |

**Key discrepancy:** 2025 KYI has **108 distinct horse IDs absent from BRDB**; these were invisible from a UKC-only denominator. The initial diagnostic stored the first 100 sorted IDs only, so detailed source investigation needs a separate bounded export of *all* 108 IDs plus their key-level appearance patterns and snapshot provenance. Do not assume those 108 are malformed or ineligible; first compare KYI identity semantics and actual UKC source coverage. 2024 has 3 source-lineage-mapping misses despite full horse-ID join.

The report is a verified research result for **KYI annual archive entries**, not proof of race result existence or retrospective as-of-safe feature availability. Full-year 2025 master coverage cannot be described as 100%. The 2026 actual population remains unverified.

**Next steps:** isolate 108 IDs with earliest/latest KYI `race_key_raw` and horse_name samples (diagnostics only, not fallback), cross-check all UKC years and archived profile records, then extend the entry audit across 2016–2025. Preserve the current generation and PWA.
