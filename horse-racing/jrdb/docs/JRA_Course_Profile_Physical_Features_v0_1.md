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

## Historical caveat

Historical `course_version` periods remain incomplete.

Therefore:

- these fields describe the current JRA physical layout;
- RRDB replay must use explicit period constraints;
- no claim is made that a current physical value is valid for all 2010–2025 races;
- three-year rolling Horse Fit research should fail closed or exclude periods where physical-version purity cannot be established.

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
