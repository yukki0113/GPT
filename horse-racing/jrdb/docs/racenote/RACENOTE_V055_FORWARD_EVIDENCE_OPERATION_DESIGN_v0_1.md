# RaceNote v0.5.5 Forward Evidence Operation Design v0.1

Status: **PROPOSED DESIGN / READY FOR IMPLEMENTATION**
Target logic: `RaceNote-Human-Context-Reader-0.5.5-candidate`
Contract: `v055-prediction-freeze-confidence-review-r4`
Date: 2026-10-17

## 1. Purpose

Define an efficient forward-operation data path for RaceNote v0.5.5.

The core rule is:

> **A forward T1 must not rebuild historical evidence from JRDB.**

Historical/post-race evidence is maintained once after each completed JRA race day and published as a canonical current asset.  
T1 for the next race day only materializes those verified current assets, binds them to the target PACI, and seals the v0.5.5 Reader.

This preserves the clean-blind boundary while avoiding repeated historical SED acquisition and rate-limit exposure.

---

## 2. v0.5.5 evidence lanes

| Lane | Role in v0.5.5 | Forward update timing | T1 behavior |
|---|---|---|---|
| Target PACI | target card / pre-race facts / target KYI | target day acquisition | resolve exact PACI only |
| Analysis v1.4 | historical runner facts / RaceNote base enrichment | post-race incremental refresh | materialize current |
| RRDB v0.5 | reinterpretation of visible prior runs | post-race/current refresh | materialize current |
| Course Fit v0.1 | approved course-fit evidence | slow/versioned refresh | materialize approved asset |
| KYI supplemental bundle | allowlisted target KYI + prior race keys | derived during T1 | build from target PACI |
| RaceLap | leader sectionals / neutral prior-race shape evidence | **post-race incremental refresh** | **materialize current; never refetch history** |

The KYI bundle remains target-day derived and is not a separate long-lived forward warehouse.

---

## 3. Forward architecture

```text
                    AFTER COMPLETED JRA DAY D
                              |
                    acquire PACI_D + SED_D once
                              |
             +----------------+----------------+
             |                                 |
      Analysis v1.4 refresh             RaceLap delta build
             |                                 |
      Analysis current                   previous RaceLap current
             |                                 + new SED_D delta
             |                                 |
             |                           new RaceLap generation
             |                                 |
             +-------------+-------------------+
                           |
                    RRDB/current refresh
                           |
                  forward evidence ready


                    BEFORE TARGET DAY D+N
                              |
                         PACI_target
                              |
       +----------------------+-----------------------+
       |                      |                       |
 Analysis current        RRDB current          RaceLap current
       |                      |                       |
       +----------- Course Fit approved -------------+
                              |
                    market-blind forecast_prep
                              |
                    target KYI bundle from PACI
                              |
                    v0.5.5 init / Reader seal
                              |
                       READY FOR T2
```

No historical JRDB endpoint belongs in the normal forward T1 path.

---

## 4. RaceLap forward-current contract

### 4.1 Storage shape

RaceLap is small enough to remain a single ZSTD Parquet.

Reference measurement for 2024-2025:

- 6,909 races
- 1,218,056 bytes
- duplicate_count = 0
- validation_status = PASS

Therefore do not introduce year/month partitioning merely for forward refresh.

Canonical logical shape:

```text
RaceLap/
  current.json
  generations/
    racelap-forward-YYYYMMDD-NN/
      manifest.json
      race_lap.parquet
      audit.json
```

A Drive-facing stable bundle may be published as:

```text
RaceLap_CURRENT.zip
  current.json
  manifest.json
  race_lap.parquet
  audit.json
```

The stable current bundle is only a pointer/delivery surface.  
Every accepted generation remains immutable and content-addressed by SHA-256.

### 4.2 Current manifest minimum fields

```json
{
  "schema_version": "jrdb-race-lap-forward-current-0.1",
  "status": "CURRENT",
  "generation_id": "racelap-forward-20261012-01",
  "dataset_schema_version": "JRDB-Race-Lap-Parquet-0.1",
  "shape_logic_version": "SRB-Neutral-RaceShape-v0.1",
  "period_from": "2024-01-06",
  "period_to": "2026-10-12",
  "race_count": 0,
  "parquet_sha256": "...",
  "parquet_size_bytes": 0,
  "validation_status": "PASS"
}
```

