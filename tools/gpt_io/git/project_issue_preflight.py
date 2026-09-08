#!/usr/bin/env python3
"""Project-specific preflight contracts for high-frequency Issue workflows."""

from __future__ import annotations

import base64
import csv
from datetime import datetime
import gzip
from io import StringIO
import json
import re
from typing import Any


REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,80}\Z")
ARTIFACT_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,160}\Z")
SIMPLE_CSV_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,120}\.csv\Z")
DRIVE_URL_PREFIX = "https://drive.google.com/"

SUPPORTED_PREFIXES = (
    "[BOATRACE_RACELIST_REQUEST]",
    "[BOATRACE_PRE_RACE_REQUEST]",
    "[EVAL_MEDIA_REQUEST]",
    "[EVAL_OCR_REQUEST]",
    "[EVAL_PACI_ENRICH_REQUEST]",
    "[JRA_RESULTS_REQUEST]",
    "[RACENOTE_REQUEST]",
)


class ProjectPreflightError(ValueError):
    """A project Issue request failed deterministic contract validation."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def infer_project_prefix(title: str) -> str | None:
    """Return the recognized project Issue prefix, if any."""
    for prefix in SUPPORTED_PREFIXES:
        if title.startswith(prefix):
            return prefix
    return None


def parse_request_id(title: str, prefix: str) -> str:
    """Validate and return the request id suffix in an Issue title."""
    request_id = title[len(prefix) :].strip()
    if not REQUEST_ID_PATTERN.fullmatch(request_id):
        raise ProjectPreflightError(
            "INVALID_REQUEST_ID",
            f"request_id after {prefix} must use 1-80 ASCII letters, digits, dot, underscore or hyphen",
        )
    return request_id


def parse_json_object(body: str) -> dict[str, Any]:
    """Parse a raw JSON Issue body and require an object at the root."""
    try:
        request = json.loads(body.strip())
    except json.JSONDecodeError as exc:
        raise ProjectPreflightError("INVALID_JSON_BODY", f"Issue body must be raw JSON: {exc}") from exc
    if not isinstance(request, dict):
        raise ProjectPreflightError("INVALID_JSON_BODY", "Issue body JSON must be an object")
    return request


def parse_date(value: object, formats: tuple[str, ...], field_name: str) -> str:
    """Validate a date value against one or more accepted formats."""
    text = str(value or "").strip()
    for date_format in formats:
        try:
            datetime.strptime(text, date_format)
            return text
        except ValueError:
            continue
    accepted = " or ".join(formats)
    raise ProjectPreflightError("INVALID_DATE", f"{field_name} has invalid format; accepted: {accepted}")


def validate_boatrace_racelist(title: str, body: str) -> dict[str, object]:
    """Validate `[BOATRACE_RACELIST_REQUEST]`."""
    prefix = "[BOATRACE_RACELIST_REQUEST]"
    request_id = parse_request_id(title, prefix)
    request = parse_json_object(body)

    date_text = parse_date(request.get("date"), ("%Y%m%d",), "date")
    venues = request.get("venues")
    if not isinstance(venues, list) or not venues:
        raise ProjectPreflightError("MISSING_VENUES", "venues must be a non-empty array")
    for index, venue in enumerate(venues):
        if not isinstance(venue, dict):
            raise ProjectPreflightError("INVALID_VENUE", f"venues[{index}] must be an object")
        missing = [key for key in ("name", "code", "day") if key not in venue]
        if missing:
            raise ProjectPreflightError(
                "MISSING_VENUE_FIELD",
                f"venues[{index}] missing required field(s): {', '.join(missing)}",
            )

    interval_value = request.get("request_interval_seconds", 1.0)
    try:
        interval = float(interval_value)
    except (TypeError, ValueError) as exc:
        raise ProjectPreflightError("INVALID_INTERVAL", "request_interval_seconds must be numeric") from exc
    if not 0 <= interval <= 60:
        raise ProjectPreflightError("INVALID_INTERVAL", "request_interval_seconds must be between 0 and 60")

    return {
        "protocol": "BOATRACE_RACELIST_REQUEST",
        "request_id": request_id,
        "date": date_text,
        "venue_count": len(venues),
    }


def validate_boatrace_pre_race(title: str, body: str) -> dict[str, object]:
    """Validate `[BOATRACE_PRE_RACE_REQUEST]`."""
    prefix = "[BOATRACE_PRE_RACE_REQUEST]"
    request_id = parse_request_id(title, prefix)
    request = parse_json_object(body)

    raw_date = str(request.get("date", "")).strip()
    compact_date = raw_date.replace("-", "").replace("/", "")
    parse_date(compact_date, ("%Y%m%d",), "date")

    venue = str(request.get("venue", "")).strip()
    if not venue:
        raise ProjectPreflightError("MISSING_VENUE", "venue must not be empty")
    if len(venue) > 40 or any(character in venue for character in "/\\\n\r\t"):
        raise ProjectPreflightError("INVALID_VENUE", "venue is invalid")

    try:
        race = int(request.get("race"))
    except (TypeError, ValueError) as exc:
        raise ProjectPreflightError("INVALID_RACE", "race must be an integer from 1 to 12") from exc
    if not 1 <= race <= 12:
        raise ProjectPreflightError("INVALID_RACE", "race must be 1-12")

    output_format = str(request.get("format", "json")).strip().lower()
    if output_format not in {"json", "csv"}:
        raise ProjectPreflightError("INVALID_FORMAT", "format must be json or csv")

    return {
        "protocol": "BOATRACE_PRE_RACE_REQUEST",
        "request_id": request_id,
        "date": compact_date,
        "venue": venue,
        "race": race,
        "format": output_format,
    }


def normalize_eval_media_targets(request: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize the two accepted Eval media request shapes."""
    raw_targets = request.get("targets")
    targets: list[dict[str, str]] = []

    if raw_targets is not None:
        if not isinstance(raw_targets, list) or not raw_targets:
            raise ProjectPreflightError("INVALID_TARGETS", "targets must be a non-empty array")
        for index, item in enumerate(raw_targets):
            if not isinstance(item, dict):
                raise ProjectPreflightError("INVALID_TARGET", f"targets[{index}] must be an object")
            date_value = str(item.get("date", "") or "").strip()
            post_id = str(item.get("post_id") or item.get("tweet_id") or item.get("status_id") or "").strip()
            targets.append({"date": date_value, "post_id": post_id})
        return targets

    dates_value = request.get("dates", [])
    post_ids_value = request.get("post_ids", request.get("tweet_ids", []))
    if isinstance(dates_value, str):
        dates = [value for value in re.split(r"[\s,]+", dates_value.strip()) if value]
    elif isinstance(dates_value, list):
        dates = [str(value).strip() for value in dates_value if str(value).strip()]
    else:
        raise ProjectPreflightError("INVALID_DATES", "dates must be a string or array")

    if isinstance(post_ids_value, str):
        post_ids = [value for value in re.split(r"[\s,]+", post_ids_value.strip()) if value]
    elif isinstance(post_ids_value, list):
        post_ids = [str(value).strip() for value in post_ids_value if str(value).strip()]
    else:
        raise ProjectPreflightError("INVALID_POST_IDS", "post_ids must be a string or array")

    if not dates or not post_ids:
        raise ProjectPreflightError("MISSING_TARGETS", "specify targets, or both dates and post_ids")
    if len(dates) != len(post_ids):
        raise ProjectPreflightError("TARGET_COUNT_MISMATCH", "dates and post_ids must have the same number of items")
    return [
        {"date": date_value, "post_id": post_id}
        for date_value, post_id in zip(dates, post_ids)
    ]


