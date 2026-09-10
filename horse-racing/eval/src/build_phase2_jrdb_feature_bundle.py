#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build one Eval Phase2 JRDB feature bundle from a pre-race PACI archive.

The bundle composes the dedicated KYI, CHA/CYB, and exact previous-run adapters.
It owns no JRDB fixed-width offsets and introduces no additional feature meaning.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import zipfile

from build_phase2_jrdb_kyi_features import (
    OUTPUT_COLUMNS as KYI_OUTPUT_COLUMNS,
    build_features as build_kyi_features,
)
from build_phase2_jrdb_previous_features import (
    OUTPUT_COLUMNS as PREVIOUS_OUTPUT_COLUMNS,
    build_features as build_previous_features,
)
from build_phase2_jrdb_training_features import (
    OUTPUT_COLUMNS as TRAINING_OUTPUT_COLUMNS,
    build_features as build_training_features,
)


VERSION = "0.1.0"
IDENTITY_COLUMNS = ("race_key", "horse_no", "race_horse_key")
COMMON_PROVENANCE_COLUMNS = (
    "source_availability_class",
    "source_file",
    "jrdb_raw_version",
)


class Phase2FeatureBundleError(RuntimeError):
    """Raised when component feature tables cannot be merged one-to-one."""


def index_rows(
    rows: list[dict[str, object]],
    component: str,
) -> dict[str, dict[str, object]]:
    """Index one component by race_horse_key and reject duplicates."""
    output: dict[str, dict[str, object]] = {}
    for row in rows:
        key = str(row.get("race_horse_key") or "").strip()
        if not key:
            raise Phase2FeatureBundleError(
                f"{component} row has blank race_horse_key"
            )
        if key in output:
            raise Phase2FeatureBundleError(
                f"duplicate {component} race_horse_key: {key}"
            )
        output[key] = row
    return output


def require_same_identity(
    base: dict[str, object],
    other: dict[str, object],
    component: str,
) -> None:
    """Validate identity fields shared by two component rows."""
    for column in IDENTITY_COLUMNS:
        if base.get(column) != other.get(column):
            raise Phase2FeatureBundleError(
                f"{component} identity mismatch: {column} "
                f"base={base.get(column)!r} other={other.get(column)!r}"
            )


def copy_component_fields(
    output: dict[str, object],
    component_row: dict[str, object],
    field_order: tuple[str, ...],
) -> None:
    """Copy non-identity, non-generic-provenance fields into one bundle row."""
    for column in field_order:
        if column in IDENTITY_COLUMNS:
            continue
        if column in COMMON_PROVENANCE_COLUMNS:
            continue
        if column in output:
            if output[column] != component_row.get(column):
                raise Phase2FeatureBundleError(
                    f"conflicting component field: {column} "
                    f"base={output[column]!r} other={component_row.get(column)!r}"
                )
            continue
        output[column] = component_row.get(column)


def output_columns() -> tuple[str, ...]:
    """Return a stable bundle column order from component contracts."""
    columns: list[str] = []

    for column in KYI_OUTPUT_COLUMNS:
        if column in COMMON_PROVENANCE_COLUMNS:
            continue
        if column not in columns:
            columns.append(column)

    for source_columns in (TRAINING_OUTPUT_COLUMNS, PREVIOUS_OUTPUT_COLUMNS):
        for column in source_columns:
            if column in IDENTITY_COLUMNS:
                continue
            if column in COMMON_PROVENANCE_COLUMNS:
                continue
            if column not in columns:
                columns.append(column)

    columns.extend(
        [
            "kyi_source_availability_class",
            "training_source_availability_class",
            "previous_source_availability_class",
            "source_file",
            "jrdb_raw_version",
        ]
    )
    return tuple(columns)