---

## 5. Incremental RaceLap refresh

Introduce a project-side entrypoint such as:

```text
horse-racing/jrdb/src/jrdb_race_lap_forward_refresh.py
```

Inputs:

- previous accepted `race_lap.parquet`
- one or more newly completed daily `SEDyymmdd.zip`
- new generation id

Processing:

1. Parse only the newly supplied SED archive(s) using the existing RaceLap contract/parser.
2. Build a delta with the exact current RaceLap schema and shape logic.
3. Read the previous Parquet directly with DuckDB.
4. Merge `previous + delta`.
5. Sort by `race_date, race_key`.
6. Write a new ZSTD Parquet generation.
7. Validate before publication.

The refresh must not download earlier SED archives.

### 5.1 Validation gates

A candidate generation is accepted only when all gates pass:

- dataset schema version unchanged;
- shape logic version unchanged;
- canonical key `race_key` unique;
- previous rows are preserved exactly;
- no previous race disappears;
- new rows belong only to explicitly requested completed race dates;
- output row count = previous unique rows + genuinely new unique rows;
- min/max race dates are correct;
- Parquet is readable through `RaceLapStore`;
- audit reports `validation_status=PASS`.

### 5.2 Idempotent retry

If all incoming race keys already exist and their canonical content is identical:

```text
status = NOOP_IDENTICAL_RETRY
```

Do not create a semantically different generation.

If an incoming race key exists but its canonical RaceLap row differs:

```text
status = CONFLICT
```

Fail closed. Never silently replace a historical row.

---

## 6. Reuse the existing post-race SED acquisition

The existing post-race Analysis refresh already acquires exactly the completed date's PACI and SED.

RaceLap forward refresh should consume that same SED materialization in the same post-race execution boundary, rather than independently calling JRDB.

Preferred execution shape:

```text
Fetch PACI_D + SED_D once
  -> Analysis candidate
  -> RaceLap candidate
  -> validation
  -> publish/promote each current asset only after its own gates pass
```

This removes duplicate network traffic and makes SED acquisition one-per-race-day.

A later refactor may extract a common post-race raw-source artifact, but that is not required for the first implementation.

---

## 7. Forward T1 freshness and leakage gates

For target date `D`:

### Hard clean-blind gates

```text
analysis.period_to < D
race_lap.period_to < D
market_blind = true
stripped_at_input_bind = true
result_opened = false
target_market_opened = false
```

### Cross-source freshness gate

Use Analysis as the existing completed-race-day reference:

```text
race_lap.period_to == analysis.period_to
```

For normal forward operation this prevents a stale RaceLap store from silently omitting the most recent completed JRA day.

If Analysis and RaceLap disagree on `period_to`, T1 fails before Reader seal.

RRDB must also satisfy the active recommendation contract:

```text
rrdb-recommendation-signals-v0.5
```

### Session binding

The v0.5.5 session continues to bind:

- evidence bundle SHA-256;
- RaceLap Parquet SHA-256;
- base main SHA;
- clean Reader manifest SHA-256.

Therefore using a reusable current asset does not weaken immutability.  
The exact RaceLap generation used for that target day remains permanently identifiable from the sealed session.

---

## 8. T1 operation after implementation

Normal forward T1 becomes:

```text
1. Resolve exact PACI for target date.
2. Materialize current Analysis v1.4.
3. Materialize current RRDB v0.5.
4. Materialize approved Course Fit.
5. Materialize RaceLap_CURRENT and verify size/SHA/manifest.
6. Validate:
     analysis.period_to < target_date
     race_lap.period_to == analysis.period_to
     race_lap.period_to < target_date
7. Build market-blind forecast_prep.
8. Build KYI supplemental bundle from target PACI.
9. Initialize v0.5.5 using the already-materialized RaceLap Parquet.
10. Seal Reader and stop at READY_FOR_V055_AUTHORING.
```

Forbidden in normal forward T1:

- annual SED fetch;
- calendar-range daily SED scan;
- rebuilding RaceLap from raw history;
- result acquisition;
- target-day SED acquisition.

---

## 9. One-time bootstrap for 2026

