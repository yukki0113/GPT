# RRDB Horse Course Fit research v0.1

The research mart measures canonical RRDB performance residuals by horse and
course attributes or immediate previous-start transitions. It does not change
RRDB v0.3 rules, serving, current pointers, or production recommendations.

Canonical sources:

- CourseMaster/geometry: regenerate with `build_jra_course_profile_phase3.py`
  from `audit_jra_course_profile_phase1.py` and the official geometry config.
- Identity: `jrdb_course_profile_identity.course_key_from_observation`.
- Performance: `jrdb_recommendation_signals.performance_signal`, using
  `-fact_horse_performance.horse_adjusted_delta_per_1000m`.
- RRDB partitions/current resolution: `RaceReviewReader`; verify manifest hashes.
- SED: accepted normalized Historical Warehouse; no Raw parser changes.
- Going normalization: `jrdb_edge_v02_canonical.track_condition_bucket`.
- Parquet validation, hashes and SQL quoting: repository `tools/data-storage`.

## Temporal and physical boundary

For each target `as_of_date`, fit sources are in `[as_of_date - 3 calendar years,
as_of_date)`. Each historical baseline uses only earlier actual starts in its
own three-year window, capped at the last 10 starts, with at least 3 non-null
canonical performance observations. A simple mean is deliberately used because
the existing `prior3_performance_mean` implementation has a different count and
does not implement the requested three-year bound. No new performance index is
introduced.

SED revisions must be available before the target. Identity/result/performance
inputs are checked against RRDB; a mismatch fails closed. RRDB standards must
have `standard_sample_end_date < race_date`. Replays requiring earlier corrected
source values must supply the corresponding canonical RRDB snapshot; the latest
snapshot is never silently used when observed inputs disagree.

All course physical axes, including direction and layout, require non-null
physical version and `physical_valid_from <= race_date` plus an exclusive end
bound when present. Before the canonical 2023 verification epoch, current
physical values are null in the ledger. Unreconstructed periods are excluded,
not assigned current geometry. Physical transition axes assert the same gate
on both the immediate previous start and the current start.

CourseMaster may supply unambiguous attributes when rail geometry cannot be
resolved; otherwise the matching canonical geometry row supplies rail-specific
values. Geometry transitions require both geometry keys. Nulls are preserved.
Obstacle and unresolved entries remain in the base, but are excluded from fits.
Same-day multiple starts are audited and excluded from transitions where either
side is ambiguous. Cancellations/exclusions (abnormal codes 1/2) are not starts;
DNFs remain starts and are never skipped to manufacture a better predecessor.

Surface is a grouping dimension in every fit. Going transitions require equal
surface. Distance transitions retain a surface-change flag and provide a separate
same-surface view. Raw going codes remain in the transition ledger and in an
additional raw-going fit table. Coarse mapping is explicit: broad 1=FIRM,
2/3/4=SOFT, separately for turf/dirt. No distance-band categories are invented.

## Stages and invocation

```bash
python horse-racing/jrdb/src/jrdb_horse_course_fit.py \
  --rrdb-root /path/to/extracted/current-root \
  --warehouse-root /path/to/accepted/warehouse \
  --course-master-dir /path/to/regenerated/phase3 \
  --as-of-date 2026-01-01 \
  --output-dir /path/to/rrdb_course_fit/v0_1/as_of=2026-01-01
```

`--stage base|residual|absolute|transition|research|all` supports independent
restarts; `--feature` selects one absolute/transition axis. Required upstream
stages are resolved through verified receipts and reused rather than rewritten.
A changed input, source implementation, date, constant, or corrupted output
invalidates the corresponding fingerprint. No giant pandas dataframe is used.

Outputs: base ledger, residual ledger, immediate-transition ledger, six absolute
axes, nine transition axes (including raw going and geometry), candidate view,
same-surface distance view, distribution/support/coverage reports, manifest and
audit. Each Parquet has a receipt with row count, schema hash, SHA-256 and elapsed
time. The transition ledger preserves continuous deltas and original endpoints;
distance/straight delta fits aggregate buckets, so exact-distance endpoint fields
in those aggregated rows are null. Other transition fits preserve from/to values.

Final-straight SIMILAR uses an initial tolerance of 5m. The canonical 57-row
geometry config includes rail differences of 2.6m, 2.7m and 5m; 5m treats these
small rail changes as similar rather than changes of straight-length environment.
The tolerance is versioned, recorded in the manifest, and not fitted to outcomes.
Straight bucket boundaries remain 350/450m; distance deltas use -400/-100/100/400m.
Shrinkage k=5, sample storage minimum=2, candidate minimum=4 and confidence
`min(1,n/8)*abs(positive_rate-.5)*2` follow the request. Zeros remain in the
denominator. These are research values, not production thresholds.

CourseStats is unchanged. PACE_PROFILE consumes canonical SED H/M/S directly;
this version does not join full-2010–2025 CourseStats into historical runs or
invent a draw-bias category. Any later CourseStats join must satisfy
`period_to_exclusive <= historical_race_date`.

## Validation

`run_rrdb_horse_course_fit_validation.py` verifies 32 pinned Warehouse assets,
regenerates Phase1/Phase3, validates physical propagation, builds all stages and
reruns to assert byte-identical artifacts and complete reuse.
The validation workflow uses an immutable accepted RRDB Actions artifact;
authenticated Drive transport is not used in Actions. It tests the
2026-01-01 snapshot over the 2023–2025 fit window with earlier baseline history.
Its outputs are research artifacts, with no Drive current-pointer promotion.

Run focused tests with:

```bash
python -m pytest horse-racing/jrdb/tests/test_jrdb_horse_course_fit.py -q
```

ROI, threshold optimization and candidate replay are separate later research.
Replay consumers should use `candidate_fit_view.parquet`, preserving as-of date,
surface, support, physical exclusions and input provenance.
