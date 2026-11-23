#!/usr/bin/env python3
"""Install verified JRDB SQL runtime from a *local* Drive-fetched ZIP without network or Actions.

The caller fetches a private Drive binary through the native connector, then passes
its local path and SHA-256 from the reviewed GitHub runtime registry. No JRDB data
is embedded in this package. Never trust a downloaded wheel by filename alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import venv
import zipfile

PACKAGES = {"duckdb": "2.0.1", "pyarrow": "25.0.1"}
BUNDLE_SCHEMA = "jrdb.offline_runtime_wheels.v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_bundle(bundle: Path, expected_sha256: str) -> tuple[dict, dict[str, bytes]]:
    if len(expected_sha256) != 64 or sha256_bytes(bundle.read_bytes()) != expected_sha256.lower():
        raise ValueError("HASH_MISMATCH: archive")
    if sys.version_info[:2] != (3, 13) or platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("UNSUPPORTED_RUNTIME: expected Python 3.13 Linux x86_64")
    with zipfile.ZipFile(bundle) as z:
        if z.testzip():
            raise ValueError("HASH_MISMATCH: corrupted ZIP member")
        names = z.namelist()
        if len(names) != 3 or len(set(names)) != len(names) or "wheel_manifest.json" not in names:
            raise ValueError("INVALID_BUNDLE: expected exactly two wheels and manifest")
        m = json.loads(z.read("wheel_manifest.json"))
        if m.get("schema_version") != BUNDLE_SCHEMA or m.get("python") != "3.13" or m.get("platform") != "linux_x86_64":
            raise ValueError("INVALID_BUNDLE: runtime manifest")
        entries = m.get("packages")
        if not isinstance(entries, list) or len(entries) != 2:
            raise ValueError("INVALID_BUNDLE: package count")
        payload = {}
        found = {}
        for e in entries:
            name = e.get("name", "")
            pkg = name.split("-")[0]
            if pkg not in PACKAGES or e.get("name") not in names or not name.endswith(".whl"):
                raise ValueError("INVALID_BUNDLE: package name")
            if not name.startswith(pkg + "-" + PACKAGES[pkg] + "-") or pkg in found:
                raise ValueError("INVALID_BUNDLE: unexpected package version")
            if "/" in name or "\\" in name or name.startswith("."):
                raise ValueError("INVALID_BUNDLE: unsafe path")
            b = z.read(name)
            if len(b) != e.get("size_bytes") or sha256_bytes(b) != e.get("sha256"):
                raise ValueError("HASH_MISMATCH: " + name)
            payload[name] = b
            found[pkg] = e["sha256"]
        if found.keys() != PACKAGES.keys() or set(names) != set(payload) | {"wheel_manifest.json"}:
            raise ValueError("INVALID_BUNDLE: incomplete package")
    return m, payload


def install(bundle: Path, archive_sha256: str, venv_dir: Path) -> dict:
    manifest, wheels = verify_bundle(bundle, archive_sha256)
    if venv_dir.exists():
        raise ValueError("DESTINATION_EXISTS: supply a fresh environment")
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(venv_dir)
    python = venv_dir / "bin" / "python"
    with tempfile.TemporaryDirectory(prefix="jrdb_wheels_") as tmp:
        staged = []
        for name, payload in wheels.items():
            p = Path(tmp) / name
            p.write_bytes(payload)
            staged.append(str(p))
        subprocess.run([str(python), "-m", "pip", "install", "--no-index",
                        "--no-deps", "--disable-pip-version-check", *staged], check=True)
    check = ("import json, duckdb, pyarrow; "
             "from importlib.metadata import version; "
             "assert version('duckdb') == '2.0.1'; "
             "assert version('pyarrow') == '25.0.1'; "
             "assert duckdb.sql('select 1').fetchone() == (1,); "
             "assert pyarrow.table({'x':[1,2,3]}).num_rows == 3; "
             "print(json.dumps({'duckdb':duckdb.__version__,"
             "'pyarrow':pyarrow.__version__,'select_1':1}))")
    out = subprocess.check_output([str(python), "-c", check], text=True)
    return {"status": "PASS", "archive_sha256": archive_sha256,
            "wheel_manifest": manifest, "version_check": json.loads(out)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--archive-sha256", required=True)
    ap.add_argument("--venv", type=Path, required=True)
    args = ap.parse_args()
    try:
        result = install(args.bundle, args.archive_sha256, args.venv)
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as e:
        print(json.dumps({"status":"BLOCKED","reason":str(e)}, sort_keys=True), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
