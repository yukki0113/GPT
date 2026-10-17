# RaceNote v0.5.5 Forward Evidence Operation Design v0.1

Status: **CURRENT IMPLEMENTATION / CANONICAL RAW ROUTING**
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
| Analysis v1.4 | historical runner facts / RaceNote base enrichment | **dedicated Analysis operation/thread** | consume supplied current; Forward T1 does not refresh or freshness-check |
| RRDB v0.5 | reinterpretation of visible prior runs | **dedicated RRDB operation/thread** | consume supplied current; Forward T1 does not refresh or freshness-check |
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

## 7. Forward T1 RaceLap freshness and clean-blind gates

For target date `D`, Forward T1 owns freshness for **RaceLap only**.

Analysis and RRDB are updated by their dedicated operations/threads. Forward T1
must not refresh them and must not compare their recency/cutoff against RaceLap.

### RaceLap freshness gate

The caller supplies an explicit RaceLap-only expected completed-date cutoff:

```text
race_lap.expected_period_to < D
race_lap.period_to == race_lap.expected_period_to
race_lap.period_to < D
```

If RaceLap is behind `expected_period_to`, the RaceLap resolver may advance it
only from explicitly materialized canonical SED input. Otherwise it fails
closed.

### Hard clean-blind gates

```text
market_blind = true
stripped_at_input_bind = true
result_opened = false
target_market_opened = false
```

Analysis/RRDB remain evidence inputs to RaceNote, but their freshness is outside
the Forward T1 ownership boundary. Existing target/future-data contamination
guards remain in force; removing freshness checks does not permit target-result
or future evidence leakage.

RRDB must still satisfy the active recommendation data contract when consumed:

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

### 8.1 Standard RaceLap entrypoint

RaceNote and other consumers must not coordinate refresh / validation /
promotion themselves. The standard entrypoint is:

```text
jrdb_race_lap_current_resolver.py
```

Its contract is:

```text
existing RaceLap CURRENT
+ Analysis period_to
+ target_date
+ optional explicit canonical SED delta
        |
        v
fresh? ---------------------- yes -> validate -> CURRENT_READY
  |
  no
  |
explicit canonical SED present?
  | no -> fail closed; never discover/fetch history
  v
incremental refresh
  -> candidate validation
  -> promotion
  -> final CURRENT validation
  -> CURRENT_READY
```

The resolver never performs JRDB or Drive acquisition. Acquisition /
materialization remains outside this layer. This keeps source routing explicit
and prevents a forecast consumer from silently performing historical I/O.

The lower-level modules remain reusable implementation primitives:

- `jrdb_race_lap_forward_refresh.py`
- `jrdb_race_lap_forward_current.py::validate`
- `jrdb_race_lap_forward_promote.py`

The normal orchestration caller is the resolver. The Actions wrapper
`.github/workflows/racelap_forward_current_resolver.yml` provides the same
verify-or-advance contract for already-materialized Actions artifacts.

### 8.2 RaceNote T1

Normal forward T1 becomes:

```text
1. Resolve exact PACI for target date.
2. Receive the Analysis current prepared by the dedicated Analysis operation.
   - no refresh here
   - no freshness/cutoff comparison here
3. Receive the RRDB current prepared by the dedicated RRDB operation.
   - no refresh here
   - no freshness/cutoff comparison here
4. Materialize approved Course Fit.
5. Materialize RaceLap_CURRENT and resolve it through RaceLapCurrentResolver.
6. Require resolver status CURRENT_READY and validate only RaceLap:
     race_lap.period_to == race_lap.expected_period_to
     race_lap.period_to < target_date
7. Build market-blind forecast_prep.
8. Build KYI supplemental bundle from target PACI.
9. Initialize v0.5.5 using the Parquet path returned by the resolver.
10. Seal Reader and stop at READY_FOR_V055_AUTHORING.
```

Forward T1 therefore orchestrates freshness/update for RaceLap only. Analysis
and RRDB are consumed as externally maintained evidence assets.

Forbidden in normal forward T1:

- annual SED fetch;
- calendar-range daily SED scan;
- rebuilding RaceLap from raw history;
- result acquisition;
- target-day SED acquisition.

---

## 9. Initial current publication from canonical Drive Raw

The common RaceLap builder / Store / Reader were already established on
2026-10-15. Initial current publication must reuse the canonical JRDB Raw
snapshots; it is not a historical acquisition job.

Authoritative input:

```text
Google Drive
GPT/horse-racing/00_raw/SED
  SED_2024.zip
  SED_2025.zip
  SED26*.zip through the accepted completed-date cutoff
```

Each canonical SED archive contains the paired SED/SRB members required by
`jrdb_race_lap_dataset.py`.

Required initial publication path:

```text
connected/native Drive materialization
  -> jrdb_race_lap_dataset.py
  -> RaceLapStore validation
  -> immutable candidate manifest
  -> jrdb_race_lap_forward_promote.py
  -> RaceLap current
```

Hard rules:

1. Do not download annual or daily historical SED from JRDB to create the initial current.
2. Do not calendar-scan historical dates.
3. Do not treat Actions artifacts from failed acquisition attempts as canonical Raw.
4. Authenticated/writable Drive transport from GitHub Actions remains prohibited by repository policy.
5. The initial full snapshot is built from canonical Drive Raw in a connected/native environment.
6. After that baseline exists, normal post-race operation advances it only with the newly completed canonical SED snapshot.
7. T1 never performs initial publication, backfill, repair, or historical acquisition.
8. Analysis supplies the accepted completed-date cutoff only; it is not a RaceLap data source.

For target 2026-10-17, the accepted cutoff remains `2026-10-12`.


## 10. Rate-limit and retry policy

Historical calendar sweeps are prohibited in forward T1.

For bounded post-race acquisition only (initial publication uses canonical Drive Raw and performs no JRDB historical fetch):

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

This may provide discovery metadata, but Forward T1 must not use it to impose Analysis/RRDB freshness gates. RaceLap owns its separate expected cutoff.

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

### E. RaceLap freshness guard

If:

```text
race_lap.expected_period_to = 2026-10-12
race_lap.period_to = 2026-10-11
```

T1 must fail before v0.5.5 Reader seal. Analysis/RRDB recency is not part of
this Forward T1 gate.

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
Post-race:
  Analysis dedicated operation -> Analysis current
  RRDB dedicated operation     -> RRDB current
  RaceLap operation            -> RaceLap incremental update -> promote current

Next race day:
  PACI target
  + externally maintained Analysis current
  + externally maintained RRDB current
  + current Course Fit
  + RaceLap current
  -> Forward T1 checks/updates RaceLap only
  -> T1 seal
  -> T2 prediction
```

The expensive operation moves to one bounded post-race delta refresh.  
The forecast-day T1 becomes deterministic, repeatable, and almost entirely local/materialization work.
