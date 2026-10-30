# Forecast Reader (work in progress)

This implementation is incomplete. `--run` fails closed; it cannot yet produce a
policy-compliant evidence bundle. See docs/IMPLEMENTATION_REPORT.md for gaps.

```
python horse-racing/jrdb/forecast_reader/forecast_reader_runner.py --request request.json --plan --output-dir OUTPUT
python horse-racing/jrdb/forecast_reader/forecast_reader_runner.py --request request.json --run --inputs inputs.json --output-dir OUTPUT
```

The request uses `forecast-reader-request.v1`, protocol `human_statistics_v1`,
10 history years, pre_race/historical_backtest, target date/venue/race_no,
timezone-aware as_of, and detail.previous_runs=1.

Input manifest `sources` maps `jrdb.paci.daily` and `jrdb.analysis.current` to
local path, sha256, size_bytes; PACI also requires snapshot_at. Acquire through
native Drive using the registered folder and exact expected filename. A keyword
search returning zero results is not evidence that data is absent. Follow
`tools/data-storage/docs/DYNAMIC_DRIVE_MANIFEST_RUNBOOK.md` for before/after
metadata and SHA pinning. Post-race current archives do not prove as-of provenance.

Sampling consumes verified normalized conditions only; it does not infer JRDB
codes. S1/S2/S3 windows and one representative per year are proposed defaults.
Previous runs use the common Parser and only KYI-linked ZED records before the
target date. No forecast marks or wagers are produced.

Tests: `python -m pytest horse-racing/jrdb/forecast_reader/tests -q`.
