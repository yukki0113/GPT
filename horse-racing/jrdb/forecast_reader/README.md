# Forecast Reader

The CLI supports deterministic plan/run execution and emits PASS, PARTIAL,
NEED_INPUT or BLOCKED according to verified source coverage. The Kyoto 菊花賞 2026 case has passed real-data acceptance through an immutable
pre-race Analysis manifest and accepted Warehouse conditions; see the report.

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
codes. The configured S0-S4 policy targets ten **races**, allows multiple races
per year, stops at 10 or after S4, and keeps venue, surface, distance, course
and class fixed. No web enrichment or automatic distance-band expansion.
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


## Operational acceptance for explicitly missing JRDB records

The Reader's technical `status` remains **PASS** or **PARTIAL** according to the
canonical evidence contract. Never rewrite a PARTIAL result to PASS. For a
user-approved missing-data policy, call `operational_acceptance.assess(evidence,
source_audit)` on the **validated, published evidence JSONs**.

- `ACCEPTED`: strict Reader PASS and all operational safeguards pass.
- `ACCEPTED_WITH_MISSING`: strict Reader PARTIAL, but sample years, target
  runner joins, sampling gate A, JRDB source provenance, and target-result
  exclusion pass. Preserve exact valid/missing axis counts and missing previous
  joins. Calculate statistical groups using only usable rows; never manufacture
  the missing observation.
- `REJECTED`: source/contract issues, incomplete target runner data, missing
  statistical years, unverified sampling, forbidden target results, or a Reader
  status other than PASS/PARTIAL.

**No Web search or external enrichment is an alternative data source.** Allowed
inputs are the verified JRDB PACI/Analysis/Warehouse records. The evaluator
does not query/download any input and never changes the canonical Evidence Bundle.

2026-10-31 Kyoto11R ファンタジーS acceptance observation:
historical S0 7 Kyoto races / 94 starts; 93 previous-run joins with 1 missing,
target 11/11 previous-run joins, 8 axes measured, Reader technical
`PARTIAL`. This is an example of `ACCEPTED_WITH_MISSING` when the full
audited source and result contracts pass; it is **not** a Reader PASS.

## S0-S4 sampling operation (2026-11)

Historical population is the previous ten calendar years. Select up to **10 races**
(not ten years and not ten horses) in priority order, without duplicate race keys:

| Stage | Seasonal window | Matching requirements |
| --- | --- | --- |
| S0 | Any date | Same normalized name and all seven conditions |
| S1 | ±21 days | Name unrestricted; all seven conditions |
| S2 | ±21 days | As S1, but weight_rule may differ |
| S3 | ±21 days | As S2, but eligibility may also differ |
| S4 | ±42 days | Revisit the S1→S3 matching tiers in order of fewer condition mismatches, then closest seasonal date |

The seven conditions are venue, surface, distance, race_class, eligibility,
course and weight_rule. **venue, surface, distance, race_class and course never
change.** Unknown condition values cannot qualify for relaxation. There is no
±70-day search, no more-than-42-day widening, no automatic distance-band
extension, and no fallback to website data. Multiple races from one year may
qualify. Each stage records the candidate decisions, selected keys, added_count,
 and cumulative_count. The output also provides target_races,
total_selected, and sample_shortfall. A sample shortage after S4 is reported,
not silently treated as ten. Exact and supplemental trends remain separate.

For operational acceptance, never equate sample_shortfall with unknown data.
An S0+S1+S2+S3+S4 pool smaller than ten is an explicit sampling limitation;
existing PASS/PARTIAL source-integrity gates still apply.
