#!/usr/bin/env python3
"""Accumulate immutable JRDB Edge forward-settlement occurrences into a ledger.

Input rows are the audit JSONL emitted by evaluate_jrdb_edge_forward.py. The ledger
never rematches a race and never mutates Edge Registry lifecycle state. It only
persists already-frozen matched Edge occurrences and produces cumulative shadow
summaries suitable for a later lifecycle-review step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

VERSION = "0.1.0"
SCHEMA_VERSION = "0.1"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
ELIGIBILITY = {"ELIGIBLE", "ABNORMAL", "NO_RESULT"}


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _mean_metric(rows: Iterable[Mapping[str, Any]], field: str) -> float | None:
    values = [_number(row.get("evidence", {}).get(field)) for row in rows]
    usable = [value for value in values if value is not None]
    return (sum(usable) / len(usable)) if usable else None


def summarize_occurrences(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mirror forward evaluator occurrence semantics for cumulative reporting."""
    eligible = [row for row in rows if row["eligibility"] == "ELIGIBLE"]
    count = len(eligible)
    result: dict[str, Any] = {
        "matches": len(rows),
        "eligible": count,
        "abnormal": sum(row["eligibility"] == "ABNORMAL" for row in rows),
        "no_result": sum(row["eligibility"] == "NO_RESULT" for row in rows),
        "unique_edges": len({row["edge_id"] for row in eligible}),
        "unique_runners": len({row["runner_identity"] for row in eligible}),
        "review_due_occurrences": sum(bool(row["review_due"]) for row in eligible),
    }
    if not count:
        return result
    win_hits = sum(int(int(row["outcome"]["finish"]) == 1) for row in eligible)
    place_hits = sum(int(float(row["outcome"].get("place_payout") or 0) > 0) for row in eligible)
    win_return = sum(float(row["outcome"].get("win_payout") or 0) for row in eligible)
    place_return = sum(float(row["outcome"].get("place_payout") or 0) for row in eligible)
    result.update({
        "win_hits": win_hits,
        "win_rate": win_hits / count,
        "place_hits": place_hits,
        "place_rate": place_hits / count,
        "win_return_yen": win_return,
        "place_return_yen": place_return,
        "win_roi": win_return / (count * 100.0),
        "place_roi": place_return / (count * 100.0),
        "historical_place_rate_weighted": _mean_metric(eligible, "place_rate"),
        "historical_place_roi_weighted": _mean_metric(eligible, "place_roi"),
        "baseline_place_rate_weighted": _mean_metric(eligible, "baseline_place_rate"),
    })
    return result


