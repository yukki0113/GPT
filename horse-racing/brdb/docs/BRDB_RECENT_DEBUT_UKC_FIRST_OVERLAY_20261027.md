# BRDB 新馬・未収録馬の段階的補完 — 2026-10-27

Status: 2026 PACI RAW UKC VERIFIED / READ-ONLY RESEARCH OVERLAY BUILDER IMPLEMENTED
No BRDB CURRENT promotion, PWA/Newspaper publication, or historical backtest cutover.

## Findings (observed raw, not inferred)

- 2025 KYI actual-entry audit had 11,930 distinct horse IDs, of which 108 were absent from 1999–2025 UKC (see Issues #2209, #2210).
- Canonical Google Drive PACI folder: `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`. Direct listing yielded **91 PACI26*.zip files**, through 2026-10-25. All 91 downloaded and validated; each ZIP has a `UKC26*.txt` member, with **39,543 valid 290-byte records** in aggregate.
- Matched on **exact 8-character registered horse ID**, not name: **104/108** have real 2026 UKC rows. Horse names matched 2025 KYI for all 104. **4/108** still missing, with exact IDs:
  - `23100951` ネバールックバック
  - `23104223` テクノラッシュ
  - `23104728` タマモレイメイ
  - `23104976` ディル
- Observed recovered fraction: 96.296%; no authority to claim these recovered records existed by their 2025 race dates.
- As a *2026-source-backed* research coverage scenario, adding 104 to the prior 11,822 matched KYI horse IDs gives 11,926 / 11,930 = 99.9665% **now available**, not historically as-of 2025. Four remain without parent facts.

## Design decision: UKC-first, provisional-only-when-needed

Don't fabricate parent ancestry for missing current debut runners. The priority order is:
1. Check the latest date-stamped UKC member already enclosed in authenticated PACI; parse with the project's official `jrdb_ukc` offsets.
2. Use same `horse_id` to construct an isolated **SOURCE_VERIFIED_2026_UKC** overlay with father/mother/BMS, birth year and official sire/BMS lineage codes, source ZIP+member and data_date.
3. If no UKC observation is available, allow **PROVISIONAL_ID_ONLY** from KYI (registered ID, horse name and entry evidence). Parent fields are UNKNOWN, not zero, and never filled from name similarity alone.
4. Only when another independently sourced parent fact is available may that row gain `PROVISIONAL_PARENT_SOURCE` field-level evidence. For grandparent matching, require exact guarded parent identity; CANDIDATE ancestry is not queryable as confirmed blood presence.
5. Never rewrite the existing immutable pedigree parquet or `BRDB CURRENT` pointer as part of this flow; Reader overlay is a separate versioned feature.

## Research artifact builder

`horse-racing/brdb/src/build_brdb_recent_ukc_recovery_overlay.py` accepts:
```
python horse-racing/brdb/src/build_brdb_recent_ukc_recovery_overlay.py \
  --paci-dir <read-only directory containing 2026 PACI*.zip> \
  --missing-json <previous KYI-vs-UKC identity audit> \
  --output-json <new research artifact>
```
Output includes 91 source ZIP SHA-256 receipts, exact observed UKC profile, chosen latest observation date, name-difference list, incomplete ID_ONLY records, and explicit `historical_asof_verified=false`. Duplicate same-date divergent records are rejected. No writes to source, CURRENT or Drive.

## Reconciliation when additional UKC arrives

Use exact `horse_id` as key; preserve all prior provisional and source receipts, compare field-by-field:
- `SAME` -> promote fields only when new source meets required timestamp/schema gate.
- `DIFF_PARENT` / `DIFF_LINEAGE` / `DIFF_BIRTH` / `DIFF_IDENTITY` -> manual review; record old/new/source and **never** silently replace.
- `STILL_MISSING` -> keep provisional and UNKNOWN parent facts.
- `SOURCE_DATE_LATER_THAN_RACE` -> cannot be used for contemporaneous 2025-backtest features without separate historical source proof.

A later UKC snapshot can provide factual pedigree to **current** research, but its timestamp alone cannot prove what was available for a previous race. Do not use latest 2026 row as 2025 race-day feature without a dated 2025 source or verified invariant methodology.

## Follow-on execution gates

1. Add/verify deterministic unit tests of single-authority UKC extraction, same-date collision fail-closed, four ID-only records and source receipts.
2. Re-run this recovery overlay whenever new PACI/UKC archives arrive (immutable dated generation / checksum, not overwriting older artifacts); compare old vs new coverage.
3. Verify parent codes and source profile birth-year consistency on 104 recovered horses; map official lineage via `lineage_code_master_v0_1.csv`. Confirm whether 2026 KYI race entrants not covered by 1999–2025 UKC have independent 2026 UKC records.
4. For remaining four, inspect other licensed current-data sources without guessing names, parentage, country or age. Never infer father/mother from KYI name.
5. Define a separate read-only Reader projection merging stable 27-year generation with exactly-keyed current UKC overlay, including state and `as_of` metadata. No PWA or production cutover until tests and user approval.
6. Continue 2016–2025 race-year join and historic-as-of audit before backtests, then approved region-root taxonomy and ancestor-presence search (Storm Cat/Halo).

No requirement to finish every ancestor before supporting 2026 new-race lineage.
