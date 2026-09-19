#!/usr/bin/env python3
"""Build one JRDB Warehouse generation from a frozen-Raw inventory.

This wrapper owns only the repeatable inventory-to-archive-spec mapping and
preflight validation.  Fixed-width parsing and Raw-to-Warehouse normalization
remain exclusively in :mod:`jrdb_raw` and
:mod:`build_jrdb_normalized_warehouse`.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from build_jrdb_normalized_warehouse import ArchiveSpec, build_generation
from jrdb_warehouse_normalize import IMPLEMENTED_FAMILIES


def load_archive_specs(inventory_path: Path, raw_root: Path) -> list[ArchiveSpec]:
    """Return every target annual archive after fail-closed local checks."""
    inventory: dict[str, Any] = json.loads(inventory_path.read_text(encoding="utf-8"))
    expected_families = set(IMPLEMENTED_FAMILIES) | {"HJC"}
    by_family = {str(item.get("family", "")).upper(): item for item in inventory.get("families", [])}
    if set(by_family) != expected_families:
        raise ValueError(f"inventory target families differ: {sorted(by_family)}")

    specs: list[ArchiveSpec] = []
    for family in sorted(expected_families):
        source = by_family[family]
        if source.get("status") != "TARGET":
            raise ValueError(f"inventory family is not TARGET: {family}")
        annual = [item for item in source.get("archives", []) if item.get("archive_class") == "annual"]
        if not annual:
            raise ValueError(f"inventory has no annual archives: {family}")
        seen_years: set[int] = set()
        for item in annual:
            year = item.get("year")
            size_bytes = item.get("size_bytes")
            if not isinstance(year, int) or not isinstance(size_bytes, int) or size_bytes < 1:
                raise ValueError(f"invalid annual inventory entry: {family}: {item!r}")
            if year in seen_years:
                raise ValueError(f"duplicate annual inventory entry: {family}:{year}")
            seen_years.add(year)
            archive = raw_root / str(year) / f"{family}.zip"
            if not archive.is_file() or archive.stat().st_size != size_bytes:
                raise ValueError(f"missing or size-mismatched frozen Raw: {archive}")
            try:
                with zipfile.ZipFile(archive) as handle:
                    corrupt_member = handle.testzip()
            except zipfile.BadZipFile as exc:
                raise ValueError(f"invalid frozen Raw ZIP: {archive}") from exc
            if corrupt_member is not None:
                raise ValueError(f"corrupt member in frozen Raw ZIP: {archive}: {corrupt_member}")
            specs.append(ArchiveSpec(family=family, year=year, path=archive))
    return sorted(specs, key=lambda item: (item.year, item.normalized_family(), str(item.path)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a JRDB Warehouse generation from a frozen inventory")
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--source-git-commit", required=True)
    args = parser.parse_args()
    specs = load_archive_specs(args.inventory, args.raw_root)
    result = build_generation(specs, args.output_root, args.generation_id, args.source_git_commit)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