def connect(path: str | Path) -> sqlite3.Connection:
    ledger = Path(path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(ledger)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    ensure_schema(connection)
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS forward_ledger_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS forward_source_import (
            source_digest TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            row_count INTEGER NOT NULL CHECK(row_count >= 0)
        );

        CREATE TABLE IF NOT EXISTS forward_occurrence (
            occurrence_key TEXT PRIMARY KEY,
            race_date TEXT NOT NULL,
            runner_identity TEXT NOT NULL,
            horse_id TEXT,
            edge_id TEXT NOT NULL,
            family TEXT,
            polarity TEXT NOT NULL,
            registry_status TEXT,
            review_due INTEGER NOT NULL CHECK(review_due IN (0, 1)),
            eligibility TEXT NOT NULL CHECK(eligibility IN ('ELIGIBLE', 'ABNORMAL', 'NO_RESULT')),
            finish INTEGER,
            abnormal_code TEXT,
            win_payout REAL NOT NULL,
            place_payout REAL NOT NULL,
            historical_place_rate REAL,
            historical_place_roi REAL,
            baseline_place_rate REAL,
            occurrence_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_forward_occurrence_edge
            ON forward_occurrence(edge_id, race_date);
        CREATE INDEX IF NOT EXISTS idx_forward_occurrence_family
            ON forward_occurrence(family, race_date);
        CREATE INDEX IF NOT EXISTS idx_forward_occurrence_polarity
            ON forward_occurrence(polarity, race_date);
        CREATE INDEX IF NOT EXISTS idx_forward_occurrence_review_due
            ON forward_occurrence(review_due, race_date);
        """
    )
    existing = connection.execute(
        "SELECT value FROM forward_ledger_meta WHERE key='schema_version'"
    ).fetchone()
    if existing is None:
        connection.execute(
            "INSERT INTO forward_ledger_meta(key, value) VALUES('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        connection.commit()
    elif existing["value"] != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported forward ledger schema version: {existing['value']} != {SCHEMA_VERSION}"
        )


def load_audit(path: str | Path) -> tuple[str, list[dict[str, Any]]]:
    source = Path(path)
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_no, raw in enumerate(payload.decode("utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"{source}: line {line_no} is not an object")
        key = validate_occurrence(value, source=source, line_no=line_no)
        if key in seen:
            raise ValueError(f"{source}: duplicate occurrence_key at line {line_no}: {key}")
        seen.add(key)
        rows.append(value)
    return digest, rows


def validate_occurrence(
    row: Mapping[str, Any], *, source: Path | None = None, line_no: int | None = None
) -> str:
    location = f"{source}: line {line_no}: " if source is not None else ""
    race_date = row.get("race_date")
    runner_identity = row.get("runner_identity")
    edge_id = row.get("edge_id")
    polarity = row.get("polarity")
    eligibility = row.get("eligibility")
    evidence = row.get("evidence")
    outcome = row.get("outcome")
    if not isinstance(race_date, str) or not DATE_RE.fullmatch(race_date):
        raise ValueError(location + "invalid race_date")
    if not isinstance(runner_identity, str) or not runner_identity.strip():
        raise ValueError(location + "invalid runner_identity")
    if not isinstance(edge_id, str) or not edge_id.strip():
        raise ValueError(location + "invalid edge_id")
    if not isinstance(polarity, str) or not polarity.strip():
        raise ValueError(location + "invalid polarity")
    if eligibility not in ELIGIBILITY:
        raise ValueError(location + f"invalid eligibility: {eligibility}")
    if not isinstance(evidence, dict) or not isinstance(outcome, dict):
        raise ValueError(location + "evidence and outcome must be objects")
    if eligibility == "ELIGIBLE" and outcome.get("finish") is None:
        raise ValueError(location + "ELIGIBLE occurrence requires outcome.finish")
    return f"{race_date}|{runner_identity}|{edge_id}"


def _insert_occurrence(connection: sqlite3.Connection, row: dict[str, Any]) -> bool:
    occurrence_key = validate_occurrence(row)
    encoded = _canonical_json(row)
    existing = connection.execute(
        "SELECT occurrence_json FROM forward_occurrence WHERE occurrence_key=?",
        (occurrence_key,),
    ).fetchone()
    if existing is not None:
        if existing["occurrence_json"] != encoded:
            raise ValueError(f"conflicting immutable forward occurrence: {occurrence_key}")
        return False

    evidence = row["evidence"]
    outcome = row["outcome"]
    finish = outcome.get("finish")
    connection.execute(
        """
        INSERT INTO forward_occurrence(
            occurrence_key, race_date, runner_identity, horse_id, edge_id, family,
            polarity, registry_status, review_due, eligibility, finish, abnormal_code,
            win_payout, place_payout, historical_place_rate, historical_place_roi,
            baseline_place_rate, occurrence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            occurrence_key,
            row["race_date"],
            row["runner_identity"],
            row.get("horse_id"),
            row["edge_id"],
            row.get("family"),
            row["polarity"],
            row.get("status"),
            int(bool(row.get("review_due"))),
            row["eligibility"],
            int(finish) if finish is not None else None,
            str(outcome.get("abnormal_code") or ""),
            float(outcome.get("win_payout") or 0),
            float(outcome.get("place_payout") or 0),
            _number(evidence.get("place_rate")),
            _number(evidence.get("place_roi")),
            _number(evidence.get("baseline_place_rate")),
            encoded,
        ),
    )
    return True


def import_audit(connection: sqlite3.Connection, path: str | Path) -> dict[str, Any]:
    source = Path(path)
    digest, rows = load_audit(source)
    prior = connection.execute(
        "SELECT source_name, row_count FROM forward_source_import WHERE source_digest=?",
        (digest,),
    ).fetchone()
    if prior is not None:
        return {
            "source": str(source),
            "source_digest": digest,
            "rows": int(prior["row_count"]),
            "inserted": 0,
            "existing": int(prior["row_count"]),
            "already_imported": True,
        }

    inserted = 0
    existing_count = 0
    try:
        connection.execute("BEGIN IMMEDIATE")
        for row in rows:
            if _insert_occurrence(connection, row):
                inserted += 1
            else:
                existing_count += 1
        connection.execute(
            "INSERT INTO forward_source_import(source_digest, source_name, row_count) VALUES (?, ?, ?)",
            (digest, source.name, len(rows)),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {
        "source": str(source),
        "source_digest": digest,
        "rows": len(rows),
        "inserted": inserted,
        "existing": existing_count,
        "already_imported": False,
    }


def load_occurrences(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    records = connection.execute(
        "SELECT occurrence_json FROM forward_occurrence ORDER BY race_date, runner_identity, edge_id"
    ).fetchall()
    return [json.loads(record["occurrence_json"]) for record in records]


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(field))].append(row)
    return {key: summarize_occurrences(buckets[key]) for key in sorted(buckets)}


def build_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = load_occurrences(connection)
    imports = [
        dict(record)
        for record in connection.execute(
            "SELECT source_digest, source_name, row_count FROM forward_source_import ORDER BY source_digest"
        ).fetchall()
    ]
    if rows:
        dates = [row["race_date"] for row in rows]
        date_range: dict[str, str | None] = {"from": min(dates), "to": max(dates)}
    else:
        date_range = {"from": None, "to": None}
    return {
        "status": "PASS",
        "ledger_version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "semantics": "immutable matched Edge occurrence ledger; 100 JPY hypothetical stake per eligible occurrence",
        "date_range": date_range,
        "source_imports": imports,
        "overall": summarize_occurrences(rows),
        "by_edge": _group_summary(rows, "edge_id"),
        "by_family": _group_summary(rows, "family"),
        "by_polarity": _group_summary(rows, "polarity"),
        "by_review_due": _group_summary(rows, "review_due"),
    }


def run(
    *,
    ledger_path: str | Path,
    audit_jsonl: Sequence[str | Path] = (),
    output_json: str | Path | None = None,
) -> dict[str, Any]:
    with connect(ledger_path) as connection:
        imports = [import_audit(connection, path) for path in audit_jsonl]
        summary = build_summary(connection)
    result = {"imports": imports, "summary": summary}
    if output_json is not None:
        output = Path(output_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, help="SQLite forward ledger path")
    parser.add_argument(
        "--audit-jsonl", action="append", default=[], help="Forward evaluator audit JSONL; repeatable"
    )
    parser.add_argument("--output-json", help="Import report + cumulative summary JSON")
    args = parser.parse_args(argv)
    result = run(
        ledger_path=args.ledger,
        audit_jsonl=args.audit_jsonl,
        output_json=args.output_json,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
