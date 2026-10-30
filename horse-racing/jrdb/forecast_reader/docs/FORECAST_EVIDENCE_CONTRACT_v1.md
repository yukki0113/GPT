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
