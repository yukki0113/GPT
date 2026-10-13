# JRA Course Profile Master — Phase 3 Initial Master Build v0.1

Status: INITIAL MASTER BUILD  
Date: 2026-10-13

## Inputs

Phase 3 combines:
- accepted Historical Warehouse BAC 2010–2025 observations from the Phase 1 audit;
- current JRA official course pages for all 10 racecourses.

The build keeps observed JRDB identity evidence and current physical JRA evidence separate.

## Schema refinement

Phase 2 correctly excludes JRDB `course_code` A/B/C/D from stable `course_key`. Phase 3 official data shows that rail position can still change circumference, width and sometimes final-straight length.

Schema v0.2 therefore adds `course_geometry_configuration`.

Stable identity remains:

```text
venue × surface × distance × physical layout variant
```

Race-day geometry is resolved separately with rail/course-code metadata. This preserves horse/course identity without discarding A/B/C/D geometry differences.

## Generated Phase 3 outputs

`build_jra_course_profile_phase3.py` emits:
- `course_master_seed_v0_1.jsonl`;
- `course_jrdb_mapping_seed_v0_1.jsonl`;
- `course_geometry_configuration_v0_1.jsonl`;
- `phase3_summary.json`.

## Mapping rules

Flat turf:
- ordinary venues use `main`;
- Niigata uses `straight / inner / outer`;
- Nakayama uses `inner / outer`, with 3200m `outer-inner`;
- Kyoto uses `inner / outer`;
- Hanshin uses `inner / outer`, with 3200m `outer-inner`.

Flat dirt uses `main`.

Obstacle observations are conservative. Single-pattern conditions are provisional. Distances with multiple observed route patterns remain `UNRESOLVED` until route-level evidence is added.

## Evidence currently populated

Current JRA official data supplies:
- venue turn direction;
- current flat starting-distance/layout membership;
- A/B/C/D rail configuration where published;
- circumference;
- width range;
- final-straight length;
- elevation difference;
- Niigata straight-course length.

`first_corner_distance_m`, full slope-segment geometry, and historical pre-renovation geometry are not guessed.

For Niigata turf 1000m, `final_straight_m` is NULL by definition because there is no final corner; `straight_course_length_m=1000` is stored in geometry configuration.

## Historical boundary

JRA documents a major Chukyo reconstruction with the renewed course first raced on 2012-03-03. Historical BAC contains old distances that are not in the current official course table. These remain historical/provisional and are not silently assigned current geometry.

## Phase 4 gate

CourseStats may proceed for mappings that are confirmed/provisionally accepted by the intended study population. Full historical aggregation should exclude unresolved obstacle routes and any historical geometry cohort whose identity cannot be reproduced reliably.
