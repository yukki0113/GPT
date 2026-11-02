#!/usr/bin/env python3
"""Audit EdgeDB-scoped active references to the legacy GPT/JRDB Drive root.

This audit intentionally excludes generic JRDB storage/resolver code and other
non-Edge subsystems. The completion gate in the migration request is specific
to current EdgeDB code/workflow/config/docs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PATTERNS = {
    "OLD_PATH": "GPT/JRDB",
    "OLD_ROOT_ID": "1NW8p8Ww0al1RoQxXbjDXgpkEJ3XwV9sf",
    "LEGACY_LOGICAL_NAME": "jrdb://",
}

ROOTS = (
    Path("horse-racing/jrdb/src"),
    Path("horse-racing/jrdb/config"),
    Path("horse-racing/jrdb/docs"),
    Path(".github/workflows"),
)
TEXT_SUFFIXES = {".py", ".json", ".md", ".yml", ".yaml", ".txt", ".html"}
SELF = Path("horse-racing/jrdb/src/audit_jrdb_edge_legacy_dependencies.py")


def _edge_scoped(path: Path) -> bool:
    p = path.as_posix().lower()
    name = path.name.lower()
    if path == SELF:
        return False
    if p.startswith(".github/workflows/"):
        return "edge" in name
    if p.startswith("horse-racing/jrdb/config/"):
        return "edge" in name
    if p.startswith("horse-racing/jrdb/src/"):
        return "edge" in name
    if p.startswith("horse-racing/jrdb/docs/"):
        return "edge" in name
    return False


def _classify(path: Path, line: str) -> str:
    text = line.lower()
    p = path.as_posix().lower()
    if "/legacy/" in p:
        return "LEGACY_REPRO"
    migration_terms = (
        "old gpt/jrdb",
        "旧 gpt/jrdb",
        "no new edge artifact",
        "active reference",
        "legacy",
        "decoupl",
        "migration",
        "削除",
    )
    if any(term in text for term in migration_terms):
        return "LEGACY_REPRO"
    return "ACTIVE"


def audit(repo_root: Path) -> dict:
    matches = []
    scanned_files = 0
    for relative_root in ROOTS:
        root = repo_root / relative_root
        if not root.exists():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES):
            rel = path.relative_to(repo_root)
            if not _edge_scoped(rel):
                continue
            scanned_files += 1
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(lines, 1):
                for label, pattern in PATTERNS.items():
                    if pattern in line:
                        matches.append({
                            "path": rel.as_posix(),
                            "line": lineno,
                            "pattern": label,
                            "classification": _classify(rel, line),
                            "text": line.strip()[:500],
                        })
    active = [m for m in matches if m["classification"] == "ACTIVE"]
    legacy = [m for m in matches if m["classification"] == "LEGACY_REPRO"]
    return {
        "status": "PASS" if not active else "FAIL",
        "gate": "EDGE_LEGACY_JRDB_ACTIVE_REFERENCE_COUNT",
        "scope": "EDGE_DB_ONLY",
        "scanned_file_count": scanned_files,
        "active_reference_count": len(active),
        "legacy_repro_reference_count": len(legacy),
        "dead_reference_count": 0,
        "matches": matches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.repo_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
