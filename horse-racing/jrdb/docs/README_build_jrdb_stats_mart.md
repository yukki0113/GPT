# JRDB Stats Mart Builder v1

`build_jrdb_stats_mart.py` creates compact yearly pre-aggregated statistics from one or more non-overlapping Analysis Lite shards.

The Stats Mart is a cache/acceleration layer. Analysis Lite remains the flexible condition-query source.

## Initial marts

### `mart_sire_yearly`

Grain:

- year
- venue_code
- track_type
- distance
- condition_code
- sire_name

Measures:

- starts
- wins
- seconds
- thirds
- top3
- win_payout_sum
- place_payout_sum

### `mart_jockey_yearly`

The same course/time grain with `jockey_name` instead of `sire_name`.

Fixed windows such as "last 5 years" and "last 10 years" are not stored. They are derived by summing yearly rows.

## Run

```bash
python src/build_jrdb_stats_mart.py \
  --analysis ./jrdb_analysis_2021_2025.sqlite \
  --db ./jrdb_stats_mart.sqlite
```

Multiple non-overlapping year shards may be supplied:

```bash
python src/build_jrdb_stats_mart.py \
  --analysis ./jrdb_analysis_2016_2020.sqlite ./jrdb_analysis_2021_2025.sqlite \
  --db ./jrdb_stats_mart_2016_2025.sqlite
```

The builder rejects overlapping years to avoid accidental double counting.

## Return-rate derivation

For 100-yen unit betting aggregation, derive from stored sums:

```text
win_return_rate   = win_payout_sum   / (starts * 100)
place_return_rate = place_payout_sum / (starts * 100)
```

Do not pre-store a fixed-window return rate.

## 2025 pilot

Built from the 2025 Analysis Lite PoC:

- sire mart rows: 21,281
- jockey mart rows: 19,329
- SQLite size: 5,464,064 bytes (~5.2 MiB)
- `PRAGMA integrity_check`: `ok`
- representative sire aggregation query: under 1 ms in the test runtime

The representative venue `05` / track type `1` / distance `1600` sire query reproduced the corresponding Analysis Lite starts/wins/top3/payout sums.

## Next validation

1. Build Stats Mart from the accepted 2021-2025 Analysis Lite.
2. Verify aggregate equality against direct Analysis queries.
3. Add full-history yearly marts once production Analysis shard boundaries are fixed.
4. Add further marts only when justified by real query patterns; avoid dimension explosion.
