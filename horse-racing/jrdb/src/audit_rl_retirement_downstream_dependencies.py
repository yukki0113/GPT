#!/usr/bin/env python3
"""Audit that RL / Training Edge retirement is safe for active downstream production.

This audit is intentionally static. It verifies that active GitHub Actions do not
request retired RL outputs, that Newspaper keeps the historical my_index input
optional, and that RaceNote/EdgeDB/PWA do not acquire a hard dependency on RL.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ACTIVE_WORKFLOW_DIR = Path(".github/workflows")
SRC_DIR = Path("horse-racing/jrdb/src")

FORBIDDEN_ACTIVE_WORKFLOW_PATTERNS = (
    "--my-index-csv",
    "score_training_edge_v0_2_daily.py",
    "project_training_edge_v0_2_input.py",
    "training_edge_v0_2_core.py",
    "build_jrdb_training_research.py",
    "migrate_jrdb_training_research_parquet.py",
)

EDGE_PWA_FORBIDDEN_PATTERNS = (
    "--my-index-csv",
    "training_edge_index",
    "score_training_edge_v0_2",
    "project_training_edge_v0_2",
    "rl_index",
    "RaceLift",
    "RL-T",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _matches(path: Path, patterns: tuple[str, ...]) -> list[str]:
    text = _text(path)
    return [pattern for pattern in patterns if pattern in text]


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    checks: list[dict[str, Any]] = []

    workflow_root = root / ACTIVE_WORKFLOW_DIR
    active_workflows = sorted(workflow_root.glob("*.yml")) + sorted(
        workflow_root.glob("*.yaml")
    )

    active_hits: list[dict[str, Any]] = []
    for path in active_workflows:
        hits = _matches(path, FORBIDDEN_ACTIVE_WORKFLOW_PATTERNS)
        if hits:
            active_hits.append(
                {
                    "path": str(path.relative_to(root)),
                    "patterns": hits,
                }
            )
    checks.append(
        {
            "name": "active_workflows_do_not_require_rl",
            "pass": not active_hits,
            "hit_count": len(active_hits),
            "hits": active_hits,
        }
    )

    newspaper = root / SRC_DIR / "jrdb_newspaper_merge_external.py"
    newspaper_text = _text(newspaper)
    checks.extend(
        [
            {
                "name": "newspaper_my_index_parameter_is_optional",
                "pass": "my_index_csv: Path | None = None" in newspaper_text,
            },
            {
                "name": "newspaper_my_index_none_path_is_supported",
                "pass": "if my_index_csv is None:" in newspaper_text,
            },
            {
                "name": "newspaper_my_index_is_marked_retired_compatibility",
                "pass": (
                    "Historical compatibility only: RL / Training Edge production generation is retired."
                    in newspaper_text
                    and "Normal production must omit this option" in newspaper_text
                ),
            },
        ]
    )

    general = _text(root / SRC_DIR / "racenote_general_evidence.py")
    synthesis = _text(root / SRC_DIR / "racenote_all_runner_synthesis.py")
    forecast = _text(root / SRC_DIR / "racenote_forecast_gen0_3.py")
    card = _text(root / SRC_DIR / "racenote_horse_evidence_card.py")

    checks.extend(
        [
            {
                "name": "racenote_general_training_edge_hidden",
                "pass": '"training_edge_visible": False' in general,
            },
            {
                "name": "racenote_general_rl_index_hidden",
                "pass": '"rl_index_visible": False' in general,
            },
            {
                "name": "racenote_synthesis_rejects_training_edge_visibility",
                "pass": (
                    'if firewall.get("training_edge_visible") is not False:' in synthesis
                    and 'if firewall.get("rl_index_visible") is not False:' in synthesis
                ),
            },
            {
                "name": "racenote_synthesis_do_not_use_training_edge",
                "pass": '"do_not_use_training_edge": True' in synthesis,
            },
            {
                "name": "racenote_forecast_training_edge_hidden",
                "pass": '"training_edge_visible": False' in forecast,
            },
            {
                "name": "racenote_card_training_edge_not_consumed",
                "pass": '"training_edge_status": "NOT_CONSUMED"' in card,
            },
        ]
    )

    edge_pwa_files: list[Path] = []
    for path in SRC_DIR.glob("*.py"):
        name = path.name
        if (
            "jrdb_edge" in name
            or name.startswith("build_jrdb_pwa")
            or name.startswith("package_jrdb_pwa")
        ):
            edge_pwa_files.append(path)

    for path in active_workflows:
        name = path.name.lower()
        if "edge" in name or "pwa" in name:
            edge_pwa_files.append(path)

    edge_pwa_hits: list[dict[str, Any]] = []
    for path in sorted(set(edge_pwa_files)):
        hits = _matches(path, EDGE_PWA_FORBIDDEN_PATTERNS)
        if hits:
            edge_pwa_hits.append(
                {
                    "path": str(path.relative_to(root)),
                    "patterns": hits,
                }
            )
    checks.append(
        {
            "name": "edgedb_pwa_no_rl_hard_dependency",
            "pass": not edge_pwa_hits,
            "hit_count": len(edge_pwa_hits),
            "hits": edge_pwa_hits,
        }
    )

    failures = [check for check in checks if not check["pass"]]
    return {
        "status": "PASS" if not failures else "FAIL",
        "audit": "rl_retirement_downstream_dependencies_v1",
        "active_workflow_count": len(active_workflows),
        "checks": checks,
        "failure_count": len(failures),
        "failures": failures,
        "summary": {
            "RACENOTE_RL_REQUIRED": False if not failures else None,
            "NEWSPAPER_RL_REQUIRED": False if not failures else None,
            "EDGEDB_RL_REQUIRED": False if not failures else None,
            "PWA_RL_REQUIRED": False if not failures else None,
            "ACTIVE_MY_INDEX_ARGUMENT_COUNT": sum(
                1
                for item in active_hits
                if "--my-index-csv" in item["patterns"]
            ),
            "RL_ABSENCE_FAILURE_PATH_COUNT": 0 if not failures else None,
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = audit(args.root)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if result["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