def validate_eval_media(title: str, body: str) -> dict[str, object]:
    """Validate `[EVAL_MEDIA_REQUEST]`."""
    prefix = "[EVAL_MEDIA_REQUEST]"
    request_id = parse_request_id(title, prefix)
    request = parse_json_object(body)
    targets = normalize_eval_media_targets(request)
    if len(targets) > 31:
        raise ProjectPreflightError("TOO_MANY_TARGETS", "maximum is 31 targets per request")

    seen_post_ids: set[str] = set()
    for target in targets:
        parse_date(target["date"], ("%Y-%m-%d",), "target date")
        post_id = target["post_id"]
        if not re.fullmatch(r"\d{10,25}", post_id):
            raise ProjectPreflightError("INVALID_POST_ID", f"invalid post_id: {post_id!r}")
        if post_id in seen_post_ids:
            raise ProjectPreflightError("DUPLICATE_POST_ID", f"duplicate post_id: {post_id}")
        seen_post_ids.add(post_id)

    output_label = str(request.get("output_label", "") or "").strip()
    if output_label and not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", output_label):
        raise ProjectPreflightError("INVALID_OUTPUT_LABEL", "output_label contains unsupported characters")

    return {
        "protocol": "EVAL_MEDIA_REQUEST",
        "request_id": request_id,
        "target_count": len(targets),
    }


