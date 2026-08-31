from __future__ import annotations

import importlib.util
from pathlib import Path

BUILD_PATH = Path(__file__).resolve().parents[1] / "src" / "build_jrdb_runperf_features.py"
AUDIT_PATH = Path(__file__).resolve().parents[1] / "src" / "audit_jrdb_runperf.py"
FIXTURE_PATH = Path(__file__).with_name("test_build_jrdb_runperf_features.py")
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "jrdb_runperf_schema_v0_1.sql"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = _load("runperf_builder_audit_test", BUILD_PATH)
AUDIT = _load("runperf_auditor", AUDIT_PATH)
FIXTURE = _load("runperf_fixture", FIXTURE_PATH)


def test_audit_passes_for_synthetic_build(tmp_path: Path) -> None:
    source = tmp_path / "index.sqlite"
    output = tmp_path / "runperf.sqlite"
    FIXTURE._make_source(source)
    BUILD.build(source, output, SCHEMA_PATH, ("EXPANDING", "ROLLING_2Y"))
    report = AUDIT.audit(output, include_db_sha256=False)
    assert report["status"] == "PASS"
    assert report["violations"]["chronology"] == 0
    assert report["violations"]["market_named_columns"] == []
