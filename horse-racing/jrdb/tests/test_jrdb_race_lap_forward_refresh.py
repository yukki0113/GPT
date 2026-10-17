"""Incremental RaceLap preservation, idempotency, and conflict regression."""
import copy

import pytest

from test_jrdb_race_lap_dataset import archive, build_dataset, build_rows
from jrdb_race_lap_forward_refresh import refresh


def test_forward_append_noop_conflict(tmp_path, monkeypatch):
    import jrdb_race_lap_forward_refresh as mod
    incoming_archive = archive(tmp_path)
    original = build_rows([incoming_archive])[0]
    previous_path = tmp_path / "old.parquet"
    build_dataset([incoming_archive], previous_path, tmp_path / "original_audit.json")
    # Identity retry must not republish.
    result = refresh(previous_path, [incoming_archive], tmp_path / "output", "lap-noop-01",
                     [original["race_date"]])
    assert result["status"] == "NOOP_IDENTICAL_RETRY"

    changed = copy.deepcopy(original)
    changed["distance_m"] += 200
    monkeypatch.setattr(mod, "build_rows", lambda _: [changed])
    with pytest.raises(ValueError, match="CONFLICT"):
        refresh(previous_path, [incoming_archive], tmp_path / "output", "lap-conflict-01")

    newer = copy.deepcopy(original)
    newer["race_key"] = "05274501"
    newer["race_date"] = "2026-10-13"
    monkeypatch.setattr(mod, "build_rows", lambda _: [newer])
    result = refresh(previous_path, [incoming_archive], tmp_path / "output", "lap-forward-01",
                     ["2026-10-13"])
    assert result["new_count"] == 1
    assert result["race_count"] == 2
    assert result["validation_status"] == "PASS"
    assert (tmp_path / "output/generations/lap-forward-01/race_lap.parquet").exists()
