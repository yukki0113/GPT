#!/usr/bin/env python3
"""Build one annual neutral JRDB Canonical SQLite shard from annual Raw ZIPs.

Fixed-width interpretation stays exclusively in ``jrdb_raw.py``. This builder only
projects Common Reader values into query-friendly SQLite tables and attaches
archive/member/hash provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jrdb_raw import (
    VERSION as PARSER_VERSION,
    Parser,
    canonical_members,
    hhmm,
    iter_archive_records,
    race_key_parts,
    ymd,
)

VERSION = "0.1.0"
SCHEMA_VERSION = "v0.1"
KINDS = ("BAC", "KYI", "CHA", "CYB", "SED", "SKB", "UKC")
HERE = Path(__file__).resolve().parent
DEFAULT_SCHEMA = HERE.parent / "schema" / "jrdb_canonical_schema_v0_1.sql"


class Inserter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.cache: dict[tuple[str, tuple[str, ...]], str] = {}

    def insert(self, table: str, values: dict[str, Any]) -> None:
        columns = tuple(values)
        cache_key = (table, columns)
        sql = self.cache.get(cache_key)
        if sql is None:
            sql = (
                f"INSERT INTO {table} ({','.join(columns)}) VALUES "
                f"({','.join('?' for _ in columns)})"
            )
            self.cache[cache_key] = sql
        self.connection.execute(sql, tuple(values[column] for column in columns))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonical_record_hash(record: bytes) -> str:
    body = record
    if body.endswith(b"\r\n"):
        body = body[:-2]
    return hashlib.sha256(body).hexdigest()


def normalized_date(value: Any) -> str | None:
    if value is None:
        return None
    return ymd(str(value))


def normalized_time(value: Any) -> str | None:
    if value is None:
        return None
    return hhmm(str(value))


def int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def copied(parsed: dict[str, Any], names: Iterable[str]) -> dict[str, Any]:
    return {name: parsed[name] for name in names}


def resolve_archive(raw_root: Path, kind: str, year: int) -> Path:
    candidates = (
        raw_root / kind / f"{kind}_{year}.zip",
        raw_root / f"{kind}_{year}.zip",
        raw_root / kind / f"{kind}{year}.zip",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"{kind} {year} archive not found under {raw_root}")


def source_fields(source_id: int, member: str, record: bytes) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_member": member,
        "record_hash": canonical_record_hash(record),
    }


def insert_source_archive(
    connection: sqlite3.Connection,
    build_id: int,
    kind: str,
    year: int,
    archive: Path,
) -> int:
    with zipfile.ZipFile(archive) as source_zip:
        member_count = len(canonical_members(source_zip, kind))
    cursor = connection.execute(
        """
        INSERT INTO source_archive(
          build_id, source_kind, year, archive_filename, archive_sha256,
          archive_size_bytes, member_count, record_count, imported_at
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            build_id,
            kind,
            year,
            archive.name,
            sha256_file(archive),
            archive.stat().st_size,
            member_count,
            0,
            now_iso(),
        ),
    )
    return int(cursor.lastrowid)


def load_bac(inserter: Inserter, parser: Parser, archive: Path, source_id: int) -> int:
    names = (
        "date_raw", "post_time_raw", "distance_raw", "surface_code", "turn_code",
        "layout_code", "race_type_code", "race_class_code", "symbol_code",
        "weight_rule_code", "grade_code", "race_name", "meeting", "field_size",
        "course_code", "meeting_area_code",
    )
    count = 0
    for member, record in iter_archive_records(archive, "BAC"):
        parsed = parser.bac(record)
        parts = race_key_parts(parsed["race_key_raw"])
        values = {
            "race_key_raw": parsed["race_key_raw"],
            "venue_code": parts["venue_code"],
            "year_yy": parts["year_yy"],
            "meeting_no_raw": parts["meeting"],
            "day_raw": parts["day_raw"],
            "race_no": parts["race_no"],
            **copied(parsed, names),
            "race_date": normalized_date(parsed["date_raw"]),
            "post_time": normalized_time(parsed["post_time_raw"]),
            "distance_m": int_or_none(parsed["distance_raw"]),
            **source_fields(source_id, member, record),
        }
        inserter.insert("bac_race", values)
        count += 1
    return count


