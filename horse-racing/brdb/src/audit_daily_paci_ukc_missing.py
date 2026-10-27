#!/usr/bin/env python3
"""Read-only audit of fixed missing KYI IDs against inventoried PACI UKC ZIPs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

JRDB_SRC = Path(__file__).resolve().parents[2] / "jrdb" / "src"
sys.path.insert(0, str(JRDB_SRC))
from jrdb_raw import canonical_members  # noqa: E402
from jrdb_ukc import parse_ukc_record, RECORD_LENGTH, SEMANTIC_FIELDS  # noqa: E402

from brdb_parent_relation import (  # noqa: E402
    AliasIndex, HorseMasterIndex, NameAlias, resolve_first_generation,
)
from brdb_ancestor_graph import ancestor_graph  # noqa: E402
from brdb_pedigree_reader import BloodReviewReader  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fixed_ids(document: dict) -> list[dict]:
    rows = document["missing_horses"]
    ids = [row["horse_id"] for row in rows]
    if (document.get("missing_in_all_ukc_years_count") != 108 or len(ids) != 108
            or len(set(ids)) != 108 or not all(re.fullmatch(r"\d{8}", x) for x in ids)):
        raise ValueError("#2210 denominator is not 108 unique eight-digit IDs")
    return rows


def scan_one(file: dict, wanted: set[str]) -> tuple[dict, list[dict]]:
    path = Path(file["path"])
    item = {"name": file["name"], "drive_id": file["id"],
            "size_bytes": None, "sha256": None, "ukc_members": [],
            "ukc_record_count": 0, "parse_errors": 0, "status": "UNVERIFIED_INPUT_GAP"}
    matches = []
    try:
        if not (re.fullmatch(r"PACI(?:25|26)\d{4}\.zip", file["name"])
                or file["name"] == "UKC_2025.zip"):
            raise ValueError("name_outside_2025_2026_scope")
        item["size_bytes"] = path.stat().st_size
        if item["size_bytes"] != file["expected_bytes"]:
            raise ValueError("drive_size_mismatch")
        item["sha256"] = sha256(path)
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"corrupt_member:{bad}")
            members = canonical_members(archive, "UKC")
            item["ukc_members"] = members
            if not members:
                item["status"] = "NO_UKC_MEMBER"
                return item, matches
            for member in members:
                with archive.open(member) as stream:
                    for line_number, line in enumerate(stream, 1):
                        item["ukc_record_count"] += 1
                        body = line.rstrip(b"\r\n")
                        if len(body) != RECORD_LENGTH:
                            item["parse_errors"] += 1
                            continue
                        try:
                            record = parse_ukc_record(body)
                        except (UnicodeError, ValueError):
                            item["parse_errors"] += 1
                            continue
                        if record.horse_id in wanted:
                            matches.append({"record": asdict(record), "semantic_hash": record.semantic_hash(),
                                            "source_zip": file["name"], "source_drive_id": file["id"],
                                            "source_zip_sha256": item["sha256"], "member": member,
                                            "line_number": line_number})
        item["status"] = "PARSE_ERROR" if item["parse_errors"] else "SCANNED"
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        item["status"] = "READ_ERROR"
        item["error"] = str(exc)
    return item, matches


def graph_data(reader: BloodReviewReader):
    import duckdb
    connection = duckdb.connect(":memory:")
    try:
        profile_path = str(reader._paths["pedigree_fact.parquet"])
        relation_path = str(reader._paths["parent_relation.parquet"])
        alias_path = str(reader._paths["pedigree_name_alias.parquet"])
        cursor = connection.execute("SELECT * FROM read_parquet(?)", [profile_path])
        names = [col[0] for col in cursor.description]
        profiles = [dict(zip(names, row)) for row in cursor.fetchall()]
        relations = connection.execute("""
            SELECT child_horse_id, role, resolution_status, resolved_parent_horse_id
            FROM read_parquet(?)
            WHERE role IN ('sire', 'dam')
        """, [relation_path]).fetchall()
        cursor = connection.execute("SELECT * FROM read_parquet(?)", [alias_path])
        alias_names = [col[0] for col in cursor.description]
        alias_rows = [dict(zip(alias_names, row)) for row in cursor.fetchall()]
    finally:
        connection.close()
    graph = defaultdict(list)
    for child, role, status, parent in relations:
        graph[child].append({"role": role, "resolution_status": status,
                             "resolved_parent_horse_id": parent})
    aliases = AliasIndex(NameAlias(**{key: row[key] for key in
        ("observed_name", "canonical_name", "birth_year", "lineage_code", "alias_version")})
        for row in alias_rows)
    return HorseMasterIndex(profiles), aliases, graph


def reach(graph: dict, root: str, max_generation: int = 5) -> dict:
    if not root:
        return {"max_reached_generation": 0, "unique_ancestor_ids": 0}
    result = ancestor_graph(root, lambda horse_id: graph.get(horse_id, []),
                            max_depth=max_generation - 1)
    resolved = [node for node in result["paths"] if node["horse_id"]]
    return {
        "max_reached_generation": max((node["depth"] + 1 for node in resolved), default=1),
        "unique_ancestor_ids": len({root, *(node["horse_id"] for node in resolved)}),
        "graph_version": result["graph_version"],
    }


def parent_audit(record: dict, master: HorseMasterIndex, aliases: AliasIndex,
                 graph: dict) -> dict:
    resolutions = resolve_first_generation(record, master=master, aliases=aliases)
    output = {}
    for role, resolution in resolutions.items():
        if resolution.resolved:
            status = "RESOLVED"
        elif resolution.status in {"MULTIPLE_CANDIDATES", "INSUFFICIENT_GUARD"} and resolution.candidate_count:
            status = "CANDIDATE"
        else:
            status = "UNKNOWN"
        output[role] = {
            "status": status, "resolver_status": resolution.status,
            "resolved_horse_id": resolution.resolved_horse_id,
            "candidate_count": resolution.candidate_count,
            "guard": resolution.guard,
            **reach(graph, resolution.resolved_horse_id),
        }
    return output


def audit(missing_path: Path, inventory_path: Path, brdb_root: Path, *,
          annual_ukc_2025: Path | None = None,
          annual_ukc_2025_drive_id: str | None = None,
          annual_ukc_2025_expected_bytes: int | None = None) -> tuple[dict, list[dict], list[dict]]:
    missing_bytes = missing_path.read_bytes()
    missing = fixed_ids(json.loads(missing_bytes))
    wanted = {row["horse_id"] for row in missing}
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    files = inventory["files"]
    if len({file["id"] for file in files}) != len(files) or len({file["name"] for file in files}) != len(files):
        raise ValueError("duplicate PACI file in inventory")
    reader = BloodReviewReader(brdb_root)
    master, aliases, graph = graph_data(reader)
    inspections = []
    observations = defaultdict(list)
    for file in files:
        item, matches = scan_one(file, wanted)
        inspections.append(item)
        for match in matches:
            observations[match["record"]["horse_id"]].append(match)
    annual_item = None
    annual_ids: set[str] = set()
    if annual_ukc_2025 is not None:
        if not annual_ukc_2025_expected_bytes or not annual_ukc_2025_drive_id:
            raise ValueError("annual UKC requires Drive ID and expected size")
        annual_item, annual_matches = scan_one({
            "name": "UKC_2025.zip", "id": annual_ukc_2025_drive_id or "",
            "path": str(annual_ukc_2025),
            "expected_bytes": annual_ukc_2025_expected_bytes,
        }, wanted)
        annual_ids = {match["record"]["horse_id"] for match in annual_matches}
        for match in annual_matches:
            observations[match["record"]["horse_id"]].append(match)
    any_gap = (not any(f["name"].startswith("PACI25") for f in files)
               or any(f["status"] != "SCANNED" for f in inspections))
    rows = []
    for source in missing:
        horse_id = source["horse_id"]
        hits = sorted(observations[horse_id], key=lambda x: (x["record"]["data_date"], x["source_zip"]))
        latest = hits[-1]["record"] if hits else None
        if hits:
            status = "FOUND"
        else:
            status = "UNVERIFIED_INPUT_GAP" if any_gap else "NOT_FOUND_IN_SCANNED"
        version_fields = ("horse_name", "sire_name", "dam_name", "broodmare_sire_name",
                          "birth_date", "sire_birth_year", "dam_birth_year",
                          "broodmare_sire_birth_year", "sire_line_code",
                          "broodmare_sire_line_code")
        profile_versions = {}
        for hit in hits:
            profile_versions.setdefault(hit["semantic_hash"], {
                "semantic_hash": hit["semantic_hash"],
                "first_observed_data_date": hit["record"]["data_date"],
                "fields": {name: hit["record"][name] for name in version_fields},
            })
        changed_fields = sorted(name for name in SEMANTIC_FIELDS
            if len({str(hit["record"][name]) for hit in hits}) > 1)
        pedigree_changed_fields = sorted(set(changed_fields) & set(version_fields))
        row = {
            "horse_id": horse_id, "kyi_horse_name_sample": source.get("horse_name_sample"),
            "status": status, "status_reason": ("exact_horse_id_in_UKC" if hits else
                "2025_PACI_absent_or_ZIP_gap" if any_gap else "absent_in_all_scanned_UKC"),
            "annual_ukc_2025_status": (
                "NOT_SCANNED" if annual_item is None else
                "FOUND" if horse_id in annual_ids else
                "NOT_FOUND_IN_SCANNED" if annual_item["status"] == "SCANNED" else
                "UNVERIFIED_INPUT_GAP"),
            "observation_count": len(hits),
            "distinct_profile_versions": len({hit["semantic_hash"] for hit in hits}),
            "conflict_history": len({hit["semantic_hash"] for hit in hits}) > 1,
            "changed_fields": changed_fields,
            "pedigree_changed_fields": pedigree_changed_fields,
            "profile_versions": list(profile_versions.values()),
            "first_observed_data_date": hits[0]["record"]["data_date"] if hits else None,
            "last_observed_data_date": hits[-1]["record"]["data_date"] if hits else None,
            "horse_name": latest["horse_name"] if latest else None,
            "sire_name": latest["sire_name"] if latest else None,
            "dam_name": latest["dam_name"] if latest else None,
            "broodmare_sire_name": latest["broodmare_sire_name"] if latest else None,
            "birth_date": latest["birth_date"] if latest else None,
            "sire_line_code": latest["sire_line_code"] if latest else None,
            "broodmare_sire_line_code": latest["broodmare_sire_line_code"] if latest else None,
            "source_occurrences": [{key: hit[key] for key in
                ("source_zip", "source_drive_id", "source_zip_sha256", "member", "line_number", "semantic_hash")}
                for hit in hits],
            "parent_connection": parent_audit(latest, master, aliases, graph) if latest else None,
        }
        rows.append(row)
    statuses = Counter(row["status"] for row in rows)
    role_stats = {role: dict(Counter(row["parent_connection"][role]["status"]
        for row in rows if row["parent_connection"])) for role in ("sire", "dam", "broodmare_sire")}
    columns = ("horse_name", "sire_name", "dam_name", "broodmare_sire_name", "birth_date",
               "sire_line_code", "broodmare_sire_line_code")
    summary = {
        "denominator": 108, "denominator_sha256": hashlib.sha256(missing_bytes).hexdigest(),
        "folder_id": inventory["folder_id"], "folder_returned_count": inventory["returned_count"],
        "inventoried_zip_count": len(files),
        "zip_year_counts": dict(Counter(file["name"][4:6] for file in files)),
        "zip_status_counts": dict(Counter(item["status"] for item in inspections)),
        "ukc_members": sum(len(item["ukc_members"]) for item in inspections),
        "ukc_records": sum(item["ukc_record_count"] for item in inspections),
        "ukc_parse_errors": sum(item["parse_errors"] for item in inspections),
        "status_counts": dict(statuses), "nonempty_fields_among_found": {
            name: sum(bool(row[name]) for row in rows if row["status"] == "FOUND") for name in columns},
        "parent_connection_counts_among_found": role_stats,
        "semantic_profile_change_horses": sum(row["conflict_history"] for row in rows),
        "pedigree_field_change_horses": sum(bool(row["pedigree_changed_fields"]) for row in rows),
        "brdb_generation_id": reader.generation_id,
        "coverage_complete_for_inventoried_files": all(item["status"] == "SCANNED" for item in inspections),
        "paci_2025_input_available": any(file["name"].startswith("PACI25") for file in files),
        "annual_ukc_2025": annual_item,
        "annual_ukc_2025_matching_ids": len(annual_ids),
    }
    return summary, rows, inspections


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--missing", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--brdb-root", type=Path, required=True)
    parser.add_argument("--annual-ukc-2025", type=Path)
    parser.add_argument("--annual-ukc-2025-drive-id")
    parser.add_argument("--annual-ukc-2025-expected-bytes", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary, rows, inspections = audit(args.missing, args.inventory, args.brdb_root,
                                       annual_ukc_2025=args.annual_ukc_2025,
                                       annual_ukc_2025_drive_id=args.annual_ukc_2025_drive_id,
                                       annual_ukc_2025_expected_bytes=args.annual_ukc_2025_expected_bytes)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in (("summary.json", summary), ("missing_108_audit.json", rows),
                        ("paci_inventory_audit.json", inspections)):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    flat = []
    for row in rows:
        item = {key: value for key, value in row.items()
                if key not in {"source_occurrences", "parent_connection", "profile_versions"}}
        item["changed_fields"] = ",".join(item["changed_fields"])
        item["pedigree_changed_fields"] = ",".join(item["pedigree_changed_fields"])
        for role in ("sire", "dam", "broodmare_sire"):
            connection = (row["parent_connection"] or {}).get(role, {})
            for field in ("status", "resolver_status", "resolved_horse_id", "candidate_count",
                          "guard", "max_reached_generation", "unique_ancestor_ids"):
                item[f"{role}_{field}"] = connection.get(field)
        flat.append(item)
    with (args.output / "missing_108_audit.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        pq.write_table(pa.Table.from_pylist(flat), args.output / "missing_108_audit.parquet")
    except ImportError:
        pass
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
