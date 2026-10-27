#!/usr/bin/env python3
"""Build a separate immutable research generation from annual UKC and daily PACI.

The 108-row audit and PACI inventory are fixed inputs. Only the 104 exact IDs
found in original PACI UKC records are added. This command never writes CURRENT.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing" / "jrdb" / "src"))
sys.path.insert(0, str(ROOT / "tools" / "data-storage"))
from jrdb_raw import canonical_members  # noqa: E402
from jrdb_ukc import RECORD_LENGTH, parse_ukc_record  # noqa: E402
import brdb_parent_relation as relation  # noqa: E402
import build_brdb_pedigree_generation as base_builder  # noqa: E402

VERSION = "research-paci-v0.1"
SELECTION = "latest_valid_profile_data_date_then_archive_date_then_zip_member_line;annual_wins"
TABLE_KEYS = {"pedigree_fact": ["horse_id"],
              "parent_relation": ["child_horse_id", "role"],
              "pedigree_name_alias": ["observed_name", "canonical_name", "birth_year", "lineage_code", "alias_version"],
              "lineage_code_master": ["lineage_code"]}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verified_file(path: Path, expected: dict) -> dict:
    if not path.is_file() or path.stat().st_size != int(expected["size_bytes"]):
        raise ValueError(f"missing/size mismatch: {path.name}")
    actual = base_builder.sha256(path)
    if actual != expected["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path.name}")
    return {"name": path.name, "size_bytes": path.stat().st_size, "sha256": actual}


def scan_daily(paci_dir: Path, inventory: list[dict], found: set[str]):
    observations = defaultdict(list)
    inventory_names = set()
    source = []
    sentinel = []
    for item in sorted(inventory, key=lambda x: x["name"]):
        name = item["name"]
        if name in inventory_names or not re.fullmatch(r"PACI\d{6}\.zip", name):
            raise ValueError(f"invalid/duplicate PACI inventory name: {name}")
        inventory_names.add(name)
        path = paci_dir / name
        archive = verified_file(path, item)
        archive_date = "20" + name[4:10]
        datetime.strptime(archive_date, "%Y%m%d")
        with zipfile.ZipFile(path) as z:
            members = canonical_members(z, "UKC")
            if members != item["ukc_members"] or z.testzip():
                raise ValueError(f"UKC inventory/member mismatch: {name}")
            count = 0
            for member in members:
                with z.open(member) as stream:
                    for line_no, line in enumerate(stream, 1):
                        count += 1
                        body = line.rstrip(b"\r\n")
                        if len(body) != RECORD_LENGTH:
                            raise ValueError(f"invalid UKC length: {name}:{member}:{line_no}")
                        record = parse_ukc_record(body)
                        if record.horse_id not in found:
                            continue
                        if record.data_date == "99999999":
                            sentinel.append({"horse_id": record.horse_id, "archive": name,
                                             "member": member, "line_number": line_no})
                            continue
                        datetime.strptime(record.data_date, "%Y%m%d")
                        if record.data_date > archive_date:
                            raise ValueError(f"future profile date: {name}:{member}:{line_no}")
                        observations[record.horse_id].append({
                            "record": asdict(record), "semantic_hash": record.semantic_hash(),
                            "archive_date": archive_date, "archive": name,
                            "archive_sha256": archive["sha256"], "member": member,
                            "line_number": line_no})
            if count != item["ukc_record_count"]:
                raise ValueError(f"UKC record count mismatch: {name}")
        source.append(archive)
    if set(observations) != found:
        raise ValueError(f"daily exact-ID coverage mismatch: missing={sorted(found - set(observations))}")
    return observations, source, sentinel


def select_daily(observations: dict, generation: str):
    added = []
    history = []
    conflicts = []
    for horse_id, rows in sorted(observations.items()):
        ordered = sorted(rows, key=lambda x: (x["record"]["data_date"], x["archive_date"],
                                              x["archive"], x["member"], x["line_number"]))
        latest = ordered[-1]
        latest_date = latest["record"]["data_date"]
        same_date = {x["semantic_hash"] for x in ordered if x["record"]["data_date"] == latest_date}
        if len(same_date) != 1:
            raise ValueError(f"same-date semantic conflict: {horse_id}")
        versions = {x["semantic_hash"] for x in ordered}
        if len(versions) > 1:
            conflicts.append({"horse_id": horse_id, "semantic_hashes": sorted(versions)})
        record = latest["record"]
        profile = {key: record.get(key) for key in base_builder.FIELDS if key in record}
        profile.update(profile_data_date=latest_date, semantic_hash=latest["semantic_hash"],
                       source_family="UKC_PACI", source_generation=generation)
        added.append(profile)
        for row in ordered:
            history.append({"horse_id": horse_id, "archive_date": row["archive_date"],
                            "profile_data_date": row["record"]["data_date"],
                            "archive": row["archive"], "archive_sha256": row["archive_sha256"],
                            "member": row["member"], "line_number": row["line_number"],
                            "semantic_hash": row["semantic_hash"],
                            "selected": row is latest})
    return added, history, conflicts


def parquet_rows(path: Path):
    import duckdb
    con = duckdb.connect(":memory:")
    try:
        cursor = con.execute("SELECT * FROM read_parquet(?)", [str(path)])
        names = [x[0] for x in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]
    finally:
        con.close()


def checked_inventory(inventory: list[dict], baseline: list[dict]) -> None:
    """Require every fixed #2212 PACI input unchanged; permit additional dates."""
    if len(baseline) != 91 or len(inventory) < len(baseline):
        raise ValueError("expected fixed 91-PACI baseline")
    by_name = {x["name"]: x for x in inventory}
    if len(by_name) != len(inventory):
        raise ValueError("duplicate PACI inventory name")
    for item in baseline:
        if by_name.get(item["name"]) != item:
            raise ValueError(f"baseline PACI changed/missing: {item['name']}")


