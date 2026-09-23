# KEIRIN Canonical Schema Contract v0.1

Date: 2026-09-23
Parent design: `keirin/docs/CANONICAL_DESIGN_v0_1.md`
Status: IMPLEMENTATION CONTRACT

## 1. Contract rules

- Storage format: Parquet + ZSTD
- Encoding: UTF-8
- Date: DATE
- Timestamp: TIMESTAMP with JST meaning documented in manifest; storage may be UTC if normalized consistently
- Integer identifiers such as rider_id / venue_code are stored as STRING when leading zeros or provider formatting may matter
- Raw labels are preserved even when normalized columns exist
- All normalized enums permit `unknown`
- Missing source facts remain NULL; do not synthesize values from current profiles
- Parser must be deterministic for identical Raw SHA + parser commit

## 2. Stage A mandatory outputs

### pre/meet

Required non-null:
- meet_key STRING
- venue_code STRING
- venue_name STRING
- meet_start_date DATE
- source_provider STRING
- source_raw_sha256 STRING
- acquired_at TIMESTAMP

Nullable:
- meet_end_date DATE
- grade_raw STRING
- grade_norm STRING
- event_name STRING
- scheduled_days INT
- actual_days INT
- meet_status STRING
- source_updated_at TIMESTAMP

Uniqueness:
- meet_key

### pre/race

Required non-null:
- race_key STRING
- meet_key STRING
- race_date DATE
- venue_code STRING
- race_no INT
- source_provider STRING
- source_raw_sha256 STRING
- acquired_at TIMESTAMP

Nullable:
- day_no INT
- day_label_raw STRING
- scheduled_start_time STRING
- race_label_raw STRING
- class_category STRING
- race_stage STRING
- grade_raw STRING
- grade_norm STRING
- distance_m INT
- laps INT
- starters_scheduled INT
- competition_category STRING
- race_ruleset STRING
- cancellation_status STRING
- detail_token STRING
- detail_disp STRING
- source_updated_at TIMESTAMP

Uniqueness:
- race_key

Foreign key:
- meet_key -> pre/meet

Stage A rule:
- detail_token is provenance/navigation metadata, not a model feature.
- race_date must come from returned official Historical data, never meet_start + offset inference.

### provenance/source_asset

Required non-null:
- source_asset_key STRING
- provider STRING
- raw_sha256 STRING
- drive_archive_name STRING
- raw_relative_path STRING
- acquired_at TIMESTAMP
- parser_version STRING

Nullable:
- source_url STRING
- request_method STRING
- request_form_json STRING
- http_status INT
- content_type STRING
- source_updated_at TIMESTAMP

Uniqueness:
- source_asset_key

### provenance/row_source_map

Required non-null:
- table_name STRING
- canonical_key STRING
- source_asset_key STRING
- parser_version STRING

Nullable:
- source_locator STRING
- parse_rule STRING

Uniqueness:
- table_name + canonical_key + source_asset_key

### provenance/parse_audit

One row per source asset / parser execution.

Fields:
- source_asset_key
- parse_status
- meet_rows
- race_rows
- warnings_count
- errors_count
- warning_codes ARRAY<STRING> or JSON string
- error_codes ARRAY<STRING> or JSON string
- parser_version
- generated_at

## 3. Stage D entry contract

### pre/entry

Required when detail acquisition is complete:
- race_key STRING
- rider_id STRING
- car_no INT
- rider_name_at_race STRING
- effective_asof TIMESTAMP
- source_raw_sha256 STRING

Nullable historical snapshot:
- frame_no INT
- age_at_race INT
- registered_prefecture STRING
- region STRING
- training_term INT
- class_current STRING
- class_previous STRING
- leg_style_raw STRING
- leg_style_norm STRING
- gear_ratio DOUBLE
- competition_score DOUBLE
- win_rate DOUBLE
- top2_rate DOUBLE
- top3_rate DOUBLE
- first_count INT
- second_count INT
- third_count INT
- outside_count INT
- withdrawal_count INT
- disqualification_count INT
- start_count INT
- home_count INT
- back_count INT
- kimarite_nige_count INT
- kimarite_makuri_count INT
- kimarite_sashi_count INT
- kimarite_mark_count INT

Uniqueness:
- race_key + rider_id

Hard rule:
If a Historical source does not expose a field at that race-time snapshot, leave NULL. Never backfill from current rider profile.