def build_bundle(paci_path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build and one-to-one merge all Phase2 JRDB feature components."""
    kyi_rows, kyi_audit = build_kyi_features(paci_path)
    training_rows, training_audit = build_training_features(paci_path)
    previous_rows, previous_audit = build_previous_features(paci_path)

    kyi_index = index_rows(kyi_rows, "KYI")
    training_index = index_rows(training_rows, "TRAINING")
    previous_index = index_rows(previous_rows, "PREVIOUS")

    kyi_keys = set(kyi_index)
    training_keys = set(training_index)
    previous_keys = set(previous_index)

    if training_keys != kyi_keys:
        missing = sorted(kyi_keys - training_keys)
        extra = sorted(training_keys - kyi_keys)
        raise Phase2FeatureBundleError(
            f"TRAINING key set mismatch: missing={missing[:5]} extra={extra[:5]}"
        )
    if previous_keys != kyi_keys:
        missing = sorted(kyi_keys - previous_keys)
        extra = sorted(previous_keys - kyi_keys)
        raise Phase2FeatureBundleError(
            f"PREVIOUS key set mismatch: missing={missing[:5]} extra={extra[:5]}"
        )

    rows: list[dict[str, object]] = []
    for key in sorted(kyi_keys):
        kyi_row = kyi_index[key]
        training_row = training_index[key]
        previous_row = previous_index[key]

        require_same_identity(kyi_row, training_row, "TRAINING")
        require_same_identity(kyi_row, previous_row, "PREVIOUS")

        output: dict[str, object] = {}
        copy_component_fields(output, kyi_row, KYI_OUTPUT_COLUMNS)
        for column in IDENTITY_COLUMNS:
            output[column] = kyi_row.get(column)
        copy_component_fields(output, training_row, TRAINING_OUTPUT_COLUMNS)
        copy_component_fields(output, previous_row, PREVIOUS_OUTPUT_COLUMNS)

        source_files = {
            str(kyi_row.get("source_file") or ""),
            str(training_row.get("source_file") or ""),
            str(previous_row.get("source_file") or ""),
        }
        source_files.discard("")
        if len(source_files) != 1:
            raise Phase2FeatureBundleError(
                f"component source file mismatch for {key}: {sorted(source_files)}"
            )

        raw_versions = {
            str(kyi_row.get("jrdb_raw_version") or ""),
            str(training_row.get("jrdb_raw_version") or ""),
            str(previous_row.get("jrdb_raw_version") or ""),
        }
        raw_versions.discard("")
        if len(raw_versions) != 1:
            raise Phase2FeatureBundleError(
                f"component JRDB Raw version mismatch for {key}: {sorted(raw_versions)}"
            )

        output["kyi_source_availability_class"] = kyi_row.get(
            "source_availability_class"
        )
        output["training_source_availability_class"] = training_row.get(
            "source_availability_class"
        )
        output["previous_source_availability_class"] = previous_row.get(
            "source_availability_class"
        )
        output["source_file"] = next(iter(source_files))
        output["jrdb_raw_version"] = next(iter(raw_versions))
        rows.append(output)

    audit: dict[str, object] = {
        "status": "success",
        "schema_version": VERSION,
        "source_file": paci_path.name,
        "runner_rows": len(rows),
        "component_rows": {
            "kyi": len(kyi_rows),
            "training": len(training_rows),
            "previous": len(previous_rows),
        },
        "component_audits": {
            "kyi": kyi_audit,
            "training": training_audit,
            "previous": previous_audit,
        },
    }
    return rows, audit


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write the combined Phase2 feature CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = output_columns()
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_audit(path: Path, audit: dict[str, object]) -> None:
    """Write bundle audit JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""
    parser = argparse.ArgumentParser(
        description="Build combined Eval Phase2 JRDB features from one PACI archive."
    )
    parser.add_argument("--paci", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main() -> int:
    """Run the combined Phase2 JRDB feature builder."""
    parser = build_argument_parser()
    args = parser.parse_args()
    try:
        rows, audit = build_bundle(args.paci)
        write_csv(args.output, rows)
        if args.audit_json is not None:
            write_audit(args.audit_json, audit)
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0
    except (
        Phase2FeatureBundleError,
        FileNotFoundError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
