from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from jrdb_edge_v02_canonical import horse_age_at_race, track_condition_bucket
from build_jrdb_edge_feature_mart_v0_2 import build as build_mart, _status as mart_status
import jrdb_edge_discovery_v0_2 as discovery_v02
import jrdb_edge_matcher_v0_2 as matcher_v02
import jrdb_edge_statistical_guard as stats_base
import jrdb_edge_temporal_validator as temporal_base
import apply_jrdb_edge_statistical_guard_v0_2  # noqa: F401
import build_jrdb_edge_registry_v0_2  # noqa: F401


def test_horse_age_uses_jra_calendar_age() -> None:
    assert horse_age_at_race("2025-01-05", "2023-04-10") == 2
    assert horse_age_at_race("2025-12-28", "2023-04-10") == 2
    assert horse_age_at_race("2025-01-05", "2026-01-01") is None


def test_track_condition_bucket_collapses_jrdb_speed_subcodes() -> None:
    assert track_condition_bucket("10") == "1"
    assert track_condition_bucket("12") == "1"
    assert track_condition_bucket("20") == "2"
    assert track_condition_bucket("31") == "3"
    assert track_condition_bucket("42") == "4"
    assert track_condition_bucket("3") == "3"
    assert track_condition_bucket(4) == "4"
    assert track_condition_bucket("99") is None


def test_v02_catalog_enables_cross_recent_and_track_but_not_human() -> None:
    catalog = json.loads((ROOT / "config/jrdb_edge_candidate_templates_v0_2.json").read_text(encoding="utf-8"))
    by_id = {row["template_id"]: row for row in catalog["templates"]}
    assert catalog["rules"]["max_modifier_count"] == 3
    assert by_id["SIRE_BROODMARE_SIRE_V2"]["enabled"] is True
    assert by_id["SIRE_AGE_V2"]["enabled"] is True
    assert by_id["SIRE_VENUE_SURFACE_DISTANCE_V2"]["enabled"] is True
    assert by_id["COURSE_EXACT_FRAME_V2"]["enabled"] is True
    assert by_id["RECENT_UPTREND_SURFACE_DISTANCE_V2"]["enabled"] is True
    assert by_id["SIRE_TRACK_CONDITION_V2"]["enabled"] is True
    assert by_id["SIRE_TRACK_CONDITION_V2"]["historical_discovery_only"] is True
    assert by_id["SIRE_TRACK_CONDITION_V2"]["modifier_fields"] == ["surface_code", "track_condition_bucket"]
    assert by_id["JOCKEY_VENUE_DISTANCE_V2"]["enabled"] is False
    assert by_id["JOCKEY_VENUE_DISTANCE_V2"]["baseline"] == "human_residual_required"


def test_v02_obstacle_rows_are_retained_but_ineligible() -> None:
    row = {
        "source_availability_class": "PRE_RACE",
        "surface_code": "3",
        "label_finish": 1,
        "label_abnormal_code": "0",
    }
    assert mart_status(row) == "EXCLUDED_OBSTACLE"
    schema = (ROOT / "schema/jrdb_edge_feature_mart_schema_v0_2.sql").read_text(encoding="utf-8")
    assert "EXCLUDED_OBSTACLE" in schema


def test_v02_canonical_filter_rejects_obstacle_and_noncanonical_transition() -> None:
    catalog = json.loads((ROOT / "config/jrdb_edge_candidate_templates_v0_2.json").read_text(encoding="utf-8"))
    flat_track = {
        "anchor": {"sire_name": "SIRE"},
        "modifiers": {"surface_code": "1", "track_condition_bucket": "3"},
    }
    obstacle_track = {
        "anchor": {"sire_name": "SIRE"},
        "modifiers": {"surface_code": "3", "track_condition_bucket": "3"},
    }
    obstacle_transition = {
        "anchor": {"sire_name": "SIRE"},
        "modifiers": {"surface_transition": "3->1"},
    }
    noncanonical_turn = {
        "anchor": {"sire_name": "SIRE"},
        "modifiers": {"turn_code": "9", "distance_m": 1600},
    }
    assert discovery_v02._candidate_is_canonical(flat_track, catalog) is True
    assert discovery_v02._candidate_is_canonical(obstacle_track, catalog) is False
    assert discovery_v02._candidate_is_canonical(obstacle_transition, catalog) is False
    assert discovery_v02._candidate_is_canonical(noncanonical_turn, catalog) is False


