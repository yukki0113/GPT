# JRDB Analysis Raw vs Warehouse Dual-Read Audit — 2026-09-21

## Decision

**PASS — Historical Analysis input is Warehouse-standard for 2010–2025.**

The dedicated current generation `jrdb_normalized_warehouse_v1_2010_2025_g20260921` was read without changing any Warehouse asset, Warehouse pointer, Analysis generation, or Analysis current pointer. The Raw-direct path used the corresponding dated members from frozen annual BAC/KYI/SED/CYB/UKC archives.

For every case below, the audit verified row count, canonical primary key, the unchanged 34-column Analysis schema, NULL/blank profile, every logical value, canonical row hash, representative aggregate query, and repeated Warehouse-read idempotence. All checks passed.

| Target date | Rows | Canonical row hash |
|---|---:|---|
| 2010-01-05 | 366 | `c8259d9475f8189f55b94a70d605ebb574cc9e2a2cc949a776db5a6d153bf87e` |
| 2010-06-12 | 385 | `1f55186434d1662b8eab357c9f338902659ade49459d048e80d397e6373574fe` |
| 2010-12-26 | 538 | `6401dbe773960b6bdae60604c1b384f05a74fe3a668e2403996f69a997b03e6f` |
| 2018-01-06 | 354 | `c0f37e6b212a8f9768aee64e9d8d06b0eb64438bda1c3be4e19dcf17145e6b33` |
| 2018-07-01 | 490 | `b58d28d4929df47c3d6535bfd8d29d8f87c121cc26f0794f15f6782e7221666c` |
| 2025-01-05 | 377 | `701f7c34a4e9ca1be0955048e790e7ba1124c0d3515331be2f6825e20bffea04` |
| 2025-12-28 | 356 | `03a1cb863f5bc8323d9be33f58f91181041e7badb4f0b89a8ff5f8e44fe3d0eb` |

An independent target-date replacement test ran Warehouse input twice for 2010-01-05: first insert 366 rows; second replacement found and replaced the same 366 rows; final fact canonical hash was unchanged. The 2026 Warehouse guard also rejected a Warehouse request and directed callers to PACI/Raw.

## Operating split

- **2010–2025 historical rebuild/backfill:** dedicated JRDB Warehouse `current.json` → DuckDB reader → Analysis.
- **2026 current daily update:** PACI + SED / Raw direct → Analysis.

Raw direct for 2010–2025 remains available only with explicit `--allow-historical-raw` for rollback or audit. The Warehouse reader rejects a year absent from its accepted manifest coverage; it cannot accidentally consume 2026.