def validate_eval_ocr(title: str, body: str) -> dict[str, object]:
    """Validate `[EVAL_OCR_REQUEST]`, including the upstream artifact reference fields."""
    prefix = "[EVAL_OCR_REQUEST]"
    request_id = parse_request_id(title, prefix)
    request = parse_json_object(body)

    run_id = str(request.get("source_run_id", "") or "").strip()
    artifact_name = str(request.get("source_artifact_name", "") or "").strip()
    if not re.fullmatch(r"\d+", run_id):
        raise ProjectPreflightError("MISSING_SOURCE_RUN", "source_run_id must be a GitHub Actions run id")
    if not ARTIFACT_NAME_PATTERN.fullmatch(artifact_name):
        raise ProjectPreflightError(
            "MISSING_SOURCE_ARTIFACT",
            "source_artifact_name is required and must use only ASCII letters, digits, dot, underscore or hyphen",
        )

    expected_venues = request.get("expected_venues")
    if expected_venues not in (None, 2, 3):
        raise ProjectPreflightError("INVALID_EXPECTED_VENUES", "expected_venues must be 2, 3, or omitted")

    return {
        "protocol": "EVAL_OCR_REQUEST",
        "request_id": request_id,
        "source_run_id": int(run_id),
        "source_artifact_name": artifact_name,
    }


