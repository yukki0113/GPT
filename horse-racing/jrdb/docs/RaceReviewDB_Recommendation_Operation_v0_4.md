# RaceReviewDB Recommendation Operation v0.4

Status: OPERATIONAL CANDIDATE  
Date: 2026-10-14  
Supersedes: `RaceReviewDB_Recommendation_Operation_v0_3.md`

## 1. Purpose

RRDB v0.4 keeps the four v0.3 prior-run signals unchanged and adds one independent
Horse Course Fit signal:

`COURSE_PROFILE_FIT`

The new lane is based on the frozen Horse Course Fit research artifact and the
current target course profile. It does not replace or retune the v0.3 signals.

## 2. Recommendation contract

Current contract version:

`rrdb-recommendation-signals-v0.4`

Operational signals:

1. `TIME_CLASS_PLUS1`
2. `FRONT_SURVIVE_GAP05`
3. `REAR_HIGH_LAST3F90`
4. `HV02_Q85_Q90`
5. `COURSE_PROFILE_FIT`

The first four retain their v0.3 definitions and thresholds.

## 3. COURSE_PROFILE_FIT

A target horse matches only when both the target course and the horse-fit evidence
satisfy the fixed contract.

### Target course gate

The target race must resolve from PACI BAC through canonical Course Identity /
CourseMaster and satisfy:

```text
course_size_class = LARGE
final_straight_bucket = LONG
```

`LONG` uses the existing research boundary:

```text
final_straight_m >= 450
```

Current physical validity must cover the target race date.

### Horse-fit gate

The same horse and target surface must have both ABSOLUTE fit rows:

```text
COURSE_SIZE = LARGE
FINAL_STRAIGHT_BUCKET = LONG
```

For both rows:

```text
sample_count >= 4
shrunk_delta >= 0.10
confidence >= 0.50
as_of_date <= target_race_date
```

If multiple snapshots exist, use the latest eligible `as_of_date`.

These thresholds are fixed from the primary forward-evaluation screen. They are
not tightened to the higher-return D15 band after observing ROI.

## 4. Evidence basis

The frozen 2026-01-01 Horse Course Fit snapshot was evaluated prospectively
against 2026 results through 2026-10-12.

For the primary fixed gate and excluding horses already matched by RRDB v0.3,
the combined LARGE + LONG profile produced:

```text
N = 76
win rate = 11.84%
top3 rate = 28.95%
win ROI = 130.1%
place ROI = 114.5%
```

The purpose of v0.4 is to expose this independent course-profile evidence in
forward operation. This is not a claim that the historical ROI is guaranteed to
persist.

## 5. PWA / Newspaper comment

Reader-facing prose is fixed to:

`大箱コースで好走傾向。`

Do not expose `LARGE`, `LONG`, thresholds, fit statistics, or internal signal
IDs in the Newspaper/PWA comment.

If this signal coexists with another RRDB signal, append the phrase after the
existing v0.3 prose.

## 6. Grade policy

Unchanged from v0.3:

- S/A grades remain disabled.
- Signal count is not a strength score.
- COURSE_PROFILE_FIT does not automatically outrank an existing RRDB signal.
- Internal fit strength may be retained for audit and RaceNote evidence.

## 7. Required inputs for future-PACI reverse lookup

v0.4 reverse lookup requires:

1. target-date PACI ZIP
2. validated `RaceReviewDB_CURRENT.zip`
3. extracted Horse Course Fit artifact root containing exactly:
   - `research/candidate_fit_view.parquet`
   - `course_master/course_master_seed_v0_1.jsonl`
   - `course_master/course_geometry_configuration_v0_1.jsonl`

Course Fit is a required v0.4 input. Missing or ambiguous Course Fit inputs must
fail closed; do not silently fall back to v0.3.

## 8. Canonical command

```bash
python horse-racing/jrdb/src/jrdb_recommendation_reverse.py \
  --race-date YYYY-MM-DD \
  --paci-zip /tmp/rrdb/input/PACIYYMMDD.zip \
  --current-zip /tmp/rrdb/input/RaceReviewDB_CURRENT.zip \
  --course-fit-root /tmp/rrdb/input/course-fit \
  --work-root /tmp/rrdb/work \
  --output-json /tmp/rrdb/output/YYYYMMDD_RRDB_v0_4_reverse.json
```

Newspaper/PWA handoff remains:

```bash
python horse-racing/jrdb/src/build_rrdb_newspaper_handoff.py \
  --reverse-json /tmp/rrdb/output/YYYYMMDD_RRDB_v0_4_reverse.json \
  --output-csv /tmp/rrdb/output/YYYYMMDD_RRDB_v0_4_PWA_handoff.csv
```

The handoff takes the recommendation contract version from reverse JSON and
therefore emits v0.4 provenance without a separate hard-coded version change.

## 9. Fail-closed rules

Do not emit COURSE_PROFILE_FIT when any of the following applies:

- target BAC row missing;
- target course identity unresolved;
- target physical validity is outside the verified period;
- target course is not both LARGE and LONG;
- no paired LARGE + LONG horse fit exists;
- either fit row fails sample, delta, or confidence threshold;
- fit snapshot is later than the target date;
- Course Fit artifact files are missing or ambiguous.

Existing v0.3 signal evaluation continues independently when prior-run history is
available. A horse with no prior run inside the v0.3 730-day window may still
match COURSE_PROFILE_FIT if the Course Fit contract itself is satisfied.

## 10. Ownership

Canonical code and contract:

GitHub `main`.

Operational RRDB source:

stable Drive `RaceReviewDB_CURRENT.zip`.

Horse Course Fit source:

the validated Horse Course Fit v0.1 artifact generated with explicit as-of date,
three-year rolling history, and physical-validity checks.

RRDB v0.4 does not mutate the Horse Course Fit research artifact.
