from data_storage.dependencies import dependency_report


def test_dependency_report_shape():
    report = dependency_report()
    assert set(report["packages"]) == {"duckdb", "pyarrow"}
    assert report["status"] in {"success", "DEPENDENCY_MISSING", "DEPENDENCY_MISMATCH"}


def test_missing_dependency_status(monkeypatch):
    import data_storage.dependencies as module

    real_find_spec = module.importlib.util.find_spec
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: None if name == "duckdb" else real_find_spec(name))
    report = dependency_report()
    assert report["status"] == "DEPENDENCY_MISSING"
    assert report["missing_packages"] == ["duckdb"]


def test_old_duckdb_version_is_dependency_mismatch(monkeypatch):
    import data_storage.dependencies as module

    real_version = module.importlib.metadata.version
    monkeypatch.setattr(
        module.importlib.metadata,
        "version",
        lambda name: "1.1.3" if name == "duckdb" else real_version(name),
    )
    report = dependency_report()
    assert report["status"] == "DEPENDENCY_MISMATCH"
    assert report["version_mismatches"] == [
        {"package": "duckdb", "actual": "1.1.3", "expected": "2.0.1"}
    ]


def test_expected_duckdb_version_passes(monkeypatch):
    import data_storage.dependencies as module

    real_version = module.importlib.metadata.version
    monkeypatch.setattr(
        module.importlib.metadata,
        "version",
        lambda name: "2.0.1" if name == "duckdb" else real_version(name),
    )
    report = dependency_report()
    if report["missing_packages"]:
        assert report["status"] == "DEPENDENCY_MISSING"
    else:
        assert report["status"] == "success"
        assert report["version_mismatches"] == []
