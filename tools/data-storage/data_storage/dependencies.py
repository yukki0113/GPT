from __future__ import annotations

import importlib.metadata
import importlib.util
import platform

REQUIRED = ("duckdb", "pyarrow")
PINNED_VERSIONS = {"duckdb": "2.0.1"}


def dependency_report() -> dict:
    packages = {}
    missing = []
    mismatched = []
    for name in REQUIRED:
        available = importlib.util.find_spec(name) is not None
        version = importlib.metadata.version(name) if available else None
        required = PINNED_VERSIONS.get(name)
        packages[name] = {"available": available, "version": version, "required_version": required}
        if available and required is not None and version != required:
            mismatched.append({"package": name, "actual": version, "expected": required})
        if not available:
            missing.append(name)
    return {
        "status": "DEPENDENCY_MISSING" if missing else ("DEPENDENCY_MISMATCH" if mismatched else "success"),
        "python_version": platform.python_version(),
        "packages": packages,
        "missing_packages": missing,
        "version_mismatches": mismatched,
    }

