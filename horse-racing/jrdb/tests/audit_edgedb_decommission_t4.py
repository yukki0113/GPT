#!/usr/bin/env python3
"""T4: fail closed on executable references to retired EdgeDB assets.

Scan tracked active code, preserving literal retirement guards, historical docs and
Training Edge research. This audit is deliberately independent of external Drive.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "horse-racing/jrdb/archive/retired-edge-training/T4_AUDIT_REPORT.json"
ACTIVE = (".github/workflows", "horse-racing/jrdb/src",
          "horse-racing/jrdb/tests", "horse-racing/brdb/src",
          "horse-racing/brdb/tests", "tools")
SUFFIXES = {".py", ".yml", ".yaml", ".sh", ".cjs", ".js", ".mjs", ".ts"}
RETIRED_MODULE = re.compile(r"^(?:jrdb_edge_|jrdb_edgedb_|racenote_edge_)")
RETIRED_FILENAME = re.compile(
    r"(?<![A-Za-z_])(?:jrdb_edge_|jrdb_edgedb_|racenote_edge_)[A-Za-z0-9_]*\.py"
)
RETIRED_OPERATION = re.compile(
    r"(?:edge_feature_mart_v0_2|edge_registry_v0_2|edge_serving_catalog|"
    r"GPT/horse-racing/20_mart/edge|(?<![a-z])20_mart/edge)"
)
RETIRED_KEY = re.compile(r"EDGEDB_PERFORMANCE_OVERLAY|edge_v05")
RUNTIME_INVOKE = re.compile(r"\b(?:python(?:3)?|pytest|py_compile|runpy|importlib|"
                            r"source|bash|sh|node)\b", re.I)
EXEMPT_GUARD = ("jrdb_newspaper_retired_sources.py", "test_newspaper_source_retirement.py",
                "test_retired_training_asset_boundary.py", "test_newspaper_retired_sources.cjs",
                "test_newspaper_edge_v05_production.cjs")
TRACKED = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
issues = []
observations = []
scanned = 0


def warn(path: str, lineno: int, text: str, label: str):
    observations.append(dict(path=path, line=lineno, classification=label,
                             excerpt=text.strip()[:180]))


for rel in TRACKED:
    if not rel or not rel.startswith(ACTIVE):
        continue
    p = ROOT / rel
    if p.suffix not in SUFFIXES or not p.is_file():
        continue
    scanned += 1
    contents = p.read_text(encoding="utf-8", errors="replace")
    guard = p.name in EXEMPT_GUARD
    if p.suffix == ".py":
        try:
            tree = ast.parse(contents, filename=rel)
        except SyntaxError as exc:
            issues.append(dict(path=rel, line=exc.lineno, reason="syntax error", evidence=str(exc)))
            continue
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            for name in modules:
                if RETIRED_MODULE.match(name):
                    issues.append(dict(path=rel, line=node.lineno,
                                       reason="retired runtime import", evidence=name))
    for lineno, line in enumerate(contents.splitlines(), 1):
        trimmed = line.strip()
        match = RETIRED_FILENAME.search(line)
        if match:
            # Historical comments and assertions about rejected legacy inputs are
            # not execution. Executable YAML shell and Python invocation are.
            executable = (p.suffix in {".yml", ".yaml", ".sh"} and
                          not trimmed.startswith("#")) or (
                          RUNTIME_INVOKE.search(line) and not trimmed.startswith(("#", "//")))
            if executable and not guard:
                issues.append(dict(path=rel, line=lineno,
                                   reason="retired module executable reference",
                                   evidence=line.strip()[:180]))
            else:
                warn(rel, lineno, line, "historical/guard reference")
        if RETIRED_OPERATION.search(line):
            if not guard and not trimmed.startswith(("#", "//")):
                issues.append(dict(path=rel, line=lineno, reason="retired Drive/artifact path",
                                   evidence=line.strip()[:180]))
            else:
                warn(rel, lineno, line, "historical/guard reference")
        elif RETIRED_KEY.search(line):
            warn(rel, lineno, line, "retired key or historical reference")

# The retirement guard is a deliberate live dependency; never remove it.
for required in ("horse-racing/jrdb/src/jrdb_newspaper_retired_sources.py",
                 "horse-racing/jrdb/src/jrdb_previous_start_research_ledger.py",
                 "horse-racing/jrdb/src/jrdb_canonical_codes.py",
                 "horse-racing/jrdb/tests/test_retired_training_asset_boundary.py"):
    if not (ROOT / required).is_file():
        issues.append(dict(path=required, reason="required shared asset missing"))

# Enforce that the selective T3 archive preserved exactly the remaining 35 entries.
manifest_path = ROOT / "horse-racing/jrdb/archive/retired-edge-training/ASSET_MAP.json"
entries = json.loads(manifest_path.read_text())
if len(entries) != 35:
    issues.append(dict(path=str(manifest_path), reason="retained archive count changed",
                       evidence=str(len(entries))))
for entry in entries:
    if "edge" in entry["original"].lower() and "training_edge" not in entry["original"].lower():
        issues.append(dict(path=entry["original"], reason="retired EdgeDB archive entry survived"))
    if not (ROOT / entry["archive"]).is_file():
        issues.append(dict(path=entry["archive"], reason="preserved archive missing"))
report = dict(status="PASS" if not issues else "FAIL", tracked_files_scanned=scanned,
              active_roots=list(ACTIVE), issues=issues, observations=observations)
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "observations"}, ensure_ascii=False))
if issues:
    raise SystemExit(1)
