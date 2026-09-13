#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build an audited Eval PWA submission CSV from an Eval completed CSV.

This module owns only transport/audit behavior for analysis comments. Research
condition selection and comment wording remain owned by the Eval research side
and are supplied as a small JSON overlay.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys
from typing import Any


VERSION = "0.1.0"
DEFAULT_ANALYSIS_VERSION = "phase2-comment-v0.1"
ANALYSIS_COLUMNS = (
    "eval_analysis_status",
    "eval_analysis_codes",
    "eval_analysis_title",
    "eval_analysis_comment",
    "eval_analysis_version",
    "eval_analysis_asof",
)
REQUIRED_SOURCE_COLUMNS = (
    "date",
    "venue_code",
    "race_no",
    "horse_no",
    "eval",
)
VALID_STATUSES = {"NONE", "WATCH", "MATCH"}


class EvalPwaSubmissionError(RuntimeError):
    """Raised when a PWA submission cannot be built without ambiguity."""


def canonical_key(row: dict[str, Any]) -> tuple[str, str, int, int]:
    """Return the stable daily horse key used by the Newspaper Eval join."""
    try:
        date_value = str(row["date"]).strip()
        venue_code = str(row["venue_code"]).strip().zfill(2)
        race_no = int(str(row["race_no"]).strip())
        horse_no = int(str(row["horse_no"]).strip())
    except (KeyError, TypeError, ValueError) as exc:
        raise EvalPwaSubmissionError(f"invalid canonical key row: {row}") from exc

    if not date_value or not venue_code:
        raise EvalPwaSubmissionError(f"blank canonical key row: {row}")
    if race_no < 1 or race_no > 12 or horse_no < 1:
        raise EvalPwaSubmissionError(f"out-of-range canonical key row: {row}")
    return date_value, venue_code, race_no, horse_no


def normalize_codes(value: Any) -> list[str]:
    """Normalize an analysis code field to a duplicate-free ordered list."""
    raw_codes: list[str] = []
    if value is None:
        return raw_codes
    if isinstance(value, list):
        for item in value:
            raw_codes.append(str(item).strip())
    else:
        for item in str(value).split(";"):
            raw_codes.append(item.strip())

    output: list[str] = []
    seen: set[str] = set()
    for code in raw_codes:
        if not code:
            continue
        if code in seen:
            continue
        seen.add(code)
        output.append(code)
    return output


