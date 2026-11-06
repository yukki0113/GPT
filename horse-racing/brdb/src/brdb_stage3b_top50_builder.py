#!/usr/bin/env python3
"""Stage 3-B source-based top-fifty pedigree expansion; research-only.

Requires DuckDB 1.1.x and real BRDB Parquet artifacts. No invented horse IDs,
regional aptitude or production review. Verified IDs mean canonical JRDB
parent-relation RESOLVED_EXACT/ALIAS only; external JBIS path names stay unbound.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

VERSION = "brdb-stage3b-top50-builder-v0.1"
EXPECTED_PEDIGREE_SHA = "1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536"
EXPECTED_RELATION_SHA = "c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85"
EXPECTED_RANKING_SHA = "e982e7b5a1467af5bb18e74f583acd9315263a74516472ca439c88b0f2eaf362"


def sha256(path: Path) -> str:
    """Hash original source files to prevent silent cohort drift."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(pedigree_file: Path, relation_file: Path, rank_file: Path,
          external_seed_file: Path) -> dict:
    """Build a deterministic, audited top-50 seed from official BRDB facts."""
    if sha256(pedigree_file) != EXPECTED_PEDIGREE_SHA:
        raise ValueError("unexpected pedigree generation SHA")
    if sha256(relation_file) != EXPECTED_RELATION_SHA:
        raise ValueError("unexpected parent-relation generation SHA")
    if sha256(rank_file) != EXPECTED_RANKING_SHA:
        raise ValueError("unexpected top-fifty ranking SHA")
    with rank_file.open(encoding="utf-8-sig", newline="") as stream:
        candidates = list(csv.DictReader(stream))[:50]
    if len(candidates) != 50:
        raise ValueError("exactly fifty ranked stallions required")
    seed = json.loads(external_seed_file.read_text(encoding="utf-8"))
    if seed.get("version") != "brdb-stage3b-external-stallion-pedigree-v0.1":
        raise ValueError("unexpected JBIS pedigree seed version")
    external = {}
    for row in seed["pedigrees"]:
        label = row["jrdb_observed_label"]
        jb = row["jbis_horse_id"]
        if label in external or not re.fullmatch(r"[0-9]{10}", jb):
            raise ValueError("duplicate/bad source identity")
        if row["source_url"] != f"https://www.jbis.jp/horse/{jb}/":
            raise ValueError("wrong JBIS source URL")
        if row["jrdb_horse_id"] is not None or row["ancestor_person_ids_verified"]:
            raise ValueError("external labels cannot mint JRDB or ancestor IDs")
        if set(row["source_name_paths"]) != {"S", "D", "SS", "SD", "DS", "DD"}:
            raise ValueError("incomplete JBIS parent labels")
        external[label] = row

    con = duckdb.connect()
    # CREATE VIEW does not accept bind variables in this DuckDB release.
    # Escaping is safe for quoted local paths; SQL values are still bound below.
    pf = str(pedigree_file).replace("'", "''")
    rf = str(relation_file).replace("'", "''")
    con.execute(f"CREATE VIEW pedigree AS SELECT * FROM read_parquet('{pf}')")
    con.execute(f"CREATE VIEW relations AS SELECT * FROM read_parquet('{rf}')")
    parents = defaultdict(dict)
    for child, role, parent_id, status, name, year in con.execute("""
        SELECT child_horse_id, role, resolved_parent_horse_id,
               resolution_status, parent_name, parent_birth_year
        FROM relations WHERE role IN ('sire', 'dam')
    """).fetchall():
        if role in parents[child]:
            raise ValueError("duplicate BRDB parent role")
        parents[child][role] = (parent_id, status, name, year)

    def walk(horse_id: str, path: str, lineage: frozenset[str], out: list):
        """Traverse only independently verified JRDB person edges."""
        if len(path) == 3:
            return
        for role, letter in (("sire", "S"), ("dam", "D")):
            child_path = path + letter
            record = parents.get(horse_id, {}).get(role)
            if record is None:
                out.append({"path": child_path, "name": None, "birth_year": None,
                            "jrdb_ancestor_id": None, "status": "UNKNOWN_RELATION"})
                continue
            parent, status, name, year = record
            verified = status in ("RESOLVED_EXACT", "RESOLVED_ALIAS") and parent
            if verified and (not re.fullmatch("[0-9]{8}", parent)
                             or parent in lineage):
                raise ValueError("invalid/cyclic JRDB ancestor ID")
            out.append({"path": child_path, "name": name, "birth_year": year,
                        "jrdb_ancestor_id": parent if verified else None,
                        "status": "JRDB_CANONICAL_ID" if verified
                        else "JRDB_PARENT_NAME_UNRESOLVED"})
            if verified:
                walk(parent, child_path, lineage | {parent}, out)

    subjects = []
    for rank, raw in enumerate(candidates, 1):
        name, year = raw["name"], int(raw["birth_year"])
        code = raw["jrdb_lineage_code"]
        candidates_p = con.execute("""
            SELECT horse_id, sire_name, dam_name, broodmare_sire_name
            FROM pedigree WHERE horse_name=?
                AND substr(birth_date,1,4)=?
                AND sex_code='1' AND sire_line_code=?
        """, [name, str(year), code]).fetchall()
        if len(candidates_p) > 1:
            raise ValueError(f"ambiguous JRDB stallion {name}")
        profile = candidates_p[0] if candidates_p else None
        extra = external.get(name)
        if profile is None and extra is None:
            raise ValueError(f"unsourced top-fifty horse {name}")
        if profile is not None and extra is not None:
            raise ValueError(f"unexpected dual source for {name}")
        paths = []
        if profile:
            root = profile[0]
            walk(root, "", frozenset({root}), paths)
            direct_bms = profile[3]
            known_ds = next((p for p in paths if p["path"] == "DS"), None)
            if direct_bms and known_ds is None:
                paths.append({"path":"DS", "name": direct_bms,
                              "birth_year": None, "jrdb_ancestor_id": None,
                              "status": "JRDB_DIRECT_BMS_NAME_ONLY"})
            if direct_bms and known_ds is not None and known_ds["name"] != direct_bms:
                raise ValueError("dam sire conflicts with direct broodmare sire")
            identity = "JRDB_PROFILE_GUARDED"
        else:
            root = None
            identity = "JBIS_EXTERNAL_PROFILE_UNBOUND_TO_JRDB"
            for p, ancestor in extra["source_name_paths"].items():
                if not isinstance(ancestor, str) or not ancestor:
                    raise ValueError("empty ancestor evidence")
                paths.append({"path":p, "name":ancestor,
                              "birth_year":None, "jrdb_ancestor_id":None,
                              "status":"JBIS_ANCESTOR_NAME_ONLY"})
        if len(set(p["path"] for p in paths)) != len(paths):
            raise ValueError("duplicate ancestor path")
        subjects.append({
            "rank":rank, "name":name, "birth_year":year, "jrdb_lineage_code":code,
            "sire_count":int(raw["sire_count"]), "bms_count":int(raw["bms_count"]),
            "identity_status":identity, "jrdb_horse_id":root,
            "external_jbis_id":extra["jbis_horse_id"] if extra else None,
            "external_source_url":extra["source_url"] if extra else None,
            "ancestor_paths":sorted(paths,key=lambda p:(len(p["path"]),p["path"])),
        })
    queue = defaultdict(lambda: {"subjects":set(), "slots":0, "paths":Counter()})
    for subject in subjects:
        for ancestor in subject["ancestor_paths"]:
            if ancestor["jrdb_ancestor_id"] is None and ancestor["name"]:
                # Name/year is only a *research grouping key*, NOT person ID.
                key = (ancestor["name"], ancestor["birth_year"])
                queue[key]["subjects"].add(subject["name"])
                queue[key]["slots"] += 1
                queue[key]["paths"][ancestor["path"]] += 1
    weights = {s["name"]:s["sire_count"]+s["bms_count"] for s in subjects}
    backlog = [{
        "observed_name":name, "observed_birth_year":year,
        "top50_subjects_affected":len(info["subjects"]),
        "unresolved_slots":info["slots"],
        "weighted_upper_bound":sum(weights[s] for s in info["subjects"]),
        "paths":dict(sorted(info["paths"].items())),
        "status":"INDIVIDUAL_ID_REVIEW_REQUIRED",
    } for (name,year),info in queue.items()]
    backlog.sort(key=lambda e:(-e["weighted_upper_bound"],e["observed_name"]))
    depths = {}
    for d in (1,2,3):
        resolved = sum(len([p for p in s["ancestor_paths"]
                            if len(p["path"]) == d and p["jrdb_ancestor_id"]])
                       for s in subjects)
        named = sum(len([p for p in s["ancestor_paths"]
                         if len(p["path"]) == d and p["name"]])
                    for s in subjects)
        depths[str(d)] = {"expected_slots":50*(2**d),
                          "canonical_paths":resolved,"name_paths":named}
    return {
        "version":VERSION, "source_generation":"5279af0bd8226cde",
        "research_only":True, "historical_asof_status":"AS_OF_UNVERIFIED",
        "prediction_safe":False, "can_override_review":False,
        "source_sha256":{
            "pedigree":sha256(pedigree_file),
            "parent_relation":sha256(relation_file),
            "ranking":sha256(rank_file),
            "external_seed":sha256(external_seed_file),
        },
        "subject_count":len(subjects),
        "jrdb_subjects":sum(s["jrdb_horse_id"] is not None for s in subjects),
        "jbis_only_subjects":sum(s["external_jbis_id"] is not None for s in subjects),
        "depth_coverage":depths, "subjects":subjects,
        "unresolved_ancestor_queue":backlog,
    }


def main() -> None:
    """Run the audit with explicit immutable input paths and output JSON."""
    parser = argparse.ArgumentParser()
    for key in ("pedigree", "relations", "ranking", "external_seed", "output"):
        parser.add_argument("--" + key.replace("_", "-"), required=True, type=Path)
    args = parser.parse_args()
    result = build(args.pedigree, args.relations, args.ranking,
                   args.external_seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",
                           encoding="utf-8")
    print(json.dumps({
        "subject_count": result["subject_count"],
        "jrdb_subjects": result["jrdb_subjects"],
        "jbis_only_subjects": result["jbis_only_subjects"],
        "depth_coverage": result["depth_coverage"],
        "unresolved_names":len(result["unresolved_ancestor_queue"]),
    },ensure_ascii=False))


if __name__ == "__main__":
    main()
