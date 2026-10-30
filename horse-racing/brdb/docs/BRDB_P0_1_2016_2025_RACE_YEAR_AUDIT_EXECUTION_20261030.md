# BRDB P0-1 — 2016–2025 KYI race-year coverage/as-of audit execution specification

Status: IMPLEMENTATION PREPARATION / NOT AN AUDIT RESULT  
Date: 2026-10-30  
Scope: Research-only. No CURRENT promotion, PWA, Newspaper, RaceNote or Blood Review v0.1 changes.

## Goal
Measure, by **race year** (2016 through 2025), exact JRDB KYI horse-ID pedigree coverage and evidence-supported historical availability using BRDB research generation `5279af0bd8226cde`. Keep 2026's fixed 91-day cohort as a separate existing benchmark.

## Confirmed implementation constraints
- `src/audit_race_year_pedigree.py` is intentionally 2026/91-PACI scoped. It validates `PACI26*.zip`, fixed 2026 dates and 91 unique files. Do **not** simply change literals and reinterpret its historical as-of calculations.
- Parse KYI and BAC via existing `horse-racing/jrdb/src/jrdb_raw.py`; use canonical horse ID (blood registration number) and race key.
- Reuse BRDB research Reader and `tools/data-storage/` for Parquet/DuckDB; do not duplicate parsers or create a new data engine.
- Research v0.2 static coverage, research v0.3 2026 daily history and v0.4 historical relations are different claims. Annual source/archive year, actual race year and horse birth year are not interchangeable.

## Input preflight (fail closed)
1. Inspect latest main BRDB README / CONTEXT / WORKFLOW, JRDB current docs and data-storage README.
2. Resolve **2016–2025 KYI/BAC** raw source inventories by canonical Drive location and exact expected filenames. Search miss alone is not missing-data evidence.
3. Resolve approved BRDB immutable generation, manifest, generation ID, and pinned SHA from canonical private Drive artifact. Validate output contents.
4. Capture all input SHA/size and exact supported date periods. Never publish restricted raw records or individual proprietary data.
5. Confirm whether SED actual starter identifiers/cancellation semantics can be reused from JRDB Historical Warehouse for **actual starts**. Until verified, report KYI *declarations*, not actual starts.

## Calculation contract
Compute separately, per year:
- `kyi_declarations_raw`, `kyi_declarations_deduplicated`, `kyi_distinct_horses`, `kyi_races`; and `actual_starts` ONLY if a verified canonical post-race source is joined.
- `horse_id_joined_static`; names `sire`, `dam`, `broodmare_sire` present; official sire and BMS lineage codes present **and** mapped; report counts and denominator.
- Historical profile status: `AS_OF_VERIFIED`, `AS_OF_UNVERIFIED`, `NOT_AVAILABLE`, `CONFLICT` (or explicit equivalent Reader statuses). No latest-profile data may silently become historical fact.
- Parent canonical-ID resolution separately by sire/dam/BMS, `UNKNOWN` separately from `FALSE`; ancestor maximum observable depth 0–5; these are diagnostics, not acceptance gates.
- Keep unique-horse and per-entry denominators separate; don't mix declaration vs starter denominators; report source range and incompleteness.

## Historical temporal guard
- `profile_data_date <= race_date` is necessary but not proof the record was available before the race; track the observation/archive date and its evidence.
- Historical UKC annual **selected snapshot** is not a full history. Where trustworthy contemporaneous source observation is unavailable, mark `AS_OF_UNVERIFIED` and withhold historical-profile claims.
- Same-day observed inputs lack intraday publication-time proof; record that limitation.
- Never use SED/result/payouts as predictors for a race being evaluated.

## Investigations requiring explicit reconciliation
1. 2016–2022: first complete coverage audit, year by year.
2. 2023–2024: reproduce legacy KYI coverage with latest generation. In 2024 inspect the 3 unmapped official lineage names/codes; distinguish code present from mapping present.
3. 2025: re-evaluate legacy 108 unmatched horses; explicitly count how many of the 104 later daily additions join the 2025 KYI cohort, without assuming all 108 are resolved.
4. 2026: keep the existing fixed 91-day audit separate from full-calendar year claims.

## Deliverables
- Code: general year-window auditor using the existing JRDB parser and BRDB Reader, with deterministic config/CLI and no hardcoded 2026/91-day assumptions.
- Tests: KYI/BAC duplicate/conflict, missing file, unsupported date, profile timing, missing lineage mapping, UNKNOWN parent, no future leakage, static-vs-as-of distinctions, invalid SHA and 2025 legacy unmatched regression.
- Artifacts: annual aggregate CSV/JSON, missing-reason distribution, safe provenance-only per-entry audit in private Drive, source SHA-pinned manifest, read-only report.
- Acceptance: all ten years explicitly categorized as `PASS`, `PARTIAL`, or `BLOCKED` with denominator and provenance; no implied 100% where a period/source is missing.
- Next gate P0-2 only after year-level inventory and data-quality exceptions are reviewed.

## Operational routing
Read-only inventory = A. Normal code/tests/docs = B (GitHub direct commit, preserving concurrent changes). Deterministic evaluation = C if source data materializable. Use D / Actions only for actual heavy, native or formally audited workloads after preflight; do not create a generic Issue solely for editing source.