def load_kyi(inserter: Inserter, parser: Parser, archive: Path, source_id: int) -> int:
    scalar_names = (
        "race_key_raw", "race_horse_key", "horse_no", "blood_registration_no",
        "horse_name", "idm", "jockey_index", "info_index", "total_index",
        "running_style_code", "distance_fit_code", "improvement_code",
        "rotation_interval", "base_win_odds", "base_win_rank", "base_place_odds",
        "base_place_rank", "training_index", "stable_index", "training_arrow_code",
        "stable_evaluation_code", "jockey_expected_top2_rate", "longshot_index",
        "hoof_code", "heavy_track_fit_code", "jrdb_class_code", "blinker_code",
        "jockey", "carried_weight_tenths", "apprentice_code", "trainer",
        "trainer_base", "frame_no", "condition_class_code", "distance_fit2_code",
        "body_weight_pre_kg", "body_weight_change_pre_kg", "cancel_flag", "sex_code",
        "turf_fit_code", "dirt_fit_code", "jockey_code", "trainer_code",
        "forecast_pace_code", "symbol_code", "start_index", "late_break_rate",
        "stable_run_no", "stable_entry_date_raw", "stable_days_before",
        "rest_reason_code", "farm_name", "farm_rank", "farm_index_rank",
    )
    count = 0
    for member, record in iter_archive_records(archive, "KYI"):
        parsed = parser.kyi(record)
        marks = parsed["marks"]
        indices = parsed["pace_indices"]
        ranks = parsed["pace_ranks"]
        forecast = parsed["forecast_positions"]
        values = {
            **copied(parsed, scalar_names),
            **{f"mark_{name}": marks[name] for name in marks},
            **{f"pace_index_{name}": indices[name] for name in indices},
            **{f"pace_rank_{name}": ranks[name] for name in ranks},
            "forecast_mid_min": forecast["mid"][0],
            "forecast_mid_max": forecast["mid"][1],
            "forecast_mid_code": forecast["mid"][2],
            "forecast_last3f_min": forecast["last3f"][0],
            "forecast_last3f_max": forecast["last3f"][1],
            "forecast_last3f_code": forecast["last3f"][2],
            "forecast_finish_min": forecast["finish"][0],
            "forecast_finish_max": forecast["finish"][1],
            "forecast_finish_code": forecast["finish"][2],
            "stable_entry_date": normalized_date(parsed["stable_entry_date_raw"]),
            **source_fields(source_id, member, record),
        }
        inserter.insert("kyi_entry", values)
        for sequence, previous in enumerate(parsed["previous"], start=1):
            inserter.insert(
                "kyi_previous_link",
                {
                    "race_key_raw": parsed["race_key_raw"],
                    "horse_no": parsed["horse_no"],
                    "sequence": sequence,
                    "prev_result_key": previous["result_key"],
                    "prev_race_key_raw": previous["race_key_raw"],
                },
            )
        for sequence, trait_code in enumerate(parsed["trait_codes"], start=1):
            inserter.insert(
                "kyi_trait",
                {
                    "race_key_raw": parsed["race_key_raw"],
                    "horse_no": parsed["horse_no"],
                    "sequence": sequence,
                    "trait_code": trait_code,
                },
            )
        count += 1
    return count


def load_cha(inserter: Inserter, parser: Parser, archive: Path, source_id: int) -> int:
    names = (
        "weekday", "workout_count", "date_raw", "course_code", "strength_code",
        "state_code", "rider_type_code", "furlongs",
    )
    count = 0
    for member, record in iter_archive_records(archive, "CHA"):
        parsed = parser.cha(record)
        key = parsed["race_horse_key"]
        values = {
            "race_horse_key": key,
            "race_key_raw": key[:8],
            "horse_no": int_or_none(key[8:10]),
            **copied(parsed, names),
            "workout_date": normalized_date(parsed["date_raw"]),
            **{f"clock_{name}_sec": parsed["clock"][name] for name in ("front", "middle", "last")},
            **{f"clock_index_{name}": parsed["clock_index"][name] for name in parsed["clock_index"]},
            "pair_result_code": parsed["pair"]["result_code"],
            "pair_strength_code": parsed["pair"]["strength_code"],
            "pair_age": parsed["pair"]["age"],
            "pair_class_code": parsed["pair"]["class_code"],
            **source_fields(source_id, member, record),
        }
        inserter.insert("cha_workout", values)
        count += 1
    return count


