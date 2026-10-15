# RaceReviewDB Recommendation Operation v0.5

Status: OPERATIONAL  
Date: 2026-10-15  
Supersedes: `RaceReviewDB_Recommendation_Operation_v0_4.md`

## 1. Purpose

RRDB v0.5 keeps the v0.4 Course Profile Fit lane and all existing non-rear
signal thresholds unchanged.

The only recommendation-rule change is a refinement of:

`REAR_HIGH_LAST3F90`

The signal now requires canonical JRDB SRB leader-lap evidence confirming that
the source race was in the strongest 20% late-loaded / rear-friendly race-shape
tail for the relevant surface and broad distance bucket.

`FRONT_SURVIVE_GAP05` is intentionally unchanged after a separate sustained
pressure study failed to improve the 2024-2025 exploration and 2026 forward
results consistently.

## 2. Recommendation contract

Current contract version:

`rrdb-recommendation-signals-v0.5`

Operational signals:

1. `TIME_CLASS_PLUS1`
2. `FRONT_SURVIVE_GAP05`
3. `REAR_HIGH_LAST3F90` — refined by SRB Q20
4. `HV02_Q85_Q90`
5. `COURSE_PROFILE_FIT`

S/A grades remain disabled.

## 3. REAR_HIGH_LAST3F90 v0.5 definition

The existing horse-position / pace conditions remain:

```text
pace_balance_percentile <= 30
corner4_frontness <= 0.40
last3f_speed_percentile >= 90
```

v0.5 additionally requires the source race to have available canonical RaceLap
evidence and:

```text
early_late_delta_sec <= frozen_q20(surface_code × distance_bucket)
```

`early_late_delta_sec` is the canonical common RaceLap shape value. It is
leader-based race context, not individual-horse sectionals.

### Distance buckets

```text
SPRINT   <= 1400m
MILE     1500-1800m
MIDDLE   1900-2200m
STAYING  >= 2300m
```

### Frozen 2024-2025 Q20 thresholds

| Surface | Bucket | Reference races | Q20 early_late_delta_sec |
|---|---|---:|---:|
| Turf | SPRINT | 981 | -0.40 |
| Turf | MILE | 1,273 | -2.10 |
| Turf | MIDDLE | 838 | -2.26 |
| Turf | STAYING | 246 | -2.90 |
| Dirt | SPRINT | 1,449 | +1.20 |
| Dirt | MILE | 1,633 | +0.14 |
| Dirt | MIDDLE | 203 | +0.96 |

Dirt STAYING is excluded because the 2024-2025 reference group contained only
39 races, below the fixed minimum of 100.

The machine-readable frozen contract is:

`config/recommendation/rear_srb_q20_v0_1.json`

The operational threshold must not be recomputed from future data.

## 4. Evidence basis

Exploration used next-race outcomes in 2024-2025. The Q20 rule was then applied
unchanged to 2026-01-01 through 2026-10-12.

### 2024-2025 exploration

```text
Existing REAR_BASE
N = 1,495
win rate = 8.76%
top3 rate = 26.89%
win ROI = 54.6%
place ROI = 79.2%

REAR + SRB Q20
N = 717
win rate = 10.60%
top3 rate = 29.71%
win ROI = 68.4%
place ROI = 73.5%
```

### 2026 forward

```text
Existing REAR_BASE
N = 712
win rate = 10.67%
top3 rate = 26.97%
win ROI = 71.7%
place ROI = 64.6%

REAR + SRB Q20
N = 334
win rate = 12.87%
top3 rate = 29.64%
win ROI = 72.1%
place ROI = 67.4%
```

The win rate, top3 rate, and canonical next-run performance all improved in the
same direction in exploration and forward periods.

## 5. FRONT_SURVIVE_GAP05

No v0.5 change.

The following SRB refinements were tested against the existing FRONT signal:

- stronger early/late front-load;
- mid-race mean pressure;
- absence of a slow middle segment;
- low pre-final-3F lap dispersion;
- sustained pressure plus late deceleration.

None produced a consistent 2024-2025 and 2026 improvement. The v0.4 definition
therefore remains canonical.

## 6. RaceLap operational input

v0.5 reverse lookup requires an immutable RaceLap Parquet accepted by the
common `RaceLapReader` contract:

```text
--race-lap-parquet /path/to/race_lap.parquet
```

The Parquet must contain the relevant source races. The reverse layer verifies
the RaceLap dataset on open through `RaceLapStore`.

For an individual source run:

- missing race row -> REAR signal fails closed;
- `NO_LAPS` -> REAR signal fails closed;
- unavailable `early_late_delta_sec` -> REAR signal fails closed;
- unsupported surface × distance bucket -> REAR signal fails closed.

These cases do **not** disable the other four RRDB signals.

Race key/date mismatch between RRDB source-run identity and RaceLap evidence is
treated as an integrity error and stops the reverse lookup.

## 7. PWA / Newspaper comment

The reader-facing REAR comment remains:

`後傾ラップ戦も後方から上位の上がりは使った。`

This wording now has stronger provenance: both the existing pace-balance
condition and actual canonical leader-lap Q20 evidence must agree that the
source race was strongly late-loaded.

Internal thresholds, percentiles, and SRB values are not exposed in the PWA
comment.

The Course Profile comment remains:

`大箱コースで好走傾向。`

## 8. Required inputs for future-PACI reverse lookup

v0.5 reverse lookup requires:

1. target-date PACI ZIP;
2. validated `RaceReviewDB_CURRENT.zip`;
3. extracted Horse Course Fit artifact root;
4. immutable RaceLap Parquet covering relevant source races.

Canonical command:

```bash
python horse-racing/jrdb/src/jrdb_recommendation_reverse.py \
  --race-date YYYY-MM-DD \
  --paci-zip /tmp/rrdb/input/PACIYYMMDD.zip \
  --current-zip /tmp/rrdb/input/RaceReviewDB_CURRENT.zip \
  --course-fit-root /tmp/rrdb/input/course-fit \
  --race-lap-parquet /tmp/rrdb/input/race_lap.parquet \
  --work-root /tmp/rrdb/work \
  --output-json /tmp/rrdb/output/YYYYMMDD_RRDB_v0_5_reverse.json
```

Newspaper/PWA handoff remains unchanged:

```bash
python horse-racing/jrdb/src/build_rrdb_newspaper_handoff.py \
  --reverse-json /tmp/rrdb/output/YYYYMMDD_RRDB_v0_5_reverse.json \
  --output-csv /tmp/rrdb/output/YYYYMMDD_RRDB_v0_5_PWA_handoff.csv
```

## 9. Fail-closed policy

The v0.5 REAR signal requires all of the following:

- prior source run exists inside the 730-day operational lookback;
- existing REAR pace / position / last3F thresholds pass;
- canonical RaceLap row exists for that exact source race;
- coverage status is `AVAILABLE`;
- `early_late_delta_sec` is available;
- a frozen Q20 threshold exists for the source surface × distance bucket;
- `early_late_delta_sec <= q20`.

No future target-race lap is used. SRB evidence is source-race post-race evidence
only.

## 10. Ownership

Canonical code/config/docs:

GitHub `main`.

Operational RRDB source:

stable `RaceReviewDB_CURRENT.zip`.

Course Fit source:

validated Horse Course Fit v0.1 artifact.

RaceLap source:

canonical common JRDB RaceLap dataset / `RaceLapReader` contract.

RRDB v0.5 does not modify the common RaceLap parsing or shape logic.