def validate_analysis_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize one research-owned analysis overlay entry."""
    key = canonical_key(entry)
    status = str(entry.get("status") or "").strip().upper()
    if status not in VALID_STATUSES:
        raise EvalPwaSubmissionError(
            f"invalid analysis status for {key}: {status!r}"
        )

    codes = normalize_codes(entry.get("codes"))
    title = str(entry.get("title") or "").strip()
    comment = str(entry.get("comment") or "").strip()

    if status == "NONE":
        if codes or title or comment:
            raise EvalPwaSubmissionError(
                f"NONE analysis must not carry visible content: {key}"
            )
    else:
        if not codes:
            raise EvalPwaSubmissionError(
                f"{status} analysis requires at least one code: {key}"
            )
        if not title or not comment:
            raise EvalPwaSubmissionError(
                f"{status} analysis requires title and comment: {key}"
            )

    return {
        "key": key,
        "status": status,
        "codes": codes,
        "title": title,
        "comment": comment,
    }


def load_analysis(path: Path | None) -> dict[tuple[str, str, int, int], dict[str, Any]]:
    """Load the research-owned analysis overlay by canonical key."""
    if path is None:
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        entries = raw.get("entries")
    else:
        entries = raw
    if not isinstance(entries, list):
        raise EvalPwaSubmissionError(
            "analysis JSON must be an array or an object with entries[]"
        )

    output: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            raise EvalPwaSubmissionError("analysis entry must be an object")
        entry = validate_analysis_entry(raw_entry)
        key = entry["key"]
        if key in output:
            raise EvalPwaSubmissionError(f"duplicate analysis key: {key}")
        output[key] = entry
    return output


def read_source(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read and validate the completed Eval CSV without changing source values."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    missing = [column for column in REQUIRED_SOURCE_COLUMNS if column not in fieldnames]
    if missing:
        raise EvalPwaSubmissionError(
            f"Eval completed CSV missing required columns: {missing}"
        )

    collisions = [column for column in ANALYSIS_COLUMNS if column in fieldnames]
    if collisions:
        raise EvalPwaSubmissionError(
            f"source CSV already contains analysis columns: {collisions}"
        )

    if not rows:
        raise EvalPwaSubmissionError("Eval completed CSV has no data rows")

    seen: set[tuple[str, str, int, int]] = set()
    for row in rows:
        key = canonical_key(row)
        if key in seen:
            raise EvalPwaSubmissionError(f"duplicate Eval completed key: {key}")
        seen.add(key)
    return fieldnames, rows


def build_submission(
    source_path: Path,
    analysis_path: Path | None,
    analysis_version: str,
    asof: str,
) -> tuple[list[str], list[dict[str, str]], dict[str, Any]]:
    """Append analysis contract columns while preserving every source row/value."""
    if not analysis_version.strip():
        raise EvalPwaSubmissionError("analysis version must not be blank")
    if not asof.strip():
        raise EvalPwaSubmissionError("analysis as-of must not be blank")

    source_columns, source_rows = read_source(source_path)
    analysis = load_analysis(analysis_path)
    source_keys = {canonical_key(row) for row in source_rows}
    unknown_keys = sorted(set(analysis) - source_keys)
    if unknown_keys:
        raise EvalPwaSubmissionError(
            f"analysis contains keys absent from source: {unknown_keys[:5]}"
        )

    output_rows: list[dict[str, str]] = []
    status_counts: Counter[str] = Counter()
    code_counts: Counter[str] = Counter()

    for source_row in source_rows:
        key = canonical_key(source_row)
        entry = analysis.get(key)

        output = dict(source_row)
        if entry is None:
            output["eval_analysis_status"] = "NONE"
            output["eval_analysis_codes"] = ""
            output["eval_analysis_title"] = ""
            output["eval_analysis_comment"] = ""
        else:
            output["eval_analysis_status"] = str(entry["status"])
            output["eval_analysis_codes"] = ";".join(entry["codes"])
            output["eval_analysis_title"] = str(entry["title"])
            output["eval_analysis_comment"] = str(entry["comment"])
            for code in entry["codes"]:
                code_counts[str(code)] += 1

        output["eval_analysis_version"] = analysis_version
        output["eval_analysis_asof"] = asof
        status_counts[output["eval_analysis_status"]] += 1
        output_rows.append(output)

    output_columns = source_columns + list(ANALYSIS_COLUMNS)
    audit: dict[str, Any] = {
        "status": "success",
        "schema_version": VERSION,
        "analysis_version": analysis_version,
        "analysis_asof": asof,
        "source_file": source_path.name,
        "analysis_file": analysis_path.name if analysis_path is not None else None,
        "source_rows": len(source_rows),
        "output_rows": len(output_rows),
        "highlighted_rows": status_counts["WATCH"] + status_counts["MATCH"],
        "status_counts": dict(sorted(status_counts.items())),
        "code_counts": dict(sorted(code_counts.items())),
        "source_column_count": len(source_columns),
        "output_column_count": len(output_columns),
        "analysis_columns": list(ANALYSIS_COLUMNS),
    }
    return output_columns, output_rows, audit


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    """Write the PWA submission CSV in Excel-friendly UTF-8 BOM form."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_audit(path: Path, audit: dict[str, Any]) -> None:
    """Write a deterministic JSON audit for the submission build."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Build an audited Eval PWA submission CSV."
    )
    parser.add_argument("--eval-csv", type=Path, required=True)
    parser.add_argument("--analysis-json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument(
        "--analysis-version",
        default=DEFAULT_ANALYSIS_VERSION,
    )
    parser.add_argument("--asof", required=True)
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main() -> int:
    """Run the audited PWA submission build."""
    parser = build_argument_parser()
    args = parser.parse_args()
    try:
        columns, rows, audit = build_submission(
            args.eval_csv,
            args.analysis_json,
            args.analysis_version,
            args.asof,
        )
        write_csv(args.output, columns, rows)
        if args.audit_json is not None:
            write_audit(args.audit_json, audit)
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0
    except (EvalPwaSubmissionError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
