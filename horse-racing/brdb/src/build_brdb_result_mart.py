#!/usr/bin/env python3
"""BRDB P0-2 descriptive research mart. NOT prediction-safe; no CURRENT writes.

Join canonical JRDB Historical Warehouse KYI/SED/BAC to BRDB pedigree facts.
Inputs are immutable SHA-pinned assets. Static pedigree is descriptive ONLY.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import duckdb

VERSION = "brdb-result-mart-research-v0.1"
PERIOD = range(2016, 2026)
TEMPORAL_LABEL = "STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_year_assets(manifest_path, root, family, years):
    manifest_path, root = Path(manifest_path), Path(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("artifact_type") != "jrdb_normalized_warehouse":
        raise ValueError(f"{family}: unaccepted warehouse manifest")
    assets = {
        int(a["year"]): a for a in manifest.get("assets", [])
        if a.get("family") == family and a.get("year") in years
    }
    if set(assets) != set(years):
        raise ValueError(f"{family}: missing year manifests {set(years) - set(assets)}")
    paths = []
    for year in years:
        a = assets[year]
        p = (root / a["relative_path"]).resolve()
        if not p.is_relative_to(root.resolve()) or not p.is_file():
            raise ValueError(f"{family}: object not materialized safely: {year}")
        if not re.fullmatch(r"[0-9a-f]{64}", a["sha256"]) or p.name != a["sha256"] + ".parquet":
            raise ValueError(f"{family}: unpinned object: {year}")
        if p.stat().st_size != a["size_bytes"] or digest(p) != a["sha256"]:
            raise ValueError(f"{family}: object size/SHA invalid: {year}")
        paths.append(str(p))
    return manifest, paths, digest(manifest_path)


def literal(value):
    """Quote an already SHA-validated local filename in DuckDB DDL/COPY SQL."""
    return "'" + str(value).replace("'", "''") + "'"


def fail_if(con, sql, why):
    n = con.execute(sql).fetchone()[0]
    if n:
        raise ValueError(f"{why}: {n}")


def materialize(kyi, sed, bac, pedigree, output, *, years=range(2016, 2026),
                expected_generation=None):
    """Construct a static descriptive-only research mart with fail-closed keys."""
    years = sorted(set(years))
    if not years or not set(years).issubset(PERIOD):
        raise ValueError("only historical 2016..2025 years allowed")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    inputs = {}
    for family, spec in [("kyi", kyi), ("sed", sed), ("bac", bac)]:
        manifest, paths, manifest_sha = load_year_assets(spec[0], spec[1], family, years)
        inputs[family] = {"generation_id": manifest["generation_id"],
                          "manifest_sha256": manifest_sha, "assets": paths}

    pedigree = Path(pedigree)
    p_manifest = pedigree / "manifest.json"
    pm = json.loads(p_manifest.read_text(encoding="utf-8"))
    if pm.get("validation_status") != "PASS" or (
        expected_generation and pm["generation_id"] != expected_generation
    ):
        raise ValueError("BRDB pedigree generation invalid")
    fact_path = pedigree / "pedigree_fact.parquet"
    if digest(fact_path) != pm["output_sha256"]["pedigree_fact.parquet"]:
        raise ValueError("pedigree master SHA mismatch")
    inputs["brdb"] = {"generation_id": pm["generation_id"],
                      "manifest_sha256": digest(p_manifest),
                      "pedigree_fact_sha256": digest(fact_path)}

    con = duckdb.connect()
    try:
        for family in ("kyi", "sed", "bac"):
            path_list = ",".join(map(literal, inputs[family]["assets"]))
            con.execute(f"CREATE TEMP VIEW {family} AS SELECT * FROM read_parquet([{path_list}])")
        con.execute("CREATE TEMP VIEW pedigree AS SELECT * FROM read_parquet(" +
                    literal(fact_path) + ")")
        for family, cols in [
            ("kyi", "race_key_raw,horse_no"), ("sed", "race_key_raw,horse_no"),
            ("bac", "race_key_raw,source_member_date"), ("pedigree", "horse_id")
        ]:
            fail_if(con, f"SELECT count(*)-count(DISTINCT ({cols})) FROM {family}",
                    family + " duplicate canonical key")
        for family in ("kyi", "sed"):
            fail_if(con, f"SELECT count(*) FROM {family} WHERE "
                         "length(blood_registration_no) != 8 OR blood_registration_no IS NULL",
                    family + " invalid horse ID")
        fail_if(con, """SELECT count(*) FROM kyi k FULL JOIN sed s
                   ON k.race_key_raw=s.race_key_raw AND k.horse_no=s.horse_no
                   WHERE k.race_key_raw IS NULL OR s.race_key_raw IS NULL
                   OR k.blood_registration_no != s.blood_registration_no""",
                "KYI/SED exact identity mismatch")
        fail_if(con, """SELECT count(*) FROM sed s JOIN bac b
                   ON s.race_key_raw=b.race_key_raw
                   WHERE s.date_raw<>b.date_raw
                   OR (s.distance_m IS NOT NULL
                       AND try_cast(b.distance_raw AS INT) IS NOT NULL
                       AND s.distance_m<>try_cast(b.distance_raw AS INT))
                   OR (s.surface_code IS NOT NULL AND b.surface_code IS NOT NULL
                       AND s.surface_code<>b.surface_code)""",
                "BAC/SED condition conflict")
        fail_if(con, """SELECT count(*) FROM bac b WHERE
                 (SELECT count(DISTINCT s.date_raw) FROM sed s
                  WHERE s.race_key_raw=b.race_key_raw)>1""",
                "BAC multiple result dates")

        con.execute("""CREATE TEMP TABLE joined AS
          SELECT try_cast(k.year AS INT) AS race_year,
                 k.race_key_raw AS race_key, k.horse_no,
                 k.blood_registration_no AS horse_id,
                 s.date_raw AS race_date, s.abnormal_code,
                 try_cast(s.finish AS INT) AS finish,
                 (s.abnormal_code='0' AND try_cast(s.finish AS INT) BETWEEN 1 AND 18)
                   AS normal_finisher,
                 (s.abnormal_code='0' AND try_cast(s.finish AS INT)=1) AS winner,
                 (s.abnormal_code='0' AND try_cast(s.finish AS INT) BETWEEN 1 AND 3)
                   AS top3,
                 coalesce(b.surface_code,s.surface_code) AS surface_code,
                 coalesce(try_cast(b.distance_raw AS INT),
                          try_cast(s.distance_m AS INT)) AS distance_m,
                 coalesce(b.race_class_code,s.race_class_code) AS race_class_code,
                 substr(k.race_key_raw,1,2) AS venue_code,
                 CASE WHEN b.race_key_raw IS NULL THEN 'SED_FALLBACK'
                      ELSE 'BAC_VERIFIED' END AS context_source,
                 CASE WHEN p.horse_id IS NULL THEN 'UNKNOWN_HORSE_ID'
                      ELSE 'STATIC_ONLY' END AS pedigree_status,
                 p.sire_name,p.dam_name,p.broodmare_sire_name,
                 p.sire_line_code,p.broodmare_sire_line_code,
                 ?::VARCHAR AS pedigree_temporal_status
          FROM kyi k
          JOIN sed s ON k.race_key_raw=s.race_key_raw AND k.horse_no=s.horse_no
          LEFT JOIN bac b ON s.race_key_raw=b.race_key_raw
          LEFT JOIN pedigree p ON k.blood_registration_no=p.horse_id""",
                    [TEMPORAL_LABEL])
        fail_if(con, "SELECT count(*) FROM joined WHERE race_year NOT IN (" +
                ",".join(map(str, years)) + ")", "year scope leak")
        fail_if(con, """SELECT count(*) FROM joined
                        WHERE substr(race_date,1,4) != cast(race_year AS VARCHAR)""",
                "race date/year mismatch")
        fail_if(con, """SELECT count(*) FROM joined
                        WHERE normal_finisher AND abnormal_code<>'0'""",
                "non-normal record marked finisher")
        original = con.execute("SELECT count(*) FROM kyi").fetchone()[0]
        count = con.execute("SELECT count(*) FROM joined").fetchone()[0]
        if count != original:
            raise ValueError(f"join cardinality changed {original}->{count}")

        rows = con.execute("""SELECT race_year,count(*) entries,
                   count(DISTINCT horse_id) horses,
                   count(*) FILTER (WHERE context_source='BAC_VERIFIED') bac_joined,
                   count(*) FILTER (WHERE context_source='SED_FALLBACK') sed_fallback,
                   count(*) FILTER (WHERE pedigree_status='STATIC_ONLY') pedigree_static,
                   count(*) FILTER (WHERE normal_finisher) normal_finishers,
                   count(*) FILTER (WHERE NOT normal_finisher) non_normal,
                   count(*) FILTER (WHERE winner) winners,
                   count(*) FILTER (WHERE top3) top3_finishers
                   FROM joined GROUP BY 1 ORDER BY 1""").fetchall()
        annual = [
            dict(zip(("race_year", "entries", "horses", "bac_joined", "sed_fallback",
                      "pedigree_static", "normal_finishers", "non_normal",
                      "winners", "top3_finishers"), row))
            for row in rows
        ]
        groups = con.execute("""SELECT race_year,sire_line_code,surface_code,
                 CASE WHEN distance_m<1400 THEN 'SPRINT_LT1400'
                      WHEN distance_m<1800 THEN 'MILE_1400_1799'
                      WHEN distance_m<2200 THEN 'MIDDLE_1800_2199'
                      ELSE 'LONG_GE2200' END distance_band,
                 count(*) FILTER (WHERE normal_finisher) normal_finishers,
                 count(*) FILTER (WHERE winner) winners,
                 count(*) FILTER (WHERE top3) top3_finishers
                 FROM joined
                 WHERE pedigree_status='STATIC_ONLY' AND distance_m>0
                 GROUP BY 1,2,3,4 ORDER BY 1,2,3,4""").fetchall()
        group_rows = [
            dict(zip(("race_year", "sire_line_code", "surface_code", "distance_band",
                      "normal_finishers", "winners", "top3_finishers"), row))
            for row in groups
        ]
        mart = output / "brdb_result_mart.parquet"
        con.execute("COPY joined TO " + literal(mart) + " (FORMAT PARQUET, COMPRESSION ZSTD)")
        grouped = output / "brdb_sire_condition_counts.json"
        grouped.write_text(json.dumps(group_rows, ensure_ascii=False,
                                      sort_keys=True, indent=2) + "\n", encoding="utf-8")
        result = {
            "version": VERSION, "status": "PASS", "research_only": True,
            "prediction_safe": False, "pedigree_temporal_policy": TEMPORAL_LABEL,
            "actual_starters": None, "source_generations": inputs,
            "yearly": annual, "total_entries": count,
            "output_sha256": {
                "brdb_result_mart.parquet": digest(mart),
                "brdb_sire_condition_counts.json": digest(grouped)},
            "warnings": [
                "Later-selected static pedigree is DESCRIPTIVE ONLY.",
                "Normal finishers are not the same as all actual starters.",
                "SED fallback used for races with absent BAC.",
                "No pre-race backtest or scoring permitted."
            ]}
        (output / "audit.json").write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
        return result
    finally:
        con.close()


def cli():
    p = argparse.ArgumentParser(description=__doc__)
    for family in ("kyi", "sed", "bac"):
        p.add_argument("--" + family + "-manifest", type=Path, required=True)
        p.add_argument("--" + family + "-root", type=Path, required=True)
    p.add_argument("--pedigree-generation", type=Path, required=True)
    p.add_argument("--expected-generation-id", required=True)
    p.add_argument("--start-year", type=int, default=2016)
    p.add_argument("--end-year", type=int, default=2025)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = materialize(
        (a.kyi_manifest, a.kyi_root),
        (a.sed_manifest, a.sed_root),
        (a.bac_manifest, a.bac_root),
        a.pedigree_generation, a.output,
        years=range(a.start_year, a.end_year + 1),
        expected_generation=a.expected_generation_id)
    print(json.dumps({"status": result["status"],
                      "rows": result["total_entries"], "output": str(a.output)}))


if __name__ == "__main__":
    cli()
