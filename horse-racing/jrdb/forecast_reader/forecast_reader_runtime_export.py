#!/usr/bin/env python3
"""Export canonical source and CPython 3.13 Linux wheels for GPT acceptance runtime.

No JRDB data is included. Outputs only source from checkout and public PyPI wheels.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRS = (
    "horse-racing/jrdb/forecast_reader",
    "horse-racing/jrdb/src",
    "tools/data-storage",
)
ALLOWED_SUFFIXES = {".py", ".json", ".yaml", ".yml", ".txt"}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "forecast_reader_source.zip"
    items = []
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zipfile:
        for folder in SOURCE_DIRS:
            for file in sorted((ROOT / folder).rglob("*")):
                if (not file.is_file() or file.suffix not in ALLOWED_SUFFIXES
                    or any(part in ("__pycache__", ".venv", "node_modules") for part in file.parts)):
                    continue
                relative = file.relative_to(ROOT)
                zipfile.write(file, relative.as_posix())
                items.append(relative.as_posix())
    wheels = output / "wheels"
    wheels.mkdir(exist_ok=True)
    command = [
        sys.executable, "-m", "pip", "download", "--disable-pip-version-check",
        "--only-binary=:all:", "--no-deps",
        "--python-version", "313", "--implementation", "cp",
        "--abi", "cp313", "--platform", "manylinux2014_x86_64",
        "--dest", str(wheels), "duckdb==1.1.3", "pyarrow==20.0.0",
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    report = {
        "schema_version": "forecast-reader-runtime-export.v1",
        "archive": archive.name,
        "source_file_count": len(items),
        "source_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "wheel_download_exit": result.returncode,
        "wheel_log_tail": (result.stdout + result.stderr)[-2500:],
        "wheels": [
            {"name": p.name, "size_bytes": p.stat().st_size,
             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(wheels.glob("*.whl"))
        ],
    }
    (output / "runtime_export_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"source_file_count": len(items), "wheel_count": len(report["wheels"]),
                      "wheel_download_exit": result.returncode}))
    return 0 if result.returncode == 0 and len(report["wheels"]) == 2 else 1

if __name__ == "__main__":
    raise SystemExit(main())
