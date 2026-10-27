# Issue #2218 — 2026 KYI / BRDB audit

Scope: 20260104–20261025; 91/91 PACI ZIPs, 10,680 unique horses, 39,543 declared entries, 2,874 races.

KYI declarations are counted. Actual-start/cancellation status is UNKNOWN. Dates after 2026-10-25 are outside scope.

| Dataset | Static horses | Static entries | Safe at first entry (horses) | Safe race-date entries |
|---|---:|---:|---:|---:|
| BASE | 6,782 / 10,680 (63.5019%) | 29,131 / 39,543 (73.6692%) | 6,782 / 10,680 (63.5019%) | 29,131 / 39,543 (73.6692%) |
| RESEARCH | 6,886 / 10,680 (64.4757%) | 29,527 / 39,543 (74.6706%) | 6,802 / 10,680 (63.6891%) | 29,235 / 39,543 (73.9322%) |
| CURRENT | 6,782 / 10,680 (63.5019%) | 29,131 / 39,543 (73.6692%) | 6,782 / 10,680 (63.5019%) | 29,131 / 39,543 (73.6692%) |

All joined profiles have sire, dam, broodmare-sire names and both official lineage codes mapped to the snapshot master.

| Dataset | Sire ID (horses) | Dam ID (horses) | BMS ID (horses) |
|---|---:|---:|---:|
| BASE | 4,802 / 10,680 (44.9625%) | 5,128 / 10,680 (48.0150%) | 3,528 / 10,680 (33.0337%) |
| RESEARCH | 4,879 / 10,680 (45.6835%) | 5,209 / 10,680 (48.7734%) | 3,588 / 10,680 (33.5955%) |
| CURRENT | 4,505 / 10,680 (42.1816%) | 4,771 / 10,680 (44.6723%) | 630 / 10,680 (5.8989%) |

Parent-ID UNKNOWN includes absent profiles and unresolved/ambiguous/conflicting candidates. Names are never treated as canonical IDs.

| Dataset | Static ancestor max depth 0 / 1 / 2 / 3 / 4 / 5 (horses) |
|---|---|
| BASE | 4413 / 507 / 3612 / 2108 / 40 / 0 |
| RESEARCH | 4316 / 510 / 3665 / 2149 / 40 / 0 |
| CURRENT | 4620 / 4477 / 1580 / 3 / 0 / 0 |

Daily additions contribute 104 horses and 396 entries; 104 of those entries are safe at race date. The four previously unmatched IDs have no entries in this cohort.

As-of uses the selected latest-profile source observation date, not first sighting. Historical reconstruction is unavailable. Annual cohort observations were matched back to original UKC records; ancestor profiles are bounded by verified pre-2026 annual members. Every as-of graph edge requires both child and parent profiles to be available. The check is date inclusive; within-day publication times are unverified.

Files: horses.csv (all horses × 3 snapshots), entries.csv (all entries × 3), missing_horses.csv, generation_differences.csv, daily_104_contribution.csv, monthly.json, reader_as_of_checks.csv, annual_selected_observations.csv, input inventories, summary.json and SHA-pinned manifest.json.

Execution: full local managed-runtime audit; no GitHub Actions run is claimed. No production publication is part of this audit.
