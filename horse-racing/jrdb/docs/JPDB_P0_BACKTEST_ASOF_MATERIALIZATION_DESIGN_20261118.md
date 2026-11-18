# JPDB P0 — RaceNote backtest date-effective jockey-history materialization design

Date: 2026-11-18. Status: **P0 architecture/proof of cutoff only; NOT P1 or RaceNote integration approval**.

## Decision: dual-gate as-of Reader

For a RaceNote backtest scheduled on target date `D`, JPDB should **compute only prior ride facts before D**, as already done conceptually by the RRDB Horse Course Fit `as_of_date` three-calendar-year historical window. Unlike merely filtering dated rows, however, the BRDB historical provenance gate requires an independently attested **source version available to the caller at prediction timestamp T**. Therefore a correct JPDB consumer must satisfy BOTH:

- **event-time gate:** `source_race_date < D`, with historical aggregation window `[max(2023-01-01, D - 3 calendar years), D)`. Strict day exclusion avoids current-race and same-meeting-day spoilers when the actual prediction time is unknown.
- **knowledge-time gate:** the *exact observed source release/snapshot version and its content* must have been publicly distributed or provably acquired `available_at <= T`; no post-target revisions, late-corrected SED, or final KYI substituted. Use the latest immutable eligible revision **as of T**, not the globally latest file.
- **target entry gate:** target KYI scheduled jockey must come from a separately verified pre-race PACI/KYI snapshot available at T. Retrospective annual KYI is not proof of the exact target-day announced starter or rider.
- **Course gate:** every historical course attribute used must have a valid physical version for that *past source race date*, with known fields only; `course_key` alone is not evidence of complete historical geometry.

### Retrieval lanes

1. **RETROSPECTIVE_DATE_CUTOFF** (P0 research): immutable finalized annual SED; exclude any event with `race_date>=D` and any unknown/restricted outcome for the requested diagnostic. This **does NOT establish original availability or post-correction values**, hence `prediction_safe=false`. It is useful for testing the deterministic window and population calculations and comparing with other auxiliary DB research.
2. **ATTESTED_ASOF** (future separately reviewed): require per-source-version immutable SHA, observed/release timestamp, revision chain, target PACI member membership and the selected historical records. Every emitted source fact must pass both gates. If one fact's availability cannot be established, exclude it with reason `UNVERIFIED_SOURCE_ASOF`, never silently fall back to final annual SED.
3. **CURRENT_PREDICTION** (future separately reviewed): use latest independently validated pre-race target PACI and refreshed completed-race SED, with an explicit wall-clock cutoff and SHA pins. Still no implicit permission to use post-target source versions.

### Proposed RaceNote request flow (not wired)

```text
RaceNote backtest request (target race date D, prediction timestamp T)
  -> existing JRDB race-key / pre-race PACI input resolution at T
  -> JPDB immutable generation Reader with explicit source refs and manifest SHA
  -> filter historical race events: max(2023-01-01, D-3y) <= race_date < D
  -> select source revision where available_at <= T
  -> resolve prior actual SED jockey, course and normal/nonstart/DNF categories
  -> group on jockey_code for descriptive n, uncertainty and support
  -> emit response with provenance, counts, coverage, confidence exclusions
  -> RaceNote merge only after a separate contract/approval gate
```

For race day D, the conservative contract uses **D-exclusive**, not `D` inclusive, even for races held earlier that same day. A refined race-specific timestamp-based policy would require both source distribution time and prediction cutoff and must be versioned separately.

### Candidate output fields for reviewed P1 design

`target_date`, `prediction_cutoff_utc`, `jockey_code`, `source_generation`, `input_snapshot_sha256`, `event_from_inclusive`, `event_to_exclusive`, `available_source_revision_ids`, `available_at_proof_status`, `population_filter_id`, `prior_flat_entries`, `normal_finishers`, `nonstarters`, `dnf`, `demoted`, `wins`, `top3`, `effective_history_days`, `asof_status`, `physical_attribute_status`, `excluded_reasons`.

These are **proposed fields**, not the implemented Reader or any agreed skill-strength, win-rate, conditional-feature or betting model. The provisional P0 diagnostic denominator may group by actual `SED.jockey_code` with abnormal `0` normal finishers; actual ride-start population and demotions need versioned policy before P1.

### Deterministic, fail-closed smoke/audit

- `tools/jpdb_p0_backtest_cutoff_audit.py` (DuckDB 1.1.3, SHA-pinned 2023–2025 SED) calculates only aggregated verification counts. It does **not export individual licensed jockey records** or score predictions.
- `tests/test_jpdb_p0_backtest_cutoff_audit.py` covers same-day/future leak rejection, start boundary, obstacle exclusion and abnormal-category denominators.
- Expected P0 evidence: at target D=2023-01-01 no 2023 historical rows; at D=2025-11-15 no 2025-11-15 or later SED and no future jockey aggregates. All input SED assets must match immutable SHA and expected row cardinality. Prohibit any target date outside accepted 2023–2025 cohort.
- A PASS result is **PASS_RETROSPECTIVE_CUTOFF_ONLY**, always `prediction_safe=false` and `as_of_certified=false`, with `actual_release_time_attested=false`.
- Results are aggregate-only, with SHA provenance, lookback bounds and count of same-day/future excluded. No physical runner/jockey rows are published to GitHub by this P0 audit.

## Open prerequisites

1. Obtain historical PACI/KYI **actual pre-race snapshots** for 2023–2025 with publication/acquisition timestamps; quantify what fraction of races can be certified.
2. Independently recover SED versions and first/late-finalized timestamps. A latest-revision annual Warehouse cannot prove what was known in 2024 or at another past T merely through `race_date`.
3. Reconcile 731 KYI-vs-SED mismatches with those snapshots and official jockey-change source; until then do not claim confirmed race-day substitutions.
4. Freeze a versioned `population_filter_id` for normal finishers, actual starts, abnormal `3` and `5`, minimum support and uncertainty.
5. Review freshness, manifest, immutable Reader and fallback behavior, then explicitly approve P1 and a later P4 RaceNote integration. Never mutate RRDB, BRDB, Course Master, RaceNote or existing Warehouse as a side effect of P0.

**Gate disposition: P0 REVIEW_REQUIRED.** Date-effective retrospective logic is necessary but not sufficient for historically faithful prediction-time backtesting.
