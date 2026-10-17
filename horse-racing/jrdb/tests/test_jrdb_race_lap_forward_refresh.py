"""Forward RaceLap append and immutable conflict tests."""
import json
from pathlib import Path

import duckdb
import pytest

from jrdb_race_lap_contract import COLUMN_TYPES
from jrdb_race_lap_forward_refresh import refresh


def _baseline(path: Path, rows: list[dict]) -> None:
    con = duckdb.connect()
    try:
        con.execute("CREATE TABLE race_lap (" + ", ".join(f'"{k}" {v}' for k,v in COLUMN_TYPES.items()) + ")")
        names = list(COLUMN_TYPES)
        con.executemany("INSERT INTO race_lap VALUES (" + ",".join("?" for _ in names) + ")",
                        [[r[k] for k in names] for r in rows])
        con.execute("COPY race_lap TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(path)])
    finally:
        con.close()


def _fixture_row(date: str, key: str) -> dict:
    # Use a full canonical row obtained through the production shape contracts.
    from jrdb_race_lap_contract import DATASET_SCHEMA_VERSION, LOGIC_VERSION
    row = dict.fromkeys(COLUMN_TYPES)
    row.update({
        "race_key":key, "race_date":date, "surface_code":"1", "distance_m":1600,
        "coverage_status":"NO_LAPS", "lap_count":0, "comparable_200m_lap_count":0,
        "partial_first_segment":False, "early_late_delta_available":False,
        "optional_srb_context_available":False, "segment_distances_m":[],
        "lap_times_sec":[], "track_bias_raw_json":"{}", "source_sed_member":"SED",
        "source_srb_member":"SRB", "source_archive":"test.zip",
        "dataset_schema_version":DATASET_SCHEMA_VERSION,
        "shape_logic_version":LOGIC_VERSION
    })
    return row


def test_forward_refresh_contract_validation(tmp_path, monkeypatch):
    # This is a regression test of the immutable guard; real SED parsing is
    # independently covered by canonical jrdb_race_lap_dataset tests.
    import jrdb_race_lap_forward_refresh as mod
    a = _fixture_row("2026-01-04", "0101010101")
    b = _fixture_row("2026-01-05", "0101010201")
    previous = tmp_path / "prev.parquet"
    _baseline(previous, [a])
    incoming = tmp_path / "SED260105.zip"
    incoming.write_bytes(b"test")
    monkeypatch.setattr(mod, "build_rows", lambda archives: [b])
    out = tmp_path / "store"
    result = refresh(previous, [incoming], out, "racelap-forward-20260105-01", ["2026-01-05"])
    assert result["new_count"] == 1
    assert result["race_count"] == 2
    assert result["validation_status"] == "PASS"
    assert (out / "generations/racelap-forward-20260105-01/manifest.json").is_file()
    monkeypatch.setattr(mod, "build_rows", lambda archives: [a])
    noop = refresh(previous, [incoming], out, "racelap-forward-noop", ["2026-01-04"])
    assert noop["status"] == "NOOP_IDENTICAL_RETRY"
    b_changed = dict(a, distance_m=1800)
    monkeypatch.setattr(mod, "build_rows", lambda archives: [b_changed])
    with pytest.raises(ValueError, match="CONFLICT"):
        refresh(previous, [incoming], out, "racelap-forward-conflict")
