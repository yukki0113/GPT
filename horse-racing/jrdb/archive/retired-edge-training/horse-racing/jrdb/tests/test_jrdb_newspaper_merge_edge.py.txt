"""Focused tests for Newspaper EdgeDB merge."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import jrdb_newspaper_merge_edge as merger  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    """Write one small JSON fixture."""
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def test_merge_edge_day_projects_special_memos_and_updates_manifest(tmp_path: Path) -> None:
    """Exact Edge rows become canonical Newspaper special memos and refresh hashes."""
    day_dir = tmp_path / "day"
    races_dir = day_dir / "races"
    races_dir.mkdir(parents=True)
    race_path = races_dir / "race.json"
    legacy_edge_matches = [{"edge_id": "LEGACY", "display_text": "legacy fallback"}]
    bundle = {
        "schema_version": "0.1",
        "bundle_kind": "jrdb_pwa_newspaper_race",
        "race": {"race_key": "01262501", "date": "2026-09-05"},
        "horses": [
            {
                "key": {"race_horse_key": "0126250104", "horse_no": 4},
                "basic": {"horse_name": "テストホース"},
                "edge_matches": legacy_edge_matches,
            }
        ],
        "metadata": {"source_status": {}},
    }
    _write_json(race_path, bundle)
    _write_json(
        day_dir / "manifest.json",
        {
            "schema_version": "0.1",
            "manifest_kind": "jrdb_pwa_newspaper_daily_manifest",
            "races": [
                {
                    "race_key": "01262501",
                    "path": "races/race.json",
                    "sha256": "old",
                    "size_bytes": 1,
                }
            ],
            "source_status": {},
        },
    )
    _write_json(day_dir / "audit.json", {"status": "PASS"})

    edge_path = tmp_path / "edge_matches.jsonl"
    edge_row = {
        "key": {
            "race_key": "01262501",
            "race_horse_key": "0126250104",
            "horse_id": "24102603",
            "horse_no": 4,
            "race_date": "2026-09-05",
        },
        "edge_matches": [
            {
                "edge_id": "EDGE-1",
                "display_text": "＋ 好走傾向",
                "status": "ACTIVE",
                "polarity": "POSITIVE",
                "evidence": {"performance_signal": "POSITIVE"},
            }
        ],
    }
    edge_path.write_text(json.dumps(edge_row, ensure_ascii=False) + "\n", encoding="utf-8")

    output_dir = tmp_path / "out"
    result = merger.merge_edge_day(day_dir, edge_path, output_dir)

    merged = json.loads((output_dir / "races" / "race.json").read_text(encoding="utf-8"))
    horse = merged["horses"][0]
    assert result["status"] == "PASS"
    assert result["merger_version"] == "0.2.0"
    assert result["merged_rows"] == 1
    assert result["memo_runners"] == 1
    assert result["memo_count"] == 1
    assert horse["special_memos"][0]["memo_text"] == "＋ 好走傾向"
    assert horse["edge_matches"] == legacy_edge_matches
    assert merged["metadata"]["source_status"]["edge"]["state"] == "READY"

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_status"]["edge"]["state"] == "READY"
    assert manifest["races"][0]["sha256"] != "old"

    day_package = json.loads((output_dir / "day-package.json").read_text(encoding="utf-8"))
    packaged_horse = day_package["races"][0]["horses"][0]
    assert packaged_horse["special_memos"][0]["memo_text"] == "＋ 好走傾向"
    assert packaged_horse["edge_matches"] == legacy_edge_matches
