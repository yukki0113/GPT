"""Integration tests from synthetic PACI fixed records through Edge Matcher."""
from __future__ import annotations

import sqlite3
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_jrdb_edge_current_facts import build_current_facts  # noqa: E402
from jrdb_edge_matcher import match_runner  # noqa: E402
from jrdb_raw import RECORD_LENGTHS  # noqa: E402


def _record(kind: str) -> bytearray:
    return bytearray(b" " * (RECORD_LENGTHS[kind] - 2))


def _put(record: bytearray, start: int, width: int, value: str) -> None:
    encoded = value.encode("ascii")
    assert len(encoded) <= width
    record[start - 1 : start - 1 + width] = encoded.ljust(width, b" ")


def _put_text(record: bytearray, start: int, width: int, value: str) -> None:
    encoded = value.encode("cp932")
    assert len(encoded) <= width
    record[start - 1 : start - 1 + width] = encoded.ljust(width, b" ")


def _write_paci(path: Path) -> None:
    race_key = "0926a101"
    prev_race_key = "09269101"

    bac = _record("BAC")
    _put(bac, 1, 8, race_key)
    _put(bac, 9, 8, "20260909")
    _put(bac, 21, 4, "1600")
    _put(bac, 25, 1, "1")
    _put(bac, 26, 1, "2")

    kyi = _record("KYI")
    _put(kyi, 1, 8, race_key)
    _put(kyi, 9, 2, "03")
    _put(kyi, 11, 8, "H0000001")
    _put_text(kyi, 19, 36, "TEST HORSE")
    _put(kyi, 284, 8, prev_race_key)
    _put(kyi, 324, 1, "2")
    _put(kyi, 336, 5, "01234")
    _put(kyi, 341, 5, "05678")

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BAC260909.txt", bytes(bac) + b"\r\n")
        archive.writestr("KYI260909.txt", bytes(kyi) + b"\r\n")


def _write_analysis(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """CREATE TABLE fact_entry_result_lite(
                race_key TEXT,
                race_date TEXT,
                horse_no INTEGER,
                horse_id TEXT,
                track_type TEXT,
                distance INTEGER,
                frame_no INTEGER
            )"""
        )
        connection.execute(
            "INSERT INTO fact_entry_result_lite VALUES(?,?,?,?,?,?,?)",
            ("09269101", "2026-08-20", 7, "H0000001", "2", 2000, 5),
        )
        connection.commit()
    finally:
        connection.close()


def _edge(edge_id: str, modifiers: dict) -> dict:
    return {
        "edge_id": edge_id,
        "status": "ACTIVE",
        "display_text": edge_id,
        "polarity": "POSITIVE",
        "strength_score": 0.8,
        "family": "TRANSITION",
        "conditions": {
            "template_id": "integration-test",
            "template_version": "v0.1",
            "anchor": {"venue_code": "09"},
            "modifiers": modifiers,
        },
    }


def test_synthetic_paci_to_current_fact_to_transition_edge_match(tmp_path: Path):
    paci = tmp_path / "PACI260909.zip"
    analysis = tmp_path / "analysis.sqlite"
    _write_paci(paci)
    _write_analysis(analysis)

    rows, summary = build_current_facts(paci, analysis)
    assert summary["status"] == "PASS"
    assert summary["runner_rows"] == 1
    assert summary["previous_RESOLVED"] == 1
    runner = rows[0]
    assert runner["race_key"] == "0926a101"
    assert runner["race_horse_key"] == "0926a10103"
    assert runner["distance_change_m"] == -400
    assert runner["distance_change_bucket"] == "LARGE_SHORTEN"
    assert runner["surface_transition"] == "2->1"
    assert runner["frame_transition"] == "MIDDLE->INNER"

    registry = [
        _edge(
            "EDGE_MATCH",
            {"surface_code": "1", "distance_change_bucket": "LARGE_SHORTEN"},
        ),
        _edge(
            "EDGE_NO_MATCH",
            {"surface_code": "1", "distance_change_bucket": "EXTEND"},
        ),
    ]
    matches = match_runner(registry, runner)
    assert [row["edge_id"] for row in matches] == ["EDGE_MATCH"]


def test_without_history_source_course_edge_survives_transition_edge_does_not(tmp_path: Path):
    paci = tmp_path / "PACI260909.zip"
    _write_paci(paci)

    rows, summary = build_current_facts(paci)
    assert summary["previous_NO_HISTORY_SOURCE"] == 1
    runner = rows[0]
    assert runner["distance_change_bucket"] is None
    assert runner["surface_transition"] is None

    course_edge = {
        "edge_id": "COURSE_OK",
        "status": "ACTIVE",
        "display_text": "course",
        "polarity": "POSITIVE",
        "family": "COURSE",
        "conditions": {
            "template_id": "course-test",
            "template_version": "v0.1",
            "anchor": {"venue_code": "09"},
            "modifiers": {"surface_code": "1", "distance_m": 1600},
        },
    }
    transition_edge = _edge(
        "TRANSITION_BLOCKED",
        {"distance_change_bucket": "LARGE_SHORTEN"},
    )
    matches = match_runner([course_edge, transition_edge], runner)
