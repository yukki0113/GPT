# RaceNote Trend Scope Implementation — 2026-09-28

## Status

Implemented foundation for PACI-driven Named / Local / Base Trend sampling.

## Normal operation target

```text
PACI acquired
  ↓
request RaceNote for mm/dd
  ↓
BAC race facts are normalized
  ↓
Trend scopes are derived automatically
  ↓
historical Analysis Lite v1.4 is queried
  ↓
Named / Local / Base Trend blocks are attached
  ↓
RaceNote-Evidence-1.0
```

No manual input of venue/distance/course rail should be required in normal operation.

## PACI/BAC fields now preserved

From the target BAC / race key:
- venue
- meeting number
- meeting day
- race number
- race name
- surface
- distance
- class
- grade
- turn/layout
- turf course rail code:
  - 1 = A
  - 2 = A1
  - 3 = A2
  - 4 = B
  - 5 = C
  - 6 = D

RaceNote also preserves the corresponding raw source codes for deterministic historical matching.

## Historical requirement

Existing Analysis Lite v1.3 does not store:
- meeting number
- meeting day
- race name
- course rail code

Therefore `jrdb_analysis_schema_v1_4.sql` and
`build_jrdb_analysis_from_raw_v1_4.py` were added.

A one-time historical rebuild to Analysis Lite v1.4 is required before the new Trend aggregator can execute against the full archive.

Existing v1.3 remains untouched.

## Trend scopes

### Named

Strict sample:
- same race name
- same venue
- same surface
- same distance
- compatible same class/grade
- same course rail where available

A same-name race held under materially different conditions does not enter the strict sample.

A second support level may drop only the rail match while preserving the other named-race conditions.

### Local

For ordinary/class races, class is preserved through all fallback levels.

Initial scope:
- same venue
- same surface
- same distance
- same class band
- same month
- same course rail
- nearby meeting day (+/- 2)

Support levels broaden in this order:
1. drop meeting-day proximity
2. drop month
3. drop course rail

Class is not dropped for ordinary/class races.

For OP/graded targets, the Local support class scope is OP+:
- G1
- G2
- G3
- other graded
- L
- OP

This is the intended support pool for new/changed graded races where the named-race sample is sparse.

### Base

Broad comparator:
- same venue
- same surface
- same distance
- all classes

Base is context only and does not overwrite Named or Local.

## Aggregation output

The implementation reuses the PWA Fact Lite aggregation idea:

```text
filters
→ parameterized WHERE
→ GROUP BY axis
→ starts / 1st / 2nd / 3rd
→ win payout sum / place payout sum
→ descriptive JSON
```

Each row contains:
- starts
- first
- second
- third
- out
- compact finish record
- win rate
- top3 rate
- win ROI
- place ROI

Reader target:

`(1-0-2-8) / 単回155% / 複回118%`

## Initial axes

- popularity
- frame
- running style
- age
- sex
- sire
- jockey
- previous distance change
- previous class

No axis receives an automatic forecast priority.

## Files

Target PACI normalization:
- `horse-racing/jrdb/src/racenote_jrdb.py`

Historical BAC projection:
- `horse-racing/jrdb/src/jrdb_analysis_raw_adapter.py`

Historical schema:
- `horse-racing/jrdb/schema/jrdb_analysis_schema_v1_4.sql`

Historical builder:
- `horse-racing/jrdb/src/build_jrdb_analysis_from_raw_v1_4.py`

Trend aggregator:
- `horse-racing/jrdb/racenote/src/racenote_trend_aggregator.py`

Tests:
- `horse-racing/jrdb/tests/test_racenote_trend_aggregator.py`

## Remaining operational step

Rebuild the historical Analysis archive with v1.4.

After the v1.4 archive exists, run the trend aggregator against an actual RaceNote and inspect:
- Named sample selection,
- Local fallback selection,
- Base comparison,
- ROI/display values.

Forecast logic remains out of scope.
