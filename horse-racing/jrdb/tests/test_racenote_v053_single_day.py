from __future__ import annotations

import json
from pathlib import Path

import racenote_v053_single_day as single


ROOT = Path(__file__).resolve().parents[1]
BT = ROOT / "backtests" / "BTDAY-0059" / "20260510"
PREP = BT / "forecast_prep"
REFERENCE = BT / "ab" / "v052" / "frozen" / "records.json"


def test_v053_single_day_can_replay_frozen_decision_cores_without_ab(tmp_path: Path) -> None:
    handoff = json.loads((PREP / "day_prep_handoff.json").read_text(encoding="utf-8"))
    root = tmp_path / "v053"

    session = single.init_session(PREP, root, handoff["main_sha"])
    assert session["logic_version"] == "RaceNote-Human-Context-Reader-0.5.3-candidate"
    assert session["market_blind"] is True
    assert session["result_opened"] is False
    assert session["expected_venues"] == ["京都", "新潟", "東京"]

    records = json.loads(REFERENCE.read_text(encoding="utf-8"))
    by_venue: dict[str, list[dict]] = {}
    for row in records:
        core = row["decision_core"]
        compression = core["candidate_compression"]
        decision = compression["decision"]
        if decision == "ADMIT_CHALLENGER":
            core["boundary_review"]["alternative_horse_no"] = compression["excluded_horse_no"]
        elif decision == "KEEP_ORDINARY_FIVE":
            core["boundary_review"]["alternative_horse_no"] = compression["external_challenger_horse_no"]
        else:
            core["boundary_review"]["alternative_horse_no"] = None
        by_venue.setdefault(row["venue"], []).append(core)

    for venue, cores in by_venue.items():
        cores.sort(key=lambda x: x["race_no"])
        incoming = root / "incoming" / f"{venue}.json"
        incoming.write_text(json.dumps(cores, ensure_ascii=False), encoding="utf-8")
        saved = single.save_venue(root, incoming)
        assert saved["venue"] == venue

    frozen = single.build_freeze(root)
    assert frozen["status"] == "FROZEN_CLEAN_BLIND"
    assert frozen["record_count"] == 36
    assert frozen["result_opened"] is False

    verified = single.verify_freeze(root)
    assert verified["session_id"] == session["session_id"]
    assert verified["record_count"] == 36


def test_single_day_session_is_one_lane_only(tmp_path: Path) -> None:
    handoff = json.loads((PREP / "day_prep_handoff.json").read_text(encoding="utf-8"))
    root = tmp_path / "v053"
    session = single.init_session(PREP, root, handoff["main_sha"])
    payload = json.loads((root / "session.json").read_text(encoding="utf-8"))

    assert "lane_definitions" not in payload
    assert "v051_enabled" not in payload
    assert "ab_profile" not in payload
    assert payload["logic_version"] == single.LOGIC
    assert not (root / "ab_session.json").exists()
