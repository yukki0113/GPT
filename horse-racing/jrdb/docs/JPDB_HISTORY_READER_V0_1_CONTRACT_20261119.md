# JPDB historical rider Reader v0.1 — read-only candidate (2026-11-19)

Status: **P1 candidate Reader implementation**; does not connect to RaceNote or change Warehouse, Course Master, RRDB, BRDB, or current daily operations.

## Source and temporal contract

- Repository module: `src/jpdb_history_reader.py`, class `JPDBHistoryReader`, method `rider_history(target_date, jockey_code)`.
- Read-only accepted source: `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`, exactly three immutable annual 2023, 2024, 2025 SED Parquet partitions (47,672 / 47,181 / 47,884 rows). Every byte is SHA-256 and length verified from pinned `config/public_drive/jpdb_p0_current_2023_2025_readonly_v0_1.json` *before DuckDB opens the data*. Optional additional `expected_manifest_sha256` protects caller's explicit binding. All three partitions are required, including when requesting an earlier date; do not silently change the cohort.
- Target date must be between **2023-01-01 and 2025-12-31**, inclusive. Source has no 2026 SED; `2026-...` fails closed until a separately accepted incremental design is implemented.
- Entry: exact five-digit `jockey_code` string, nonzero; no implicit name matching, leading-zero truncation, or injected SQL.
- Event-time window: **`[max(2023-01-01, target_date - 3 calendar years), target_date)`**. Date D is exclusive, including any races with earlier post times on D. Parameterized SQL filters at the source before grouping, without scanning future rows into Python outputs.
- SED historical availability: user-approved assumed prior-day policy `JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1`. Final accepted annual SED is a proxy for prior-day-available results, not proof of source publication time. `release_time_attested=false`, `historical_revision_attested=false` and `prediction_safe_strict_asof=false` accompany responses. No target entry is resolved; `target_entry_source=NOT_RESOLVED_BY_THIS_READER`.

## Output

Reader returns a dictionary (no free-form query or per-race records):

- `schema_version=jpdb-history-reader-v0.1`, `target_date`, `jockey_code`, `history_from_inclusive`, `history_to_exclusive`, `lookback_calendar_years`.
- Policy and trace: `asof_policy`, `availability_basis`, `source_generation`, `source_manifest_sha256`, immutable `source_assets` (per-year SHA, size and expected rows), `population_filter_id=JPDB_FLAT_NORMAL_FINISHERS_DIAGNOSTIC_V1`.
- `sample_status=NO_HISTORY|HAS_HISTORY`, `all_flat` and `by_surface.turf|dirt`.
- Each aggregate provides `entries`, `normal_finishes`, `nonstarters`, `dnf`, `demoted`, `wins`, `top3`, `earliest_date`, `latest_date`, `normal_win_rate`, `normal_top3_rate`.
- Both rates have **normal finishers as denominator**, return `null` when denominator is zero, and should *not* be described as approved race-start win/place percentages. The diagnostic population excludes obstacles and requires `abnormal_code in ('0','')` for normal finishers/wins/top3; `1/2` counted as nonstarters, `3` as DNF, `5` as demoted. These definitions are versioned diagnostics, not an accepted final official denominator or a causal jockey-skill score.
- No history returns zero counts and null rates rather than invented defaults. There is no minimum sample-size threshold or confidence label at v0.1.

## CLI

```bash
python horse-racing/jrdb/src/jpdb_history_reader.py \
  --input-root /secure/verified/parquet/root \
  --manifest horse-racing/jrdb/config/public_drive/jpdb_p0_current_2023_2025_readonly_v0_1.json \
  --target-date 2025-11-15 --jockey-code 01234 \
  --output /secure/results/rider.json
```

CLI uses the same Reader class; output defaults to stdout if omitted. It refuses to overwrite an existing destination. `--expected-manifest-sha256` can pin an externally reviewed manifest. Results containing a selected jockey's history must remain in an approved private execution/output boundary, not copied to a public GitHub audit/Actions log.

## Boundaries and open work

1. Initial Reader supports **historical 2023–2025 only**, no 2026 YTD or future years, no data refresh or CURRENT publisher.
2. Exposes only simple descriptive counts and per-surface splits. No course, venue, class, distance, pace, runner adjustment, opponent quality, win expectation or condition-level scoring. They require separate P2/P3 research specification.
3. Does not resolve the target race's scheduled jockey. A RaceNote caller must separately validate its input KYI/PACI and label historical `FINAL_KYI_PROXY` when contemporaneous pre-race snapshot is unavailable. Neither this Reader nor post-race SED may override the target's predicted jockey.
4. Does not turn 731 final-KYI/SED differences into official substitutions; no rider-change label is inferred.
5. Before production RaceNote handoff, freeze the population denominator, document support/uncertainty, test target roster integration, and approve P4 separately.

Read-only focused regression: `tests/test_jpdb_history_reader.py` (synthetic). Private-source aggregate-only smoke: `tools/jpdb_history_reader_smoke.py` compares Reader values with independent parameterized DuckDB aggregates for twelve historical jockey codes, but **does not expose any jockey IDs in public artifacts**.

This candidate is intended for modular, explicit date-rider calls as requested, not auto-promoted into RaceNote.
