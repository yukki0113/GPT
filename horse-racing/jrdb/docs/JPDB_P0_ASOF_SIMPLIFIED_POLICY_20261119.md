# JPDB — historical SED as-of operational simplification (2026-11-19)

**Status: user-approved modeling assumption / prospective JPDB design policy.**
This decision supersedes the historical SED **source-release-timestamp gate** in
`JPDB_P0_ASOF_RIDER_SOURCE_CONTRACT_20261118.md` and
`JPDB_P0_BACKTEST_ASOF_MATERIALIZATION_DESIGN_20261118.md`
**for JPDB research/backtest calculations only**. Earlier audit outputs and their
original verification conclusions remain unchanged.

## Approved decision

For a RaceNote backtest with target race date `D`, treat the latest accepted
SED outcome for every completed race on date `d < D` as information **assumed
available at D**. Do not require historical first-release timestamp, per-day
source snapshots or SED late-revision lineage solely to permit that historical
outcome to enter an **assumption-based** JPDB backtest.

This is an explicit approximation, **not a factual proof** of the source's
historical distribution timing or revision content.

Policy ID:
`JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1`

- Temporal rule: `source_race_date < target_race_date` (strict, whole-day
  exclusion). No target-day results, even from earlier post times; no future rows.
- Historical lookback: `[max(2023-01-01, D-3 calendar years), D)`. The
  three-year duration is a design starting point, not a proven optimal sample size.
- Source binding: accepted canonical Warehouse `CURRENT`, pinned generation,
  asset SHA and read-only Reader; use `SED.jockey_code` as *actual past rider*.
- Results are labeled `asof_policy=JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1`,
  `availability_basis=ASSUMED_PREVIOUS_DAY`,
  `release_time_attested=false`, `historical_revision_attested=false`.
- Do **not** label these records `SOURCE_RELEASE_ATTESTED`, `STRICT_POINT_IN_TIME`
  or claim a reproducible first-publication snapshot.
- The previously measured `KYI.jockey_code != SED.jockey_code` 731 cases are
  **not** resolved by this assumption. Historical entry KYI for target D remains
  a separate source authority; no SED from D may determine its planned rider.
  When using annual KYI retrospectively, label it `FINAL_KYI_PROXY` rather
  than asserting an observed pre-race snapshot or official substitution.
- For known timestamped **current** operations, preserve ordinary source
  freshness validation; this historical approximation does not authorize
  consuming future SED data or unverified files.
- P1 population denominators, field-specific abnormal codes, statistical
  confidence/support, the 2026 incremental source, and RaceNote publication
  must still receive their own acceptance. This decision removes **only** the
  SED release/revision historical-evidence blocker.

## Distinguish the three statuses

| Property | Meaning |
|---|---|
| `event_cutoff_verified=true` | SQL/Reader demonstrably excludes `d >= D`. Already checked on accepted 2023–2025 SED. |
| `assumption_based_backtest_eligible=true` | SED prior-day results may be used under this expressly approved approximation. |
| `historical_release_attested=false` | No claim that the exact archive values existed in the contemporaneous release. |

The old P0 result `PASS_RETROSPECTIVE_CUTOFF_ONLY` remains an accurate
**historical test result**; it is not silently rewritten as a strict
contemporaneous-provenance PASS. New consumers must record policy ID in their
request, audit and output to keep future comparisons reproducible.

## Design implication

The conceptual JPDB path is:

```text
RaceNote backtest race date D
  -> target-entry KYI/horse identity (independently labeled source)
  -> JPDB Reader on SHA-verified accepted SED Warehouse
  -> select flat SED rows where
       max(2023-01-01, D-3y) <= race_date < D
  -> aggregate by actual historical jockey_code
  -> produce per-jockey n / class & condition support /
       descriptive performance with denominator version
  -> emit asof_policy, source_generation, SHA, date-bound and caveats
  -> RaceNote integration only after P1/P4 interface and population review
```

This decision is intentionally narrower than claiming all historical input
families are perfectly reproduced. All prior audit counts, Course Master
physical PARTIAL classification and upstream sources remain unchanged.
