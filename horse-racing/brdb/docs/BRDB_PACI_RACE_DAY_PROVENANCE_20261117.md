# BRDB PACI race-day provenance acceptance — 2026-11-17

Status: **PASS FOR EXACT PACI USER-SIDE PRE-OFF AVAILABILITY / PROVIDER RELEASE TIME UNKNOWN / NO PREDICTION PROMOTION**

## Scope

This audit addresses the remaining D4 race-day timing question for the already accepted real PACI field. It does not re-evaluate D3 historical as-of correctness and does not authorize predictive use.

Accepted D4 field:
- PACI: `PACI261115.zip`
- race key: `05265412`
- target: 2026-11-15, venue 05, turf raw code 1, 2000m, 18 declared horses
- PACI SHA-256: `3c80e70a74a13874a82b7f7cf4c5f9415d6abbf186ec0ccfa1d2842e51a7b050`

## Evidence

Connected Drive metadata for the canonical PACI file:
- Drive file ID: `1wVcoTvNw38nFaPcDWJme-zMsl6MobR3l`
- canonical parent: `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`
- size: 565,352 bytes
- created: `2026-11-14T12:16:37.800Z` = **2026-11-14 21:16:37.800 JST**
- modified: `2026-11-14T12:16:37.800Z` = **2026-11-14 21:16:37.800 JST**
- current bytes match the fixed PACI SHA above.

Canonical BAC record for race `05265412`:
- race date: 2026-11-15
- scheduled post time: **16:10 JST**

The exact current PACI bytes therefore have a Drive content-modification timestamp **68,002 seconds (18h 53m 22s) before scheduled post**.

## Conservative decision

`paci_acquisition_status=PRE_OFF_DRIVE_BYTES_ATTESTED`

Meaning: the exact SHA-pinned PACI bytes currently used by D4 were already present, with no later Drive content modification, in the user's canonical PACI Drive folder before the race's scheduled post time.

This is stronger than the previous `SAME_DAY_RELEASE_TIME_UNVERIFIED` placeholder for this specific field.

It does **not** mean:
- JRDB provider publication timestamp is independently known;
- every historical PACI/UKC snapshot is pre-off attested;
- D3 historical evidence is as-of verified;
- any result-derived or retrospectively selected evidence is prediction-safe.

Those remain:
- `provider_release_status=UNKNOWN_NOT_ATTESTED`
- `d3_historical_asof_status=AS_OF_UNVERIFIED_UNCHANGED`
- `prediction_safe=false`

## Implementation and tests

- `src/audit_brdb_paci_race_day_provenance.py`
- `tests/test_audit_brdb_paci_race_day_provenance.py`
- `config/paci_20261115_drive_metadata_snapshot.json`
- `src/run_brdb_paci_race_day_provenance_acceptance.py`

Six exact committed tests PASS:
1. previous-day acquisition is pre-off;
2. same-day acquisition before post is pre-off;
3. modification after post is not attested;
4. wrong canonical Drive parent fails closed;
5. provider release is never promoted;
6. D3 as-of state is never promoted.

## Real Actions acceptance

- Issue: [#2618](https://github.com/yukki0113/GPT/issues/2618)
- Run: [44026682894](https://github.com/yukki0113/GPT/actions/runs/44026682894)
- source commit: `c9e15a8da836682a592488bd7e81c11ead5bc20a`
- fallback: **PASS**
- artifact: `data-storage-fallback-44026682894` (ID `14303611215`)
- DuckDB 1.1.3 / PyArrow 25.0.1 (fallback environment; this audit itself does not depend on DuckDB)

Output SHA:
- `paci_race_day_provenance_20261115_05265412.json`: `b52b222ae565e0dfb566a6f629c20394d2ab4c19b70ff81b67905d13f0c9470a`
- `paci_race_day_provenance_tests.log`: `60e42cbbd2a24bc3c697425be02c90440237ec19a04645dba4ae2ef5b65a3fb0`

## Durable storage

Stored in ChatGPT Library:
- `/BRDB/Provenance/paci_race_day_provenance_20261115_05265412.json`
- `/BRDB/Provenance/paci_race_day_provenance_tests_20261117.log`

Both were materialized back and independently SHA-verified.

## Boundary

For D4 research, the selected real PACI field now has a concrete pre-off user-side source snapshot. The remaining predictive blocker is not this PACI archive's availability; it is the broader historical/as-of validity of research evidence (notably frozen D3) and the separately defined M6 prospective scientific gate.
