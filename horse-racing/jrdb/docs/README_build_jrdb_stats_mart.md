# JRDB Stats Mart Builder v1.1

`build_jrdb_stats_mart.py` creates compact yearly pre-aggregated statistics from one or more non-overlapping Analysis Lite v1.1 shards.

Stats Mart is a cache/acceleration layer. Analysis Lite remains the flexible condition-query source.

## v1.1 correction

The old mart `condition_code` inherited the ambiguous Analysis v1.0 field and represented race condition/class, not actual track condition.

v1.1 uses:

- `track_condition_code` from SED actual track condition
- `frame_no` for frame statistics

`race_condition_code` remains available in Analysis Lite for flexible filtering but is not added to the default mart grain to avoid unnecessary dimension explosion.

## Initial marts

### `mart_sire_yearly`

Grain:

- year
- venue_code
- track_type
- distance
- track_condition_code
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

The same course/time/track-condition grain with `jockey_name` instead of `sire_name`.

### `mart_frame_yearly`

The same grain with `frame_no` instead of sire/jockey.

Fixed windows such as "last 5 years" and "last 10 years" are not stored. They are derived by summing yearly rows.

## Run

```bash
python src/build_jrdb_stats_mart.py \
  --analysis ./jrdb_analysis_2016_2025.sqlite \
  --db ./jrdb_stats_mart_2016_2025.sqlite
```

Multiple non-overlapping year shards may also be supplied. The builder rejects overlapping years to avoid accidental double counting.

## Return-rate derivation

For 100-yen unit betting aggregation:

```text
win_return_rate   = win_payout_sum   / (starts * 100)
place_return_rate = place_payout_sum / (starts * 100)
```

Do not pre-store a fixed-window return rate.

## Validation history

### v1.0 2025 pilot

- sire rows: 21,281
- jockey rows: 19,329
- SQLite: ~5.2 MiB
- integrity_check: ok

### v1.1 corrected 2016-2025 pilot

Built from the corrected ten-year Analysis Lite v1.1:

- sire rows: **194,656**
- jockey rows: **155,118**
- frame rows: **38,151**
- SQLite: **52,518,912 bytes (~50.09 MiB)**
- integrity_check: **ok**

Measured build-source aggregation timings in the test runtime:

- sire yearly aggregation: ~1.09 s
- jockey yearly aggregation: ~0.99 s
- frame yearly aggregation: ~0.68 s

Representative ten-year Tokyo turf 1600m / good-family condition / sire query against the completed mart: **~1.61 ms**.

This confirms that the yearly mart remains comfortably below the remote connector ceiling and materially accelerates frequent aggregate queries.

## Design rule

Do not add dimensions to every mart merely because Analysis Lite contains them. Add a mart only for demonstrated frequent query patterns; otherwise query Analysis Lite directly. This keeps yearly marts useful without creating a combinatorial row explosion.