def build(base_dir: Path, annual_dir: Path, paci_dir: Path, inventory_path: Path,
          audit_path: Path, denominator_path: Path, output_root: Path,
          baseline_inventory_path: Path | None = None) -> dict:
    from data_storage.convert import convert
    from data_storage.validate import validate

    base_manifest = read_json(base_dir / "manifest.json")
    if base_manifest.get("validation_status") != "PASS" or base_manifest.get("source_archive_count") != 27:
        raise ValueError("expected validated 27-year annual generation")
    for name, digest in base_manifest["output_sha256"].items():
        if base_builder.sha256(base_dir / name) != digest:
            raise ValueError(f"base generation object SHA mismatch: {name}")
    annual = [verified_file(annual_dir / x["name"], x) for x in base_manifest["source_archives"]]
    audit = read_json(audit_path)
    if base_builder.sha256(denominator_path) != "c3361fc60fee3e752b7e34f51b108462dfd8ba10a1b7bfafa63b5bf375acc830":
        raise ValueError("#2210 denominator SHA-256 mismatch")
    denominator = read_json(denominator_path)
    if len(audit) != 108 or len({x["horse_id"] for x in audit}) != 108:
        raise ValueError("#2212 audit must contain 108 unique IDs")
    if (denominator["missing_in_all_ukc_years_count"] != 108 or
            {x["horse_id"] for x in audit} !=
            {x["horse_id"] for x in denominator["missing_horses"]}):
        raise ValueError("#2212 audit IDs differ from fixed #2210 denominator")
    found = {x["horse_id"] for x in audit if x["status"] == "FOUND"}
    missing = {x["horse_id"] for x in audit if x["status"] == "NOT_FOUND_IN_SCANNED"}
    if len(found) != 104 or len(missing) != 4:
        raise ValueError("#2212 104/4 denominator mismatch")
    inventory = read_json(inventory_path)
    baseline_inventory_path = baseline_inventory_path or inventory_path
    baseline_inventory = read_json(baseline_inventory_path)
    checked_inventory(inventory, baseline_inventory)
    observations, daily, sentinel = scan_daily(paci_dir, inventory, found)
    for item in audit:
        if item["horse_id"] not in found:
            continue
        expected = {(x["source_zip"], x["source_zip_sha256"], x["member"],
                     x["line_number"], x["semantic_hash"])
                    for x in item["source_occurrences"]}
        actual = {(x["archive"], x["archive_sha256"], x["member"],
                   x["line_number"], x["semantic_hash"])
                  for x in observations[item["horse_id"]]}
        if not expected.issubset(actual):
            raise ValueError(f"#2212 observation provenance mismatch: {item['horse_id']}")
    identity = {"version": VERSION, "selection": SELECTION,
                "code_sha256": base_builder.sha256(Path(__file__)),
                "base_manifest_sha256": base_builder.sha256(base_dir / "manifest.json"),
                "audit_sha256": base_builder.sha256(audit_path),
                "denominator_sha256": base_builder.sha256(denominator_path),
                "inventory_sha256": base_builder.sha256(inventory_path),
                "baseline_inventory_sha256": base_builder.sha256(baseline_inventory_path),
                "annual": annual, "daily": daily}
    generation = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    destination = output_root / f"brdb-pedigree-research-{generation}"
    if destination.exists():
        raise FileExistsError(destination)
    profiles = parquet_rows(base_dir / "pedigree_fact.parquet")
    original = {x["horse_id"]: x for x in profiles}
    if len(original) != len(profiles) or found & set(original):
        raise ValueError("annual IDs duplicated or daily target already present")
    additions, history, conflicts = select_daily(observations, generation)
    profiles.extend(additions)
    profiles.sort(key=lambda x: x["horse_id"])
    aliases = parquet_rows(base_dir / "pedigree_name_alias.parquet")
    lineage = parquet_rows(base_dir / "lineage_code_master.parquet")
    master = relation.HorseMasterIndex(profiles)
    alias_index = relation.AliasIndex(relation.NameAlias(
        observed_name=a["observed_name"], canonical_name=a["canonical_name"],
        birth_year=a["birth_year"], lineage_code=a["lineage_code"],
        alias_version=a["alias_version"], evidence_type=a["evidence_type"])
        for a in aliases)
    relations = []
    counts = {role: Counter() for role in base_builder.ROLES}
    for p in profiles:
        for role, value in relation.resolve_first_generation(p, master=master, aliases=alias_index).items():
            if p["horse_id"] in found:
                counts[role][value.status] += 1
            relations.append({"child_horse_id": p["horse_id"], "role": role,
                              "parent_name": value.requested_name,
                              "parent_birth_year": value.requested_birth_year,
                              "parent_lineage_code": value.requested_lineage_code,
                              "resolved_parent_horse_id": value.resolved_horse_id,
                              "resolution_status": value.status,
                              "resolution_method": value.resolution_method,
                              "candidate_count": value.candidate_count,
                              "guard_result": value.guard, "resolver_version": "v0.1",
                              "source_generation": generation})
    old_rel = {(x["child_horse_id"], x["role"]): x for x in parquet_rows(base_dir / "parent_relation.parquet")}
    compare_cols = ("parent_name", "parent_birth_year", "parent_lineage_code",
                    "resolved_parent_horse_id", "resolution_status", "resolution_method",
                    "candidate_count", "guard_result")
    relation_diff = [{"horse_id": x["child_horse_id"], "role": x["role"],
                      "before": {k: old_rel[x["child_horse_id"], x["role"]][k] for k in compare_cols},
                      "after": {k: x[k] for k in compare_cols}} for x in relations
                     if x["child_horse_id"] in original and any(
                         old_rel[x["child_horse_id"], x["role"]][k] != x[k] for k in compare_cols)]
    destination.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="brdb-candidate-") as tmp:
        stage = Path(tmp)
        con = sqlite3.connect(stage / "stage.sqlite")
        con.executescript(base_builder.SCHEMA.read_text(encoding="utf-8"))
        for table, rows in (("pedigree_fact", profiles), ("parent_relation", relations),
                            ("pedigree_name_alias", aliases), ("lineage_code_master", lineage)):
            base_builder.table_rows(con, table, rows)
        con.commit()
        output_hashes = {}
        row_counts = {}
        for table, keys in TABLE_KEYS.items():
            target = destination / f"{table}.parquet"
            config = {"source": {"format": "sqlite", "path": str(stage / "stage.sqlite"), "table": table},
                      "target": {"path": str(target), "compression": "zstd"},
                      "keys": {"canonical": keys}, "sort_by": keys,
                      "validation": {"require_row_count_match": True, "require_unique_key": True}}
            conversion = convert(config)
            if not validate(config, conversion)["passed"]:
                raise ValueError(f"Parquet validation failed: {table}")
            row_counts[table] = conversion["row_count_source"]
            output_hashes[target.name] = base_builder.sha256(target)
        con.close()
    first_seen = {k: min(x["archive_date"] for x in rows) for k, rows in observations.items()}
    row_audit = [{"horse_id": p["horse_id"], "horse_name": p["horse_name"],
                  "first_observed_archive_date": first_seen[p["horse_id"]],
                  "profile_data_date": p["profile_data_date"],
                  "sire_name": p["sire_name"], "dam_name": p["dam_name"],
                  "broodmare_sire_name": p["broodmare_sire_name"],
                  "sire_line_code": p["sire_line_code"],
                  "broodmare_sire_line_code": p["broodmare_sire_line_code"],
                  "relations": {x["role"]: {"status": x["resolution_status"],
                                             "horse_id": x["resolved_parent_horse_id"]}
                                for x in relations if x["child_horse_id"] == p["horse_id"]}}
                 for p in additions]
    base_builder.dump(destination / "added_104.json", row_audit)
    columns = ("horse_id", "horse_name", "first_observed_archive_date",
               "profile_data_date", "sire_name", "dam_name",
               "broodmare_sire_name", "sire_line_code", "broodmare_sire_line_code",
               "sire_status", "sire_horse_id", "dam_status", "dam_horse_id",
               "broodmare_sire_status", "broodmare_sire_horse_id")
    with (destination / "added_104.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in row_audit:
            flat = {key: row[key] for key in columns[:9]}
            for role in base_builder.ROLES:
                flat[f"{role}_status"] = row["relations"][role]["status"]
                flat[f"{role}_horse_id"] = row["relations"][role]["horse_id"]
            writer.writerow(flat)
    base_builder.dump(destination / "observation_history.json", history)
    base_builder.dump(destination / "relation_diff.json", relation_diff)
    audit_out = {"added_count": len(additions), "missing_count": len(missing),
                 "missing_ids": sorted(missing), "annual_profile_regression": "PASS",
                 "annual_relation_diff_count": len(relation_diff),
                 "daily_semantic_conflict_horses": conflicts,
                 "sentinel_observations": sentinel,
                 "daily_relation_status": {k: dict(v) for k, v in counts.items()},
                 "first_observed_min": min(first_seen.values()),
                 "first_observed_max": max(first_seen.values()),
                 "as_of_2025_exposed_count": sum(x <= "20251231" for x in first_seen.values())}
    base_builder.dump(destination / "audit.json", audit_out)
    for name in ("audit.json", "added_104.json", "added_104.csv",
                 "observation_history.json", "relation_diff.json"):
        output_hashes[name] = base_builder.sha256(destination / name)
    manifest = {"artifact_type": "brdb_pedigree", "generation_id": generation,
                "schema_version": "v0.1", "builder_version": VERSION,
                "source_family": "UKC+PACI_UKC", "source_archive_count": len(annual) + len(daily),
                "source_min_data_date": base_manifest["source_min_data_date"],
                "source_max_data_date": max(x["profile_data_date"] for x in additions),
                "source_archives": annual + daily, "row_counts": row_counts,
                "canonical_keys": {"pedigree_fact": ["horse_id"],
                                   "parent_relation": ["child_horse_id", "role"]},
                "alias_version": base_manifest["alias_version"],
                "lineage_source_version": base_manifest["lineage_source_version"],
                "validation_status": "PASS", "output_sha256": output_hashes,
                "research_only": True, "base_generation_id": base_manifest["generation_id"],
                "identity": identity, "selection_rule": SELECTION,
                "available_from": "20260101"}
    base_builder.dump(destination / "manifest.json", manifest)
    return {"output": str(destination), "generation_id": generation, "audit": audit_out}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base_generation", "annual_dir", "paci_dir", "inventory", "audit", "denominator", "output_root"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    parser.add_argument("--baseline-inventory", type=Path,
                        help="original 91-entry #2212 inventory; required when extending --inventory")
    args = parser.parse_args()
    print(json.dumps(build(args.base_generation, args.annual_dir, args.paci_dir,
                           args.inventory, args.audit, args.denominator, args.output_root,
                           args.baseline_inventory), ensure_ascii=False))


if __name__ == "__main__":
    main()