def validate_eval_paci_enrich(title: str, body: str) -> dict[str, object]:
    """Validate `[EVAL_PACI_ENRICH_REQUEST]` including the embedded OCR CSV envelope."""
    prefix = "[EVAL_PACI_ENRICH_REQUEST]"
    request_id = parse_request_id(title, prefix)
    request = parse_json_object(body)

    payload = str(request.get("eval_csv_gzip_b64", "") or "").strip()
    if not payload:
        raise ProjectPreflightError("MISSING_EVAL_CSV", "eval_csv_gzip_b64 is required")
    if len(payload) > 120000:
        raise ProjectPreflightError("EVAL_CSV_TOO_LARGE", "eval_csv_gzip_b64 is too large")
    try:
        compressed = base64.b64decode(payload, validate=True)
        raw = gzip.decompress(compressed)
    except Exception as exc:
        raise ProjectPreflightError("INVALID_EVAL_CSV_PAYLOAD", f"cannot decode eval_csv_gzip_b64: {type(exc).__name__}") from exc
    if len(raw) > 2_000_000:
        raise ProjectPreflightError("EVAL_CSV_TOO_LARGE", "decoded Eval CSV is too large")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProjectPreflightError("INVALID_EVAL_CSV_ENCODING", "Eval CSV must be UTF-8/UTF-8-BOM") from exc

    reader = csv.DictReader(StringIO(text))
    required_columns = ["date", "venue", "race_no", "horse_no", "eval"]
    if reader.fieldnames is None:
        raise ProjectPreflightError("MISSING_EVAL_CSV_HEADER", "Eval CSV has no header")
    missing = [name for name in required_columns if name not in reader.fieldnames]
    if missing:
        raise ProjectPreflightError("MISSING_EVAL_CSV_COLUMN", "Eval CSV missing required columns: " + ", ".join(missing))
    rows = list(reader)
    if not rows:
        raise ProjectPreflightError("EMPTY_EVAL_CSV", "Eval CSV has no data rows")

    normalized_dates: set[str] = set()
    for row in rows:
        date_value = str(row.get("date", "") or "").strip()
        valid = False
        for date_format in ("%Y-%m-%d", "%Y%m%d"):
            try:
                normalized_dates.add(datetime.strptime(date_value, date_format).date().isoformat())
                valid = True
                break
            except ValueError:
                continue
        if not valid:
            raise ProjectPreflightError("INVALID_EVAL_DATE", f"invalid Eval date: {date_value!r}")
    if len(normalized_dates) > 10:
        raise ProjectPreflightError("TOO_MANY_EVAL_DATES", "maximum is 10 dates per request")

    fail_on_unmatched = request.get("fail_on_unmatched", True)
    if not isinstance(fail_on_unmatched, bool):
        raise ProjectPreflightError("INVALID_FAIL_ON_UNMATCHED", "fail_on_unmatched must be true or false")

    output_name = str(request.get("output_name", "") or "").strip()
    if output_name and not SIMPLE_CSV_NAME_PATTERN.fullmatch(output_name):
        raise ProjectPreflightError("INVALID_OUTPUT_NAME", "output_name must be a simple ASCII .csv file name")

    return {
        "protocol": "EVAL_PACI_ENRICH_REQUEST",
        "request_id": request_id,
        "input_rows": len(rows),
        "date_count": len(normalized_dates),
    }


def validate_jra_results(title: str, body: str) -> dict[str, object]:
    """Validate `[JRA_RESULTS_REQUEST]`."""
    prefix = "[JRA_RESULTS_REQUEST]"
    request_id = parse_request_id(title, prefix)
    request = parse_json_object(body)

    interval_value = request.get("request_interval_seconds", 0.7)
    try:
        interval = float(interval_value)
    except (TypeError, ValueError) as exc:
        raise ProjectPreflightError("INVALID_INTERVAL", "request_interval_seconds must be numeric") from exc
    if interval < 0:
        raise ProjectPreflightError("INVALID_INTERVAL", "request_interval_seconds must be >= 0")

    dates_value = request.get("dates", "")
    if isinstance(dates_value, list):
        dates_raw = " ".join(str(item) for item in dates_value)
    else:
        dates_raw = str(dates_value or "")
    date_from = str(request.get("date_from", "") or "").strip()
    date_to = str(request.get("date_to", "") or "").strip()

    if dates_raw.strip():
        if date_from or date_to:
            raise ProjectPreflightError("DATE_MODE_CONFLICT", "use either dates or date_from/date_to, not both")
        dates = [item for item in re.split(r"[\s,]+", dates_raw.strip()) if item]
        if not dates:
            raise ProjectPreflightError("MISSING_DATES", "dates is empty")
        for date_value in dates:
            parse_date(date_value, ("%Y-%m-%d",), "dates item")
        mode = "dates"
        count = len(dates)
    else:
        if not date_from or not date_to:
            raise ProjectPreflightError("MISSING_DATE_RANGE", "specify dates or both date_from and date_to")
        start = datetime.strptime(parse_date(date_from, ("%Y-%m-%d",), "date_from"), "%Y-%m-%d").date()
        end = datetime.strptime(parse_date(date_to, ("%Y-%m-%d",), "date_to"), "%Y-%m-%d").date()
        if start > end:
            raise ProjectPreflightError("INVALID_DATE_RANGE", "date_from must be <= date_to")
        mode = "range"
        count = (end - start).days + 1

    return {
        "protocol": "JRA_RESULTS_REQUEST",
        "request_id": request_id,
        "mode": mode,
        "date_count": count,
    }


