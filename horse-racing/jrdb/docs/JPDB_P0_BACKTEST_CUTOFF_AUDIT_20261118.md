# JPDB P0 — RaceNote-oriented date-cutoff retrospective audit, 2026-11-18

> **2026-11-19 JPDB policy update:** Historical SED release-time/late-revision attestation is **not a prerequisite** for the assumption-based JPDB backtest lane. For an outcome race date strictly before the target date, the accepted final SED is assumed available under `JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1`. See [approved simplified SED as-of policy](JPDB_P0_ASOF_SIMPLIFIED_POLICY_20261119.md). This is a modeling assumption, not proof of historical release timing. The audit findings and stricter provenance interpretation below remain the record of the original 2026-11-18 investigation; they are not silently relabeled. Target-day SED exclusion, target KYI caveats, population decisions, and separate RaceNote approval still apply.


**Gate:** `PASS_RETROSPECTIVE_CUTOFF_ONLY` (**NOT historical as-of certified**). Research audit, not a JPDB Reader, not a P1 implementation, and not wired to RaceNote.

## Evidence and reproducibility

- Exact accepted 2023–2025 SED Parquet from `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`, three annual SHA-pinned SED assets from `horse-racing/jrdb/config/public_drive/jpdb_p0_current_2023_2025_readonly_v0_1.json`. Runner authenticated no private Drive calls: public read-only fetch verified **9/9 input assets**.
- Deterministic P0 tool: `horse-racing/jrdb/tools/jpdb_p0_backtest_cutoff_audit.py`. Pinned execution source `96573652653e9b539010e78a7d66be9ef7794417` (subsequent commit `cbf2ed8dc276ace50d8975d364d70572884b1cd3` removes only an unreachable placeholder).
- Focused synthetic tests: `horse-racing/jrdb/tests/test_jpdb_p0_backtest_cutoff_audit.py`; **3/3 PASS**, including same-day and future exclusion, obstacles, nonstarter/DNF classification, empty 2023 boundary, malformed/out-of-scope dates.
- GitHub [Issue #2649](https://github.com/yukki0113/GPT/issues/2649), [Actions run 44273595770](https://github.com/yukki0113/GPT/actions/runs/44273595770), [artifact 14412799267](https://github.com/yukki0113/GPT/actions/runs/44273595770/artifacts/14412799267). Runner **PASS**, DuckDB `1.1.3`, PyArrow `25.0.1`; both deterministic steps exit `0`.
- Aggregate-only output: `output/jpdb_p0_cutoff_audit_2023_2025.json`, SHA-256 `d48740d92ab449df94420df5293ca0a52d517b2c71f202347fba9ffe2ed150e9`, 5,876 bytes. No per-jockey facts or licensed source rows exported.
- Source SHA verification inside auditor uses the exact SED Parquet byte sizes, SHA-256 and year cohort expected counts; independent public Drive transport receipt also verifies download.

## Actual date-effective cutoff results

3-calendar-year lookback is clamped to JPDB's approved start `2023-01-01`. The event-time interval is **`[max(2023-01-01, D - 3 years), D)`**. Obstacles (surface code 3) are excluded. Daily target date D is strictly exclusive; no same-day outcomes enter source rider history.

| Backtest target D | Prior flat SED entries | Distinct historical jockey codes | Normal finishers | Normal wins | Last included race day | Target-day-and-future flat entries excluded |
|---|---:|---:|---:|---:|---|---:|
| 2023-01-01 | 0 | 0 | 0 | 0 | — | 138,491 |
| 2024-01-01 | 46,212 | 187 | 45,902 | 3,332 | 2023-12-28 | 92,279 |
| 2025-01-01 | 92,008 | 226 | 91,339 | 6,665 | 2024-12-28 | 46,483 |
| 2025-11-15 | 132,089 | 248 | 131,133 | 9,564 | 2025-11-09 | 6,402 |
| 2025-12-13 | 135,776 | 254 | 134,795 | 9,819 | 2025-12-07 | 2,715 |

These values come from actual real annual SED SQL aggregates, not merely manifest totals. The selected source population has 138,491 **flat** SED entries in 2023–2025; total SED all surfaces is 142,737.

For 2025-11-15, the read-only diagnostic further classifies **503 nonstarters (`1/2`), 452 DNF (`3`), one demotion (`5`)** before D; these labels are *diagnostic only* and do not freeze the P1 official denominator. The tool checks every per-jockey tuple's aggregate invariants internally, but only exports aggregate validation counts.

## Important boundary: event time != source knowledge time

This proves a useful deterministic operation for a backtest: no SED *race event* dated D or later is allowed into the computed source history. It does **not** prove that the annual Warehouse's eventual SED version was available to an actual predictor at the historical time T. Historic PACI/KYI target-entry snapshot and pre-race publication time are still missing. JRDB also intentionally refreshes SED late after the meeting; revised results could differ from what was known earlier.

Therefore:

- `prediction_safe=false`, `as_of_certified=false`, `source_available_by_target_verified=false`, `actual_release_time_attested=false`.
- This P0 artifact is a research diagnostic; it must **not** be plugged into RaceNote's backtest predictor as historically certified. It is neither a production rider feature API nor an approval to start P1.
- For a future reviewed Reader, enforce **two clocks**: past race event date strictly before target D *and* source version proven `available_at <= prediction_time T`; independently prove target KYI/PACI was available by T. Fail closed when knowledge-time proof is absent, with no fallback to later final SED.
- An appropriately labeled retrospective-only research comparison is possible but must not be confused with genuine as-of backtest performance.

Full proposed materialization and RaceNote handoff: [JPDB_P0_BACKTEST_ASOF_MATERIALIZATION_DESIGN_20261118.md](JPDB_P0_BACKTEST_ASOF_MATERIALIZATION_DESIGN_20261118.md).

## P0 status

| Gate | Result |
|---|---|
| BAC/KYI/SED canonical 2023–2025 structural join | PASS |
| Course Master 2023–2025 flat identity / conservative epoch | PASS (physical fields PARTIAL) |
| Deterministic strict target-date cutoff / no future-race-event rows | **PASS** |
| Historical original source-version available-at replay | **OPEN / NOT ATTESTED** |
| Official rider-change resolution and denominators | OPEN |
| P1/production RaceNote integration | NOT AUTHORIZED |

**Overall P0 = REVIEW_REQUIRED.** Next investigation must retrieve original 2023–2025 PACI/KYI distribution/version evidence and contemporaneous SED first/late-finalization provenance, or formally limit claims to retrospective date-filtered analysis.
