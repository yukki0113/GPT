"""Join PACI KYI previous result keys to ZED, using the shared raw parser."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jrdb_raw import Parser, ReaderAudit, iter_archive_records, result_key  # noqa: E402


def read_previous(archive: Path, race_key: str, target_date: date) -> tuple[list[dict], dict]:
    audit = ReaderAudit()
    parser = Parser(audit)
    runners = [parser.kyi(record) for _, record in iter_archive_records(archive, "KYI", audit)
               if record[:8].decode("ascii", errors="replace") == race_key]
    horse_keys = [r["race_horse_key"] for r in runners]
    if not runners or len(horse_keys) != len(set(horse_keys)):
        raise ValueError("DUPLICATE_RACE_OR_RUN" if runners else "SOURCE_NOT_FOUND")
    keys = [r["previous"][0]["result_key"] for r in runners if r["previous"][0]["result_key"]]
    if len(keys) != len(set(keys)):
        raise ValueError("DUPLICATE_RACE_OR_RUN")
    matched = {}
    for _, record in iter_archive_records(archive, "ZED", audit):
        key = result_key(record)
        if key not in keys:
            continue
        if key in matched:
            raise ValueError("DUPLICATE_RACE_OR_RUN")
        try:
            previous_date = date.fromisoformat(f"{key[8:12]}-{key[12:14]}-{key[14:16]}")
        except ValueError as exc:
            raise ValueError("UNKNOWN_CONDITION: previous date") from exc
        if previous_date >= target_date:
            raise ValueError("FUTURE_LEAK")
        matched[key] = parser.zed(record)
    if audit.record_length_errors:
        raise ValueError("INVALID_SOURCE: record length")
    output = []
    for runner in sorted(runners, key=lambda r: r["horse_no"]):
        key = runner["previous"][0]["result_key"]
        previous = matched.get(key)
        if previous and (not key.startswith(runner["blood_registration_no"]) or
                         previous["race_key_raw"] != runner["previous"][0]["race_key_raw"]):
            raise ValueError("SOURCE_CHANGED: previous key mismatch")
        result = None
        if previous:
            result = {"result_key": key, "race_key": previous["race_key_raw"],
                      "date": previous["date_raw"], "name": previous["race_name"],
                      "distance_m": previous["distance_m"], "race_class_code": previous["race_class_code"],
                      "grade_code": previous["grade_code"], "finish": previous["finish"],
                      "popularity": previous["final_popularity"], "field_size": previous["field_size"],
                      "corners": previous["corners"], "abnormal_code": previous["abnormal_code"],
                      "source_kind": "PACI_ZED"}
        output.append({"horse_no": runner["horse_no"], "horse_name": runner["horse_name"],
                       "horse_id": runner["blood_registration_no"], "race_horse_key": runner["race_horse_key"],
                       "running_style_code": runner["running_style_code"], "frame": runner["frame_no"],
                       "sex_code": runner["sex_code"], "jockey": runner["jockey"],
                       "previous_run": result})
    return output, {"runner_count": len(output), "previous_available": len(matched),
                    "missing_previous": len(output) - len(matched)}
