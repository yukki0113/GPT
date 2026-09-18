#!/usr/bin/env python3
"""Create a read-only inventory of frozen JRDB Raw archives from Drive listings.

The Drive connector remains responsible for obtaining folder listings.  This
module normalizes those listings into the stable, machine-readable input
contract used by the normalized Warehouse build; it never downloads, changes,
or infers missing Raw archives.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from jrdb_raw import RECORD_LENGTHS

INVENTORY_VERSION = "1"
TARGET_FAMILIES = ("BAC", "KYI", "CHA", "CYB", "SED", "SKB", "ZED", "ZKB", "UKC", "HJC")
OUT_OF_SCOPE_FAMILIES = {"PACI": "PACI is a future daily-normalized input route"}
ANNUAL_ARCHIVE = re.compile(r"^(?P<family>[A-Za-z0-9]+)_(?P<year>(?:19|20)\d{2})\.zip$", re.IGNORECASE)
DAILY_ARCHIVE = re.compile(r"^(?P<family>[A-Za-z0-9]+)[_-]?(?P<date>(?:19|20)\d{6})\.zip$", re.IGNORECASE)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _size(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid Drive size: {value!r}") from exc


def _archive_shape(name: str, family: str) -> dict[str, Any]:
    annual = ANNUAL_ARCHIVE.fullmatch(name)
    if annual and annual.group("family").upper() == family:
        return {"archive_class": "annual", "year": int(annual.group("year")), "date": None}
    daily = DAILY_ARCHIVE.fullmatch(name)
    if daily and daily.group("family").upper() == family:
        return {"archive_class": "daily", "year": int(daily.group("date")[:4]), "date": daily.group("date")}
    return {"archive_class": "unclassified", "year": None, "date": None}


def _family_status(family: str) -> tuple[str, str | None]:
    if family in TARGET_FAMILIES:
        return "TARGET", None
    if family in OUT_OF_SCOPE_FAMILIES:
        return "OUT_OF_SCOPE", OUT_OF_SCOPE_FAMILIES[family]
    if family not in RECORD_LENGTHS:
        return "UNSUPPORTED", "no current jrdb_raw.Parser support"
    return "NOT_REQUESTED", "parser support exists but family is outside this Warehouse request"


def build_inventory(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Drive folder-listing snapshot without touching archive bytes.

    Input contract::

      {"raw_root": {"id": "...", "title": "00_raw"},
       "families": [{"id": "...", "title": "BAC", "files": [...]}, ...]}

    ``files`` are the file objects returned by the Drive folder-list operation.
    Their archive checksums are intentionally marked unavailable: Drive listing
    metadata alone cannot prove an archive checksum.
    """
    raw_root = snapshot.get("raw_root")
    families = snapshot.get("families")
    if not isinstance(raw_root, dict) or not _text(raw_root.get("id")):
        raise ValueError("snapshot.raw_root.id is required")
    if not isinstance(families, list):
        raise ValueError("snapshot.families must be a list")

    normalized_families: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in families:
        if not isinstance(source, dict):
            raise ValueError("each snapshot family must be an object")
        family = _text(source.get("title")).upper()
        if not family:
            raise ValueError("snapshot family title is required")
        if family in seen:
            raise ValueError(f"duplicate Drive family folder: {family}")
        seen.add(family)
        status, reason = _family_status(family)
        files = source.get("files", [])
        if not isinstance(files, list):
            raise ValueError(f"snapshot files must be a list: {family}")
        archives: list[dict[str, Any]] = []
        for item in files:
            if not isinstance(item, dict):
                raise ValueError(f"snapshot file must be an object: {family}")
            name = _text(item.get("title") or item.get("name"))
            file_id = _text(item.get("id"))
            if not name or not file_id:
                raise ValueError(f"Drive archive requires id and title: {family}")
            if item.get("file_or_folder") == "folder":
                continue
            shape = _archive_shape(name, family)
            archives.append(
                {
                    "archive_name": name,
                    "drive_id": file_id,
                    "size_bytes": _size(item.get("size")),
                    "modified_time": item.get("modified_time") or item.get("modifiedTime"),
                    "mime_type": item.get("mime_type") or item.get("mimeType"),
                    "archive_sha256": None,
                    "archive_checksum_status": "UNAVAILABLE_FROM_DRIVE_LISTING",
                    **shape,
                }
            )
        archives.sort(key=lambda item: (item["archive_class"], item["year"] or -1, item["date"] or "", item["archive_name"]))
        normalized_families.append(
            {
                "family": family,
                "status": status,
                "status_reason": reason,
                "folder_id": _text(source.get("id")),
                "archive_count": len(archives),
                "annual_archive_count": sum(item["archive_class"] == "annual" for item in archives),
                "daily_archive_count": sum(item["archive_class"] == "daily" for item in archives),
                "unclassified_archive_count": sum(item["archive_class"] == "unclassified" for item in archives),
                "archives": archives,
            }
        )
    normalized_families.sort(key=lambda item: item["family"])
    present = {item["family"] for item in normalized_families}
    return {
        "artifact_type": "jrdb_frozen_raw_inventory",
        "inventory_version": INVENTORY_VERSION,
        "raw_root": {"id": _text(raw_root["id"]), "title": _text(raw_root.get("title"))},
        "target_families": list(TARGET_FAMILIES),
        "missing_target_families": [family for family in TARGET_FAMILIES if family not in present],
        "families": normalized_families,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True, help="Drive folder-listing snapshot JSON")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing inventory: {args.output}")
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    inventory = build_inventory(snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "families": len(inventory["families"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
