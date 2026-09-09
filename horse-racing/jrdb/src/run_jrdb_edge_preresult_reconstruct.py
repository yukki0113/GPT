#!/usr/bin/env python3
"""Reconstruct pre-result Edge matching for historical blind prediction freezes.

This runner is deliberately result-free: it accepts PACI, Analysis Lite, and a
published ACTIVE Edge Registry only. It never downloads HJC/SED and never
settles outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

SHA_RE = re.compile(r"[0-9a-f]{64}")
DATE_RE = re.compile(r"20\d{6}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_request(path: Path) -> dict[str, Any]:
    request = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "dates",
        "analysis_url",
        "analysis_sha256",
        "registry_run_id",
        "registry_artifact_name",
        "registry_sha256",
        "sources",
    }
    missing = sorted(required - set(request))
    if missing:
        raise ValueError(f"missing required fields: {missing}")

    dates = [str(value).strip() for value in request["dates"]]
    if not dates or len(dates) > 31 or dates != sorted(dates):
        raise ValueError("dates must be a non-empty sorted list with <=31 entries")
    if len(set(dates)) != len(dates) or any(not DATE_RE.fullmatch(day) for day in dates):
        raise ValueError("dates must be unique YYYYMMDD values")

    analysis_url = str(request["analysis_url"]).strip()
    analysis_sha = str(request["analysis_sha256"]).strip().lower()
    registry_sha = str(request["registry_sha256"]).strip().lower()
    if not analysis_url.startswith("https://drive.google.com/"):
        raise ValueError("analysis_url must be a Google Drive URL")
    if not SHA_RE.fullmatch(analysis_sha) or not SHA_RE.fullmatch(registry_sha):
        raise ValueError("analysis_sha256/registry_sha256 must be lowercase SHA-256")

    run_id = request["registry_run_id"]
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
        raise ValueError("registry_run_id must be a positive integer")
    artifact = str(request["registry_artifact_name"]).strip()
    if not artifact:
        raise ValueError("registry_artifact_name must be non-empty")

    sources = request["sources"]
    if not isinstance(sources, dict) or set(sources) != set(dates):
        raise ValueError("sources keys must exactly equal dates")
    normalized_sources: dict[str, dict[str, str]] = {}
    for day in dates:
        row = sources[day]
        if not isinstance(row, dict):
            raise ValueError(f"sources.{day} must be an object")
        paci_sha = str(row.get("paci_sha256", "")).strip().lower()
        if not SHA_RE.fullmatch(paci_sha):
            raise ValueError(f"sources.{day}.paci_sha256 must be lowercase SHA-256")
        normalized_sources[day] = {"paci_sha256": paci_sha}

    return {
        "dates": dates,
        "analysis_url": analysis_url,
        "analysis_sha256": analysis_sha,
        "registry_run_id": run_id,
        "registry_artifact_name": artifact,
        "registry_sha256": registry_sha,
        "sources": normalized_sources,
        "evaluation_mode": "PRE_RESULT_RECONSTRUCTION",
    }


def download_registry(request: dict[str, Any], work: Path, repository: str) -> Path:
    registry_dir = work / "registry"
    registry_dir.mkdir(parents=True)
    subprocess.run(
        [
            "gh",
            "run",
            "download",
            str(request["registry_run_id"]),
            "--repo",
            repository,
            "--name",
            request["registry_artifact_name"],
            "--dir",
            str(registry_dir),
        ],
        check=True,
    )
    candidates = list(registry_dir.rglob("edge_registry_active.jsonl"))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one edge_registry_active.jsonl; found {len(candidates)}")
    path = candidates[0]
    actual = sha256_file(path)
    if actual != request["registry_sha256"]:
        raise RuntimeError(f"Registry SHA mismatch expected={request['registry_sha256']} actual={actual}")
    return path


def download_analysis(request: dict[str, Any], work: Path) -> Path:
    downloaded = work / "analysis.download"
    subprocess.run(["gdown", request["analysis_url"], "-O", str(downloaded)], check=True)
    database = work / "jrdb_analysis.sqlite"
    if zipfile.is_zipfile(downloaded):
        with zipfile.ZipFile(downloaded) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise RuntimeError(f"Analysis ZIP corrupt member: {bad}")
            members = [
                name
                for name in archive.namelist()
                if not name.endswith("/") and Path(name).name.lower().endswith((".sqlite", ".bin"))
            ]
            if len(members) != 1:
                raise RuntimeError(f"Analysis ZIP must contain exactly one DB: {members}")
            with archive.open(members[0]) as source, database.open("wb") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
    else:
        shutil.copyfile(downloaded, database)

    actual = sha256_file(database)
    if actual != request["analysis_sha256"]:
        raise RuntimeError(f"Analysis SHA mismatch expected={request['analysis_sha256']} actual={actual}")
    with sqlite3.connect(database) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"Analysis integrity_check={integrity}")
    return database


def reconstruct_day(
    day: str,
    request: dict[str, Any],
    output_root: Path,
    registry: Path,
    analysis: Path,
    repo_root: Path,
) -> dict[str, Any]:
    day_dir = output_root / "days" / day
    raw_dir = day_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetcher = repo_root / "horse-racing/jrdb/src/fetch_jrdb_paci.py"
    matcher = repo_root / "horse-racing/jrdb/src/run_jrdb_edge_match_current.py"
    subprocess.run([sys.executable, str(fetcher), "--date", day, "--out-dir", str(raw_dir)], check=True)

    paci = raw_dir / f"PACI{day[2:]}.zip"
    if not paci.is_file():
        raise RuntimeError(f"PACI missing: {paci}")
    paci_sha = sha256_file(paci)
    expected_paci = request["sources"][day]["paci_sha256"]
    if paci_sha != expected_paci:
        raise RuntimeError(f"PACI SHA mismatch {day}: expected={expected_paci} actual={paci_sha}")

    matches = day_dir / "edge_matches.jsonl"
    facts = day_dir / "current_facts.jsonl"
    subprocess.run(
        [
            sys.executable,
            str(matcher),
            "--paci",
            str(paci),
            "--analysis-db",
            str(analysis),
            "--registry-jsonl",
            str(registry),
            "--output-jsonl",
            str(matches),
            "--facts-jsonl",
            str(facts),
            "--statuses",
            "ACTIVE",
        ],
        check=True,
    )

    rows = [json.loads(line) for line in matches.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {
        "paci_sha256": paci_sha,
        "matches_sha256": sha256_file(matches),
        "facts_sha256": sha256_file(facts),
        "runner_rows": len(rows),
        "matched_runners": sum(bool(row.get("edge_matches")) for row in rows),
        "matches": sum(len(row.get("edge_matches") or []) for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--head-sha")
    parser.add_argument("--request-id")
    args = parser.parse_args()

    request = load_request(Path(args.request_json))
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    repo_root = Path(args.repo_root).resolve()
    repository = os.environ.get("GITHUB_REPOSITORY", "yukki0113/GPT")

    with tempfile.TemporaryDirectory(prefix="jrdb-preresult-") as temp:
        work = Path(temp)
        registry = download_registry(request, work, repository)
        analysis = download_analysis(request, work)
        days = {
            day: reconstruct_day(day, request, output_root, registry, analysis, repo_root)
            for day in request["dates"]
        }

    result = {
        "status": "success",
        "run_id": args.run_id,
        "head_sha": args.head_sha,
        "request_id": args.request_id,
        "evaluation_mode": "PRE_RESULT_RECONSTRUCTION",
        "result_data_used": False,
        "request": request,
        "days": days,
    }
    (output_root / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
