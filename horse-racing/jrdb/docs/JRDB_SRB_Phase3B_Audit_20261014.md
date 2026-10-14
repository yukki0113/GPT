# JRDB SRB Phase 3B Audit — 2026-10-14

Status: RESEARCH / INTEGRATION CANDIDATE

## 1. Scope

This audit follows the 2026 YTD SRB Phase 3 study. It resolves the three missing September race dates, isolates the cause of missing optional SRB fields after 2026-08-29, and defines a neutral RaceNote lap-shape evidence contract.

## 2. September gap resolution

GitHub Issue #2020 triggered the authenticated JRDB daily-history route for 2026-09-06 through 2026-09-13, SED only.

Downloaded race-date archives:

- SED260906.zip: 36 races, 491 horse-result rows, 35 populated lap arrays, 1 obstacle no-lap race
- SED260912.zip: 24 races, 316 horse-result rows, 23 populated lap arrays, 1 obstacle no-lap race
- SED260913.zip: 24 races, 314 horse-result rows, 23 populated lap arrays, 1 obstacle no-lap race

All three current upstream archives contain RCA + SED + SRB.

Updated 2026 YTD coverage through 2026-10-12:

- 87 race dates
- 2,730 races
- 37,686 horse-result rows
- 2,636 races with populated SRB lap arrays
- 94 no-lap races, all obstacle-surface records in the materialized sample

## 3. Optional SRB field investigation

The stored Drive copy of SED260829.zip and a fresh authenticated re-fetch of the same upstream object were compared.

Stored Drive snapshot:

- size: 33,598 bytes
- members: SED260829.txt, SRB260829.txt
- optional SRB context populated: 0 / 36 races
- SHA-256: 6c55825ce58ee7e9782879e02b8f36fdcb1d1f6a47529dfc0fdd9dd36fd85db4

Fresh JRDB backnumber snapshot on 2026-10-14:

- size: 59,176 bytes
- members: RCA260829.csv, SED260829.txt, SRB260829.txt
- optional SRB context populated: 36 / 36 races
- SHA-256: 0a602d031d5dcf48fd957791ec0c63c59a778a5bad231000a2f55576b9da2caa

Member-level comparison shows that both SED260829.txt and SRB260829.txt changed, and RCA260829.csv was added. The current upstream backnumber is therefore a later revised package, not merely the same ZIP with different compression metadata.

The supplied SRB specification states an update timing of approximately Monday 16:00 and describes the current and previous week files being updated. That behavior is consistent with the observed early-vs-late snapshots.

Conclusion: the ordinary immediate post-race SED acquisition is sufficient for the race-level lap array, but it is not guaranteed to contain finalized SRB optional context. A later JRDB refresh can change SED/SRB bytes and add RCA.

## 4. Raw retention implication

The project Raw invariant says acquired source bytes should not normally be overwritten; when replacement is unavoidable, the previous version must be retained with audit evidence.

Therefore Phase 3B does not silently replace the existing Drive SED260829.zip.

Recommended storage/operation policy:

1. Keep the immediate post-race SED snapshot as the original acquisition evidence.
2. After the JRDB Monday update window, re-fetch the prior race weekend.
3. Compare size, SHA-256, ZIP members and optional-SRB coverage.
4. If unchanged, record FINAL_UNCHANGED.
5. If changed, retain both snapshots under an explicit revision/audit contract before changing any canonical pointer.
6. Consumers requiring only lap arrays may use the immediate snapshot; consumers requiring pace-up/bias/comment must require a finalized snapshot.

The exact Drive revision-retention layout should be fixed before any existing Raw object is replaced.

## 5. RaceNote lap-shape evidence contract

Implemented files:

- schema/racenote_lap_shape_evidence_schema_v0_1.json
- src/racenote_lap_shape_evidence.py
- tests/test_racenote_lap_shape_evidence.py

Policy is intentionally neutral:

- source: JRDB SRB
- leader-based race observation
- not an individual horse sectional
- no additive score
- historical runs only, as-of exclusive
- partial first segment excluded from comparable 200m metrics

Derived neutral facts:

- early3f_sec when the first three segments are all 200m
- late3f_sec
- early_late_delta_sec
- lap_std_sec
- lap_range_sec
- fastest_lap_sec
- fastest_segment_no
- max_accel_sec
- max_decel_sec
- last_vs_best_sec
- last3_slope_sec_per_segment
- pace_up_remaining_furlongs when present

These values are evidence/context only. Phase 3 did not justify direct score promotion.

## 6. CI

The two new RaceNote lap-shape tests pass in GitHub Actions. The overall JRDB Common Reader workflow remains red because of the pre-existing RaceNote store-resolution fixture missing Analysis columns; no SRB/lap-shape test failed.

## 7. Remaining work

Before production RaceNote consumption:

1. define the Raw revision retention/pointer rule for late-finalized SED;
2. publish the three recovered September ZIPs to canonical Drive once the transport step can preserve the individual files and verification contract;
3. optionally add lap-shape evidence into the General Evidence / RaceReview reading lane without numeric weighting;
4. extend historical coverage if annual SED archives contain SRB members;
5. true-forward evaluate the resulting evidence wording/selection before changing production decisions.