def test_v02_temporal_validator_accepts_all_added_condition_fields() -> None:
    expected = {
        "frame_no", "horse_age", "rotation_interval", "pre_idm", "training_score",
        "stable_score", "uptrend_code", "training_arrow_code", "stable_evaluation_code",
        "body_weight_pre_kg", "body_weight_change_pre_kg", "track_condition_bucket",
    }
    assert expected <= temporal_base.ALLOWED_FIELDS


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


def test_broodmare_sire_routes_to_pedigree_lifecycle_policy() -> None:
    policies = json.loads((ROOT / "config/jrdb_edge_validation_policies_v0_2.json").read_text(encoding="utf-8"))
    selected = discovery_v02.select_policy_v02(
        family="PEDIGREE",
        anchor_type="broodmare_sire",
        first_seen_date="2018-01-01",
        total_n=1000,
        as_of_date="2025-12-31",
        catalog=policies,
    )
    assert selected.policy_id == "LIFECYCLE_SIRE_V1"
    assert selected.validation_class == "LIFECYCLE"


def test_v02_matcher_accepts_new_condition_fields_and_track_fails_closed_without_current_source() -> None:
    age_edge = {
        "edge_id": "EDGE-V02",
        "status": "ACTIVE",
        "display_text": "v0.2",
        "polarity": "POSITIVE",
        "conditions": {
            "template_id": "SIRE_AGE_V2",
            "template_version": "2026-09-09.v2.1",
            "anchor": {"sire_name": "SIRE"},
            "modifiers": {"horse_age": 2},
        },
    }
    runner = {"race_date": "2026-09-12", "sire_name": "SIRE", "horse_age": 2}
    assert matcher_v02.edge_matches_runner(age_edge, runner) is not None

    track_edge = {
        "edge_id": "EDGE-TRACK-V02",
        "status": "ACTIVE",
        "display_text": "track",
        "polarity": "POSITIVE",
        "conditions": {
            "template_id": "SIRE_TRACK_CONDITION_V2",
            "template_version": "2026-09-09.v2.1",
            "anchor": {"sire_name": "SIRE"},
            "modifiers": {"surface_code": "1", "track_condition_bucket": "3"},
        },
    }
    assert matcher_v02.edge_matches_runner(track_edge, runner) is None
    runner_with_pre_race_track = {
        **runner,
        "surface_code": "1",
        "track_condition_bucket": "3",
    }
    assert matcher_v02.edge_matches_runner(track_edge, runner_with_pre_race_track) is not None
    assert "horse_age" in matcher_v02.base.CONDITION_FIELDS
    assert "track_condition_bucket" in matcher_v02.base.CONDITION_FIELDS
    assert "uptrend_code" in stats_base.ALLOWED_FIELDS
    assert "track_condition_bucket" in stats_base.ALLOWED_FIELDS


def test_feature_mart_v02_projects_age_recent_and_isolated_track_condition(tmp_path: Path) -> None:
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
    # Track condition is stored in the SED-derived race-level result-context table,
    # separate from runner_result labels/payouts.
    con.execute(
        """INSERT INTO race_result_context(
          race_key,track_condition_code,weather_code,source_member,semantic_hash
        ) VALUES(?,?,?,?,?)""",
        ("05250101", "31", "1", "SED250105.txt", "rc"),
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
    assert result["historical_track_condition_rows"] == 1
    assert result["historical_track_condition_races"] == 1
    assert result["excluded_obstacle"] == 0
    out = sqlite3.connect(output)
    row = out.execute(
        """SELECT horse_age,pre_idm,uptrend_code,training_arrow_code,
                  stable_evaluation_code,frame_no,track_condition_code,
                  track_condition_bucket,track_condition_source_class
           FROM edge_runner_fact"""
    ).fetchone()
    meta = out.execute(
        "SELECT historical_track_condition_count,excluded_obstacle_count FROM meta_edge_feature_mart_build"
    ).fetchone()
    out.close()
    assert row == (2, 55.0, "2", "1", "3", 8, "31", "3", "HISTORICAL_RESULT_CONTEXT")
    assert meta == (1, 0)