def load_cyb(inserter: Inserter, parser: Parser, archive: Path, source_id: int) -> int:
    names = (
        "training_type_code", "training_course_type_code", "distance_pattern_code",
        "focus_code", "training_index", "condition_index", "volume_grade",
        "condition_change_code", "comment", "comment_date_raw",
        "training_grade_code", "one_week_ago_index", "one_week_ago_course",
    )
    count = 0
    for member, record in iter_archive_records(archive, "CYB"):
        parsed = parser.cyb(record)
        key = parsed["race_horse_key"]
        values = {
            "race_horse_key": key,
            "race_key_raw": key[:8],
            "horse_no": int_or_none(key[8:10]),
            **copied(parsed, names),
            **{f"course_count_{name}": parsed["course_counts"][name] for name in parsed["course_counts"]},
            "comment_date": normalized_date(parsed["comment_date_raw"]),
            **source_fields(source_id, member, record),
        }
        inserter.insert("cyb_training", values)
        count += 1
    return count


def load_sed(inserter: Inserter, parser: Parser, archive: Path, source_id: int) -> int:
    names = (
        "result_key", "race_key_raw", "horse_no", "blood_registration_no", "date_raw",
        "horse_name", "race_name", "distance_m", "surface_code", "turn_code",
        "layout_code", "track_condition_code", "race_type_code", "race_class_code",
        "race_symbol_code", "weight_condition_code", "grade_code", "field_size",
        "finish", "abnormal_code", "time_raw", "carried_weight_tenths", "jockey",
        "trainer", "final_win_odds", "final_popularity_raw", "final_popularity", "idm",
        "course_lane_code", "result_uptrend_code", "result_class_code", "mood_code",
        "first_second_time_diff_sec", "first3f_sec", "last3f_sec",
        "first3f_leader_diff_sec", "last3f_leader_diff_sec", "race_pace_code",
        "horse_pace_code", "final_place_odds_lower", "jockey_code", "trainer_code",
        "body_weight_kg", "body_weight_change_kg", "weather_code",
        "body_condition_code", "course_code", "race_running_style_code", "win_payout",
        "place_payout", "fourth_corner_lane_code", "start_time_raw",
    )
    count = 0
    for member, record in iter_archive_records(archive, "SED"):
        parsed = parser.sed(record)
        values = {
            **copied(parsed, names),
            "race_date": normalized_date(parsed["date_raw"]),
            **{f"metric_{name}": parsed["metrics"][name] for name in parsed["metrics"]},
            **{f"corner{index}": value for index, value in enumerate(parsed["corners"], start=1)},
            "start_time": normalized_time(parsed["start_time_raw"]),
            **source_fields(source_id, member, record),
        }
        inserter.insert("sed_result", values)
        count += 1
    return count


def load_skb(inserter: Inserter, parser: Parser, archive: Path, source_id: int) -> int:
    count = 0
    for member, record in iter_archive_records(archive, "SKB"):
        parsed = parser.skb(record)
        result_key = parsed["result_key"]
        leg = parsed["leg_codes"]
        values = {
            "result_key": result_key,
            "leg_overall_code": leg["overall"],
            "leg_left_front_code": leg["left_front"],
            "leg_right_front_code": leg["right_front"],
            "leg_left_hind_code": leg["left_hind"],
            "leg_right_hind_code": leg["right_hind"],
            **copied(parsed, ("paddock_comment", "leg_comment", "equipment_comment", "race_comment")),
            **source_fields(source_id, member, record),
        }
        inserter.insert("skb_extension", values)
        for sequence, code in enumerate(parsed["tokki_codes"], start=1):
            inserter.insert("skb_tokki", {"result_key": result_key, "sequence": sequence, "tokki_code": code})
        for sequence, code in enumerate(parsed["equipment_codes"], start=1):
            inserter.insert("skb_equipment", {"result_key": result_key, "sequence": sequence, "equipment_code": code})
        count += 1
    return count


