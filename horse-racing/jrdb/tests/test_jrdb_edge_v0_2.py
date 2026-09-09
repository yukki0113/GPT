from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from jrdb_edge_v02_canonical import horse_age_at_race
from build_jrdb_edge_feature_mart_v0_2 import build as build_mart
import jrdb_edge_discovery_v0_2 as discovery_v02
import jrdb_edge_matcher_v0_2 as matcher_v02
import jrdb_edge_statistical_guard as stats_base
import apply_jrdb_edge_statistical_guard_v0_2  # noqa: F401


def test_horse_age_uses_jra_calendar_age() -> None:
    assert horse_age_at_race("2025-01-05", "2023-04-10") == 2
    assert horse_age_at_race("2025-12-28", "2023-04-10") == 2
    assert horse_age_at_race("2025-01-05", "2026-01-01") is None


def test_v02_catalog_enables_cross_and_recent_but_not_human() -> None:
    catalog = json.loads((ROOT / "config/jrdb_edge_candidate_templates_v0_2.json").read_text(encoding="utf-8"))
    by_id = {row["template_id"]: row for row in catalog["templates"]}
    assert catalog["rules"]["max_modifier_count"] == 3
    assert by_id["SIRE_BROODMARE_SIRE_V2"]["enabled"] is True
    assert by_id["SIRE_AGE_V2"]["enabled"] is True
    assert by_id["SIRE_VENUE_SURFACE_DISTANCE_V2"]["enabled"] is True
    assert by_id["COURSE_EXACT_FRAME_V2"]["enabled"] is True
    assert by_id["RECENT_UPTREND_SURFACE_DISTANCE_V2"]["enabled"] is True
    assert by_id["JOCKEY_VENUE_DISTANCE_V2"]["enabled"] is False
    assert by_id["JOCKEY_VENUE_DISTANCE_V2"]["baseline"] == "human_residual_required"


def test_recent_policy_routes_to_dynamic_recent() -> None:
    policies = json.loads((ROOT / "config/jrdb_edge_validation_policies_v0_2.json").read_text(encoding="utf-8"))
    selected = discovery_v02.select_policy_v02(
        family="RECENT",
        anchor_type="recent",
        first_seen_date="2020-01-01",
        total_n=1000,
        as_of_date="2025-12-31",
        catalog=policies,
    )
    assert selected.policy_id == "DYNAMIC_RECENT_V2"
    assert selected.validation_class == "DYNAMIC"


def test_v02_matcher_accepts_new_condition_fields() -> None:
    edge = {
        "edge_id": "EDGE-V02",
        "status": "ACTIVE",
        "display_text": "v0.2",
        "polarity": "POSITIVE",
        "conditions": {
            "template_id": "SIRE_AGE_V2",
            "template_version": "2026-09-09.v2",
            "anchor": {"sire_name": "SIRE"},
            "modifiers": {"horse_age": 2},
        },
    }
    runner = {"race_date": "2026-09-12", "sire_name": "SIRE", "horse_age": 2}
    assert matcher_v02.edge_matches_runner(edge, runner) is not None
    assert "horse_age" in matcher_v02.base.CONDITION_FIELDS
    assert "uptrend_code" in stats_base.ALLOWED_FIELDS


def test_feature_mart_v02_projects_age_and_recent_fields(tmp_path: Path) -> None:
    source = tmp_path / "index.sqlite"
    output = tmp_path / "mart.sqlite"
    con = sqlite3.connect(source)
    con.executescript((ROOT / "schema/jrdb_index_base_schema_v0_1.sql").read_text(encoding="utf-8"))
    con.execute(
        """INSERT INTO race_context(
          race_key,race_date,year,venue_code,race_no,availability_class,source_kind,record_hash,
          distance_m,surface_code,turn_code,declared_field_size
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("05250101", "2025-01-05", 2025, "05", 1, "PRE_RACE", "BAC", "r", 1600, "1", "1", 12),
    )
    con.execute(
        """INSERT INTO runner_pre(
          race_key,horse_no,horse_id,horse_name,frame_no,sex_code,jockey_code,trainer_code,
          rotation_interval,pre_idm,training_score,stable_score,uptrend_code,training_arrow_code,
          stable_evaluation_code,body_weight_pre_kg,body_weight_change_pre_kg,record_hash
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("05250101", 1, "H1", "HORSE", 8, "1", "J1", "T1", 4, 55.0, 60.0, 58.0, "2", "1", "3", 480, 6, "p"),
    )
    con.execute(
        """INSERT INTO horse_profile_observation(
          horse_id,data_date,horse_name,sire_name,broodmare_sire_name,birth_date,semantic_hash,record_hash
        ) VALUES(?,?,?,?,?,?,?,?)""",
        ("H1", "2025-01-01", "HORSE", "SIRE", "BMS", "2023-04-10", "s", "u"),
    )
    con.execute(
        """INSERT INTO runner_result(
          race_key,horse_no,horse_id,horse_name,finish,abnormal_code,win_payout,place_payout,record_hash
        ) VALUES(?,?,?,?,?,?,?,?,?)""",
        ("05250101", 1, "H1", "HORSE", 1, "0", 350, 150, "x"),
    )
    con.commit()
    con.close()

    result = build_mart(source, output, ROOT / "schema/jrdb_edge_feature_mart_schema_v0_2.sql")
    assert result["rows"] == 1
    out = sqlite3.connect(output)
    row = out.execute(
        "SELECT horse_age,pre_idm,uptrend_code,training_arrow_code,stable_evaluation_code,frame_no FROM edge_runner_fact"
    ).fetchone()
    out.close()
    assert row == (2, 55.0, "2", "1", "3", 8)
