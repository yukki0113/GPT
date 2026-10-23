#!/usr/bin/env python3
"""Build an immutable BRDB pedigree generation from JRDB UKC archives."""
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
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing" / "jrdb" / "src"))
sys.path.insert(0, str(ROOT / "tools" / "data-storage"))
import jrdb_ukc  # noqa: E402
import brdb_parent_relation as relation  # noqa: E402

SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "brdb_pedigree_fact_schema_v0_1.sql"
LINEAGE = Path(__file__).resolve().parents[1] / "config" / "lineage_code_master_v0_1.csv"
FIELDS = ("horse_id", "horse_name", "birth_date", "sex_code", "sire_name",
          "sire_birth_year", "dam_name", "dam_birth_year", "broodmare_sire_name",
          "broodmare_sire_birth_year", "sire_line_code", "broodmare_sire_line_code",
          "breeding_place", "profile_data_date", "semantic_hash", "source_family",
          "source_generation")
ROLES = ("sire", "dam", "broodmare_sire")
STATUSES = ("RESOLVED_EXACT", "RESOLVED_ALIAS", "NO_CANDIDATE",
            "MULTIPLE_CANDIDATES", "INSUFFICIENT_KEY", "INSUFFICIENT_GUARD", "CONFLICT")
BUILDER_VERSION = "0.2.0"\nSENTINEL_DATES = {"99999999"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def archives_from(paths: list[str]) -> list[Path]:
    archives = set()
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            archives.update(p.rglob("UKC_*.zip"))
        elif p.is_file():
            archives.add(p)
        else:
            raise FileNotFoundError(p)
    if not archives:
        raise ValueError("no UKC ZIP archives found")
    return sorted(archives, key=lambda p: (p.name, str(p)))


def load_lineage(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    seen = set()
    for row in rows:
        code = row["lineage_code"].strip()
        if not re.fullmatch(r"\d{4}", code) or code in seen:
            raise ValueError(f"invalid or duplicate lineage_code: {code}")
        seen.add(code)
        if row["major_code"] != code[:2] or not row["major_name"].strip() or not row["minor_name"].strip():
            raise ValueError(f"invalid lineage master entry: {code}")
    return rows


def ingest(con: sqlite3.Connection, paths: list[Path]) -> dict:
    con.execute("CREATE TABLE observation(horse_id TEXT, data_date TEXT, semantic_hash TEXT, archive TEXT, member TEXT, profile_json TEXT)")
    stats = {"archive_count": len(paths), "text_member_count": 0, "raw_observation_count": 0,
             "invalid_record_count": 0, "source_archives": [], "quarantined_date_records": []}
    buffer = []
    target_2025 = set()
    for archive in paths:
        stats["source_archives"].append({"name": archive.name, "sha256": sha256(archive), "size_bytes": archive.stat().st_size})
        with zipfile.ZipFile(archive) as z:
            for member in sorted(z.namelist()):
                if not re.search(r"(^|/)UKC[^/]*\.txt$", member, re.I):
                    continue
                stats["text_member_count"] += 1
                with z.open(member) as stream:
                    for line_no, line in enumerate(stream, 1):
                        body = line.rstrip(b"\r\n")
                        stats["raw_observation_count"] += 1
                        if len(body) != jrdb_ukc.RECORD_LENGTH:
                            stats["invalid_record_count"] += 1
                            raise ValueError(f"invalid UKC record length {archive.name}:{member}:{line_no}: {len(body)}")
                        record = jrdb_ukc.parse_ukc_record(body)
                        if not record.horse_id or not re.fullmatch(r"\d{8}", record.data_date):
                            raise ValueError(f"invalid UKC identity/date {archive.name}:{member}:{line_no}")
                        if record.data_date in SENTINEL_DATES:\n                            stats["quarantined_date_records"].append({"horse_id": record.horse_id, "data_date": record.data_date, "archive": archive.name, "member": member, "line_no": line_no})\n                            continue\n                        try:\n                            datetime.strptime(record.data_date, "%Y%m%d")\n                        except ValueError as exc:\n                            raise ValueError(f"invalid UKC calendar date {archive.name}:{member}:{line_no}: {record.data_date}") from exc\n                        if archive.name == "UKC_2025.zip":
                            target_2025.add(record.horse_id)
                        buffer.append((record.horse_id, record.data_date, record.semantic_hash(), archive.name,
                                       member, json.dumps(asdict(record), ensure_ascii=False, sort_keys=True)))
                        if len(buffer) >= 10000:
                            con.executemany("INSERT INTO observation VALUES (?,?,?,?,?,?)", buffer)
                            buffer.clear()
    if buffer:
        con.executemany("INSERT INTO observation VALUES (?,?,?,?,?,?)", buffer)
    con.execute("CREATE INDEX ix_observation_horse_date ON observation(horse_id,data_date)")
    stats["min_data_date"], stats["max_data_date"] = con.execute("SELECT min(data_date),max(data_date) FROM observation").fetchone()
    stats["target_2025_count"] = len(target_2025)
    return stats, target_2025


def reduce_profiles(con: sqlite3.Connection, generation: str) -> list[dict]:
    conflicts = con.execute("""
      SELECT horse_id FROM observation o
      WHERE data_date=(SELECT max(data_date) FROM observation WHERE horse_id=o.horse_id)
      GROUP BY horse_id HAVING count(DISTINCT semantic_hash)>1 ORDER BY horse_id LIMIT 50
    """).fetchall()
    if conflicts:
        raise ValueError("same-date semantic conflicts: " + ",".join(row[0] for row in conflicts))
    rows = con.execute("""
      SELECT o.profile_json,o.semantic_hash FROM observation o
      WHERE o.rowid=(SELECT min(x.rowid) FROM observation x
                     WHERE x.horse_id=o.horse_id AND
                     x.data_date=(SELECT max(y.data_date) FROM observation y WHERE y.horse_id=o.horse_id))
      ORDER BY o.horse_id
    """)
    profiles = []
    for raw, semantic_hash in rows:
        record = json.loads(raw)
        profile = {key: record.get(key) for key in FIELDS if key in record}
        profile.update(profile_data_date=record["data_date"], semantic_hash=semantic_hash,
                       source_family="UKC", source_generation=generation)
        profiles.append(profile)
    return profiles


def alias_candidates(profiles: list[dict], con: sqlite3.Connection, target_ids: set[str], generation: str) -> tuple[list[dict], dict]:
    """Review deterministic dam/BMS spelling evidence; never use fuzzy matching."""
    by_key = defaultdict(list)
    for p in profiles:
        if p["birth_date"] and p["birth_date"][:4].isdigit() and p["sex_code"] == "2":
            by_key[p["horse_name"], int(p["birth_date"][:4])].append(p)
    pairs = defaultdict(list)
    apparent = 0
    collisions = []
    for child in profiles:
        if child["horse_id"] not in target_ids:
            continue
        candidates = by_key.get((child["dam_name"], child["dam_birth_year"]), [])
        if len(candidates) != 1:
            continue
        dam = candidates[0]
        if (dam["sire_name"], dam["sire_birth_year"]) == (child["broodmare_sire_name"], child["broodmare_sire_birth_year"]):
            continue
        apparent += 1
        if (dam["sire_birth_year"] == child["broodmare_sire_birth_year"]
                and dam["sire_line_code"] == child["broodmare_sire_line_code"]
                and dam["sire_line_code"] and dam["sire_name"] and child["broodmare_sire_name"]):
            key = (child["broodmare_sire_name"], dam["sire_name"], dam["sire_birth_year"], dam["sire_line_code"])
            pairs[key].append((child["horse_id"], dam["horse_id"], child["profile_data_date"]))
        else:
            collisions.append({"child_horse_id": child["horse_id"], "candidate_dam_horse_id": dam["horse_id"]})
    aliases = []
    evidence = Counter()
    for (observed, canonical, year, code), samples in sorted(pairs.items()):
        historical_rows = 0
        for _, dam_id, _ in samples:
            found = False
            for (raw,) in con.execute("SELECT profile_json FROM observation WHERE horse_id=?", (dam_id,)):
                previous = json.loads(raw)
                if previous["sire_name"] == observed and previous["sire_birth_year"] == year:
                    found = True
                    break
            historical_rows += int(found)
        historical = historical_rows > 0
        repeated = len(samples) >= 2
        if not (historical or repeated):
            continue
        evidence["historical_spelling_evidence_count"] += historical_rows
        evidence["repeated_relation_evidence_count"] += len(samples) if repeated else 0
        dates = [x[2] for x in samples]
        aliases.append({"observed_name": observed, "canonical_name": canonical, "birth_year": year,
                        "lineage_code": code, "evidence_type": "HISTORICAL_SPELLING" if historical else "REPEATED_RELATION",
                        "evidence_count": len(samples), "first_observed": min(dates), "last_observed": max(dates),
                        "alias_version": "v0.1", "source_generation": generation})
    return aliases, {"apparent_inconsistency_count": apparent, "spelling_case_count": sum(map(len, pairs.values())),
                     "collision_count": len(collisions), "collisions": collisions,
                     "candidate_pair_count": len(pairs), "promoted_alias_pair_count": len(aliases), **evidence}


def table_rows(con: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ",".join("?" for _ in columns)
    con.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                    [tuple(row.get(key) for key in columns) for row in rows])


def build(inputs: list[str], output_root: Path, lineage_path: Path = LINEAGE, alias_path: Path | None = None) -> dict:
    from data_storage.convert import convert
    from data_storage.validate import validate
    archives = archives_from(inputs)
    identity = [(p.name, sha256(p)) for p in archives]
    generation = hashlib.sha256(json.dumps({"builder_version": BUILDER_VERSION, "archives": identity}, sort_keys=True).encode()).hexdigest()[:16]
    destination = output_root / f"brdb-pedigree-generation-{generation}"
    if destination.exists():
        raise FileExistsError(destination)
    lineage = load_lineage(lineage_path)
    with tempfile.TemporaryDirectory(prefix="brdb-pedigree-") as tmp:
        stage = Path(tmp)
        con = sqlite3.connect(stage / "stage.sqlite")
        source, target_ids = ingest(con, archives)\n        if len(source["quarantined_date_records"]) != 8 and any(p.name == "UKC_1999.zip" for p in archives):\n            raise ValueError("unexpected sentinel count for 1999 source; review before building")
        profiles = reduce_profiles(con, generation)
        if len(profiles) != len({p["horse_id"] for p in profiles}):
            raise ValueError("nonunique horse_id")
        aliases, alias_audit = alias_candidates(profiles, con, target_ids, generation)
        if alias_path:
            with alias_path.open(encoding="utf-8", newline="") as f:
                aliases = list(csv.DictReader(f))
            for a in aliases:
                a["birth_year"] = int(a["birth_year"])
                a["evidence_count"] = int(a["evidence_count"])
                if a["evidence_count"] < 1 or not a["evidence_type"] or not a["alias_version"]:
                    raise ValueError("alias lacks evidence/version")
                a["source_generation"] = generation
        con.executescript(SCHEMA.read_text(encoding="utf-8"))
        table_rows(con, "pedigree_fact", profiles)
        table_rows(con, "lineage_code_master", lineage)
        table_rows(con, "pedigree_name_alias", aliases)
        master = relation.HorseMasterIndex(profiles)
        alias_index = relation.AliasIndex(relation.NameAlias(
            observed_name=a["observed_name"], canonical_name=a["canonical_name"],
            birth_year=a["birth_year"], lineage_code=a["lineage_code"],
            alias_version=a["alias_version"], evidence_type=a["evidence_type"]) for a in aliases)
        distributions = {"all": {r: Counter() for r in ROLES}, "target_2025": {r: Counter() for r in ROLES}}
        relation_rows = []
        resolved = {}
        for p in profiles:
            result = relation.resolve_first_generation(p, master=master, aliases=alias_index)
            resolved[p["horse_id"]] = result
            for role, value in result.items():
                distributions["all"][role][value.status] += 1
                if p["horse_id"] in target_ids:
                    distributions["target_2025"][role][value.status] += 1
                relation_rows.append({"child_horse_id": p["horse_id"], "role": role, "parent_name": value.requested_name,
                                      "parent_birth_year": value.requested_birth_year,
                                      "parent_lineage_code": value.requested_lineage_code,
                                      "resolved_parent_horse_id": value.resolved_horse_id,
                                      "resolution_status": value.status, "resolution_method": value.resolution_method,
                                      "candidate_count": value.candidate_count, "guard_result": value.guard,
                                      "resolver_version": "v0.1", "source_generation": generation})
        table_rows(con, "parent_relation", relation_rows)
        con.commit()
        alias_audit["affected_relation_rows"] = sum(row["resolution_status"] == "RESOLVED_ALIAS" for row in relation_rows)
        by_id = {p["horse_id"]: p for p in profiles}
        recursion = Counter()
        for child_id in target_ids:
            direct = resolved.get(child_id, {})
            for parent_role in ("sire", "dam"):
                parent = direct.get(parent_role)
                if not parent or not parent.resolved_horse_id:
                    continue
                for ancestor_role in ("sire", "dam"):
                    ancestor = resolved[parent.resolved_horse_id][ancestor_role]
                    if ancestor.resolved:
                        recursion[f"{parent_role}_s_{ancestor_role}"] += 1
        mapped = {x["lineage_code"] for x in lineage}
        codes = Counter(code for p in profiles for code in (p["sire_line_code"], p["broodmare_sire_line_code"]) if code)
        coverage = {field: sum(bool(p[field]) and bool(p[year]) for p in profiles)
                    for field, year in (("sire_name","sire_birth_year"),("dam_name","dam_birth_year"),
                                        ("broodmare_sire_name","broodmare_sire_birth_year"))}
        coverage.update({field: sum(bool(p[field]) for p in profiles)
                         for field in ("sire_line_code", "broodmare_sire_line_code")})
        audit = {"source": {**source, "unique_horse_id_count": len(profiles)},
                 "pedigree_coverage": coverage,
                 "relation_status": {cohort: {role: {status: counts[status] for status in STATUSES}
                     | {"resolution_percentage": round(100 * (counts["RESOLVED_EXACT"] + counts["RESOLVED_ALIAS"]) /
                       (len(profiles) if cohort == "all" else len(target_ids)), 4)}
                     for role, counts in roles.items()} for cohort, roles in distributions.items()},
                 "recursive_target_2025": dict(recursion), "alias": alias_audit,
                 "lineage": {"observed_codes": dict(sorted(codes.items())), "mapped_count": len(codes.keys() & mapped),
                             "unmapped_values": dict(sorted((k, v) for k, v in codes.items() if k not in mapped)),
                             "major_frequency": {major: sum(n for code, n in codes.items() if code.startswith(major))
                                 for major in sorted({x[:2] for x in codes})},
                             "minor_frequency": dict(sorted(codes.items()))}}
        if by_id.get("22110095"):
            assert resolved["22110095"]["dam"].status == "CONFLICT"
        destination.mkdir(parents=True)
        counts = {}
        hashes = {}
        for table, key in (("pedigree_fact", ["horse_id"]), ("parent_relation", ["child_horse_id", "role"]),
                           ("pedigree_name_alias", ["observed_name", "canonical_name", "birth_year", "lineage_code", "alias_version"]),
                           ("lineage_code_master", ["lineage_code"])):
            target = destination / f"{table}.parquet"
            config = {"source": {"format": "sqlite", "path": str(stage / "stage.sqlite"), "table": table},
                      "target": {"path": str(target), "compression": "zstd"},
                      "keys": {"canonical": key}, "sort_by": key,
                      "validation": {"require_row_count_match": True, "require_unique_key": True}}
            conversion = convert(config)
            check = validate(config, conversion)
            if not check["passed"]:
                raise ValueError(f"{table} Parquet validation failed: {check}")
            counts[table] = conversion["row_count_source"]
            hashes[target.name] = sha256(target)
        dump(destination / "audit.json", audit)
        hashes["audit.json"] = sha256(destination / "audit.json")
        manifest = {"artifact_type": "brdb_pedigree", "generation_id": generation,
                    "schema_version": "v0.1", "builder_version": BUILDER_VERSION,
                    "source_family": "UKC", "source_archive_count": len(archives),
                    "source_min_data_date": source["min_data_date"], "source_max_data_date": source["max_data_date"],
                    "source_archives": source["source_archives"], "row_counts": counts,
                    "canonical_keys": {"pedigree_fact": ["horse_id"], "parent_relation": ["child_horse_id", "role"]},
                    "alias_version": "v0.1", "lineage_source_version": sorted({x["source_version"] for x in lineage}),
                    "validation_status": "PASS", "output_sha256": hashes}
        dump(destination / "manifest.json", manifest)
        con.close()
    return {"output": str(destination), "manifest": manifest, "audit": audit}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="UKC ZIP files or directories")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--lineage-master", type=Path, default=LINEAGE)
    parser.add_argument("--alias-master", type=Path)
    args = parser.parse_args()
    result = build(args.inputs, args.output_root, args.lineage_master, args.alias_master)
    print(json.dumps({"output": result["output"], "generation_id": result["manifest"]["generation_id"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
