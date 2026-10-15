"""End-to-end canonical ZIP -> native Parquet contract tests."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jrdb_race_lap_dataset import build_archive_rows, build_dataset, build_rows
from jrdb_race_lap_shape import shape_from_segments
from test_racenote_lap_shape_evidence import make_sed, make_srb, put

FULL = [125, 110, 121, 132, 128, 118, 121]
PARTIAL = [70, 106, 119, 127, 123, 123, 124, 128, 132]


def archive(tmp_path, name="SED261012.zip", key="05264501", distance=1400, laps=None,
            pace="", bias="", comment="", date="20261012", missing=False, duplicate=False):
    path = tmp_path / name
    srb = bytearray(make_srb(key, FULL if laps is None else laps, pace))
    if bias:
        put(srb, 321, 3, bias)
    if comment:
        put(srb, 343, 500, comment)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("SED261012.txt", make_sed(key, date, distance) + b"\r\n")
        zf.writestr("SRB261012.txt", b"" if missing else (bytes(srb) + b"\r\n") * (2 if duplicate else 1))
    return path


def test_full_metrics(tmp_path):
    row = build_rows([archive(tmp_path)])[0]
    assert row["segment_distances_m"] == [200] * 7
    assert row["lap_count"] == row["comparable_200m_lap_count"] == 7
    assert not row["partial_first_segment"]
    expected = {"early3f_sec":35.6, "late3f_sec":36.7, "early_late_delta_sec":1.1,
                "lap_std_sec":0.662, "lap_range_sec":2.2, "fastest_lap_sec":11.0,
                "fastest_segment_no":2, "max_accel_sec":1.5, "max_decel_sec":1.1,
                "last_vs_best_sec":1.1, "last3_slope_sec_per_segment":-0.35}
    for key, value in expected.items():
        assert row[key] == value


@pytest.mark.parametrize("distance,laps,first", [(1700,PARTIAL,100),(2100,[70]+[120]*10,100),(1150,[90]+[120]*5,150)])
def test_partial(tmp_path,distance,laps,first):
    row=build_rows([archive(tmp_path,distance=distance,laps=laps)])[0]
    assert row["segment_distances_m"] == [first]+[200]*(len(laps)-1)
    assert row["partial_first_segment"]
    assert row["comparable_200m_lap_count"] == len(laps)-1
    assert row["early3f_sec"] is row["early_late_delta_sec"] is None
    assert row["fastest_segment_no"] == 2


@pytest.mark.parametrize("options", [{},{"pace":"3"},{"bias":"内"},{"comment":"直線で加速"}])
def test_context_and_no_laps(tmp_path,options):
    row=build_rows([archive(tmp_path,laps=[],**options)])[0]
    assert row["coverage_status"] == "NO_LAPS"
    assert row["lap_count"] == 0
    assert row["lap_times_sec"] == row["segment_distances_m"] == []
    assert row["max_accel_sec"] is row["max_decel_sec"] is None
    assert row["optional_srb_context_available"] == bool(options)
    assert row["race_comment"] == options.get("comment")


@pytest.mark.parametrize("options", [{"missing":True},{"duplicate":True},{"laps":[125,110]},{"date":"20260230"}])
def test_bad_source_fails(tmp_path,options):
    with pytest.raises(ValueError):
        build_rows([archive(tmp_path,**options)])


def test_duplicate_across_archives(tmp_path):
    a=archive(tmp_path)
    b=archive(tmp_path,name="other.zip")
    with pytest.raises(ValueError,match="duplicate"):
        build_rows([a,b])


def test_internal_blank(tmp_path):
    a=archive(tmp_path)
    with zipfile.ZipFile(a) as zf:
        sed,srb=zf.read("SED261012.txt"),bytearray(zf.read("SRB261012.txt"))
    srb[11:14]=b"   "
    with zipfile.ZipFile(a,"w") as zf:
        zf.writestr("SED261012.txt",sed); zf.writestr("SRB261012.txt",srb)
    with pytest.raises(ValueError,match="internal blank"):
        build_rows([a])


def test_deterministic_and_no_overwrite(tmp_path):
    a=archive(tmp_path)
    b=archive(tmp_path,name="SED260905.zip",key="01262501",date="20260905",distance=1700,laps=PARTIAL)
    assert build_rows([a,b]) == build_rows([b,a])
    p,q=tmp_path/"one.parquet",tmp_path/"two.parquet"
    report=build_dataset([a,b],p,tmp_path/"one.json")
    other=build_dataset([b,a],q,tmp_path/"two.json")
    assert p.read_bytes() == q.read_bytes()
    assert report == other
    assert report["validation_status"] == "PASS"
    assert report["race_count"] == 2
    assert report["output_sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        build_dataset([a],p,tmp_path/"three.json")
    before=p.read_bytes()
    build_dataset([a,b],p,tmp_path/"one.json",replace=True)
    assert p.read_bytes() == before
    assert not list(tmp_path.glob("*.duckdb"))


def test_output_aliases_rejected(tmp_path):
    a=archive(tmp_path)
    with pytest.raises(ValueError):
        build_dataset([a],a,tmp_path/"audit.json",replace=True)


def test_malformed_extra_member_fails_closed(tmp_path):
    a=archive(tmp_path)
    with zipfile.ZipFile(a,"a") as zf:
        zf.writestr("SRB261013.txt",b"truncated record")
    with pytest.raises(ValueError,match="record lengths"):
        build_rows([a])


def test_cli_exit_and_existing_output(tmp_path):
    import subprocess
    a=archive(tmp_path)
    script=Path(__file__).resolve().parents[1]/"src/jrdb_race_lap_dataset.py"
    command=[sys.executable,str(script),str(a),"--output",str(tmp_path/"out.parquet"),"--audit",str(tmp_path/"audit.json")]
    run=subprocess.run(command,text=True,capture_output=True)
    assert run.returncode == 0,run.stderr
    assert json.loads(run.stdout)["validation_status"] == "PASS"
    run=subprocess.run(command,text=True,capture_output=True)
    assert run.returncode != 0
    assert "exists" in run.stderr


def test_duplicate_sed_horse_rows_keep_one_race(tmp_path):
    a=archive(tmp_path)
    with zipfile.ZipFile(a) as zf:
        sed,srb=zf.read("SED261012.txt"),zf.read("SRB261012.txt")
    with zipfile.ZipFile(a,"w") as zf:
        zf.writestr("SED261012.txt",sed*18)
        zf.writestr("SRB261012.txt",srb)
    assert len(build_rows([a])) == 1
