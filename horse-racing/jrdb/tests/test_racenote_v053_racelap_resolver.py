from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import racenote_v053_from_paci as entry


def test_paci_entry_resolves_current_bundle_before_daily_build(tmp_path, monkeypatch):
    paci = tmp_path / "PACI261017.zip"
    paci.write_bytes(b"paci")
    current = tmp_path / "racelap-current"
    current.mkdir()
    resolved_parquet = tmp_path / "resolved" / "race_lap.parquet"
    resolved_parquet.parent.mkdir()
    resolved_parquet.write_bytes(b"parquet")
    output = tmp_path / "output"

    receipt = {
        "schema_version": "jrdb-race-lap-current-resolver-0.1",
        "status": "CURRENT_READY",
        "updated": False,
        "generation_id": "racelap-test",
        "period_to": "2026-10-12",
        "parquet": str(resolved_parquet),
    }
    handoff = {
        "race_count": 1,
        "market_blind": True,
    }

    def fake_bind(_daily_root, forecast_prep, *_args):
        reader = forecast_prep / "reader"
        reader.mkdir(parents=True)
        (reader / "東京_01.json").write_text(
            json.dumps({"race": {"venue": "東京", "race_no": 1}}, ensure_ascii=False),
            encoding="utf-8",
        )
        return handoff

    argv = [
        "racenote_v053_from_paci.py",
        "--date", "2026-10-17",
        "--paci", str(paci),
        "--selection-id", "DAILY-20261017",
        "--main-sha", "a" * 40,
        "--analysis-root", str(tmp_path / "analysis"),
        "--course-fit-root", str(tmp_path / "fit"),
        "--race-lap-current-bundle", str(current),
        "--race-lap-expected-period-to", "2026-10-12",
        "--racereview-root", str(tmp_path / "rrdb"),
        "--output-root", str(output),
        "--prep-only",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    with (
        mock.patch.object(entry, "resolve_current", return_value=receipt) as resolve,
        mock.patch.object(
            entry,
            "build_daily_package",
            return_value=({"status": "PASS"}, {"status": "PASS"}, []),
        ) as build,
        mock.patch.object(entry, "bind", side_effect=fake_bind),
    ):
        assert entry.main() == 0

    resolve.assert_called_once_with(
        current,
        "2026-10-17",
        "2026-10-12",
        sed_archives=None,
        expected_dates=None,
        work_root=None,
        generation_id=None,
        resolved_bundle=None,
    )
    assert build.call_args.kwargs["race_lap_parquet"] == resolved_parquet
    operation = json.loads(
        (output / "operation_handoff.json").read_text(encoding="utf-8")
    )
    assert operation["status"] == "FORECAST_PREP_READY"
    assert operation["race_lap_resolution"]["status"] == "CURRENT_READY"
    assert operation["race_lap_resolution"]["generation_id"] == "racelap-test"

    assert operation["race_count"] == 1
    assert operation["expected_venues"] == ["東京"]
