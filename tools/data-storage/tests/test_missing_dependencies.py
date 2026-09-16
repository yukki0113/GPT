from data_storage.dependencies import dependency_report


def test_dependency_report_shape():
    report = dependency_report()
    assert set(report["packages"]) == {"duckdb", "pyarrow"}
    assert report["status"] in {"success", "DEPENDENCY_MISSING"}


def test_missing_dependency_status(monkeypatch):
    import data_storage.dependencies as module

    real_find_spec = module.importlib.util.find_spec
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: None if name == "duckdb" else real_find_spec(name))
    report = dependency_report()
    assert report["status"] == "DEPENDENCY_MISSING"
    assert report["missing_packages"] == ["duckdb"]
