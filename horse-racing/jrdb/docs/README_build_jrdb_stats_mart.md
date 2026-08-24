# JRDB Stats Mart Builder v1.1

`build_jrdb_stats_mart.py` creates compact yearly pre-aggregated statistics from one or more non-overlapping Analysis Lite shards.
`refresh_jrdb_stats_mart_year.py` refreshes only selected year partitions after in-season Analysis updates.

Stats Mart is a cache/acceleration layer. Analysis Lite remains the flexible condition-query source. Analysis v1.2 adds prev1 columns but does not change the mart grain, so Stats Mart v1.1 remains compatible.

## Mart grain

Default dimensions:

- year
- venue_code
- track_type
- distance
- track_condition_code
- sire / jockey / frame dimension

Default marts:

- `mart_sire_yearly` — mandatory
- `mart_jockey_yearly`
- `mart_frame_yearly`

Measures:

- starts
- wins
- seconds
- thirds
- top3
- win_payout_sum
- place_payout_sum

`race_condition_code` remains available in Analysis Lite but is intentionally not added to the default mart grain to avoid dimension explosion.

Fixed windows such as last 5/10 years are derived by summing yearly rows.

## Full build

```bash
python src/build_jrdb_stats_mart.py \
  --analysis ./jrdb_analysis_2016_2025.sqlite \
  --db ./jrdb_stats_mart_2016_2025.sqlite
```

Multiple non-overlapping Analysis shards may be supplied. Overlapping years are rejected.

## In-season year refresh

After completed dates are incrementally replaced/appended in Analysis Lite, refresh only the current year:

```bash
python src/refresh_jrdb_stats_mart_year.py \
  --analysis ./jrdb_analysis.sqlite \
  --mart ./jrdb_stats_mart.sqlite \
  --years 2026
```

The refresher recalculates the selected year from Analysis, deletes the old mart rows for that year, and inserts the recalculated rows inside a transaction. Historical years are untouched.

This is intentionally simpler and safer than attempting row-level mart deltas; a single current-year aggregation is small and fast.

## Return-rate derivation

For 100-yen unit betting aggregation:

```text
win_return_rate   = win_payout_sum   / (starts * 100)
place_return_rate = place_payout_sum / (starts * 100)
```

Do not pre-store fixed-window return rates.

## Validation

### Corrected 2016-2025 full mart

- sire rows: **194,656**
- jockey rows: **155,118**
- frame rows: **38,151**
- SQLite: **52,518,912 bytes (~50.09 MiB)**
- integrity_check: **ok**
- representative ten-year sire query: ~1.61 ms

### Current-year refresh regression

A copy of the validated 2016-2025 mart had year 2025 deleted/recalculated from Analysis v1.2.

Refreshed 2025 rows:

- sire: 19,360
- jockey: 14,681
- frame: 3,328
- integrity_check: `ok`

The refreshed database was compared against the original full-build mart across all three mart tables:

- sire differences: 0
- jockey differences: 0
- frame differences: 0

Therefore the current-year refresh path is equivalent to a full mart rebuild for the refreshed year.

## Production cadence

During the season:

```text
completed-date Raw
  -> Analysis incremental replacement
  -> refresh current year in Stats Mart
```

At year-end, rebuild the rolling ten-year Analysis window from Raw and then perform a clean full Stats Mart build.

## Design rule

Do not add dimensions to every mart merely because Analysis Lite contains them. Add marts only for demonstrated frequent query patterns; otherwise query Analysis Lite directly.
