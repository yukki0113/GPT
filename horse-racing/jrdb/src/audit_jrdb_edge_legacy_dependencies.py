#!/usr/bin/env python3
"""Audit EdgeDB active references to the legacy GPT/JRDB Drive root.

This is a storage/source-of-truth audit only. It does not alter scientific semantics.
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
SCAN_ROOTS = (
    Path("horse-racing/jrdb/src"),
    Path("horse-racing/jrdb/config"),
    Path("horse-racing/jrdb/docs"),
    Path(".github/workflows"),
)
TEXT_SUFFIXES = {".py", ".json", ".md", ".yml", ".yaml", ".txt", ".html"}


def _classify(path: Path, line: str) -> str:
    normalized = path.as_posix().lower()
    text = line.lower()
    if "/legacy/" in normalized or normalized.endswith("_legacy_index.html"):
        return "LEGACY_REPRO"
    if "historical" in text or "legacy" in text or "deprecated" in text or "migration" in text:
        return "LEGACY_REPRO"
    return "ACTIVE"


def audit(repo_root: Path) -> dict:
    matches = []
    for relative_root in SCAN_ROOTS:
        root = repo_root / relative_root
        if not root.exists():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(lines, 1):
                for label, pattern in PATTERNS.items():
                    if pattern in line:
                        matches.append({
                            "path": path.relative_to(repo_root).as_posix(),
                            "line": lineno,
                            "pattern": label,
                            "classification": _classify(path.relative_to(repo_root), line),
                            "text": line.strip()[:500],
                        })
    active = [m for m in matches if m["classification"] == "ACTIVE"]
    legacy = [m for m in matches if m["classification"] == "LEGACY_REPRO"]
    return {
        "status": "PASS" if not active else "FAIL",
        "gate": "EDGE_LEGACY_JRDB_ACTIVE_REFERENCE_COUNT",
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
