# Forecast Reader (work in progress)

The CLI supports deterministic plan/run execution and emits PASS, PARTIAL,
NEED_INPUT or BLOCKED according to verified source coverage. Real-data acceptance
is limited by unavailable as-of historical condition evidence; see the report.

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

## Integrated execution

The CLI now connects verified sources through BAC resolution, historical sampling,
eight-axis aggregation, KYI→ZED (or declared immutable Raw SED archives), descriptive
runner comparisons, contract validation and atomic bundle publication. Normalized
fixture/export history is accepted as `jrdb.history.normalized` (forecast-history.v1).
Canonical Analysis archives are unpacked with the common helper and only the
manifest-declared prior-year partitions are hashed and queried with data_storage.
They require a verified `jrdb.historical_conditions` export (forecast-conditions.v1,
races array) to supply unavailable eligibility, class and weight conditions.
Absent coverage returns NEED_INPUT/UNKNOWN_CONDITION. Do not infer those fields
from grade alone. See the evidence contract for source metadata fields.

For local dependency preflight use the common `data_storage check-deps`. If the
pinned dependency repair is blocked, follow the existing dynamic Drive runbook and
DATA_STORAGE_FALLBACK contract. The fallback step's repository entrypoint is
`horse-racing/jrdb/forecast_reader/forecast_reader_runner.py` with argv for request,
inputs and output-dir. All staged source paths and hashes must match the same
manifest; inspect Actions audit and all four JSON files before accepting results.
Do not publish proprietary inputs in the request or artifact. No new shell entrypoint
or credential mechanism is introduced. Live Actions fallback has not been rerun for
this reader.

### Immutable historical-generation route

`jrdb.analysis.current` may point to a previously published `jrdb_analysis`
manifest JSON, not only the mutable current archive. Stage its exact relative
asset paths below the manifest directory; the reader validates every historical
partition SHA/size/row count/year. Its native observation must bind the old
manifest, rather than assigning a pre-race timestamp to a newer current archive.

`jrdb.historical_conditions` can now point directly to the accepted final
Historical Warehouse manifest. Supply `asset_paths` mapping its relative asset
paths to local, connector-materialized files. Required ten-year BAC assets are
checked against that manifest. Declared SED assets may supply missing BAC race
conditions using only the shared parser's condition fields; contradictions between
horse rows fail closed. No new Raw byte parser or external client is introduced.

The real Kyoto 菊花賞 2026 case reached CLI PASS using the 2026-10-18 Analysis
manifest and accepted BAC/SED assets. See final acceptance in IMPLEMENTATION_REPORT.
The older live NEED_INPUT notes in this README describe the initial current-only
route, not the reconstructed immutable-generation route.
