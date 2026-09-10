import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import run_racenote_v11p_settlement as settlement  # noqa: E402


def test_validate_freeze_reads_current_outputs_schema(tmp_path, monkeypatch):
    day = "20260704"
    day_file = "RaceNote_v1_1_Polarity_Gated_20260704_PRE_HJC.json"
    day_payload = {
        "freeze_stage": "PRE_HJC",
        "result_data_used": False,
        "date": "2026-07-04",
        "races": [{} for _ in range(36)],
    }
    day_sha = settlement.dump_json(tmp_path / day_file, day_payload)
    canonical_sha = "a" * 64
    manifest = {
        "freeze_stage": "PRE_HJC",
        "result_data_used": False,
        "dates": [day],
        "outputs": {
            "combined_canonical_payload_sha256": canonical_sha,
            "days": {day: {"file": day_file, "sha256": day_sha, "races": 36}},
        },
    }
    manifest_name = "freeze.json"
    manifest_sha = settlement.dump_json(tmp_path / manifest_name, manifest)
    monkeypatch.setattr(settlement, "EXPECTED_DATES", (day,))
    monkeypatch.setattr(settlement, "FREEZE_MANIFEST", manifest_name)
    request = {
        "freeze": {
            "manifest_sha256": manifest_sha,
            "combined_canonical_payload_sha256": canonical_sha,
        }
    }
    loaded_manifest, loaded_days = settlement.validate_freeze(tmp_path, request)
    assert loaded_manifest["outputs"]["days"][day]["sha256"] == day_sha
    assert loaded_days[day]["date"] == "2026-07-04"