def load_ukc(inserter: Inserter, parser: Parser, archive: Path, source_id: int) -> int:
    names = (
        "horse_id", "horse_name", "sex_code", "coat_color_code", "horse_symbol_code",
        "sire_name", "dam_name", "broodmare_sire_name", "sire_birth_year",
        "dam_birth_year", "broodmare_sire_birth_year", "owner_name", "owner_group_code",
        "breeder_name", "breeding_place", "deregistered_flag", "sire_line_code",
        "broodmare_sire_line_code",
    )
    count = 0
    for member, record in iter_archive_records(archive, "UKC"):
        parsed = parser.ukc(record)
        values = {
            **copied(parsed, names),
            "birth_date_raw": parsed["birth_date"],
            "birth_date": normalized_date(parsed["birth_date"]),
            "data_date_raw": parsed["data_date"],
            "data_date": normalized_date(parsed["data_date"]),
            **source_fields(source_id, member, record),
        }
        inserter.insert("ukc_profile", values)
        count += 1
    return count


LOADERS = {
    "BAC": load_bac,
    "KYI": load_kyi,
    "CHA": load_cha,
    "CYB": load_cyb,
    "SED": load_sed,
    "SKB": load_skb,
    "UKC": load_ukc,
}


def configure(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("PRAGMA cache_size=-200000")
    connection.execute("PRAGMA foreign_keys=ON")


def build_canonical(raw_root: Path, year: int, db_path: Path, schema_path: Path) -> dict[str, int]:
    if db_path.exists():
        db_path.unlink()
    connection = sqlite3.connect(db_path)
    configure(connection)
    connection.executescript(schema_path.read_text(encoding="utf-8"))
    cursor = connection.execute(
        "INSERT INTO canonical_build(schema_version,parser_version,started_at,status,years_json) VALUES(?,?,?,?,?)",
        (SCHEMA_VERSION, PARSER_VERSION, now_iso(), "BUILDING", json.dumps([year])),
    )
    build_id = int(cursor.lastrowid)
    connection.commit()
    parser = Parser()
    inserter = Inserter(connection)
    manifest: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    try:
        for kind in KINDS:
            archive = resolve_archive(raw_root, kind, year)
            source_id = insert_source_archive(connection, build_id, kind, year, archive)
            count = LOADERS[kind](inserter, parser, archive, source_id)
            counts[kind] = count
            connection.execute("UPDATE source_archive SET record_count=? WHERE source_id=?", (count, source_id))
            connection.commit()
            row = connection.execute(
                "SELECT archive_filename,archive_sha256,archive_size_bytes,member_count,record_count FROM source_archive WHERE source_id=?",
                (source_id,),
            ).fetchone()
            manifest.append({
                "kind": kind,
                "filename": row[0],
                "sha256": row[1],
                "size_bytes": row[2],
                "member_count": row[3],
                "record_count": row[4],
            })
            print(f"{kind}: {count}", flush=True)
        connection.execute("ANALYZE")
        connection.commit()
        connection.execute("VACUUM")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"integrity_check failed: {integrity}")
        connection.execute(
            "UPDATE canonical_build SET finished_at=?,status='SUCCESS',source_manifest_json=?,integrity_check=? WHERE build_id=?",
            (now_iso(), json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), integrity, build_id),
        )
        connection.commit()
    except Exception as exc:
        connection.rollback()
        connection.execute(
            "UPDATE canonical_build SET finished_at=?,status='ERROR',message=? WHERE build_id=?",
            (now_iso(), str(exc), build_id),
        )
        connection.commit()
        raise
    finally:
        connection.close()
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one annual neutral JRDB Canonical SQLite shard")
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    counts = build_canonical(args.raw_root, args.year, args.db, args.schema)
    print(json.dumps({
        "status": "success",
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "db": str(args.db),
        "size_bytes": args.db.stat().st_size,
        "record_counts": counts,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
