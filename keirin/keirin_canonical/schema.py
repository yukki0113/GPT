"""Stable Stage A Arrow schemas; nullable fields retain their types."""

import pyarrow as pa


def schema_for(table):
    s, i, d, t = pa.string(), pa.int32(), pa.date32(), pa.timestamp("us", tz="UTC")
    fields = {
        "meet": [("meet_key",s),("venue_code",s),("venue_name",s),("meet_start_date",d),("source_provider",s),("source_raw_sha256",s),("acquired_at",t),("meet_end_date",d),("grade_raw",s),("grade_norm",s),("event_name",s),("scheduled_days",i),("actual_days",i),("meet_status",s),("source_updated_at",t)],
        "race": [("race_key",s),("meet_key",s),("race_date",d),("venue_code",s),("race_no",i),("source_provider",s),("source_raw_sha256",s),("acquired_at",t),("day_no",i),("day_label_raw",s),("scheduled_start_time",s),("race_label_raw",s),("class_category",s),("race_stage",s),("grade_raw",s),("grade_norm",s),("distance_m",i),("laps",i),("starters_scheduled",i),("competition_category",s),("race_ruleset",s),("cancellation_status",s),("detail_token",s),("detail_disp",s),("source_updated_at",t)],
        "source_asset": [("source_asset_key",s),("provider",s),("raw_sha256",s),("drive_archive_name",s),("raw_relative_path",s),("acquired_at",t),("parser_version",s),("source_url",s),("request_method",s),("request_form_json",s),("http_status",i),("content_type",s),("source_updated_at",t)],
        "row_source_map": [("table_name",s),("canonical_key",s),("source_asset_key",s),("parser_version",s),("source_locator",s),("parse_rule",s)],
        "parse_audit": [("source_asset_key",s),("parse_status",s),("meet_rows",i),("race_rows",i),("warnings_count",i),("errors_count",i),("warning_codes",s),("error_codes",s),("parser_version",s),("generated_at",t)],
    }
    return pa.schema([pa.field(name, typ, nullable=name not in {
        "meet_key","venue_code","venue_name","meet_start_date","source_provider","source_raw_sha256","acquired_at","race_key","race_date","race_no","source_asset_key","provider","raw_sha256","drive_archive_name","raw_relative_path","parser_version","table_name","canonical_key","parse_status","meet_rows","race_rows","warnings_count","errors_count","warning_codes","error_codes","generated_at"}) for name,typ in fields[table]])


def validated_table(name, rows):
    schema = schema_for(name)
    for row in rows:
        for field in schema:
            if not field.nullable and row.get(field.name) is None:
                raise ValueError(f"{name}: required {field.name} is NULL")
    return pa.Table.from_pylist(rows, schema=schema)
