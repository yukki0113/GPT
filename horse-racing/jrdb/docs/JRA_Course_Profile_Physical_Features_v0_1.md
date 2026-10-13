# JRA Course Profile — Physical Features Completion v0.1

Status: COMPLETED  
Date: 2026-10-13

## Purpose

This document completes the physical-feature fields required by RRDB horse-course-fit research without changing CourseStats semantics or RRDB v0.3.

The completion covers:

- `final_straight_slope_flag`
- `course_size_class`

The source of truth remains the current JRA course-profile config:

`config/course_profile/official_current_course_geometry_v0_1.json`

## Final-straight slope

`final_straight_slope_flag=true` means the current flat course has a material uphill section in the home/final straight before the finish.

`false` means no material uphill is documented in the final straight: flat or downhill/near-flat final sections are included here.

This is a current-course physical attribute, not a historical `course_version` claim.

### Current mapping

| venue | turf | dirt |
| --- | --- | --- |
| 01 Sapporo | false | false |
| 02 Hakodate | false | false |
| 03 Fukushima | true | true |
| 04 Niigata | false | false |
| 05 Tokyo | true | true |
| 06 Nakayama | true | true |
| 07 Chukyo | true | true |
| 08 Kyoto | false | false |
| 09 Hanshin | true | true |
| 10 Kokura | false | true |

Primary evidence is JRA official racecourse/course material. The config keeps the JRA course-page locator on each geometry row.

Important examples:

- Tokyo: uphill section in the home straight; dirt has the same two-slope structure.
- Nakayama: the well-known steep uphill is in the final straight for both turf and dirt.
- Chukyo: the rebuilt turf/dirt courses have an uphill immediately after entering the straight.
- Kyoto: the major hill is around the third corner; the final straight is flat.
- Hanshin: turf and dirt both have a finish-side uphill.
- Kokura: turf final straight is flat; dirt has a gentle uphill from about 400m remaining into the straight.
- Hakodate: the finish-side section is not classified as an uphill final straight; current course descriptions show the late section descending from around the fourth corner.
- Sapporo and Niigata: no material finish-side uphill is used for this binary feature.

## Course size class

`course_size_class` is intentionally **not a JRA subjective label**.

It is a deterministic, versioned project-derived bucket from the geometry row's `circumference_m` so that downstream RRDB code does not invent its own "small/large" classification.

Definition:

```text
SMALL   circumference_m < 1600
MEDIUM  1600 <= circumference_m < 1800
LARGE   circumference_m >= 1800
```

Non-circuit layouts, or combined layouts for which no single canonical circumference exists, remain null.

Examples include the Niigata straight course and combined outer-inner routes.

This class measures circuit scale only. It does **not** claim to measure turn radius or maneuverability. Downstream research must not rename it as a causal "tight-turn" measure without a separate definition.

## Phase 3 propagation

`build_jra_course_profile_phase3.py` propagates the geometry-level values to CourseMaster only when the resolved geometry rows agree on one non-null value.

If rail configurations disagree, or no applicable circumference exists, the CourseMaster value remains null.

## Historical validity contract

Historical `course_version` periods remain incomplete. v0.1 therefore defines a conservative verification epoch rather than pretending that every current physical value is proven for the full 2010–2025 Warehouse period.

Canonical validity for RRDB physical-feature research:

```text
physical_valid_from = 2023-01-01
physical_valid_to_exclusive = null
historical_course_version_status = NOT_FULLY_RECONSTRUCTED
```

Semantics:

- `2023-01-01` is the earliest date RRDB v0.1 is allowed to treat the current physical attributes as verified for research use.
- It is **not** a claim that each course changed on 2023-01-01.
- Races before that date must not receive current slope / straight / course-size attributes in Horse Fit or Transition Fit.
- Transition features that use physical attributes require both the previous race and the current race to fall inside the verified physical period.
- If a later course-shape change is identified, `physical_valid_to_exclusive` must be populated and a new `physical_version_id` created rather than mutating the old version.

Evidence supporting this conservative epoch includes:

- Kyoto: JRA states that the 2020-autumn to 2023-spring renovation did not involve a large-scale change of course shape.
- Chukyo: JRA documents the current enlarged course and uphill straight as the layout introduced with the March 2012 reopening, so the 2023+ epoch is safely after that structural change.
- Hanshin: the 2024–2025 closure is documented by JRA as a stand refresh project; v0.1 does not infer a new course geometry from that closure.

This is deliberately more conservative than the likely true historical validity of many venues.

Historical reconstruction before 2023 may be added later as separate versioned rows. Until then, fail closed.

This completion does not modify the existing CourseStats long-period baseline.

## RRDB handoff

After this completion, RRDB can use:

- `TURN_DIRECTION`
- `FINAL_SLOPE`
- `FINAL_STRAIGHT_BUCKET`
- `COURSE_SIZE`
- `LAYOUT`
- `PACE_PROFILE`

and corresponding transition families, subject to as-of and historical-version constraints.

The canonical performance source remains `-horse_adjusted_delta_per_1000m`; `performance_signal` may be used as a research alias only.

RRDB v0.3 remains unchanged.
