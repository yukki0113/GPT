#!/usr/bin/env python3
"""Compare finalized SED fields consumed by accepted Analysis and RRDB CURRENT.

This gate distinguishes packaging/timestamp changes from forecast-relevant
content changes. It does not rebuild or promote producer data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import zipfile
from typing import Any, Iterable

import duckdb

from racenote_forward_errors import DataInvalid, OrchestrationMissing, run_cli
from jrdb_analysis_parquet_current import resolve_current
from jrdb_analysis_raw_adapter import parse_sed as project_analysis_sed
from jrdb_postrace_review_acceptance import _paths as rrdb_paths
from jrdb_postrace_review_source import project_sed_result
from jrdb_raw import Parser, read_fixed_records

SCHEMA = "racenote-forward-consumed-field-consistency-v1"
ANALYSIS_FIELDS = (
    "finish", "abnormal_code", "final_win_odds", "final_win_popularity",
    "win_payout", "place_payout",
)
RRDB_HORSE_FIELDS = (
    "horse_id", "horse_name", "finish", "time_sec", "carried_weight_kg",
    "course_lane_code", "fourth_corner_lane_code", "first3f_sec", "last3f_sec",
    "first3f_leader_diff_sec", "last3f_leader_diff_sec",
    "corner1_position", "corner2_position", "corner3_position", "corner4_position",
    "race_running_style_code", "jrdb_track_diff", "jrdb_pace_score",
    "jrdb_late_break_score", "jrdb_position_score", "jrdb_trouble_score",
    "jrdb_prev_trouble_score", "jrdb_mid_trouble_score", "jrdb_late_trouble_score",
)
RRDB_RACE_FIELDS = (
    "venue_code", "surface_code", "distance_m", "field_size",
    "race_pace_code", "winner_time_sec",
)
MAX_EXAMPLES = 30


class ConsumedFieldConsistencyError(DataInvalid):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _date(path: Path) -> dt.date:
    m = re.fullmatch(r"SED(\d{6})\.zip", path.name, re.IGNORECASE)
    if not m:
        raise ConsumedFieldConsistencyError(f"bad finalized SED name: {path.name}")
    raw = m.group(1)
    yy = int(raw[:2])
    return dt.date(2000 + yy if yy < 80 else 1900 + yy, int(raw[2:4]), int(raw[4:6]))


def _records(path: Path, day: dt.date) -> list[bytes]:
    expected = f"SED{day:%y%m%d}.txt".upper()
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if Path(n).name.upper() == expected]
        if len(names) != 1:
            raise ConsumedFieldConsistencyError(
                f"{path}: expected exactly one {expected}, got {len(names)}"
            )
        bad = archive.testzip()
        if bad:
            raise ConsumedFieldConsistencyError(f"{path}: bad ZIP member {bad}")
        rows = read_fixed_records(archive, names[0], "SED")
        if not rows:
            raise ConsumedFieldConsistencyError(f"{path}: no valid SED rows")
        return rows


def _norm(value: object) -> object:
    if value == "":
        return None
    if isinstance(value, float):
        if value != value:
            return None
        return round(value, 9)
    return value


def _keyed(rows: Iterable[dict[str, Any]], keys: tuple[str, ...]) -> dict[tuple, dict]:
    result = {}
    for row in rows:
        key = tuple(row.get(name) for name in keys)
        if key in result:
            raise ConsumedFieldConsistencyError(f"duplicate comparison key: {key}")
        result[key] = row
    return result


def _compare(expected: dict, actual: dict, fields: tuple[str, ...], label: str) -> dict:
    missing = sorted(set(expected) - set(actual), key=str)
    extra = sorted(set(actual) - set(expected), key=str)
    mismatches = []
    for key in sorted(set(expected) & set(actual), key=str):
        for field in fields:
            left, right = _norm(expected[key].get(field)), _norm(actual[key].get(field))
            if left != right and len(mismatches) < MAX_EXAMPLES:
                mismatches.append(
                    {"key": list(key), "field": field, "sed": left, "current": right}
                )
    return {
        "label": label,
        "expected_rows": len(expected),
        "actual_rows": len(actual),
        "missing_keys": [list(x) for x in missing[:MAX_EXAMPLES]],
        "extra_keys": [list(x) for x in extra[:MAX_EXAMPLES]],
        "mismatches": mismatches,
        "status": "PASS" if not missing and not extra and not mismatches else "FAIL",
    }


def _dicts(connection: duckdb.DuckDBPyConnection, sql: str, params: list[object]) -> list[dict]:
    cursor = connection.execute(sql, params)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _analysis_actual(root: Path, day: str) -> list[dict]:
    current = resolve_current(root)
    manifest = json.loads(Path(current["manifest"]).read_text(encoding="utf-8"))
    paths = [str((root / p["relative_path"]).resolve()) for p in manifest["fact_table"]["partitions"]]
    fields = ", ".join(("race_key", "horse_no", *ANALYSIS_FIELDS))
    con = duckdb.connect(":memory:")
    try:
        return _dicts(
            con,
            f"SELECT {fields} FROM read_parquet(?, union_by_name=true) "
            "WHERE CAST(race_date AS VARCHAR)=? ORDER BY race_key,horse_no",
            [paths, day],
        )
    finally:
        con.close()


def _rrdb_actual(root: Path, day: str) -> tuple[list[dict], list[dict]]:
    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    if pointer.get("status") != "CURRENT":
        raise ConsumedFieldConsistencyError("RRDB pointer is not CURRENT")
    manifest = json.loads((root / pointer["manifest"]).read_text(encoding="utf-8"))
    if manifest.get("validation_status") != "PASS":
        raise ConsumedFieldConsistencyError("RRDB manifest is not PASS")
    horse_paths = [str(x) for x in rrdb_paths(root, manifest, "fact_horse_performance")]
    race_paths = [str(x) for x in rrdb_paths(root, manifest, "fact_race_context")]
    horse_fields = ", ".join(("race_key", "horse_no", *RRDB_HORSE_FIELDS))
    race_fields = ", ".join(("race_key", *RRDB_RACE_FIELDS))
    con = duckdb.connect(":memory:")
    try:
        horses = _dicts(
            con,
            f"SELECT {horse_fields} FROM read_parquet(?, union_by_name=true) "
            "WHERE CAST(race_date AS VARCHAR)=? ORDER BY race_key,horse_no",
            [horse_paths, day],
        )
        races = _dicts(
            con,
            f"SELECT {race_fields} FROM read_parquet(?, union_by_name=true) "
            "WHERE CAST(race_date AS VARCHAR)=? ORDER BY race_key",
            [race_paths, day],
        )
        return horses, races
    finally:
        con.close()


def validate(
    sed_archives: list[Path], analysis_root: Path, rrdb_root: Path, *,
    fail_on_mismatch: bool = True,
) -> dict:
    if not sed_archives:
        raise OrchestrationMissing("finalized SED delivery missing")
    parser = Parser()
    days = []
    seen = set()
    for archive in sorted(map(Path, sed_archives), key=lambda x: x.name):
        day = _date(archive)
        day_text = day.isoformat()
        if day_text in seen:
            raise ConsumedFieldConsistencyError(f"duplicate finalized SED date: {day_text}")
        seen.add(day_text)
        analysis_expected, rrdb_expected, race_expected = [], [], {}
        for raw in _records(archive, day):
            parsed = parser.sed(raw)
            (race_key, horse_no), result, _ = project_analysis_sed(raw, day_text, day.year)
            analysis_expected.append({"race_key": race_key, "horse_no": horse_no, **result})
            review = project_sed_result(parsed)
            rrdb_expected.append(review)
            race = race_expected.setdefault(
                review["race_key"],
                {
                    "race_key": review["race_key"],
                    "venue_code": review["venue_code"],
                    "surface_code": review["surface_code"],
                    "distance_m": review["distance_m"],
                    "field_size": review["field_size"],
                    "race_pace_code": review["race_pace_code"],
                    "winner_time_sec": None,
                },
            )
            if review.get("finish") == 1:
                race["winner_time_sec"] = review.get("time_sec")
        analysis_actual = _analysis_actual(analysis_root, day_text)
        rrdb_horse_actual, rrdb_race_actual = _rrdb_actual(rrdb_root, day_text)
        reports = [
            _compare(
                _keyed(analysis_expected, ("race_key", "horse_no")),
                _keyed(analysis_actual, ("race_key", "horse_no")),
                ANALYSIS_FIELDS, "analysis",
            ),
            _compare(
                _keyed(rrdb_expected, ("race_key", "horse_no")),
                _keyed(rrdb_horse_actual, ("race_key", "horse_no")),
                RRDB_HORSE_FIELDS, "rrdb_horse",
            ),
            _compare(
                _keyed(race_expected.values(), ("race_key",)),
                _keyed(rrdb_race_actual, ("race_key",)),
                RRDB_RACE_FIELDS, "rrdb_race",
            ),
        ]
        days.append({
            "date": day_text,
            "sed_file": archive.name,
            "sed_sha256": _sha(archive),
            "analysis": reports[0],
            "rrdb_horse": reports[1],
            "rrdb_race": reports[2],
            "status": "PASS" if all(x["status"] == "PASS" for x in reports) else "FAIL",
        })
    result = {
        "schema_version": SCHEMA,
        "status": "PASS" if all(x["status"] == "PASS" for x in days) else "FAIL",
        "dates": [x["date"] for x in days],
        "analysis_fields": list(ANALYSIS_FIELDS),
        "rrdb_horse_fields": list(RRDB_HORSE_FIELDS),
        "rrdb_race_fields": list(RRDB_RACE_FIELDS),
        "days": days,
    }
    if fail_on_mismatch and result["status"] != "PASS":
        raise ConsumedFieldConsistencyError(json.dumps(result, ensure_ascii=False))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sed", type=Path, action="append", required=True)
    ap.add_argument("--analysis-root", type=Path, required=True)
    ap.add_argument("--rrdb-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = validate(args.sed, args.analysis_root, args.rrdb_root, fail_on_mismatch=False)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "PASS":
        raise ConsumedFieldConsistencyError(
            f"finalized SED consumed-field mismatch; review {args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main, "CONSUMED_FIELD_VALIDATION"))
