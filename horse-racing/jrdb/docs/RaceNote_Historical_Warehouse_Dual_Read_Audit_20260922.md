# RaceNote Historical Warehouse Phase 1 Dual-Read Audit

- Accepted generation: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- Current contract: `GPT/horse-racing/10_warehouse/jrdb/v1/current.json`
- Status: **PASS**

| Target date | Races | Horses | Previous keys | Raw vs Warehouse gates |
| --- | ---: | ---: | ---: | --- |
| 2018-12-28 | 24 | 368 | 1,184 (2017–2018) | PASS |
| 2025-12-28 | 24 | 356 | 1,160 (2024–2025) | PASS |

Both targets passed row count, primary key, schema, NULL/blank semantics, all logical values, canonical semantic bundle hash, representative CHA/CYB and ZED/ZKB joins, repeated-read determinism, and idempotence. The Raw side uses BAC/KYI/CHA/CYB/ZED/ZKB; `SED/SKB` are not compatible substitutes for RaceNote's PACI result/note inputs.

## 2010 boundary scan

The frozen 2010 KYI archive contains 50,105 rows and 65,835 references to 2009 results; it also contains 2,811 references to 2005–2008. Because the accepted Warehouse begins in 2010, those result rows are intentionally outside coverage. The reader fails closed and permits only the explicit, provenance-recorded Raw boundary fallback.

## Non-changes

No accepted Parquet, Warehouse pointer, PACI daily flow, RaceNote schema/version, or existing Archive/release was changed by this audit.
