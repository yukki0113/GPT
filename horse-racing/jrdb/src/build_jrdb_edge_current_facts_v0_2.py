#!/usr/bin/env python3
"""Extend the validated current Edge facts with v0.2 pre-race fields."""
from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import build_jrdb_edge_current_facts as base
from jrdb_edge_v02_canonical import horse_age_at_race
from jrdb_raw import Parser, ReaderAudit

VERSION = "0.2.0"


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_current_facts(
    paci_path: str | Path, analysis_db: str | Path | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, audit = base.build_current_facts(paci_path, analysis_db)
    by_key = {str(row["race_horse_key"]): row for row in rows}
    profiles: dict[str, list[Mapping[str, Any]]] = {}
    entry_extra: dict[str, dict[str, Any]] = {}

    reader_audit = ReaderAudit()
    parser = Parser(reader_audit)
    with zipfile.ZipFile(paci_path) as archive:
        for raw in base._records(archive, "UKC", reader_audit, required=False):
            parsed = parser.ukc(raw)
            horse_id = _text(parsed.get("horse_id"))
            if horse_id:
                profiles.setdefault(horse_id, []).append(parsed)

        for raw in base._records(archive, "KYI", reader_audit, required=True):
            parsed = parser.kyi(raw)
            key = str(parsed["race_horse_key"])
            entry_extra[key] = {
                "rotation_interval": _int(parsed.get("rotation_interval")),
                "pre_idm": _float(parsed.get("idm")),
                "training_score": _float(parsed.get("training_index")),
                "stable_score": _float(parsed.get("stable_index")),
                "uptrend_code": _text(parsed.get("improvement_code")),
                "training_arrow_code": _text(parsed.get("training_arrow_code")),
                "stable_evaluation_code": _text(parsed.get("stable_evaluation_code")),
                "body_weight_pre_kg": _int(parsed.get("body_weight_pre_kg")),
                "body_weight_change_pre_kg": _int(parsed.get("body_weight_change_pre_kg")),
            }

    if reader_audit.record_length_errors:
        raise base.CurrentFactError(
            f"PACI fixed-record length error in v0.2 enrichment: {dict(reader_audit.record_length_errors)}"
        )

    profile_statuses = Counter()
    for key, row in by_key.items():
        row.update(entry_extra.get(key, {}))
        horse_id = _text(row.get("horse_id"))
        target_date = str(row["race_date"])
        status = "NO_HORSE_ID"
        profile = None
        if horse_id:
            status, profile = base.select_profile_asof(profiles.get(horse_id, []), target_date)
        profile_statuses[status] += 1
        birth_date = None if profile is None else _text(profile.get("birth_date"))
        row["birth_date"] = birth_date
        row["horse_age"] = horse_age_at_race(target_date, birth_date)

    audit = dict(audit)
    audit["v02_version"] = VERSION
    audit["v02_profile_status_counts"] = dict(sorted(profile_statuses.items()))
    audit["v02_fields"] = [
        "horse_age", "birth_date", "rotation_interval", "pre_idm", "training_score",
        "stable_score", "uptrend_code", "training_arrow_code", "stable_evaluation_code",
        "body_weight_pre_kg", "body_weight_change_pre_kg",
    ]
    return rows, audit


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--paci", required=True)
    p.add_argument("--analysis-db")
    p.add_argument("--output-jsonl", required=True)
    p.add_argument("--audit-json")
    args = p.parse_args()
    rows, audit = build_current_facts(args.paci, args.analysis_db)
    with Path(args.output_jsonl).open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if args.audit_json:
        Path(args.audit_json).write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
    print(json.dumps({"status":"PASS","version":VERSION,"runner_rows":len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