A one-time bootstrap is required because the current RaceLap canonical asset was originally built from completed annual archives and no reusable 2026 current was established.

Bootstrap rules:

1. Reuse `SED_2024.zip` and `SED_2025.zip`.
2. For 2026, use **known JRA race dates only**, taken from the PACI/day inventory or an accepted operation ledger.
3. Do not scan every calendar day.
4. Reuse already available raw SED artifacts when possible.
5. For missing 2026 race dates, fetch one exact daily SED per race date with normal throttling.
6. Persist/checkpoint downloaded daily SEDs so a single 429 does not discard the other successful acquisitions.
7. Retry only missing/error dates.
8. Build one initial forward current generation through the latest completed JRA date.
9. Publish it as the RaceLap current baseline.
10. Never repeat this bootstrap during T1.

For the current 2026-10-17 target, the expected bootstrap cutoff is the same completed date already represented by Analysis: `2026-10-12`.

---

## 10. Rate-limit and retry policy

Historical calendar sweeps are prohibited in forward T1.

For post-race acquisition or one-time bootstrap:

- request only known race dates;
- default inter-request delay must be non-zero;
- HTTP 429 is retryable;
- exponential/backoff retry is required;
- successful date ZIPs are retained across retry attempts;
- retry operates on missing/error dates only;
- no full-range restart after one transient error.

A run with one failed race date must produce a machine-readable partial acquisition receipt instead of discarding the successful files.

---

## 11. Proposed repository changes

### New

```text
horse-racing/jrdb/docs/racenote/RACENOTE_V055_FORWARD_EVIDENCE_OPERATION_DESIGN_v0_1.md
horse-racing/jrdb/src/jrdb_race_lap_forward_refresh.py
horse-racing/jrdb/tests/test_jrdb_race_lap_forward_refresh.py
```

### Modify

```text
.github/workflows/jrdb_post_race_parquet_refresh_issue.yml
  - reuse fetched SED for RaceLap candidate generation
  - package RaceLap candidate/audit with the post-race handoff

horse-racing/jrdb/docs/racenote/RACENOTE_V055_SINGLE_DAY_RUNBOOK_v0_1.md
  - forward T1 consumes canonical RaceLap current
  - forward T1 must not rebuild historical RaceLap

horse-racing/jrdb/config/racenote_forecast_logic_current.json
  - add RaceLap forward-current contract/pointer after publication path is established
```

Optional after the first working implementation:

```text
horse-racing/jrdb/config/racenote_forward_evidence_current.json
```

This can provide one readiness registry for Analysis / RRDB / Course Fit / RaceLap.

---

## 12. Acceptance criteria

The design is complete only when these operational tests pass.

### A. Incremental equivalence

Build a RaceLap store through date D by:

1. full historical build;
2. previous-current + daily SED incremental refresh.

The resulting canonical rows must be row-level equivalent.

### B. Idempotent retry

Apply the same SED date twice.

Expected:

```text
NOOP_IDENTICAL_RETRY
```

No duplicate race keys.

### C. Conflict guard

Supply a modified input for an existing race key.

Expected: fail closed with `CONFLICT`.

### D. Forward T1 no-history-fetch

A forward T1 must complete with no invocation of:

```text
fetch_jrdb_history.py --from-year ...
fetch_jrdb_history.py --from-date <historical range> ...
```

Only the exact target PACI and canonical current evidence assets are materialized.

### E. Freshness guard

If:

```text
analysis.period_to = 2026-10-12
race_lap.period_to = 2026-10-11
```

T1 must fail before v0.5.5 Reader seal.

### F. Clean-blind guard

The sealed session must still report:

```text
market_blind=true
result_opened=false
target_market_opened=false
```

---

## 13. Operational outcome

After implementation, the ordinary weekly cycle is:

```text
Sunday/Monday post-race:
  fetch each completed date once
  -> Analysis update
  -> RaceLap incremental update
  -> RRDB update
  -> promote current assets

Next race day:
  PACI target
  + current Analysis
  + current RRDB
  + current Course Fit
  + current RaceLap
  -> T1 seal
  -> T2 prediction
```

The expensive operation moves to one bounded post-race delta refresh.  
The forecast-day T1 becomes deterministic, repeatable, and almost entirely local/materialization work.
