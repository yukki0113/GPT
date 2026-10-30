import importlib.util
from datetime import date
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from previous_run_reader import read_previous

spec = importlib.util.spec_from_file_location("common_fixture", ROOT.parent / "tests/test_jrdb_raw_common.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def test_join_and_guard(monkeypatch):
    import previous_run_reader as reader
    kyi = fixture.make_kyi()
    zed = fixture.make_sed("20231001", "20260810", "0526A001", "01")
    monkeypatch.setattr(reader, "iter_archive_records", lambda archive, kind, audit: [("fixture", kyi if kind == "KYI" else zed)])
    runners, coverage = read_previous(Path("unused"), "0526A101", date(2026, 8, 30))
    assert coverage == {"runner_count": 1, "previous_available": 1, "missing_previous": 0}
    assert runners[0]["previous_run"]["result_key"] == "2023100120260810"
    with pytest.raises(ValueError, match="FUTURE_LEAK"):
        read_previous(Path("unused"), "0526A101", date(2026, 8, 10))


def test_duplicate_zed_rejected(monkeypatch):
    import previous_run_reader as reader
    kyi = fixture.make_kyi()
    zed = fixture.make_sed("20231001", "20260810", "0526A001", "01")
    monkeypatch.setattr(reader, "iter_archive_records", lambda archive, kind, audit: [("fixture", kyi)] if kind == "KYI" else [("a", zed), ("b", zed)])
    with pytest.raises(ValueError, match="DUPLICATE"):
        read_previous(Path("unused"), "0526A101", date(2026, 8, 30))
