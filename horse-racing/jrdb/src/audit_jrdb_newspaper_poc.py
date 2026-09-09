#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build and audit one real-data JRDB Newspaper race bundle.

This tool is a consumer-level PoC harness. It resolves the target race from
(date, venue_code, race_no), builds the Newspaper bundle through
``jrdb_newspaper_build``, validates the published JSON Schema, and writes both
``race.json`` and ``audit.json``. It deliberately does not import RaceNote.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from jrdb_newspaper_build import build_race_bundle, load_paci
from jrdb_raw import race_key_parts

VERSION = "0.1.1"


def _nested(row: dict[str, Any], *keys: str) -> Any:
    value: Any = row
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _analysis_metadata(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    with path.open("rb") as handle:
        if handle.read(16) != b"SQLite format 3\x00":
            raise ValueError(f"Analysis is not SQLite: {path}")
    connection = sqlite3.connect(path)
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        if quick_check != "ok":
            raise ValueError(f"Analysis quick_check failed: {quick_check}")
        row_count, min_date, max_date = connection.execute(
            "SELECT COUNT(*), MIN(race_date), MAX(race_date) FROM fact_entry_result_lite"
        ).fetchone()
    finally:
        connection.close()
    return {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "quick_check": quick_check,
        "fact_entry_result_lite_rows": row_count,
        "min_race_date": min_date,
        "max_race_date": max_date,
    }


def _resolve_race_key(
    parsed: dict[str, list[dict[str, Any]]],
    *,
    date: str,
    venue_code: str,
    race_no: int,
) -> str:
    candidates: list[str] = []
    for bac in parsed.get("BAC", []):
        race_key = str(bac.get("race_key_raw") or "")
        if not race_key:
            continue
        parts = race_key_parts(race_key)
        if (
            str(bac.get("date_raw") or "") == date
            and str(parts.get("venue_code") or "") == venue_code
            and parts.get("race_no") == race_no
        ):
            candidates.append(race_key)
    if len(candidates) != 1:
        raise ValueError(
            "target BAC identity is not unique: "
            f"date={date} venue={venue_code} race={race_no} candidates={candidates}"
        )
    return candidates[0]


def _schema_validate(bundle: dict[str, Any], schema_path: Path) -> None:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:  # pragma: no cover - exercised in workflow env
        raise RuntimeError("jsonschema is required for Newspaper PoC audit") from exc

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(bundle), key=lambda error: list(error.path))
    if errors:
        rendered = [f"{list(error.path)}: {error.message}" for error in errors[:20]]
        raise ValueError("schema validation failed: " + " | ".join(rendered))


