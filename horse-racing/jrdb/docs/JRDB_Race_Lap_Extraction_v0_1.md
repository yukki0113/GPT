# JRDB Race Lap Extraction v0.1

Status: CURRENT  
Established: 2026-10-14

## 1. Purpose

JRDB ordinary post-race SED delivery already contains the race-level SRBYYMMDD.txt member.
This contract defines how SRB data is exposed for analysis and prediction research without introducing another upstream acquisition route.

SEDYYMMDD.zip -> SEDYYMMDD.txt (horse-level result / race distance) + SRBYYMMDD.txt (race-level lap / corner / bias / comment).

SRB fixed-width parse -> distance-aware lap normalization using SED race distance -> consumer/research features.

No separate SRB download or additional subscription is required for the verified 2026 delivery shape.

## 2. SRB fixed-width facts

The supplied JRDB SRB specification defines:

- file name: SRB + YYMMDD + .txt
- bundled in the ordinary SED archive
- fixed-width text
- record length: 852 bytes including CR/LF; 850-byte body
- race key: bytes 1-8
- leader-based lap times: 18 slots, 3 bytes each, bytes 9-62
- unit: tenths of a second
- corner-position strings: bytes 63-318
- pace-up remaining-furlong field: bytes 319-320
- track-bias fields: bytes 321-342
- race comment: bytes 343-842

src/jrdb_raw.py owns those fixed offsets. It returns all 18 lap slots, preserving unused trailing slots as None. It does not infer distance-aware segments.

## 3. Distance-aware normalization

src/jrdb_race_lap.py joins SRB to SED by the canonical 8-byte race key and uses SED distance_m to expand populated lap slots.

The non-200m remainder is the first measured segment:

- 1400m: 7 x 200m
- 1700m: 100m + 8 x 200m
- 1150m: 150m + 5 x 200m

The normalizer validates:

1. populated SRB lap slots have no internal blank;
2. lap count equals ceil(distance_m / 200);
3. segment distances sum exactly to the SED race distance;
4. SED records for the same race key do not disagree on distance.

Races with no SRB lap values are omitted from segment output rather than inventing values. This is intentional for unsupported/non-applicable race types.

## 4. Normalized row contract

One output row represents one measured race segment. Required fields are race_key_raw, distance_m, segment_no, start_m, end_m, segment_distance_m, lap_sec, source_archive, source_sed_member, and source_srb_member.

The row is a race-level observation. It is the time recorded for the leading horse through the relevant measurement interval, not an individual horse's 200m sectional.

## 5. CLI

python src/jrdb_race_lap.py SED261012.zip --output race_laps.jsonl

When --output is omitted, JSONL is written to stdout.

## 6. Verification evidence

Two real 2026 deliveries were inspected:

- SED260905.zip: SED + SRB, SRB body length 850, 36 race rows
- SED261012.zip: SED + SRB, SRB body length 850, 24 race rows

Representative official-JRA cross-checks:

- 2026-09-05 Sapporo 1R, dirt 1700m: 7.0, 10.6, 11.9, 12.7, 12.3, 12.3, 12.4, 12.8, 13.2
- 2026-10-12 Tokyo 1R, dirt 1400m: 12.5, 11.0, 12.1, 13.2, 12.8, 11.8, 12.1

The SRB values matched the JRA published race lap sequence exactly in both checks, including the initial 100m segment for the 1700m race.

## 7. Prediction boundary

SRB is post-race data. For RaceNote/forecast use it may describe only completed historical races strictly before the target race's as-of boundary.

Do not use the target race's SRB in pre-race prediction. Do not reinterpret race-level leader laps as the target horse's individual sectionals.

Feature engineering, pace classification, and any scoring/calibration remain consumer/research responsibilities and are not part of the Common Raw Reader.
