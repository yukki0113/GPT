# JRDB Analysis Lite horse-history index benchmark — 2026-09-07

## Purpose

RaceNote v1.0 history enrichment repeatedly reads prior JRA rows from Analysis Lite using:

```sql
WHERE horse_id=? AND race_date<?
```

and, for compact older runs:

```sql
WHERE horse_id=? AND race_date<?
ORDER BY race_date DESC, race_no DESC
LIMIT ?
```

This note records the empirical reason for adding `ix_analysis_horse_history` to Analysis Lite schema v1.2. The logical schema and RaceNote output contract are unchanged.

## Source artifacts

Benchmark used the project operational artifacts current on 2026-09-07:

- Analysis Lite: `jrdb_analysis_2016_2026YTD_20260823_v1_2.sqlite`
- Stats Mart: `jrdb_stats_mart_2016_2026YTD_20260823_v1_1.sqlite`
- Analysis rows: 513,512
- baseline Analysis size: 197,492,736 bytes

The benchmark was local SQLite execution after the artifacts were materialized. Drive transfer time is therefore excluded.

## Baseline query plan

Before the new index, SQLite planned a horse-history aggregate as:

```text
SEARCH fact_entry_result_lite USING INDEX ix_analysis_date (race_date<?)
```

The horse identifier was not part of the chosen index. RaceNote therefore scanned the rows before the target date and filtered by `horse_id` repeatedly.

## Added index

```sql
CREATE INDEX ix_analysis_horse_history
ON fact_entry_result_lite(horse_id, race_date DESC, race_no DESC);
```

After creation, both the aggregate and newest-history query used `ix_analysis_horse_history` with `horse_id=? AND race_date<?`.

## RaceNote-shaped benchmark

The benchmark reproduces the SQL access pattern in `racenote_history_engine.py`, including target entry lookup, older runs, horse historical profile, sire/jockey exact and distance-range statistics, frame statistics, Analysis target-year YTD and Stats Mart prior-year queries.

### 2024-12-28 Nakayama 11R, 2000m, 18 runners

- engine-equivalent queries: 303
- baseline: 10.7868 s
- indexed: 0.0736 s
- improvement: about 146x

Baseline dominant categories:

- horse historical summaries, 90 queries: 7.5648 s
- older runs, 18 queries: 3.1177 s

Indexed:

- horse historical summaries, 90 queries: 0.0012 s
- older runs, 18 queries: 0.0016 s

The 304 captured query results including benchmark setup were identical before and after the index. SHA-256 of the serialized query result set was identical:

```text
fa2c3c830ff152c4fe322fcc2fa3ee67628d02f18a18511fead8d7ebf74cb3e4
```

### Distance-overlap worst cases

At 1400m and 1800m RaceNote intentionally evaluates two overlapping distance ranges, increasing the engine-equivalent query count to 409.

| race | distance | queries | baseline | indexed |
|---|---:|---:|---:|---:|
| 2024-12-22 Kyoto 3R | 1400m | 409 | 11.9180 s | 0.3362 s |
| 2024-12-28 Kyoto 7R | 1800m | 409 | 10.2665 s | 0.1613 s |

## Storage and update cost

Creating the index on the 513,512-row Analysis DB:

- build time: about 0.57 s
- size increase: 15,446,016 bytes (about 14.7 MiB)
- `PRAGMA integrity_check`: `ok`

A delete-and-reinsert simulation for all 385 rows on 2024-12-28 measured:

- baseline: 39.8 ms
- indexed: 64.5 ms
- additional maintenance cost: about 25 ms

This cost is negligible for the daily incremental update path compared with the RaceNote read-side benefit.

## Production E2E verification

The indexed Analysis candidate was published to Drive as a ZIP transport and tested through the normal `[RACENOTE_REQUEST]` GitHub Actions path.

Target:

- date: 2024-12-28
- venue: Nakayama
- race: 11R
- backend: `racenote_archive`
- runners: 18

Baseline:

- Issue: #452
- run: `34072355676`
- Analysis: original unindexed v1.2 SQLite
- RaceNote request step: about 7.94 s

Indexed candidate:

- Issue: #453
- run: `34087811996`
- Analysis storage ZIP: 60,569,456 bytes
- Analysis payload SQLite: 212,938,752 bytes
- RaceNote request step: about 5.90 s
- workflow status: success
- warning count: 0

The final RaceNote JSON was byte-for-byte identical:

- filename: `race_bundle_20241228_中山11R.json`
- bytes: 264,682 both
- SHA-256: `b9e82e8db7d7b514dbf9bde962317d9d7487b93d192fba4dc2e23f645435e46f`

The nested `request_manifest.json` was also byte-for-byte identical:

- bytes: 2,324 both
- SHA-256: `a3d927a60a0028d6492590a5d24ab7ff634ef6c907fc107dc7793664dafbfb08`

The outer ZIP SHA differs because ZIP metadata timestamps differ; the payload contents do not.

Cold transfer also became smaller because the accepted Analysis artifact is transported as ZIP rather than raw SQLite. The measured Actions download stage was about 12.38 s on the baseline run and about 9.97 s on the indexed run. Runner region/network variance means this transfer-time difference is supporting evidence rather than a strict performance guarantee.

## Production promotion

After the E2E equality gate passed, Google Drive live manifest `JRDB/manifest/jrdb_store_manifest_v1.json` was updated so `jrdb://analysis/current` points to the indexed ZIP artifact.

Accepted artifact revision:

```text
historyidx-20260907
```

Storage:

- size: 60,569,456 bytes
- SHA-256: `0c0d604e331e9afc6ba9c8489b993915f817b41bdb3303a2a8a0fb53dfbbe023`

Payload:

- size: 212,938,752 bytes
- SHA-256: `25e9cb29f0d957f484d4f2daec7a8656a9a7ef0435dde09338f31c61be91457a`
- `PRAGMA integrity_check`: `ok`
- rows: 513,512

The original unindexed Analysis file remains in Drive as a rollback artifact. The live logical locator, not deletion or in-place replacement of that old file, performs the production switch.

## Regression gate

`tests/test_racenote_analysis_history_index.py` pins:

1. presence of `ix_analysis_horse_history` in Analysis v1.2 schema,
2. SQLite planner use for horse-history aggregate queries,
3. planner use for ordered `older_runs` retrieval,
4. unchanged descending history order.

`.github/workflows/jrdb_common_reader_tests.yml` watches both the Analysis schema and this test. After adding the regression to CI, run `34088419323` completed with conclusion `success`.

## Decision

Keep Analysis Lite logical schema version at **v1.2**. This is a physical access optimization only; no column, type, key, result semantic, as-of rule or RaceNote output contract changes.

Do not rewrite RaceNote history enrichment into a batch-query implementation solely for performance at this stage. The dedicated Analysis Lite index removes the measured bottleneck while keeping consumer logic and source responsibilities unchanged.

The production Drive artifact now contains this index. Future Analysis rebuilds using `jrdb_analysis_schema_v1_2.sql` receive it automatically.
