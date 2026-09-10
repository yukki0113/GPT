#!/usr/bin/env python3
"""v0.2 Edge Registry pipeline profile built on the validated V2 orchestrator."""
from __future__ import annotations

import sys
from pathlib import Path

import run_jrdb_edge_registry_pipeline as base

VERSION = "0.2.7"
ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "config/jrdb_edge_candidate_templates_v0_2.json"
POLICIES = ROOT / "config/jrdb_edge_validation_policies_v0_2.json"
_BASE_BUILD_STAGES = base.build_stages

# Frozen from Full #827 / run 34442743305. These checks apply only to the
# canonical 2010-2025 sensitivity run so shorter smoke periods remain valid.
FULL_SUGGESTIVE_BASELINE_CANDIDATES = 519
FULL_SUGGESTIVE_BASELINE_CHANNELS = 540
FULL_SUGGESTIVE_EDGE_SET_SHA256 = "a65138340b905f5bd5650ca773346a3262dcd5a62e0bc823e1e5de0d2cea86f4"
FULL_SUGGESTIVE_CHANNEL_SET_SHA256 = "bbe29fd342b6a6e9a833612390e4ab39da19b55b2cd9503e26211a5d6fe589b5"


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
            replaced.append(
                base.Stage(
                    "suggestive_bootstrap_research",
                    (
                        python,
                        str(ROOT / "src/research_jrdb_edge_suggestive_bootstrap_v0_1.py"),
                        "--mart",
                        str(paths.mart_db),
                        "--registry",
                        str(paths.out_dir / "edge_registry.sqlite"),
                        "--registry-audit",
                        str(paths.out_dir / "edge_registry_audit.json"),
                        "--output-jsonl",
                        str(paths.out_dir / "edge_suggestive_bootstrap_research.jsonl"),
                        "--audit-json",
                        str(paths.out_dir / "edge_suggestive_bootstrap_research_audit.json"),
                        "--audit-md",
                        str(paths.out_dir / "edge_suggestive_bootstrap_research_audit.md"),
                        "--q-low",
                        "0.05",
                        "--q-high",
                        "0.10",
                        "--bootstrap-samples",
                        "400",
                    ),
                    base.FAILURE_CLASS_DOMAIN,
                )
            )

            sensitivity_command = [
                python,
                str(ROOT / "src/research_jrdb_edge_suggestive_bootstrap_sensitivity_v0_1.py"),
                "--mart",
                str(paths.mart_db),
                "--registry",
                str(paths.out_dir / "edge_registry.sqlite"),
                "--registry-audit",
                str(paths.out_dir / "edge_registry_audit.json"),
                "--baseline-jsonl",
                str(paths.out_dir / "edge_suggestive_bootstrap_research.jsonl"),
                "--output-jsonl",
                str(paths.out_dir / "edge_suggestive_bootstrap_sensitivity.jsonl"),
                "--audit-json",
                str(paths.out_dir / "edge_suggestive_bootstrap_sensitivity_audit.json"),
                "--audit-md",
                str(paths.out_dir / "edge_suggestive_bootstrap_sensitivity_audit.md"),
                "--bootstrap-samples",
                "2000",
            ]
            if request.from_year == 2010 and request.to_year == 2025:
                sensitivity_command.extend(
                    [
                        "--expected-baseline-candidates",
                        str(FULL_SUGGESTIVE_BASELINE_CANDIDATES),
                        "--expected-baseline-channels",
                        str(FULL_SUGGESTIVE_BASELINE_CHANNELS),
                        "--expected-edge-set-sha256",
                        FULL_SUGGESTIVE_EDGE_SET_SHA256,
                        "--expected-channel-set-sha256",
                        FULL_SUGGESTIVE_CHANNEL_SET_SHA256,
                    ]
                )
            replaced.append(
                base.Stage(
                    "suggestive_bootstrap_sensitivity",
                    tuple(sensitivity_command),
                    base.FAILURE_CLASS_DOMAIN,
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
