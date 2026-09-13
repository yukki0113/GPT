"""Authenticated Drive-to-Sheets adapter for a Chat-triggered FT2 import.

This script is intended for GitHub Actions because it consumes a service
account secret. It discovers or validates the four immutable daily CSVs,
executes the repository's deterministic normalizer, writes all ledger views,
verifies the written generation, and only then marks the day complete.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from forward_trial_analysis_import import (
    ATOMIC_AGGREGATE_TABS, IMPORT_COMPLETE, RULE_VERSION,
    ForwardTrialValidationError, build_payload,
)
from forward_trial_chat_ledger import build_atomic_payload, values_rows

DEFAULT_SPREADSHEET_ID = "1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM"
SOURCE_KINDS = {
    "prediction": "事前予想",
    "sales": "販売選別",
    "result": "結果",
    "racecard": "公式出走表",
}
CURRENT_SHEETS = (
    "FT2_全R明細", "FT2_取込管理", "FT2_開催メタ", "販売記事台帳", "販売掲載明細",
)
ERROR_TOKENS = ("#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#N/A", "#NUM!", "#NULL!")


def credentials_from_environment():
    """Build Google credentials from the configured Actions secret."""
    from google.oauth2 import service_account

    raw = os.environ.get("GPT_GDRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise ForwardTrialValidationError("GPT_GDRIVE_SERVICE_ACCOUNT_JSON is not configured")
    info = json.loads(raw)
    scopes = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/spreadsheets"]
    return service_account.Credentials.from_service_account_info(info, scopes=scopes)


def services(credentials):
    """Create Drive and Sheets API clients."""
    from googleapiclient.discovery import build

    return (build("drive", "v3", credentials=credentials, cache_discovery=False),
            build("sheets", "v4", credentials=credentials, cache_discovery=False))


def list_source_files(drive, folder_id: str, target_date: str) -> list[dict[str, object]]:
    query = f"'{folder_id}' in parents and trashed = false and name contains '{target_date}'"
    response = drive.files().list(q=query, fields="files(id,name,mimeType,modifiedTime,size,md5Checksum)",
                                  orderBy="modifiedTime desc", pageSize=1000).execute()
    return list(response.get("files", []))


def resolve_source_files(files: Sequence[Mapping[str, object]], target_date: str,
                         explicit_ids: Mapping[str, str] | None = None) -> dict[str, dict[str, object]]:
    """Resolve exactly one immutable CSV per source kind; ambiguity fails closed."""
    explicit_ids = explicit_ids or {}
    by_id = {str(item["id"]): item for item in files}
    resolved: dict[str, dict[str, object]] = {}
    for kind, marker in SOURCE_KINDS.items():
        requested_id = str(explicit_ids.get(kind, "")).strip()
        if requested_id:
            if requested_id not in by_id:
                raise ForwardTrialValidationError(f"explicit {kind} file is not in the source folder")
            candidates = [by_id[requested_id]]
        else:
            candidates = [item for item in files if marker in str(item.get("name", ""))]
            if kind == "prediction":
                candidates = [item for item in candidates if "根拠" not in str(item.get("name", ""))]
        candidates = [item for item in candidates
                      if str(item.get("name", "")).startswith(target_date) and str(item.get("name", "")).lower().endswith(".csv")]
        if len(candidates) != 1:
            names = [str(item.get("name", "")) for item in candidates]
            raise ForwardTrialValidationError(f"{kind} source must resolve to exactly one CSV: {names}")
        resolved[kind] = dict(candidates[0])
    if len({item["id"] for item in resolved.values()}) != 4:
        raise ForwardTrialValidationError("the four source assets must have distinct file IDs")
    return resolved


def download_sources(drive, resolved: Mapping[str, Mapping[str, object]], directory: Path) -> dict[str, Path]:
    """Download sources and record content SHA256 values."""
    paths: dict[str, Path] = {}
    for kind, item in resolved.items():
        content = drive.files().get_media(fileId=item["id"]).execute()
        path = directory / str(item["name"])
        path.write_bytes(content)
        item["sha256"] = hashlib.sha256(content).hexdigest()
        paths[kind] = path
    return paths


def current_values(sheets, spreadsheet_id: str) -> dict[str, dict[str, object]]:
    """Read only the source-of-truth tabs needed to build the transaction."""
    output: dict[str, dict[str, object]] = {}
    for title in CURRENT_SHEETS:
        result = sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"'{title}'", valueRenderOption="UNFORMATTED_VALUE",
            dateTimeRenderOption="FORMATTED_STRING").execute()
        output[title] = {"values": result.get("values", [])}
    return output


def sheet_metadata(sheets, spreadsheet_id: str) -> dict[str, dict[str, object]]:
    response = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id, includeGridData=False).execute()
    return {item["properties"]["title"]: {
        "sheet_id": item["properties"]["sheetId"],
        "row_count": item["properties"].get("gridProperties", {}).get("rowCount", 1),
        "column_count": item["properties"].get("gridProperties", {}).get("columnCount", 1),
    } for item in response.get("sheets", [])}


def column_name(count: int) -> str:
    result = ""
    while count:
        count, remainder = divmod(count - 1, 26)
        result = chr(65 + remainder) + result
    return result


def prepare_grids(sheets, spreadsheet_id: str, payload: Mapping[str, object],
                  metadata: Mapping[str, Mapping[str, object]]) -> None:
    requests = []
    for title, content in payload["sheets"].items():
        if title not in metadata:
            raise ForwardTrialValidationError(f"missing destination sheet: {title}")
        required_rows = len(content["rows"]) + 1
        required_columns = len(content["headers"])
        current = metadata[title]
        if required_rows > int(current["row_count"]):
            requests.append({"appendDimension": {"sheetId": current["sheet_id"], "dimension": "ROWS",
                                                  "length": required_rows - int(current["row_count"])}})
        if required_columns > int(current["column_count"]):
            requests.append({"appendDimension": {"sheetId": current["sheet_id"], "dimension": "COLUMNS",
                                                  "length": required_columns - int(current["column_count"])}})
    if requests:
        sheets.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def replace_values(sheets, spreadsheet_id: str, payload: Mapping[str, object]) -> None:
    """Clear and replace all generated tabs while management remains non-complete."""
    ranges = [f"'{title}'" for title in payload["sheets"]]
    sheets.spreadsheets().values().batchClear(spreadsheetId=spreadsheet_id, body={"ranges": ranges}).execute()
    data = []
    for title, content in payload["sheets"].items():
        values = [list(content["headers"])] + list(content["rows"])
        last_column = column_name(len(content["headers"]))
        data.append({"range": f"'{title}'!A1:{last_column}{len(values)}", "majorDimension": "ROWS", "values": values})
    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"valueInputOption": "RAW", "data": data}).execute()


def management_state_payload(payload: Mapping[str, object], state: str) -> dict[str, object]:
    prepared = copy.deepcopy(payload)
    management = prepared["sheets"]["FT2_取込管理"]
    headers = list(management["headers"])
    date_index = headers.index("対象日")
    state_index = headers.index("取込状態")
    for row in management["rows"]:
        if str(row[date_index]) == str(payload["target_date"]):
            row[state_index] = state
    return prepared


def verify_written_generation(sheets, spreadsheet_id: str, payload: Mapping[str, object]) -> dict[str, object]:
    """Verify counts, atomic generation, legacy mirror, and formula-error absence."""
    actual: dict[str, list[list[object]]] = {}
    error_cells = []
    for title, expected in payload["sheets"].items():
        result = sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"'{title}'", valueRenderOption="UNFORMATTED_VALUE",
            dateTimeRenderOption="FORMATTED_STRING").execute()
        values = result.get("values", [])
        actual[title] = values
        for row_index, row in enumerate(values, 1):
            for column_index, value in enumerate(row, 1):
                if isinstance(value, str) and any(token in value for token in ERROR_TOKENS):
                    error_cells.append(f"{title}!R{row_index}C{column_index}:{value}")
        expected_rows = len(expected["rows"]) + 1
        if len(values) != expected_rows:
            raise ForwardTrialValidationError(f"post-write row count mismatch {title}: {len(values)} != {expected_rows}")
    detail = values_rows(actual["FT2_全R明細"])
    if len(detail) != len({str(row["FT2_ID"]) for row in detail}):
        raise ForwardTrialValidationError("post-write FT2 duplicate detected")
    audit = values_rows(actual["FT2_集計監査"])
    generation_ids = {str(row["aggregate_generation_id"]) for row in audit}
    if generation_ids != {str(payload["aggregate_generation_id"])} or len(audit) != len(ATOMIC_AGGREGATE_TABS):
        raise ForwardTrialValidationError("post-write Atomic Aggregate Set generation mismatch")
    if error_cells:
        raise ForwardTrialValidationError("spreadsheet formula errors: " + ", ".join(error_cells[:20]))
    return {"raw_R": len(detail), "genuine_R": sum(row["forward_status"] == "GENUINE" for row in detail),
            "contaminated_R": sum(row["forward_status"] == "CONTAMINATED" for row in detail),
            "duplicate_R": 0, "formula_errors": 0, "atomic_tabs": len(audit)}


def finalize_management(sheets, spreadsheet_id: str, payload: Mapping[str, object]) -> None:
    management = payload["sheets"]["FT2_取込管理"]
    headers = list(management["headers"])
    date_index = headers.index("対象日")
    state_index = headers.index("取込状態")
    target_row = next(index for index, row in enumerate(management["rows"], 2)
                      if str(row[date_index]) == str(payload["target_date"]))
    cell = f"{column_name(state_index + 1)}{target_row}"
    sheets.spreadsheets().values().update(spreadsheetId=spreadsheet_id,
        range=f"'FT2_取込管理'!{cell}", valueInputOption="RAW", body={"values": [[IMPORT_COMPLETE]]}).execute()
    check = sheets.spreadsheets().values().get(spreadsheetId=spreadsheet_id,
        range=f"'FT2_取込管理'!{cell}", valueRenderOption="FORMATTED_VALUE").execute()
    if check.get("values") != [[IMPORT_COMPLETE]]:
        raise ForwardTrialValidationError("management completion state did not persist")


def run_import(date: str, folder_id: str, spreadsheet_id: str,
               explicit_ids: Mapping[str, str] | None, output_path: Path, dry_run: bool = False) -> dict[str, object]:
    if not re.fullmatch(r"\d{8}", date):
        raise ForwardTrialValidationError("date must be YYYYMMDD")
    datetime.strptime(date, "%Y%m%d")
    credentials = credentials_from_environment()
    drive, sheets = services(credentials)
    process_datetime = datetime.now().astimezone().isoformat(timespec="seconds")
    with tempfile.TemporaryDirectory(prefix="ft2-chat-import-") as temporary:
        directory = Path(temporary)
        files = list_source_files(drive, folder_id, date)
        resolved = resolve_source_files(files, date, explicit_ids)
        paths = download_sources(drive, resolved, directory)
        manifest = {"existing_sales_crosscheck": True, "dates": [{
            "date": date,
            **{kind: {"path": path.name, "file_id": resolved[kind]["id"]} for kind, path in paths.items()},
        }]}
        manifest_path = directory / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        daily_payload = build_payload(manifest_path, process_datetime)
        current = current_values(sheets, spreadsheet_id)
        rows = lambda title: values_rows(current.get(title, {}).get("values", []))
        payload = build_atomic_payload(
            rows("FT2_全R明細"), daily_payload, process_datetime, True,
            rows("FT2_取込管理"), rows("FT2_開催メタ"), rows("販売記事台帳"), rows("販売掲載明細"),
        )
        if payload["state"] != IMPORT_COMPLETE:
            raise ForwardTrialValidationError(f"completion gates failed: {payload['completion_checks']}")
        report = {"status": "dry-run" if dry_run else "success", "target_date": payload["target_date"],
                  "spreadsheet_id": spreadsheet_id, "aggregate_generation_id": payload["aggregate_generation_id"],
                  "sources": {kind: {key: item.get(key) for key in ("id", "name", "sha256")} for kind, item in resolved.items()},
                  "completion_checks": payload["completion_checks"]}
        if not dry_run:
            prepared = management_state_payload(payload, "集計再生成中")
            metadata = sheet_metadata(sheets, spreadsheet_id)
            prepare_grids(sheets, spreadsheet_id, prepared, metadata)
            replace_values(sheets, spreadsheet_id, prepared)
            report["verification"] = verify_written_generation(sheets, spreadsheet_id, payload)
            finalize_management(sheets, spreadsheet_id, payload)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Import one immutable FT2 day into the canonical Google Sheet")
    parser.add_argument("--date", required=True)
    parser.add_argument("--folder-id", required=True)
    parser.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    parser.add_argument("--file-ids-json", help="optional JSON mapping prediction/sales/result/racecard to Drive IDs")
    parser.add_argument("--output", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    explicit_ids = json.loads(args.file_ids_json) if args.file_ids_json else None
    output = Path(args.output)
    try:
        run_import(args.date, args.folder_id, args.spreadsheet_id, explicit_ids, output, args.dry_run)
    except Exception as exc:
        failure = {"status": "failure", "failure_class": "DOMAIN_VALIDATION_FAILED"
                   if isinstance(exc, ForwardTrialValidationError) else "IMPLEMENTATION_ERROR",
                   "error_code": type(exc).__name__, "message": str(exc), "retryable": False}
        output.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
