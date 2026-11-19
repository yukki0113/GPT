# JPDB P1.1 — CORE / batch historical jockey Reader v0.1

Date: 2026-11-19. **Status: separate P1.1 candidate implementation; not RaceNote P4 production approval.**

## Scope

The new `src/jpdb_performance_reader_v11.py` module provides `JPDBPerformanceReader(JPDBHistoryReader)` and `rider_histories(target_date=..., jockey_codes=[...])`. It **does not replace or change** the existing `jpdb_history_reader.py` and `rider_history()` contract. The inherited old method remains compatible.

- Source: SHA/size/annual count validated 2023–2025 accepted Warehouse SED. Exact five-digit jockey code strings (leading zeros kept). Parameterized DuckDB SQL and a single GROUP BY query for each of three fixed windows across all requested riders; no single-rider query per target horse. Duplicate codes and more than 64 requested codes are rejected rather than silently deduplicated.
- Source rows: flat only, `surface_code IN ('1','2')`; jockey from **past SED actual**, target entry source not resolved. `race_date < target_date` strictly. No same-day or future results. Policy `JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1` is an assumed historical prior-day available record, *not* a proven original publication version.
- Periods: `ROLLING_3Y` = last 3 calendar years (clamped to 2023-01-01), `RECENT_365D` and `RECENT_90D` = calendar date difference of exactly 365 and 90 days, respectively, also clamped to source start. Windows always include lower bound and exclude target date. Short windows are nested in long.
- Release: only reader API to an approved private runtime. Caller needs to supply authorized canonical input paths/manifest; CLI requires `--output` and never silently overwrites files. Per-jockey aggregate outputs are **not written to the public GitHub audit artifact**.

## Candidate result classes

**Population ID** `JPDB_FLAT_RIDE_START_V1_CANDIDATE`; deliberately different from v0.1 `JPDB_FLAT_NORMAL_FINISHERS_DIAGNOSTIC_V1`.

| Source SED abnormal code | Exclusively counted as | Start-denominator candidate |
|---|---|---|
| `0`, blank, and `1 <= finish <= field_size` | `normal_finishers`; add `wins`, `top2`, `top3` by finish | Yes |
| `0`, blank, invalid/missing finish or field size | `invalid_normal_finish` | No, review |
| `1` | `cancellations` | No |
| `2` | `exclusions` | No |
| `3` | `dnf` | Yes; no ordinary finish rank |
| `5` | `demotion_review` | Tentatively yes; result meaning unresolved |
| Other / NULL | `unknown_codes` | No, review |

Every flat entry belongs to exactly one of seven categories. The rule is checked via `sum(category counts) == entries`, including each surface and combined population. Invalid normal finish and unrecognized abnormal codes are **not treated as losses**. `actual_starts_candidate=normal_finishers+dnf+demotion_review` (an explicitly provisional count).

Rates:
- `normal_win_rate`, `normal_top2_rate`, `normal_top3_rate` use **normal finishers** as denominator, NULL on zero.
- `start_basis_win_rate_candidate` and `start_basis_top3_rate_candidate` are computed only when **all** `unknown_codes`, `invalid_normal_finish`, `demotion_review` equal zero and `actual_starts_candidate > 0`. They are otherwise NULL, with `start_rate_status=REVIEW_REQUIRED|NO_STARTS`; available values are labeled `CANDIDATE_ONLY`, *not officially accepted win rates*.
- `sample_support_status=NO_HISTORY` for zero rows, `INSUFFICIENT` for fewer than 30 starts, `DESCRIPTIVE_ONLY` at 30+; any unresolved count sets `REVIEW_REQUIRED` first. Threshold 30 is a design default for **descriptive convenience**, not statistical significance, ability, expected ROI, or a final P2 threshold.
- `source_generation`, `source_manifest_sha256`, `source_assets`, `asof_policy`, `target_date`, `population_filter_id` in the response. `target_entry_source=NOT_RESOLVED_BY_THIS_READER`, `historical_release_attested=false`, `strict_asof_certified=false` are preserved.

## API

```python
from jpdb_performance_reader_v11 import JPDBPerformanceReader

with JPDBPerformanceReader(
    input_root=verified_private_root,
    manifest=accepted_manifest_path,
    expected_manifest_sha256=known_manifest_sha256,
) as reader:
    # Multiple source IDs in one request. These are *illustrative* IDs.
    result = reader.rider_histories(
        target_date="2025-11-15",
        jockey_codes=["01234", "12345"],
    )
    rider = result["jockey_histories"]["01234"]
    last_365 = rider["windows"]["RECENT_365D"]["by_surface"]["turf"]
```

Return schema `jpdb-performance-reader-v1.1-candidate`. Three windows contain `all_flat`, `by_surface.turf`, `by_surface.dirt` with identical field definitions. `NO_HISTORY` returns 0 counts, NULL rates. Range is still 2023–2025; requesting 2026 fails closed.

## Verification and remaining gates

- Focused synthetic test: `tests/test_jpdb_performance_reader_v11.py`. Original compatibility test: `tests/test_jpdb_history_reader.py`.
- Actual-source audit: `tools/jpdb_p11_performance_smoke.py` uses 12 internally chosen real SED jockey IDs, independent SQL for raw classes/counts/wins, 2023 date boundary, and v0.1 API comparison. Public output contains only aggregate counts, no jockey IDs/rows.
- Original BAC/KYI and Course Master do not enter P1.1 CORE. Venue/distance/course and related qualities remain P2.
- Open P1.1: **real disposition of abnormal 5** and whether data supplies a complete/reliable official actual-start denominator. This implementation isolates uncertain records and holds **affected** rates. A 2023–2025 full-population audit is necessary before any final public rate agreement.
- P1.2 remains responsible for **2026 daily SED** and 2025/2026 boundary. P4 remains responsible for target KYI/PACI roster provenance and RaceNote handoff. The candidate must not alter RaceNote prediction, Freeze, results or scores.

The tool is deliberately useful for descriptive internal analysis without granting a predictive ability certification.
