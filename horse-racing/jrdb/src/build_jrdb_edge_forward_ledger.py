#!/usr/bin/env python3
"""Append immutable daily JRDB Edge forward settlements to a cumulative SQLite ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import evaluate_jrdb_edge_forward as forward_eval

VERSION = "0.1.0"
SCHEMA_VERSION = "0.1"
RUNNER_ID_RE = re.compile(r"^([0-9A-Za-z]{8}):(\d{2})$")


class LedgerError(ValueError):
    """Raised when immutable forward-ledger contracts are violated."""


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS forward_day(
  race_date TEXT PRIMARY KEY,
  source_sha256 TEXT NOT NULL,
  semantic_sha256 TEXT NOT NULL,
  occurrence_count INTEGER NOT NULL CHECK(occurrence_count >= 0),
  ledger_version TEXT NOT NULL,
  schema_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS forward_occurrence(
  race_date TEXT NOT NULL,
  runner_identity TEXT NOT NULL,
  edge_id TEXT NOT NULL,
  family TEXT NOT NULL,
  polarity TEXT NOT NULL,
  status TEXT NOT NULL,
  review_due INTEGER NOT NULL CHECK(review_due IN (0,1)),
  registry_version TEXT,
  occurrence_json TEXT NOT NULL,
  PRIMARY KEY(race_date,runner_identity,edge_id),
  FOREIGN KEY(race_date) REFERENCES forward_day(race_date)
);
CREATE INDEX IF NOT EXISTS idx_forward_edge ON forward_occurrence(edge_id,race_date);
"""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _iso(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise LedgerError(f"{field} must be ISO date text")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise LedgerError(f"{field} must be ISO date text") from exc


def _text(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f"forward occurrence requires non-empty {field}")
    return value.strip()


def _validate(row: Any, line_no: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise LedgerError(f"audit line {line_no} is not an object")
    normalized = dict(row)
    normalized["race_date"] = _iso(row.get("race_date"), "race_date")
    normalized["runner_identity"] = _text(row, "runner_identity")
    normalized["edge_id"] = _text(row, "edge_id")
    normalized["family"] = _text(row, "family")
    normalized["polarity"] = _text(row, "polarity")
    normalized["status"] = _text(row, "status")
    normalized["eligibility"] = _text(row, "eligibility")
    normalized["review_due"] = bool(row.get("review_due"))
    if not isinstance(row.get("evidence"), dict) or not isinstance(row.get("outcome"), dict):
        raise LedgerError(f"audit line {line_no} requires evidence/outcome objects")

    match = RUNNER_ID_RE.fullmatch(normalized["runner_identity"])
    if not match:
        raise LedgerError(f"audit line {line_no} has invalid runner_identity")
    outcome = row["outcome"]
    try:
        outcome_id = (str(outcome.get("race_key") or ""), int(outcome.get("horse_no")))
    except (TypeError, ValueError) as exc:
        raise LedgerError(f"audit line {line_no} outcome has invalid horse_no") from exc
    if outcome_id != (match.group(1), int(match.group(2))):
        raise LedgerError(f"audit line {line_no} runner/outcome identity mismatch")
    if outcome.get("race_date") not in (None, "") and _iso(outcome["race_date"], "outcome.race_date") != normalized["race_date"]:
        raise LedgerError(f"audit line {line_no} race_date mismatch")
    return normalized


def load_daily_audit(path: str | Path, *, race_date: str | None = None) -> tuple[str, list[dict[str, Any]], str, str]:
    raw = Path(path).read_bytes()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = _validate(json.loads(line), line_no)
        except json.JSONDecodeError as exc:
            raise LedgerError(f"audit line {line_no} is invalid JSON") from exc
        identity = (row["runner_identity"], row["edge_id"])
        if identity in seen:
            raise LedgerError(f"duplicate forward occurrence in audit: {identity}")
        seen.add(identity)
        rows.append(row)

    dates = {row["race_date"] for row in rows}
    explicit = _iso(race_date, "race_date") if race_date is not None else None
    if len(dates) > 1:
        raise LedgerError(f"daily audit contains multiple race dates: {sorted(dates)}")
    if rows:
        day = next(iter(dates))
        if explicit is not None and explicit != day:
            raise LedgerError(f"explicit race_date {explicit} != audit race_date {day}")
    elif explicit is not None:
        day = explicit
    else:
        raise LedgerError("empty daily audit requires explicit race_date")

    semantic = _canonical({"race_date": day, "occurrences": sorted(_canonical(row) for row in rows)}).encode()
    return day, rows, hashlib.sha256(raw).hexdigest(), hashlib.sha256(semantic).hexdigest()


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)


def import_daily_audit(connection: sqlite3.Connection, path: str | Path, *, race_date: str | None = None) -> dict[str, Any]:
    initialize(connection)
    day, rows, source_sha, semantic_sha = load_daily_audit(path, race_date=race_date)
    existing = connection.execute(
        "SELECT semantic_sha256,occurrence_count FROM forward_day WHERE race_date=?", (day,)
    ).fetchone()
    if existing:
        if existing[0] == semantic_sha:
            return {"status": "NOOP", "race_date": day, "occurrences": existing[1], "semantic_sha256": semantic_sha}
        raise LedgerError(f"immutable forward day conflict for {day}")

    try:
        connection.execute("BEGIN")
        connection.execute(
            "INSERT INTO forward_day VALUES(?,?,?,?,?,?)",
            (day, source_sha, semantic_sha, len(rows), VERSION, SCHEMA_VERSION),
        )
        for row in rows:
            connection.execute(
                "INSERT INTO forward_occurrence VALUES(?,?,?,?,?,?,?,?,?)",
                (day, row["runner_identity"], row["edge_id"], row["family"], row["polarity"], row["status"],
                 int(row["review_due"]), row.get("registry_version"), _canonical(row)),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"status": "IMPORTED", "race_date": day, "occurrences": len(rows),
            "source_sha256": source_sha, "semantic_sha256": semantic_sha}


def _with_drift(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = forward_eval.summarize_occurrences(rows)
    if result.get("eligible"):
        historical_rate = result.get("historical_place_rate_weighted")
        historical_roi = result.get("historical_place_roi_weighted")
        result["place_rate_vs_historical"] = (
            result["place_rate"] - historical_rate if historical_rate is not None else None
        )
        result["place_roi_vs_historical"] = (
            result["place_roi"] - historical_roi if historical_roi is not None else None
        )
    return result


def summarize(connection: sqlite3.Connection, *, from_date: str | None = None, to_date: str | None = None) -> dict[str, Any]:
    initialize(connection)
    clauses, params = [], []
    if from_date is not None:
        clauses.append("race_date>=?")
        params.append(_iso(from_date, "from_date"))
    if to_date is not None:
        clauses.append("race_date<=?")
        params.append(_iso(to_date, "to_date"))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = [json.loads(row[0]) for row in connection.execute(
        "SELECT occurrence_json FROM forward_occurrence" + where + " ORDER BY race_date,runner_identity,edge_id", params
    )]
    day_rows = connection.execute(
        "SELECT race_date,occurrence_count FROM forward_day" + where + " ORDER BY race_date", params
    ).fetchall()

    def grouped(field: str) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            buckets.setdefault(str(row.get(field)), []).append(row)
        return {key: _with_drift(value) for key, value in sorted(buckets.items())}

    edge_registry: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = f"{row['edge_id']}|{row.get('registry_version') or 'UNKNOWN'}"
        edge_registry.setdefault(key, []).append(row)
    dates = [row[0] for row in day_rows]
    return {
        "status": "PASS", "ledger_version": VERSION, "schema_version": SCHEMA_VERSION,
        "date_range": {"from": dates[0] if dates else None, "to": dates[-1] if dates else None,
                       "days": len(dates), "zero_match_days": sum(row[1] == 0 for row in day_rows)},
        "overall": _with_drift(rows),
        "by_edge": grouped("edge_id"),
        "by_edge_registry": {key: _with_drift(value) for key, value in sorted(edge_registry.items())},
        "by_family": grouped("family"), "by_polarity": grouped("polarity"),
        "by_review_due": grouped("review_due"), "by_registry_version": grouped("registry_version"),
    }


def run(*, ledger_path: str | Path, audit_jsonl: str | Path, race_date: str | None = None,
        output_json: str | Path | None = None, from_date: str | None = None, to_date: str | None = None) -> dict[str, Any]:
    ledger = Path(ledger_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(ledger)
    try:
        result = {"import": import_daily_audit(connection, audit_jsonl, race_date=race_date),
                  "summary": summarize(connection, from_date=from_date, to_date=to_date)}
    finally:
        connection.close()
    if output_json is not None:
        output = Path(output_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--audit-jsonl", required=True)
    parser.add_argument("--race-date", help="Required only when the daily audit has zero occurrences")
    parser.add_argument("--output-json")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    args = parser.parse_args()
    print(json.dumps(run(ledger_path=args.ledger, audit_jsonl=args.audit_jsonl, race_date=args.race_date,
                         output_json=args.output_json, from_date=args.from_date, to_date=args.to_date),
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
