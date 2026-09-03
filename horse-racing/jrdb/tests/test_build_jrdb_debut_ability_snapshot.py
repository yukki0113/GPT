"""Smoke tests for time-aware Debut Ability snapshot construction."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
BUILDER_PATH = SRC / "build_jrdb_debut_ability_snapshot.py"
AUDIT_PATH = SRC / "audit_jrdb_debut_ability_snapshot.py"
INDEX_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_index_base_schema_v0_1.sql"
OFFICIAL_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_official_runperf_schema_v0_1.sql"
DEBUT_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_debut_ability_snapshot_schema_v0_1.sql"


def _load(name: str, path: Path):
    """Load one module directly from its repository path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = _load("debut_ability_builder_smoke", BUILDER_PATH)
AUDIT = _load("debut_ability_audit_smoke", AUDIT_PATH)


def _insert_race(connection: sqlite3.Connection, race_key: str, race_date: str, year: int, race_no: int) -> None:
    """Insert one minimal PRE_RACE race context."""
    connection.execute(
        """
        INSERT INTO race_context(
          race_key,race_date,year,venue_code,race_no,distance_m,surface_code,
          availability_class,source_kind,record_hash
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (race_key,race_date,year,"01",race_no,1600,"1","PRE_RACE","BAC",f"hash-{race_key}"),
    )


def _insert_runner(
    connection: sqlite3.Connection,
    race_key: str,
    horse_no: int,
    horse_id: str,
    jockey: str,
    trainer: str,
) -> None:
    """Insert one minimal pre-race runner."""
    connection.execute(
        """
        INSERT INTO runner_pre(
          race_key,horse_no,horse_id,horse_name,sex_code,jockey_code,trainer_code,
          carried_weight_kg,record_hash
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (race_key,horse_no,horse_id,horse_id,"1",jockey,trainer,55.0,f"pre-{race_key}-{horse_no}"),
    )


def _insert_profile(
    connection: sqlite3.Connection,
    horse_id: str,
    data_date: str,
    sire: str,
    damsire: str = "DS1",
) -> None:
    """Insert one time-stamped UKC profile observation."""
    connection.execute(
        """
        INSERT INTO horse_profile_observation(
          horse_id,data_date,horse_name,sex_code,sire_name,dam_name,broodmare_sire_name,
          birth_date,sire_birth_year,dam_birth_year,broodmare_sire_birth_year,
          breeder_name,breeding_place,sire_line_code,broodmare_sire_line_code,
          semantic_hash,source_member,record_hash
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            horse_id,data_date,horse_id,"1",sire,"DAM",damsire,"20100301",2000,2001,1999,
            "BREEDER","PLACE","SL1","DSL1",f"semantic-{horse_id}-{data_date}","UKC",f"profile-{horse_id}-{data_date}",
        ),
    )


def _insert_official_label(
    connection: sqlite3.Connection,
    race_key: str,
    race_date: str,
    year: int,
    horse_no: int,
    horse_id: str,
    value: float,
) -> None:
    """Insert one valid official RunPerf result used only after its race date closes."""
    connection.execute(
        """
        INSERT INTO official_runperf(
          race_key,race_date,year,horse_no,horse_id,source_calculation_status,score_status,
          runperf_raw,score_provenance
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (race_key,race_date,year,horse_no,horse_id,"OK","OK",value,"fixture"),
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Create a two-date fixture with same-day labels and prior/same-day UKC observations."""
    index = tmp_path / "index.sqlite"
    official = tmp_path / "official.sqlite"

    connection = sqlite3.connect(index)
    try:
        connection.executescript(INDEX_SCHEMA.read_text(encoding="utf-8"))
        _insert_race(connection,"R2012","20120101",2012,1)
        _insert_runner(connection,"R2012",1,"H1","J1","T1")
        _insert_runner(connection,"R2012",2,"H2","J2","T2")
        _insert_profile(connection,"H1","20111220","S1")
        _insert_profile(connection,"H2","20111220","S1")

        _insert_race(connection,"R2013","20130101",2013,1)
        _insert_runner(connection,"R2013",1,"H3","J1","T1")
        _insert_profile(connection,"H3","20121220","S1")
        # Same-day UKC is verified PRE_RACE profile data and should be selected.
        _insert_profile(connection,"H3","20130101","S1")
        connection.execute(
            """
            INSERT INTO workout_main(
              race_key,horse_no,training_date,workout_count,course_code,jrdb_workout_index,record_hash
            ) VALUES(?,?,?,?,?,?,?)
            """,
            ("R2013",1,"20121228",2,"01",72,"workout-R2013-1"),
        )
        connection.execute(
            """
            INSERT INTO training_analysis(
              race_key,horse_no,training_type_code,training_course_type_code,jrdb_workout_index,
              finish_index,training_volume_code,record_hash
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            ("R2013",1,"A","1",70,68,"B","training-R2013-1"),
        )
        connection.commit()
    finally:
        connection.close()

    connection = sqlite3.connect(official)
    try:
        connection.executescript(OFFICIAL_SCHEMA.read_text(encoding="utf-8"))
        _insert_official_label(connection,"R2012","20120101",2012,1,"H1",0.40)
        _insert_official_label(connection,"R2012","20120101",2012,2,"H2",0.80)
        connection.commit()
    finally:
        connection.close()
    return index, official


def test_same_day_results_do_not_enter_debut_prior_and_same_day_profile_is_selected(tmp_path: Path) -> None:
    """Daily batching blocks same-day result leakage while verified same-day UKC is selected."""
    index, official = _fixture(tmp_path)
    output = tmp_path / "debut.sqlite"
    BUILDER.build(index,official,output,DEBUT_SCHEMA)

    connection = sqlite3.connect(output)
    connection.row_factory = sqlite3.Row
    try:
        first_day = connection.execute(
            "SELECT * FROM debut_pedigree_feature WHERE race_key='R2012' ORDER BY horse_no"
        ).fetchall()
        assert len(first_day) == 2
        assert all(row["sire_debut_n"] == 0 and row["sire_debut_runperf_raw"] is None for row in first_day)

        target = connection.execute(
            "SELECT * FROM debut_target_runner WHERE race_key='R2013' AND horse_no=1"
        ).fetchone()
        pedigree = connection.execute(
            "SELECT * FROM debut_pedigree_feature WHERE race_key='R2013' AND horse_no=1"
        ).fetchone()
        training = connection.execute(
            "SELECT * FROM debut_training_feature WHERE race_key='R2013' AND horse_no=1"
        ).fetchone()
        assert target is not None and pedigree is not None and training is not None
        assert target["is_true_first_start"] == 1
        assert target["profile_data_date"] == "20130101"
        assert target["profile_prior_day_available"] == 1
        assert target["profile_same_day_observation_exists"] == 1
        assert target["sire_name"] == "S1"
        assert pedigree["sire_debut_n"] == 2
        assert abs(pedigree["sire_debut_runperf_raw"] - 0.60) < 1e-12
        assert training["cha_missing"] == 0
        assert training["cyb_missing"] == 0
    finally:
        connection.close()


def test_structural_audit_passes_and_predictive_holdout_remains_unopened(tmp_path: Path) -> None:
    """The structural audit must pass without selecting a model or opening predictive holdout metrics."""
    index, official = _fixture(tmp_path)
    output = tmp_path / "debut.sqlite"
    report_path = tmp_path / "audit.json"
    BUILDER.build(index,official,output,DEBUT_SCHEMA)
    report = AUDIT.audit(output,index,official)
    report_path.write_text(__import__("json").dumps(report,allow_nan=False),encoding="utf-8")
    assert report["status"] == "PASS"
    assert report["violations"] == {key:0 for key in report["violations"]}
    assert report["2024_2025_predictive_metrics_inspected"] is False
    assert report["model_selected"] is False
