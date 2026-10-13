# JRA Course Profile Master — CourseMaster Schema v0.1

Status: Phase 2 design frozen for Phase 3 initial master build  
Date: 2026-10-13

## 1. Purpose

`JRA_Course_Profile_Master` provides reusable, physically grounded JRA course identities and structural attributes for JRDB, RRDB, RaceNote, PWA/Newspaper, and future models.

The master intentionally excludes period-dependent performance tendencies such as pace bias, running-style win rate, draw bias, and last-3F importance. Those belong to `CourseStats`.

## 2. Phase 1 evidence incorporated

The accepted Historical Warehouse BAC audit for 2010–2025 found:

- 55,239 BAC rows, 55,215 latest distinct JRA races;
- 153 distinct `(venue_code, surface_code, distance_m)` base conditions;
- 433 observed `(venue, surface, distance, turn, layout, course_code)` combinations;
- 18,147 latest races with blank `course_code`;
- no undefined surface / turn / layout / course codes;
- 24 repeated `race_key_raw` values, with zero cases where the course-condition tuple changed across revisions;
- only five base conditions where `(turn_code, layout_code)` itself has multiple observed variants:
  - Niigata turf 2000m;
  - Tokyo obstacle 3300m;
  - Kyoto turf 1400m;
  - Kyoto turf 1600m;
  - Kyoto obstacle 3170m.

The audit proves that `course_code` (A/A1/A2/B/C/D) is unsuitable as a mandatory physical-course identity component. It remains source observation metadata.

## 3. Identity model

### 3.1 `course_key`

`course_key` is the stable physical/topological course identity used by downstream joins.

Logical identity:

```text
venue_code × surface_code × distance_m × layout_variant
```

`layout_variant` is a curated physical variant token, not a direct copy of JRDB `layout_code` or `course_code`.

Default value is `main` only when one physical layout is established. Simultaneous physically distinct layouts such as inner/outer receive separate identities.

Canonical display format:

```text
JRA:{venue_code}:{surface_token}:{distance_m}:{layout_variant}
```

where:

- `surface_token`: `T` turf, `D` dirt, `O` obstacle;
- `layout_variant`: lowercase stable token such as `main`, `inner`, `outer`, `straight`.

Examples after physical confirmation:

```text
JRA:04:T:2000:inner
JRA:04:T:2000:outer
JRA:08:T:1600:inner
JRA:08:T:1600:outer
```

The key must not embed a validity date or mutable descriptive value.

### 3.2 `course_version_id`

A structural renovation can change slope, straight length, start position, turn count, elevation profile, or other physical properties while downstream systems still need a stable conceptual `course_key`.

Therefore physical history is versioned separately:

```text
{course_key}:v001
{course_key}:v002
```

The effective dates live in `valid_from` / `valid_to_exclusive`; they are not encoded in the ID. Correcting an effective date therefore does not force a new identifier.

### 3.3 JRDB observation mapping

JRDB source fields are observations, not the master primary key:

```text
venue_code
surface_code
distance_m
turn_code
layout_code
course_code
```

`course_jrdb_mapping` resolves those observations to a `course_key` / optional `course_version_id` with a validity period and mapping status.

`course_code` is retained here so A/B/C/D observations remain auditable, but it is not part of CourseMaster uniqueness.

## 4. Tables

### 4.1 `course_master`

One row per stable physical course identity.

Required columns:

```text
course_key
venue_code
venue_name
surface_code
surface
distance_m
layout_variant
status
created_at
updated_at
```

`status`: `ACTIVE`, `HISTORICAL`, `PROVISIONAL`, `RETIRED`.

### 4.2 `course_version`

One row per structural version of a course.

Priority physical attributes from the requirements:

```text
turn_direction
turn_count
start_position
start_straight_m
first_corner_distance_m
final_straight_m
start_slope_flag
start_slope_type
final_straight_slope_flag
final_straight_slope_type
elevation_difference_m
elevation_profile
course_width_class
course_size_class
inner_outer_layout
```

Additional control columns:

```text
valid_from
valid_to_exclusive
version_status
physical_data_status
notes
```

`physical_data_status`: `CONFIRMED`, `PARTIAL`, `PROVISIONAL`, `UNKNOWN`.

No statistical performance metric is allowed in this table.

### 4.3 `course_jrdb_mapping`

Maps JRDB observations to physical identity.

```text
mapping_id
venue_code
surface_code
distance_m
turn_code
layout_code
course_code
course_key
course_version_id
valid_from
valid_to_exclusive
mapping_status
mapping_reason
```

`mapping_status`: `CONFIRMED`, `PROVISIONAL`, `UNRESOLVED`, `REJECTED`.

Rules:

1. Multiple `course_code` values may map to the same `course_key`.
2. Blank `course_code` is valid input and must not block resolution.
3. `layout_code` must not be assumed to represent a physical distinction without evidence.
4. `turn_code` is checked for consistency but is not copied blindly into key text.
5. unresolved or conflicting observations fail closed; they are not guessed into `main`.

### 4.4 `course_attribute_evidence`

Column-level provenance for physical values.

```text
evidence_id
course_version_id
attribute_name
attribute_value_text
source_kind
source_title
source_locator
retrieved_at
effective_from
effective_to_exclusive
evidence_status
notes
```

Preferred source order for physical attributes:

1. JRA official course information / official renovation announcement;
2. other authoritative primary source;
3. verified secondary source only when primary material is unavailable.

Do not encode qualitative impressions such as “front runners advantageous” as CourseMaster evidence. Such claims must be derived into CourseStats.

## 5. Temporal semantics

All validity ranges use half-open intervals:

```text
valid_from <= race_date < valid_to_exclusive
```

A NULL `valid_to_exclusive` means currently open-ended.

A race-to-course join is valid only if:

1. the JRDB observation maps to a `course_key`;
2. the race date falls inside the mapping validity range;
3. when a version is known, the date falls inside exactly one `course_version` range.

Overlapping active versions for the same `course_key` are invalid.

## 6. Phase 3 resolver policy

Resolution order:

```text
BAC latest accepted observation
  -> exact JRDB mapping candidate
  -> date validity check
  -> confirmed course_key
  -> course_version valid on race_date
```

`course_code` is used as an observation discriminator only if historical evidence demonstrates that it is required to select a physical identity. Otherwise several `course_code` rows should resolve to one identity.

The five Phase 1 multi `(turn, layout)` conditions require explicit Phase 3 physical verification before their mappings are frozen. Obstacle `layout_code=3/9` differences are especially not to be interpreted as distinct physical courses without evidence.

## 7. CourseStats boundary

The following remain outside CourseMaster:

- average first/last 3F and race time;
- pace profile / pace index distributions;
- running-style win/place rates;
- winner/top-3 4C position;
- last-3F percentile importance;
- draw win/place rates and adjusted draw advantage.

They will be built in Phase 4 keyed by `course_key` + aggregation period and, where necessary, `course_version_id`.

## 8. Acceptance gates for Phase 3

Phase 3 may populate a row as `CONFIRMED` only when:

- JRDB identity tuple is observed or an explicit historical-only course is documented;
- physical layout variant is supported by evidence;
- validity period is non-overlapping;
- every populated external physical attribute has at least one evidence record;
- unknown values remain NULL/UNKNOWN rather than inferred from reputation or race results.
