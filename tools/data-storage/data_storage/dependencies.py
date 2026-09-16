from __future__ import annotations

import importlib.metadata
import importlib.util
import platform

REQUIRED = ("duckdb", "pyarrow")


def dependency_report() -> dict:
    packages = {}
    missing = []
    for name in REQUIRED:
        available = importlib.util.find_spec(name) is not None
        version = importlib.metadata.version(name) if available else None
        packages[name] = {"available": available, "version": version}
        if not available:
            missing.append(name)
    return {
        "status": "success" if not missing else "DEPENDENCY_MISSING",
        "python_version": platform.python_version(),
        "packages": packages,
        "missing_packages": missing,
    }

