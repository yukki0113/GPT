"""Physical validation and single-query batch lookup regressions."""
import copy
from unittest.mock import patch

import duckdb
import pytest

from test_jrdb_race_lap_dataset import archive, build_rows, build_dataset
from jrdb_race_lap_contract import COLUMN_TYPES
from jrdb_race_lap_store import RaceLapStore, RaceLapStoreError


def write_rows(path, rows, types=None):
    types = COLUMN_TYPES if types is None else types
    with duckdb.connect(":memory:") as con:
        con.execute("CREATE TABLE data ("+", ".join(f'"{k}" {t}' for k,t in types.items())+")")
        if rows:
            con.executemany("INSERT INTO data VALUES ("+", ".join("?" for _ in types)+")",[[r[k] for k in types] for r in rows])
        literal="'"+str(path).replace("'","''")+"'"
        con.execute(f"COPY data TO {literal} (FORMAT PARQUET)")


@pytest.fixture
def valid(tmp_path):
    p=tmp_path/"data.parquet"
    build_dataset([archive(tmp_path)],p,tmp_path/"audit.json")
    return p


def test_lookup_and_batch_one_query(valid):
    store=RaceLapStore(valid)
    assert store.metadata()["race_count"] == 1
    row=store.get(" 05264501 ")
    assert row["race_date"] == "2026-10-12"
    assert row["lap_times_sec"][0] == 12.5
    assert isinstance(row["track_bias_raw"],dict)
    assert store.get("00000000") is None
    with patch.object(store,"_query",wraps=store._query) as query:
        rows=store.get_many(iter(["05264501","00000000","05264501"]))
        assert query.call_count == 1
        assert rows == {"05264501":row,"00000000":None}
        assert query.call_args.args[1][1:] == ["05264501","00000000"]
    with patch.object(store,"_query") as query:
        assert store.get_many([]) == {}
        query.assert_not_called()


@pytest.mark.parametrize("key", ["", " ", "123", "x' OR 1=1 --"])
def test_invalid_key(valid,key):
    with pytest.raises(ValueError):
        RaceLapStore(valid).get(key)


def test_sql_key_bound(valid):
    store=RaceLapStore(valid)
    assert store.get("' OR 1=1") is None
    assert store.metadata()["race_count"] == 1


def test_missing(tmp_path):
    with pytest.raises(RaceLapStoreError):
        RaceLapStore(tmp_path/"missing.parquet")


@pytest.mark.parametrize("mutation", [
    {"race_key":None},{"race_key":" short "},
    {"dataset_schema_version":"bad"},{"shape_logic_version":"bad"},
    {"track_bias_raw_json":"{"},{"track_bias_raw_json":"[]"},
    {"track_bias_raw_json":'{"corner1": NaN}'},
    {"lap_count":6},{"segment_distances_m":[100]*7},
    {"segment_distances_m":[None]*7},{"lap_times_sec":[float('nan')]*7},
    {"lap_std_sec":float('inf')},{"race_date":None},{"source_archive":None},
    {"early_late_delta_available":False},{"comparable_200m_lap_count":6},
    {"partial_first_segment":True},{"fastest_segment_no":8},
    {"coverage_status":"NO_LAPS"},{"race_comment":"extra"},
])
def test_corruption_fails_closed(tmp_path,mutation):
    row=build_rows([archive(tmp_path)])[0]
    row.update(mutation)
    p=tmp_path/"bad.parquet"
    write_rows(p,[row])
    with pytest.raises(RaceLapStoreError):
        RaceLapStore(p)


def test_duplicates_and_mixed_versions(tmp_path):
    row=build_rows([archive(tmp_path)])[0]
    p=tmp_path/"bad.parquet"
    write_rows(p,[row,row])
    with pytest.raises(RaceLapStoreError,match="duplicate"):
        RaceLapStore(p)
    second=copy.deepcopy(row); second.update(race_key="00000000",shape_logic_version="other")
    write_rows(p,[row,second])
    with pytest.raises(RaceLapStoreError,match="version"):
        RaceLapStore(p)


@pytest.mark.parametrize("mode", ["missing_column","wrong_type","empty"])
def test_schema_errors(tmp_path,mode):
    row=build_rows([archive(tmp_path)])[0]
    types=dict(COLUMN_TYPES)
    if mode == "missing_column":
        types.pop("race_date")
    if mode == "wrong_type":
        types["lap_times_sec"]="VARCHAR"
    p=tmp_path/"bad.parquet"
    write_rows(p,[] if mode == "empty" else [row],types)
    with pytest.raises(RaceLapStoreError):
        RaceLapStore(p)


def test_duplicate_result_after_open(valid):
    store=RaceLapStore(valid)
    raw=store._query(store._select(),[str(valid)])[0]
    with patch.object(store,"_query",return_value=[raw,raw]):
        with pytest.raises(RaceLapStoreError,match="duplicate"):
            store.get("05264501")
