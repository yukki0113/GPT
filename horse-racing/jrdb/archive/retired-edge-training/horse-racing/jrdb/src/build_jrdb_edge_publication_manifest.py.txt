#!/usr/bin/env python3
"""Build a fail-closed publication manifest for JRDB Edge Registry assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "jrdb_edge_registry_publication"
REQUIRED_FILES = (
    "edge_registry.sqlite",
    "edge_registry_active.jsonl",
    "edge_registry_active.csv",
    "edge_registry_audit.json",
    "edge_statistical_guard.jsonl",
    "edge_statistical_guard_audit.json",
    "edge_registry_summary.json",
    "edge_registry_summary.md",
)


class PublicationManifestError(RuntimeError):
    """Publication assets are incomplete or internally inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationManifestError(f"invalid JSON: {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationManifestError(f"JSON root must be an object: {path.name}")
    return value


def _validate_source(
    *, issue_number: int, run_id: int, head_sha: str, request_id: str, from_year: int, to_year: int
) -> None:
    if issue_number <= 0 or run_id <= 0:
        raise PublicationManifestError("issue_number and run_id must be positive")
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha.lower()):
        raise PublicationManifestError("head_sha must be a 40-character hexadecimal Git SHA")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", request_id):
        raise PublicationManifestError("invalid request_id")
    if from_year < 2010 or to_year < from_year:
        raise PublicationManifestError("invalid source year range")


def build_manifest(
    publication_dir: str | Path,
    *,
    issue_number: int,
    run_id: int,
    head_sha: str,
    request_id: str,
    from_year: int,
    to_year: int,
    template_version: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(publication_dir)
    if not root.is_dir():
        raise PublicationManifestError(f"publication directory not found: {root}")
    _validate_source(
        issue_number=issue_number,
        run_id=run_id,
        head_sha=head_sha,
        request_id=request_id,
        from_year=from_year,
        to_year=to_year,
    )
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", template_version):
        raise PublicationManifestError("invalid template_version")

    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise PublicationManifestError(f"missing required publication file(s): {missing}")

    registry_path = root / "edge_registry.sqlite"
    connection = sqlite3.connect(registry_path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise PublicationManifestError(f"registry integrity_check failed: {integrity}")
        meta_rows = connection.execute(
            "SELECT registry_version,policy_version,source_scope,status FROM edge_registry_meta"
        ).fetchall()
        if len(meta_rows) != 1:
            raise PublicationManifestError(f"expected one edge_registry_meta row, found {len(meta_rows)}")
        registry_version, policy_version, source_scope, meta_status = map(str, meta_rows[0])
        if meta_status != "VALID":
            raise PublicationManifestError(f"registry metadata status is not VALID: {meta_status}")
        counts = {
            str(status): int(count)
            for status, count in connection.execute(
                "SELECT status,COUNT(*) FROM edge_definition GROUP BY status ORDER BY status"
            )
        }
    finally:
        connection.close()

    registry_audit = _load_json(root / "edge_registry_audit.json")
    if registry_audit.get("status") != "PASS":
        raise PublicationManifestError(
            f"edge_registry_audit status is not PASS: {registry_audit.get('status')!r}"
        )
    stat_audit = _load_json(root / "edge_statistical_guard_audit.json")
    if stat_audit.get("status") != "PASS":
        raise PublicationManifestError(
            f"edge_statistical_guard_audit status is not PASS: {stat_audit.get('status')!r}"
        )
    _load_json(root / "edge_registry_summary.json")

    files = {
        name: {"size_bytes": (root / name).stat().st_size, "sha256": sha256_file(root / name)}
        for name in REQUIRED_FILES
    }
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    live_count = counts.get("ACTIVE", 0) + counts.get("PROVISIONAL", 0)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "READY",
        "generated_at": timestamp,
        "registry_version": registry_version,
        "policy_version": policy_version,
        "template_version": template_version,
        "source_scope": source_scope,
        "source": {
            "issue_number": issue_number,
            "run_id": run_id,
            "head_sha": head_sha.lower(),
            "request_id": request_id,
            "from_year": from_year,
            "to_year": to_year,
        },
        "integrity": {
            "registry_sqlite": "ok",
            "registry_audit": "PASS",
            "statistical_guard_audit": "PASS",
        },
        "registry_counts": counts,
        "live_edge_count": live_count,
        "statistical_guard": {
            "bootstrap_evaluated": stat_audit.get("bootstrap_evaluated"),
            "downgraded_to_watch": stat_audit.get("downgraded_to_watch"),
            "performance_stat_pass": stat_audit.get("performance_stat_pass"),
            "value_stat_pass": stat_audit.get("value_stat_pass"),
        },
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--from-year", type=int, required=True)
    parser.add_argument("--to-year", type=int, required=True)
    parser.add_argument("--template-version", required=True)
    args = parser.parse_args()
    manifest = build_manifest(
        args.publication_dir,
        issue_number=args.issue_number,
        run_id=args.run_id,
        head_sha=args.head_sha,
        request_id=args.request_id,
        from_year=args.from_year,
        to_year=args.to_year,
        template_version=args.template_version,
    )
    Path(args.output).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "manifest_version": VERSION, "output": args.output}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
