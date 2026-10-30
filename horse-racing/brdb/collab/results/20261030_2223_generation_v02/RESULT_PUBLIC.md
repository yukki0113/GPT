# Issue #2223 — full daily research generation v0.2

Status: full build, actual-cohort audit and deterministic rebuild PASS. PR is ready for review after artifact readback verification.

Generation: `5279af0bd8226cde`; source code commit: `8cce021ff02f548870a3b79e11fd7f92e7ea9610`.
Master: **132,652 unique profiles** = 128,754 annual + 104 preserved daily + 3,794 additional daily.

Inputs: 27 annual ZIPs and 91 PACI ZIPs, SHA-pinned and fully processed. KYI scope is 2026-01-04–2026-10-25, 10,680 horses / 39,543 declared entries. Actual-start/cancellation status and intraday publication time are unverified.

| Metric | Horses | Declared entries |
|---|---:|---:|
| Static exact ID join | 10,680/10,680 (100.000000%) | 39,543/39,543 (100.000000%) |
| Sire/dam/BMS names | 10,680/10,680 (100.000000%) | 39,543/39,543 (100.000000%) |
| Sire official lineage mapped | 10,680/10,680 (100.000000%) | 39,543/39,543 (100.000000%) |
| BMS official lineage mapped | 10,680/10,680 (100.000000%) | 39,543/39,543 (100.000000%) |

The static 100% values above were measured against the generated Parquet and explicit research Reader; they are no longer a potential estimate.

| Static canonical ID resolution | Horses | Entries |
|---|---:|---:|
| sire | 7,543/10,680 (70.627341%) | 28,164/39,543 (71.223731%) |
| dam | 8,068/10,680 (75.543071%) | 30,215/39,543 (76.410490%) |
| broodmare_sire | 5,716/10,680 (53.520599%) | 21,222/39,543 (53.668159%) |

Unresolved/ambiguous/conflicting IDs remain UNKNOWN. No name rescue is used. All per-role UNKNOWN counts, rates and as-of rates are in summary_public.json.

| Max sire/dam ancestor generation | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---:|---:|---:|---:|---:|---:|
| Fixed KYI horses | 845 | 697 | 5356 | 3614 | 168 | 0 |

Race-date-safe entries: **33,029/39,543 (83.526794%)**, #2220 prediction 33,029, difference 0. Annual profiles contribute 29,131 safe entries, preserved daily profiles 104, additional daily profiles 3,794. Earliest-scanned-entry-safe horse count is 7,975/10,680 (74.672285%). The latest-only Reader hides a profile before its selected observation date; earlier raw history is not reconstructed.

Regression: all 128,754 annual facts and 104 old daily facts are exact; annual and old-daily parent-relation differences are both 0. Previous selected-source differences are 0. Rebuild generation ID and all 22 generation-file bytes match.

History: 39,543 original daily records retained; 0 daily quarantined; 0 same-latest-date conflicts. All 8 known annual sentinel-date records remain excluded. There are 191 daily semantic histories with changes; fields include owner/sex/symbol and one sire-name history. Full source rows/hashes and changed fields are in the private artifact. Annual-vs-daily review differences: 535 IDs, of which 218 differ in basic fact fields (sex_code only). These daily values do not overwrite the annual master.

Validation: 14 focused tests PASS; all 3,898 added profiles queried singly and in batch with equal facts; each is hidden the day before its selected source. All 104 real legacy profiles pass single/batch compatibility; 19 real pedigree projections exercise resolved/alias/conflict cases. All 39,543 daily source records were independently checked against their raw ZIP/member/line hashes. CSV reaggregation matches JSON; future-profile exposure is 0.

The full generation, 3,898-row audit, 10,680-horse and 39,543-entry audits, semantic/difference histories, complete input/output manifests, private request and reproduction logs are in the approved Drive artifact. Detailed private raw-input inventories were rejected for public GitHub publication by automatic approval review; GitHub retains aggregate output metadata and checksums.

Execution: local managed runtime (Python 3.12.14, DuckDB 1.1.3, PyArrow 25.0.1), no Actions run claimed. No CURRENT, production consumer or legacy builder/Reader is changed.
