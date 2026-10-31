# Forecast Evidence v1

The request is exactly schema_version, protocol, target, as_of, history_years,
mode and detail. Modes share the same pre-race boundary. The target accepts
optional assertions against BAC fields; unknown assertions fail closed.

A source entry has path, name (actual local basename), kind (logical source key),
version, size_bytes, sha256, snapshot_at with timezone. SHA and size are measured
locally. An external caller must establish authentic before/after Drive metadata;
a user-supplied timestamp alone does not establish historical availability.

Normalized history exports use `forecast-history.v1` with races and rows. Races
use race_key/date/name/venue/surface/distance/race_class/eligibility/course/weight_rule.
Class and eligibility semantics must be verified upstream. Rows carry race_key,
race_date, horse_id, finish and the Analysis-style eight-axis columns. Previous
history joins use (prev_race_key_1, horse_id) with strict earlier date.

The bundle has forecast_evidence.json, sampling_audit.json, source_audit.json and
manifest.json. JSON keys and group order are stable. Manifest hashes the three
other files; it also records request and code hashes. Output is atomically renamed.
Repeat identical outputs are idempotent; changed outputs at an existing request
path fail closed.

PASS requires all gates. Missing data yields PARTIAL or NEED_INPUT. UNKNOWN class
and eligibility never count as equal. Exact and supplement remain separate.
Runner matches mean membership of an observed historical group, not estimated
ability or a favorable trend. Null values have explicit unknown coverage.

Target finish, payouts and final popularity are prohibited. Previous-run finish
and popularity may appear only for dates strictly before target date. Historical
statistics use only the ten complete prior calendar years. Reader generates no
marks, wagers or outcome estimates.

## Review correction: reference history, provenance and comparisons

`jrdb.history.references` is an optional independently verified forecast-history.v1
source for earlier reference rows (for example 2015 previous runs). Its rows join
on (race_key, horse_id) and must not duplicate cohort input keys. The statistical
cohort always filters to the ten prior calendar years; reference rows never add
starts. Coverage records requested/joined/missing previous rows, years, races and
starts. Missing expected years or duplicate partition/key coverage cannot PASS.

Every source now requires `provenance`: provider=native_drive, observation_id,
before and after metadata objects (id, name, size_bytes, modified_time, parent_ids,
version), and download_sha256. Metadata must be stable, bind the input bytes/name,
and predate the request cutoff. These observations must be acquired externally
through the native authenticated connector and retained for audit; Reader cannot
independently authenticate arbitrary caller-authored JSON. snapshot_at alone fails.

Each runner has all eight comparisons. `membership_only=true` means same-value
historical group presence, not favorable suitability. Evidence includes starts,
finishes and top3 counts. Base KYI popularity is pre-race only; absent pre-race
popularity is unknown, with explicit prohibition of final popularity. UKC birth
date supplies calendar age; UKC sire fields preserve bloodline evidence. Static
running_style_code and previous corners remain separate.

Nested forbidden output fields are scanned in evidence, sampling and source audits.
Only the direct runners[i].previous_run subtree may carry a finish field; its date
must be strictly before target. Final-popularity/odds and payouts are prohibited
anywhere in the published bundle.