def _forbidden_racenote_imports(builder_path: Path) -> list[str]:
    tree = ast.parse(builder_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return [name for name in imports if name.startswith("racenote")]


def audit_bundle(
    bundle: dict[str, Any],
    *,
    paci_path: Path,
    paci_sha256: str,
    parser_audit: dict[str, int],
    builder_path: Path,
    analysis_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    horses = bundle.get("horses") or []
    history_lengths = [len(horse.get("history") or []) for horse in horses]
    layer_counts: Counter[str] = Counter()
    detailed_field_nulls: Counter[str] = Counter()
    compact_field_nulls: Counter[str] = Counter()
    detailed_count = 0
    compact_count = 0

    detailed_fields = (
        "race_name",
        "class_label",
        "surface",
        "distance_m",
        "track_condition",
        "field_size",
        "finish",
        "final_popularity",
        "jockey_name",
        "carried_weight_kg",
        "time_sec",
        "last3f_sec",
        "idm",
        "body_weight_kg",
    )
    compact_fields = (
        "race_key",
        "date",
        "venue_code",
        "race_no",
        "class_label",
        "grade_label",
        "surface",
        "distance_m",
        "track_condition",
        "finish",
        "final_popularity",
        "final_win_odds",
        "abnormal_code",
    )

    for horse in horses:
        for run in horse.get("history") or []:
            layer = str(run.get("source_layer") or "unknown")
            layer_counts[layer] += 1
            if layer == "detailed_recent_history":
                detailed_count += 1
                for field in detailed_fields:
                    if run.get(field) is None:
                        detailed_field_nulls[field] += 1
            elif layer == "compact_older_history":
                compact_count += 1
                for field in compact_fields:
                    if run.get(field) is None:
                        compact_field_nulls[field] += 1

    current_field_null_counts = {
        "horse_name": sum(_nested(h, "basic", "horse_name") is None for h in horses),
        "sire_name": sum(_nested(h, "basic", "sire_name") is None for h in horses),
        "broodmare_sire_name": sum(
            _nested(h, "basic", "broodmare_sire_name") is None for h in horses
        ),
        "running_style_label": sum(
            _nested(h, "basic", "running_style_label") is None for h in horses
        ),
        "idm": sum(_nested(h, "jrdb", "ability", "idm") is None for h in horses),
        "total_index": sum(
            _nested(h, "jrdb", "ability", "total_index") is None for h in horses
        ),
        "training_index": sum(
            _nested(h, "jrdb", "training", "summary", "training_index") is None
            for h in horses
        ),
    }

    non_null_addons: list[dict[str, Any]] = []
    non_empty_edges: list[int | None] = []
    for horse in horses:
        horse_no = _nested(horse, "key", "horse_no")
        for source, value in (horse.get("addons") or {}).items():
            if value is not None:
                non_null_addons.append({"horse_no": horse_no, "source": source})
        if horse.get("edge_matches"):
            non_empty_edges.append(horse_no)

    forbidden_imports = _forbidden_racenote_imports(builder_path)
    if forbidden_imports:
        raise ValueError(f"forbidden RaceNote imports: {forbidden_imports}")
    if non_null_addons or non_empty_edges:
        raise ValueError(
            "base PoC unexpectedly contains addons/edges: "
            f"addons={non_null_addons} edges={non_empty_edges}"
        )

    target_date = str((bundle.get("race") or {}).get("date") or "")
    chronology_violations: list[dict[str, Any]] = []
    duplicate_history_keys: list[dict[str, Any]] = []
    for horse in horses:
        horse_no = _nested(horse, "key", "horse_no")
        seen: set[tuple[Any, Any, Any]] = set()
        for run in horse.get("history") or []:
            run_date = str(run.get("date") or "")
            if not run_date or run_date >= target_date:
                chronology_violations.append(
                    {"horse_no": horse_no, "sequence": run.get("sequence"), "date": run_date}
                )
            identity = (run.get("result_key"), run.get("race_key"), run_date)
            if identity in seen:
                duplicate_history_keys.append(
                    {"horse_no": horse_no, "sequence": run.get("sequence"), "identity": identity}
                )
            seen.add(identity)
    if chronology_violations:
        raise ValueError(f"history chronology violations: {chronology_violations[:10]}")
    if duplicate_history_keys:
        raise ValueError(f"duplicate history identities: {duplicate_history_keys[:10]}")

    race = bundle.get("race") or {}
    source_status = ((bundle.get("metadata") or {}).get("source_status") or {}).get(
        "jrdb_history", {}
    )

    return {
        "status": "PASS",
        "auditor_version": VERSION,
        "source": {
            "paci_file": paci_path.name,
            "paci_size_bytes": paci_path.stat().st_size,
            "paci_sha256": paci_sha256,
            "parser_audit": parser_audit,
            "analysis": analysis_source,
        },
        "race": race,
        "horse_count": len(horses),
        "declared_field_size": race.get("field_size"),
        "history": {
            "min_per_horse": min(history_lengths) if history_lengths else 0,
            "max_per_horse": max(history_lengths) if history_lengths else 0,
            "total_runs": sum(history_lengths),
            "horses_with_0": sum(value == 0 for value in history_lengths),
            "horses_with_1_2": sum(1 <= value <= 2 for value in history_lengths),
            "horses_with_3_plus": sum(value >= 3 for value in history_lengths),
            "horses_with_8": sum(value == 8 for value in history_lengths),
            "layer_counts": dict(layer_counts),
            "detailed_run_count": detailed_count,
            "detailed_field_null_counts": dict(detailed_field_nulls),
            "compact_run_count": compact_count,
            "compact_field_null_counts": dict(compact_field_nulls),
            "source_status": source_status,
        },
        "current_field_null_counts": current_field_null_counts,
        "architecture": {
            "forbidden_racenote_imports": forbidden_imports,
            "addons_all_null": not non_null_addons,
            "edges_all_empty": not non_empty_edges,
        },
        "chronology": {
            "target_date": target_date,
            "violations": 0,
            "duplicate_history_identities": 0,
        },
        "schema_validation": "PASS",
    }


def build_and_audit(
    *,
    paci_path: Path,
    date: str,
    venue_code: str,
    race_no: int,
    schema_path: Path,
    builder_path: Path,
    output_dir: Path,
    analysis_path: Path | None = None,
    expected_paci_sha256: str | None = None,
) -> dict[str, Any]:
    paci_sha256 = _sha256(paci_path)
    if expected_paci_sha256 and paci_sha256 != expected_paci_sha256.lower():
        raise ValueError(
            f"PACI SHA mismatch: expected={expected_paci_sha256.lower()} actual={paci_sha256}"
        )

    analysis_source = _analysis_metadata(analysis_path)
    parsed, parser_audit = load_paci(paci_path)
    race_key = _resolve_race_key(
        parsed,
        date=date,
        venue_code=venue_code,
        race_no=race_no,
    )
    bundle = build_race_bundle(
        parsed,
        race_key,
        source_sha256=paci_sha256,
        analysis_path=analysis_path,
    )
    _schema_validate(bundle, schema_path)
    audit = audit_bundle(
        bundle,
        paci_path=paci_path,
        paci_sha256=paci_sha256,
        parser_audit=parser_audit,
        builder_path=builder_path,
        analysis_source=analysis_source,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    race_path = output_dir / "race.json"
    race_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    race_bytes = race_path.read_bytes()
    audit["race_key"] = race_key
    audit["bundle"] = {
        "size_bytes": len(race_bytes),
        "sha256": hashlib.sha256(race_bytes).hexdigest(),
    }
    (output_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return audit


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Audit one real-data JRDB Newspaper race PoC")
    parser.add_argument("--paci", type=Path, required=True)
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--venue-code", required=True)
    parser.add_argument("--race-no", type=int, required=True)
    parser.add_argument("--analysis", type=Path)
    parser.add_argument("--expected-paci-sha256")
    parser.add_argument(
        "--schema",
        type=Path,
        default=root / "schema" / "jrdb_pwa_newspaper_race_schema_v0_1.json",
    )
    parser.add_argument(
        "--builder-path",
        type=Path,
        default=root / "src" / "jrdb_newspaper_build.py",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    audit = build_and_audit(
        paci_path=args.paci,
        date=args.date,
        venue_code=str(args.venue_code).zfill(2),
        race_no=args.race_no,
        schema_path=args.schema,
        builder_path=args.builder_path,
        output_dir=args.output_dir,
        analysis_path=args.analysis,
        expected_paci_sha256=args.expected_paci_sha256,
    )
    print(json.dumps(audit, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
