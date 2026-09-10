#!/usr/bin/env python3
"""v0.2 Edge Registry pipeline profile built on the validated V2 orchestrator."""
from __future__ import annotations

import sys
from pathlib import Path

import run_jrdb_edge_registry_pipeline as base

VERSION = "0.2.4"
ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "config/jrdb_edge_candidate_templates_v0_2.json"
POLICIES = ROOT / "config/jrdb_edge_validation_policies_v0_2.json"
_BASE_BUILD_STAGES = base.build_stages


def build_stages_v02(request, paths, python):
    stages = _BASE_BUILD_STAGES(request, paths, python)
    replaced = []
    for stage in stages:
        command = list(stage.command)
        if stage.name == "feature_mart":
            command[1] = str(ROOT / "src/build_jrdb_edge_feature_mart_v0_2.py")
        elif stage.name == "discovery":
            command[1] = str(ROOT / "src/jrdb_edge_discovery_v0_2.py")
            command.extend(["--templates", str(TEMPLATES), "--policies", str(POLICIES)])
        elif stage.name == "registry":
            command[1] = str(ROOT / "src/build_jrdb_edge_registry_v0_2.py")
            command.extend(["--policies", str(POLICIES)])
        elif stage.name == "statistical_guard":
            command[1] = str(ROOT / "src/apply_jrdb_edge_statistical_guard_v0_2.py")
        replaced.append(base.Stage(stage.name, tuple(command), stage.failure_class, stage.retryable))
        if stage.name == "summary":
            replaced.append(
                base.Stage(
                    "watch_audit",
                    (
                        python,
                        str(ROOT / "src/audit_jrdb_edge_watch.py"),
                        "--registry",
                        str(paths.out_dir / "edge_registry.sqlite"),
                        "--output-json",
                        str(paths.out_dir / "edge_watch_audit.json"),
                        "--output-md",
                        str(paths.out_dir / "edge_watch_audit.md"),
                    ),
                    base.FAILURE_CLASS_IMPLEMENTATION,
                )
            )
            replaced.append(
                base.Stage(
                    "stat_watch_audit",
                    (
                        python,
                        str(ROOT / "src/audit_jrdb_edge_stat_watch.py"),
                        "--registry",
                        str(paths.out_dir / "edge_registry.sqlite"),
                        "--output-json",
                        str(paths.out_dir / "edge_stat_watch_audit.json"),
                        "--output-md",
                        str(paths.out_dir / "edge_stat_watch_audit.md"),
                    ),
                    base.FAILURE_CLASS_IMPLEMENTATION,
                )
            )
    return replaced


base.build_stages = build_stages_v02


def main() -> int:
    argv = sys.argv[1:]
    if "--template-version" not in argv:
        argv.extend(["--template-version", "2026-09-09.v2.2"])
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
