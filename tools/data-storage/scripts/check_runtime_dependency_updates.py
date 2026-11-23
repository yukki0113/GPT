#!/usr/bin/env python3
"""Read-only monitoring of the *approved* ChatGPT offline-runtime dependency set.

No dependency installs, artifact uploads, version pin changes or predictions.
PyPI JSON is authoritative for published wheels, not for DuckDB LTS status.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/chatgpt_offline_runtime_v1.json"
MONITORED = ("duckdb", "pyarrow", "numpy")
STABLE_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+)+$")


def version_key(s: str) -> tuple[int, ...] | None:
    if not STABLE_VERSION.fullmatch(s):
        return None
    return tuple(map(int, s.split(".")))


def classify(current: str, candidate: str) -> str:
    old = version_key(current)
    new = version_key(candidate)
    if old is None or new is None:
        return "unknown"
    old, new = (old + (0,) * 3)[:3], (new + (0,) * 3)[:3]
    if new[0] != old[0]:
        return "major"
    if new[1] != old[1]:
        return "minor"
    if new[2] != old[2]:
        return "patch"
    return "same"


def published_stable_releases(info: dict) -> list[str]:
    releases = info.get("releases", {})
    if not isinstance(releases, dict):
        raise ValueError("INVALID_PYPI: releases object missing")
    values = []
    for ver, files in releases.items():
        if version_key(ver) is None or not isinstance(files, list):
            continue
        if any(f.get("packagetype") == "bdist_wheel" and not f.get("yanked", False) for f in files):
            values.append(ver)
    return sorted(values, key=version_key, reverse=True)


def wheel_hint(info: dict, candidate: str) -> dict:
    """Informational tag check, not an assertion of runtime compatibility."""
    files = info["releases"][candidate]
    compatible = []
    for f in files:
        name = f.get("filename", "")
        if f.get("packagetype") != "bdist_wheel" or f.get("yanked"):
            continue
        if "x86_64" not in name or "manylinux" not in name:
            continue
        if "-cp313-" in name or "-cp312-abi3-" in name or "-py3-none-" in name:
            compatible.append(name)
    return {"python313_linux_x86_64_wheel_hint": bool(compatible),
            "wheel_filenames": compatible[:5],
            "requires_further_abi_glibc_check": True}


def inspect(registry: dict, pypi: dict[str, dict], at: str) -> dict:
    baselines = {x["package"]: x["version"] for x in registry["packages"]}
    if set(baselines) != set(MONITORED):
        raise ValueError("INVALID_REGISTRY: expected exactly duckdb, pyarrow and numpy")
    report = {"schema_version": "gpt.runtime_dependency_watch.v1",
              "checked_at_utc": at,
              "runtime_registry_sha256": None,
              "status": "NO_UPDATES",
              "promotion": "NEVER_AUTOMATIC",
              "components": []}
    for name in MONITORED:
        releases = published_stable_releases(pypi[name])
        if not releases:
            raise ValueError(f"INVALID_PYPI: no eligible stable wheels for {name}")
        current, latest = baselines[name], releases[0]
        current_key, latest_key = version_key(current), version_key(latest)
        if current_key is None:
            raise ValueError("INVALID_REGISTRY: nonstable baseline")
        newer = latest_key > current_key
        if newer:
            report["status"] = "REVIEW_REQUIRED"
        report["components"].append({
            "name": name,
            "approved_runtime_version": current,
            "latest_stable_with_non_yanked_wheel": latest,
            "newer_available": newer,
            "change_type": classify(current, latest),
            "pypi_url": f"https://pypi.org/project/{name}/{latest}/",
            "source_notes": ("DuckDB LTS eligibility and support lifecycle MUST be confirmed "
                             "manually against official DuckDB release calendar" if name == "duckdb"
                             else "PyPI publication is not a compatibility or promotion approval"),
            **wheel_hint(pypi[name], latest),
        })
    return report


def download_json(name: str) -> dict:
    url = f"https://pypi.org/pypi/{name}/json"
    req = urllib.request.Request(url, headers={"User-Agent": "GPT-Dependency-Watch/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    raw = args.registry.read_bytes()
    import hashlib
    registry = json.loads(raw)
    fetched = {name: download_json(name) for name in MONITORED}
    report = inspect(registry, fetched,
                     datetime.now(timezone.utc).isoformat(timespec="seconds"))
    report["runtime_registry_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "components": [(x["name"], x["approved_runtime_version"],
                                      x["latest_stable_with_non_yanked_wheel"])
                                     for x in report["components"]]}))


if __name__ == "__main__":
    main()
