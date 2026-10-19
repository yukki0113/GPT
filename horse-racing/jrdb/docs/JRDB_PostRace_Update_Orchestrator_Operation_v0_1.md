# JRDB Post-Race Update Orchestrator Operation v0.1

Status: CURRENT  
Effective: 2026-10-19

## 1. Purpose

The user-facing post-race command is treated as one end-to-end operation:

```text
mmdd〜mmddの開催後取得をお願いします
```

The operation covers:

1. first-available SED acquisition,
2. first-available HJC acquisition,
3. canonical Raw publication and verification,
4. resolution of the matching canonical PACI for every race date,
5. Analysis v1.4 incremental candidate generation,
6. RaceReviewDB incremental candidate generation,
7. canonical Drive promotion for both derived stores,
8. Drive round-trip verification,
9. one aggregate completion report.

The user should not have to manually move from the Raw thread to separate
Analysis or RaceReviewDB maintenance threads.

## 2. Execution boundary

Authenticated JRDB acquisition remains GitHub-Actions-native.

Google Drive canonical publication remains GPT/native-Drive-native.

GitHub Actions must not write directly to Google Drive. The orchestrator is
therefore a logical end-to-end operation spanning both execution domains, not
one monolithic Actions workflow.

## 3. Shared source contract

For every target race date, the orchestrator resolves exactly one validated:

- PACIYYMMDD.zip
- SEDYYMMDD.zip
- HJCYYMMDD.zip

PACI may already exist from the pre-race operation and should normally be
reused from canonical Raw rather than fetched again.

Analysis and RaceReviewDB must consume the same PACI and SED bytes. HJC is part
of the post-race Raw completeness gate but is not a direct input to the current
Analysis v1.4 or RaceReviewDB builders.

The local coordinator writes one source receipt containing race date, family,
file name, byte size, SHA-256, and member count.

## 4. Local candidate coordinator

Reference implementation:

```text
horse-racing/jrdb/src/run_jrdb_post_race_orchestrator.py
```

It validates common date coverage and ZIP integrity, then calls existing
canonical builders:

- Analysis:
  `build_jrdb_analysis_post_race_parquet_native_v1_4.build_native_candidate`
- RaceReviewDB:
  `jrdb_postrace_review_incremental.incremental_update`

The coordinator does not duplicate either calculation implementation.

Example:

```bash
python horse-racing/jrdb/src/run_jrdb_post_race_orchestrator.py \
  --analysis-root ./analysis-current \
  --rrdb-current-zip ./RaceReviewDB_CURRENT.zip \
  --paci ./PACI261018.zip \
  --sed ./SED261018.zip \
  --hjc ./HJC261018.zip \
  --analysis-generation-id analysis-v1_4-postrace-20261018 \
  --rrdb-generation-id jrdb-race-review-v0_1-20261018 \
  --work-root ./work/postrace-20261018 \
  --rrdb-output-root ./work/rrdb-candidate \
  --summary-json ./work/postrace-20261018-summary.json
```

Multiple dates are supplied by repeating `--paci`, `--sed`, and `--hjc`.
Coverage must match exactly across all three families.

## 5. Candidate semantics

The Analysis builder creates a SHADOW candidate and must not modify its
`current.json`.

The RaceReviewDB builder is invoked with `promote=False` and therefore creates
a complete audited candidate without advancing canonical CURRENT.

The coordinator fails closed when:

- PACI/SED/HJC coverage differs,
- a ZIP is corrupt,
- a required family member is missing,
- Analysis candidate status is not CANDIDATE_PASS,
- RaceReviewDB candidate status is not PASS,
- either derived store reports target dates different from the shared source
  receipt.

## 6. Canonical promotion

After local candidate PASS:

1. publish the Analysis immutable generation to its canonical Drive root,
2. re-download/re-read and verify manifest, SHA/size, row count and audit,
3. advance Analysis `current.json` in place only after round-trip PASS,
4. publish the RaceReviewDB immutable generation/snapshot,
5. re-download/re-read and verify its manifest, generation, period and bytes,
6. replace the stable `RaceReviewDB_CURRENT.zip` bytes in place only after
   round-trip PASS,
7. preserve the stable CURRENT Drive file ID.

A candidate PASS alone is not operational completion.

## 7. Raw-thread execution sequence

The Raw acquisition thread should execute the following sequence for
`開催後取得をお願いします`:

```text
resolve target race dates
  -> Drive-first SED/HJC duplicate check
  -> authenticated SED/HJC fetch where needed
  -> validate and publish SED/HJC to canonical Raw
  -> resolve canonical PACI for every target date
  -> materialize validated Analysis CURRENT
  -> materialize RaceReviewDB_CURRENT.zip
  -> run run_jrdb_post_race_orchestrator.py
  -> Analysis Drive promotion + round-trip
  -> RaceReviewDB Drive promotion + round-trip
  -> aggregate completion report
```

If canonical PACI is missing, fetch and publish it before candidate generation
rather than asking the user to open another maintenance flow.

## 8. Completion report

A successful user-facing completion report should include at least:

- target race dates,
- SED/HJC canonical publication result,
- shared PACI/SED source SHA identity,
- previous/new Analysis generation IDs,
- previous/new RaceReviewDB generation IDs,
- RaceReviewDB period_to,
- Drive round-trip verification result for both stores,
- overall status.

Overall status is COMPLETE only when Raw publication, both candidate builds,
both canonical promotions and both round-trip checks have passed.