def validate_racenote(title: str, body: str) -> dict[str, object]:
    """Validate `[RACENOTE_REQUEST]`."""
    prefix = "[RACENOTE_REQUEST]"
    request_id = parse_request_id(title, prefix)
    request = parse_json_object(body)

    raw_date = str(request.get("date", "")).replace("-", "").replace("/", "").strip()
    parse_date(raw_date, ("%Y%m%d",), "date")

    venue_value = request.get("venue")
    venue = None if venue_value is None else str(venue_value).strip() or None
    race_value = request.get("race")
    race = None
    if race_value is not None:
        try:
            race = int(race_value)
        except (TypeError, ValueError) as exc:
            raise ProjectPreflightError("INVALID_RACE", "race must be an integer") from exc
        if venue is None:
            raise ProjectPreflightError("MISSING_VENUE", "race requires venue")
        if not 1 <= race <= 12:
            raise ProjectPreflightError("INVALID_RACE", "race must be 1..12")

    analysis_url = str(request.get("analysis_url", "") or "").strip()
    mart_url = str(request.get("mart_url", "") or "").strip()
    if not analysis_url.startswith(DRIVE_URL_PREFIX):
        raise ProjectPreflightError("MISSING_ANALYSIS_URL", "analysis_url must be a Google Drive URL")
    if not mart_url.startswith(DRIVE_URL_PREFIX):
        raise ProjectPreflightError("MISSING_MART_URL", "mart_url must be a Google Drive URL")

    try:
        stats_window_years = int(request.get("stats_window_years", 5))
    except (TypeError, ValueError) as exc:
        raise ProjectPreflightError("INVALID_STATS_WINDOW", "stats_window_years must be an integer") from exc
    if not 1 <= stats_window_years <= 10:
        raise ProjectPreflightError("INVALID_STATS_WINDOW", "stats_window_years must be 1..10")

    raw_urls = request.get("raw_urls", {}) or {}
    if not isinstance(raw_urls, dict):
        raise ProjectPreflightError("INVALID_RAW_URLS", "raw_urls must be an object")
    for raw_key, raw_url in raw_urls.items():
        key = str(raw_key).strip().upper()
        if not re.fullmatch(r"(BAC|KYI|CHA|CYB|SED|SKB)_\d{4}", key):
            raise ProjectPreflightError("INVALID_RAW_URL_KEY", f"invalid raw_urls key: {key}")
        if not str(raw_url).strip().startswith(DRIVE_URL_PREFIX):
            raise ProjectPreflightError("INVALID_RAW_URL", f"raw_urls[{key}] must be a Google Drive URL")

    return {
        "protocol": "RACENOTE_REQUEST",
        "request_id": request_id,
        "date": raw_date,
        "venue": venue,
        "race": race,
        "raw_url_count": len(raw_urls),
    }


def validate_project_request(title: str, body: str) -> dict[str, object] | None:
    """Validate a recognized high-frequency project Issue, or return None."""
    prefix = infer_project_prefix(title)
    if prefix is None:
        return None
    validators = {
        "[BOATRACE_RACELIST_REQUEST]": validate_boatrace_racelist,
        "[BOATRACE_PRE_RACE_REQUEST]": validate_boatrace_pre_race,
        "[EVAL_MEDIA_REQUEST]": validate_eval_media,
        "[EVAL_OCR_REQUEST]": validate_eval_ocr,
        "[EVAL_PACI_ENRICH_REQUEST]": validate_eval_paci_enrich,
        "[JRA_RESULTS_REQUEST]": validate_jra_results,
        "[RACENOTE_REQUEST]": validate_racenote,
    }
    return validators[prefix](title, body)