## 4. Line contract

### pre/line_group

Required:
- line_snapshot_key STRING
- race_key STRING
- line_id STRING
- source_kind STRING
- effective_asof TIMESTAMP

Nullable:
- line_order_display INT
- member_count INT
- head_rider_id STRING
- line_status STRING
- source_name STRING
- confidence DOUBLE
- raw_representation STRING

Allowed source_kind:
- published
- manual
- inferred

Canonical fact gate:
- Only rows with `source_kind=published` belong in official fact views.
- manual/inferred rows may be stored physically in a hypothesis area but must not enter the fact view.

### pre/line_member

Required:
- line_snapshot_key STRING
- race_key STRING
- line_id STRING
- rider_id STRING
- position_no INT

Nullable:
- role_raw STRING
- role_norm STRING
- relation_to_front_rider_id STRING

Allowed role_norm:
- head_self_power
- second_bante
- third
- fourth_plus
- solo
- unknown

Uniqueness:
- line_snapshot_key + rider_id

Audit:
- one rider cannot appear in two standard line groups for the same published snapshot
- position_no must be unique within a standard line
- if line_status=solo then member_count=1 and position_no=1
- head_rider_id must equal position_no=1 rider where present

### pre/position_contest

Use for `競り` and other non-simple structures.

Fields:
- race_key
- target_rider_id
- target_position
- contender_rider_id
- contest_type
- source_kind
- effective_asof
- raw_representation

Do not force a contested formation into a fake simple line.

## 5. Race ruleset contract

Allowed normalized values:
- standard_keirin_line
- girls_international_no_line
- advance_international_no_line
- other
- unknown

Important:
- `standard_keirin_line` does not mean a published line snapshot is always available.
- line coverage and ruleset classification are separate metrics.

## 6. POST contract

### post/result

Required:
- race_key
- rider_id
- car_no
- result_status
- source_raw_sha256

Nullable:
- finish_order
- finish_time
- margin_raw
- kimarite_raw
- home_marker
- back_marker
- start_marker
- penalty_raw
- disqualification_raw

Uniqueness:
- race_key + rider_id

### post/race_result

Required:
- race_key
- race_completed_flag

Nullable:
- winner_rider_id
- winner_car_no
- winning_kimarite
- result_updated_at
- cancellation_status

Uniqueness:
- race_key

### post/payout

Required:
- race_key
- bet_type
- selection_key

Nullable:
- payout_yen
- popularity_rank
- refund_flag

Uniqueness:
- race_key + bet_type + selection_key

## 7. Coverage metrics

Every generation must emit counts and percentages by year.

Mandatory:
- meet_coverage
- race_coverage
- entry_detail_coverage
- competition_score_coverage
- leg_style_coverage
- home_count_coverage
- back_count_coverage
- result_coverage
- payout_coverage
- published_line_coverage
- rider_comment_coverage

Definitions:
- denominator for published_line_coverage = races classified as standard_keirin_line
- numerator = races with at least one valid published line snapshot that passes integrity checks
- no-line rulesets are excluded, not counted as missing line
- unknown rulesets are reported separately

## 8. Null semantics

Use NULL for:
- unavailable
- not present in source
- not yet parsed

Use explicit enums for:
- not_applicable
- cancelled
- no_line_ruleset

Do not encode missing numeric values as 0.

## 9. Prediction views

Canonical tables remain source-oriented.
Create DuckDB views separately.

Suggested:
- `v_pre_race_entry`
- `v_pre_standard_line_member`
- `v_post_result`
- `v_training_cutoff_previous_day_2100`

The training cutoff view must enforce:
`available_at <= prediction_asof`.

## 10. Stage A PASS criteria

A Stage A generation is PASS only when:
- all 10 Drive archives are readable
- every Raw asset has SHA/provenance
- duplicate meet_key = 0
- duplicate race_key = 0
- orphan race -> meet = 0
- race_date inferred by arithmetic = 0
- parser errors = 0 or explicitly quarantined
- year-level race counts are reported
- all outputs reproducible from generation manifest

Stage A does not require entry/line/result coverage.

## 11. Versioning

Breaking schema changes:
- increment canonical version directory, e.g. v0_2

Non-breaking parser fixes:
- keep schema version
- bump parser version / generation id

Never overwrite an existing generation silently.
