#!/usr/bin/env python3
"""Add true first-surface/blinkers history families to the frozen v0.5 inventory.

The existing T1-T6 implementation remains the owner of its metrics and rows.
This entrypoint runs it unchanged, verifies the accepted Warehouse bridge, then
builds only the three history-dependent families and combines their inventory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "horse-racing" / "jrdb" / "src"
sys.path.insert(0, str(SRC))

import jrdb_edge_v05_prototype_aggregation as base

WAREHOUSE_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"
WAREHOUSE_DIGEST = "sha256:fb28c17889cf2a9028b58e1bac3164b89a0b4c66eadfb5d3dba19d1ace88499a"
WAREHOUSE_RUN = 37592837881
WAREHOUSE_ARTIFACT_ID = 11468713930
FIRST_SPECS = {
    "T4_SIRE_FIRST_DIRT": {"conditions": ["sire_name", "first_dirt"], "parent": ["sire_name"], "family": "T4"},
    "T4_SIRE_FIRST_TURF": {"conditions": ["sire_name", "first_turf"], "parent": ["sire_name"], "family": "T4"},
    "T5_SIRE_FIRST_BLINKERS": {"conditions": ["sire_name", "first_blinkers"], "parent": ["sire_name"], "family": "T5"},
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_warehouse(root: Path) -> dict[str, Any]:
    manifest_path = root / "research_materialization_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("generation_id") != WAREHOUSE_GENERATION:
        raise ValueError("accepted Warehouse generation/status mismatch")
    years = list(range(2010, 2026))
    if manifest.get("years") != years or manifest.get("families") != ["KYI", "SED"]:
        raise ValueError("Warehouse family/year selection mismatch")
    assets = manifest.get("assets") or []
    if len(assets) != 32 or manifest.get("asset_count") != 32:
        raise ValueError("Warehouse artifact must contain exactly 32 annual assets")
    counts = Counter(str(x.get("family", "")).upper() for x in assets)
    if counts != Counter({"KYI": 16, "SED": 16}):
        raise ValueError(f"Warehouse partition count mismatch: {dict(counts)}")
    seen: set[tuple[str, int]] = set()
    for asset in assets:
        family, year = str(asset["family"]).upper(), int(asset["year"])
        if (family, year) in seen or year not in years:
            raise ValueError("duplicate or unexpected Warehouse partition")
        seen.add((family, year))
        path = root / str(asset["relative_path"])
        if not path.is_file() or path.stat().st_size != int(asset["size_bytes"]):
            raise ValueError(f"Warehouse asset size/missing mismatch: {family} {year}")
        actual = sha256(path)
        if actual != str(asset["sha256"]).removeprefix("sha256:"):
            raise ValueError(f"Warehouse asset SHA256 mismatch: {family} {year}")
    if len(seen) != 32:
        raise ValueError("Warehouse partition matrix incomplete")
    return {"generation_id": WAREHOUSE_GENERATION, "run_id": WAREHOUSE_RUN,
            "artifact_id": WAREHOUSE_ARTIFACT_ID, "artifact_digest": WAREHOUSE_DIGEST,
            "partition_count": 32, "family_partition_counts": dict(counts),
            "years": years, "manifest_sha256": sha256(manifest_path),
            "manifest": manifest}


def build_history_features(con: Any, warehouse: Path, feature_path: Path,
                           output_path: Path) -> dict[str, Any]:
    """Reconcile canonical SED/KYI history and attach pre-race chronology flags."""
    import duckdb

    manifest = json.loads((warehouse / "research_materialization_manifest.json").read_text(encoding="utf-8"))
    lookup = {(str(a["family"]).upper(), int(a["year"])): warehouse / a["relative_path"] for a in manifest["assets"]}
    sed_paths = [str(lookup[("SED", y)]) for y in range(2010, 2026)]
    kyi_paths = [str(lookup[("KYI", y)]) for y in range(2010, 2026)]
    def parquet_list(paths: list[str]) -> str:
        return "[" + ",".join("'" + p.replace("'", "''") + "'" for p in paths) + "]"
    con.execute(f"CREATE OR REPLACE TEMP VIEW sed_raw AS SELECT trim(CAST(blood_registration_no AS VARCHAR)) blood_id, trim(CAST(race_key_raw AS VARCHAR)) race_key, trim(CAST(horse_no AS VARCHAR)) horse_no, CAST(race_date AS VARCHAR) race_date, trim(CAST(surface_code AS VARCHAR)) surface FROM read_parquet({parquet_list(sed_paths)})")
    con.execute("CREATE OR REPLACE TEMP VIEW sed_groups AS SELECT blood_id,race_key,horse_no,min(race_date) race_date,min(surface) surface,count(*) raw_rows,count(DISTINCT surface) surface_variants FROM sed_raw GROUP BY blood_id,race_key,horse_no")
    sed_raw_rows = int(con.execute("SELECT count(*) FROM sed_raw").fetchone()[0])
    sed_unique = int(con.execute("SELECT count(*) FROM sed_groups").fetchone()[0])
    sed_duplicate_groups = int(con.execute("SELECT count(*) FROM sed_groups WHERE raw_rows>1").fetchone()[0])
    sed_conflicts = int(con.execute("SELECT count(*) FROM sed_groups WHERE surface_variants!=1 OR blood_id='' OR race_key='' OR horse_no='' OR race_date IS NULL").fetchone()[0])
    con.execute("""
      CREATE OR REPLACE TEMP VIEW sed_history AS
      SELECT g.*, count(DISTINCT race_key) OVER(PARTITION BY blood_id,race_date) same_day_races,
             min(race_date) OVER(PARTITION BY blood_id) first_seen
      FROM sed_groups g
    """)
    con.execute("""
      CREATE OR REPLACE TEMP VIEW sed_flags AS
      SELECT h.*,
        CASE WHEN surface_variants!=1 OR same_day_races>1 OR blood_id='' OR race_key='' OR horse_no='' OR race_date IS NULL THEN NULL
             WHEN surface!='2' THEN FALSE
             WHEN EXISTS (SELECT 1 FROM sed_history p WHERE p.blood_id=h.blood_id AND p.surface='2' AND p.race_date<h.race_date AND p.surface_variants=1) THEN FALSE
             WHEN substr(first_seen,1,4)='2010' THEN NULL ELSE TRUE END first_dirt,
        CASE WHEN surface_variants!=1 OR same_day_races>1 OR blood_id='' OR race_key='' OR horse_no='' OR race_date IS NULL THEN NULL
             WHEN surface!='1' THEN FALSE
             WHEN EXISTS (SELECT 1 FROM sed_history p WHERE p.blood_id=h.blood_id AND p.surface='1' AND p.race_date<h.race_date AND p.surface_variants=1) THEN FALSE
             WHEN substr(first_seen,1,4)='2010' THEN NULL ELSE TRUE END first_turf
      FROM sed_history h
    """)

    con.execute(f"CREATE OR REPLACE TEMP VIEW kyi_raw AS SELECT trim(CAST(blood_registration_no AS VARCHAR)) blood_id, trim(CAST(race_key_raw AS VARCHAR)) race_key, trim(CAST(horse_no AS VARCHAR)) horse_no, trim(CAST(blinker_code AS VARCHAR)) blinker_code FROM read_parquet({parquet_list(kyi_paths)})")
    con.execute("""
      CREATE OR REPLACE TEMP VIEW kyi_groups AS
      SELECT k.blood_id,k.race_key,k.horse_no,min(k.blinker_code) blinker_code,
             count(*) raw_rows,count(DISTINCT k.blinker_code) code_variants,
             min(s.race_date) race_date
      FROM kyi_raw k LEFT JOIN sed_groups s USING(blood_id,race_key,horse_no)
      GROUP BY k.blood_id,k.race_key,k.horse_no
    """)
    kyi_raw_rows = int(con.execute("SELECT count(*) FROM kyi_raw").fetchone()[0])
    kyi_duplicate_groups = int(con.execute("SELECT count(*) FROM kyi_groups WHERE raw_rows>1").fetchone()[0])
    kyi_conflicts = int(con.execute("SELECT count(*) FROM kyi_groups WHERE code_variants!=1 OR race_date IS NULL OR blood_id='' OR race_key='' OR horse_no=''").fetchone()[0])
    con.execute("""
      CREATE OR REPLACE TEMP VIEW kyi_history AS
      SELECT g.*, count(DISTINCT race_key) OVER(PARTITION BY blood_id,race_date) same_day_races,
             min(race_date) OVER(PARTITION BY blood_id) first_seen
      FROM kyi_groups g
    """)
    con.execute("""
      CREATE OR REPLACE TEMP VIEW kyi_flags AS
      SELECT h.*,
        CASE WHEN code_variants!=1 OR same_day_races>1 OR race_date IS NULL OR blood_id='' OR race_key='' OR horse_no='' OR (blinker_code NOT IN ('1','2','3','0','') AND blinker_code IS NOT NULL) THEN NULL
             WHEN blinker_code NOT IN ('1','2','3') OR blinker_code IS NULL THEN FALSE
             WHEN EXISTS (SELECT 1 FROM kyi_history p WHERE p.blood_id=h.blood_id AND p.blinker_code IN ('1','2','3') AND p.race_date<h.race_date AND p.code_variants=1) THEN FALSE
             WHEN substr(first_seen,1,4)='2010' THEN NULL ELSE TRUE END first_blinkers_chronology,
        CASE WHEN blinker_code='1' THEN TRUE WHEN blinker_code IN ('0','2','3','') OR blinker_code IS NULL THEN FALSE ELSE NULL END code_first_use
      FROM kyi_history h
    """)
    mismatch = int(con.execute("SELECT count(*) FROM kyi_flags WHERE first_blinkers_chronology IS NOT NULL AND code_first_use IS NOT NULL AND first_blinkers_chronology!=code_first_use").fetchone()[0])
    mismatch_cur = con.execute("SELECT blood_id,race_key,horse_no,race_date,blinker_code,first_blinkers_chronology,code_first_use FROM kyi_flags WHERE first_blinkers_chronology IS NOT NULL AND code_first_use IS NOT NULL AND first_blinkers_chronology!=code_first_use ORDER BY race_date,blood_id,race_key LIMIT 20")
    mismatch_samples = [dict(zip([d[0] for d in mismatch_cur.description], row)) for row in mismatch_cur.fetchall()]
    code_cur = con.execute("SELECT coalesce(nullif(blinker_code,''),'<BLANK>') code,count(*) n FROM kyi_groups GROUP BY 1 ORDER BY 1")
    blinker_code_distribution = [{"code": row[0], "count": int(row[1])} for row in code_cur.fetchall()]
    con.execute("""
      CREATE OR REPLACE TEMP VIEW kyi_flags_checked AS
      SELECT *, CASE WHEN first_blinkers_chronology IS NULL OR code_first_use IS NULL OR first_blinkers_chronology!=code_first_use THEN NULL ELSE first_blinkers_chronology END first_blinkers
      FROM kyi_flags
    """)
    con.execute(f"""
      COPY (
        SELECT f.*,
               CASE WHEN s.race_key IS NULL OR CAST(f.surface_code AS VARCHAR)!=s.surface OR CAST(f.horse_id AS VARCHAR)!=s.blood_id THEN NULL ELSE s.first_dirt END first_dirt,
               CASE WHEN s.race_key IS NULL OR CAST(f.surface_code AS VARCHAR)!=s.surface OR CAST(f.horse_id AS VARCHAR)!=s.blood_id THEN NULL ELSE s.first_turf END first_turf,
               CASE WHEN s.race_key IS NULL OR CAST(f.surface_code AS VARCHAR)!=s.surface OR CAST(f.horse_id AS VARCHAR)!=s.blood_id THEN NULL ELSE k.first_blinkers END first_blinkers,
               CASE WHEN s.race_key IS NULL THEN 'NO_SED_JOIN'
                    WHEN CAST(f.surface_code AS VARCHAR)!=s.surface THEN 'SURFACE_MISMATCH'
                    WHEN CAST(f.horse_id AS VARCHAR)!=s.blood_id THEN 'BLOOD_ID_MISMATCH'
                    ELSE 'MATCHED' END history_join_status
        FROM read_parquet('{str(feature_path).replace("'", "''")}') f
        LEFT JOIN sed_flags s ON CAST(f.race_key AS VARCHAR)=s.race_key AND CAST(f.horse_no AS VARCHAR)=s.horse_no
          AND substr(CAST(f.race_date AS VARCHAR),1,10)=substr(s.race_date,1,10)
        LEFT JOIN kyi_flags_checked k ON CAST(f.race_key AS VARCHAR)=k.race_key AND CAST(f.horse_no AS VARCHAR)=k.horse_no
          AND CAST(f.horse_id AS VARCHAR)=k.blood_id AND s.race_date=k.race_date
        WHERE f.race_date BETWEEN '2022-01-01' AND '2025-12-31'
      ) TO '{str(output_path).replace("'", "''")}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    join_counts = {str(status): int(n) for status, n in con.execute("SELECT history_join_status,count(*) FROM read_parquet(?) GROUP BY 1", [str(output_path)]).fetchall()}
    surf_unknown = {"first_dirt": int(con.execute("SELECT count(*) FROM read_parquet(?) WHERE first_dirt IS NULL", [str(output_path)]).fetchone()[0]),
                    "first_turf": int(con.execute("SELECT count(*) FROM read_parquet(?) WHERE first_turf IS NULL", [str(output_path)]).fetchone()[0]),
                    "first_blinkers": int(con.execute("SELECT count(*) FROM read_parquet(?) WHERE first_blinkers IS NULL", [str(output_path)]).fetchone()[0])}
    return {"sed_rows": sed_raw_rows, "sed_reconciled_events": sed_unique,
            "sed_duplicate_groups_collapsed": sed_duplicate_groups, "sed_conflict_groups": sed_conflicts,
            "same_day_multi_race_horses_dates": int(con.execute("SELECT count(*) FROM sed_history WHERE same_day_races>1").fetchone()[0]),
            "kyi_rows": kyi_raw_rows, "kyi_duplicate_groups_collapsed": kyi_duplicate_groups,
            "kyi_conflict_or_unjoined_groups": kyi_conflicts,
            "history_join_counts": join_counts, "unknown_feature_rows": surf_unknown,
            "blinker_chronology_count": int(con.execute("SELECT count(*) FROM kyi_flags WHERE first_blinkers_chronology=TRUE").fetchone()[0]),
            "blinker_code_1_count": int(con.execute("SELECT count(*) FROM kyi_flags WHERE code_first_use=TRUE").fetchone()[0]),
            "blinker_code_parity_mismatch_count": mismatch, "blinker_mismatch_examples": mismatch_samples,
            "blinker_code_distribution": blinker_code_distribution,
            "identity_coverage": {"surface_event_rows": sed_unique,
                                  "valid_canonical_registration": int(con.execute("SELECT count(*) FROM sed_groups WHERE regexp_full_match(blood_id,'[0-9]{8}')").fetchone()[0])}}


def assemble_new_candidates(con: Any, enriched: Path, base_output: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import pyarrow as pa

    base.SPECS.update(FIRST_SPECS)
    conditions = {
        "T4_SIRE_FIRST_DIRT": "first_dirt",
        "T4_SIRE_FIRST_TURF": "first_turf",
        "T5_SIRE_FIRST_BLINKERS": "first_blinkers",
    }
    grouped: list[dict[str, Any]] = []
    for template, flag in conditions.items():
        rows = con.execute(f"SELECT sire_name,count(*) n FROM read_parquet(?) WHERE race_date BETWEEN '2024-01-01' AND '2025-12-31' AND is_pre_race_eligible=1 AND {flag}=TRUE AND sire_name IS NOT NULL GROUP BY sire_name ORDER BY sire_name", [str(enriched)]).fetchall()
        for sire, n in rows:
            cond = {"sire_name": str(sire), flag: "true"}
            spec = FIRST_SPECS[template]
            parent = {"sire_name": str(sire)}
            pkey = base.fingerprint({"template": "T4_SIRE" if template.startswith("T4") else "T5_SIRE", "conditions": parent})
            grouped.append({"candidate_id": base.candidate_id(template, cond), "template_id": template,
                            "template_version": "v0.5.1", "family": spec["family"], "conditions": cond,
                            "condition_fingerprint": base.fingerprint(cond), "condition_values": [cond[x] for x in spec["conditions"]],
                            "discovery_population_n": int(n), "parent_template": "T4_SIRE" if template.startswith("T4") else "T5_SIRE",
                            "parent_values": [str(sire)], "parent_key": pkey, "depth": 2})
    ids = [x["candidate_id"] for x in grouped]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate first-history candidate IDs")
    metrics: list[dict[str, Any]] = []
    parents: dict[tuple[str, str], dict[str, Any]] = {}
    for template in conditions:
        subset = [c for c in grouped if c["template_id"] == template]
        metrics.extend(base._metrics_query(con, template, subset, enriched))
        parents.update(base._parent_metrics(con, template, subset, enriched))
    byid: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in metrics:
        byid[row["candidate_id"]][row["period"]] = base._metric_obj(row)
    result: list[dict[str, Any]] = []
    for c in grouped:
        m = byid[c["candidate_id"]]
        ctx = m.get("context_2022_2023", base._metric_obj(None)); y24 = m.get("year_2024", base._metric_obj(None))
        y25 = m.get("year_2025", base._metric_obj(None)); recent = m.get("overall_2024_2025", base._metric_obj(None))
        pset = {period: parents.get((c["parent_key"], period)) for period in ("context_2022_2023", "year_2024", "year_2025", "overall_2024_2025")}
        def parent_obj(period: str) -> dict[str, Any]:
            r = pset[period]
            if not r: return {"n": 0, "win_rate": None, "place_rate": None, "win_roi": None, "place_roi": None}
            return {"n": int(r["n"]), "win_rate": r["win_rate"], "place_rate": r["place_rate"], "win_roi": r["win_roi"], "place_roi": r["place_roi"]}
        pr = parent_obj("overall_2024_2025")
        c["metrics"] = {"overall_2024_2025": recent, "2024": y24, "2025": y25, "context_2022_2023": ctx}
        c["parent_metrics"] = {"overall_2024_2025": pr, "2024": parent_obj("year_2024"), "2025": parent_obj("year_2025"), "context_2022_2023": parent_obj("context_2022_2023")}
        c["parent_delta"] = {key: (recent[key] - pr[key]) if recent.get(key) is not None and pr.get(key) is not None else None for key in ("win_rate", "place_rate", "win_roi", "place_roi")}
        c["support_class"] = base.support_class(recent["n"]); c["freshness"] = base._freshness(ctx, y24, y25, recent)
        d = c["parent_delta"]["place_rate"]; roi = recent.get("place_roi")
        c["positive_value_eligible"] = base.positive_value_eligible(recent["n"], roi)
        c["value_strength_band"] = base.value_strength_band(roi)
        parent_ok = pr.get("n", 0) > 0 and pr.get("place_rate") is not None and pr.get("place_roi") is not None
        c["negative_value_eligible"] = base.negative_value_eligible(recent["n"], d, c["parent_delta"].get("place_roi"), parent_ok)
        c["positive_shortlist_status"] = "ELIGIBLE_NO_CLUSTER" if c["positive_value_eligible"] else "BELOW_VALUE_GATE"
        labels = base.performance_labels(d, c["parent_delta"].get("win_rate"))
        if c["positive_value_eligible"]: labels.append("NICHE_VALUE_POSITIVE")
        if c["negative_value_eligible"]: labels.append("NICHE_VALUE_NEGATIVE")
        if ctx["n"] < 5: labels.append("INSUFFICIENT")
        if c["support_class"] == "MICRO" and c["freshness"] in {"CURRENT", "EMERGING"}: labels.append("CURRENT_BUT_LOW_SUPPORT")
        if c["freshness"] in {"EMERGING", "DECAYING"}: labels.append(c["freshness"])
        if recent.get("hit_pop_8_plus", 0) > 0: labels.append("LONGSHOT_EVIDENCE")
        if d is not None and d > 0 and roi is not None and roi < 100: labels.append("SATURATED_OR_PRICED")
        if roi is not None and roi < 80: labels.append("WEAK")
        c["research_labels"] = sorted(set(labels)); c["shortlist_eligible"] = recent["n"] >= 5
        cond = c["conditions"]
        label = "初ダート" if c["template_id"].endswith("FIRST_DIRT") else "初芝" if c["template_id"].endswith("FIRST_TURF") else "初ブリンカー"
        direction = "でプラス" if d is not None and d > 0 else "でマイナス" if d is not None and d < 0 else "の傾向を要確認"
        c["memo"] = f"{cond['sire_name']}産駒は{label}{direction}"
        c.update({"redundancy_cluster_id": None, "representative_candidate_id": c["candidate_id"], "redundancy_status": "NO_SUGGESTED_CLUSTER"})
        result.append(c)

    # Pairwise support/popularity diagnostics are already calculated by the same frozen metric helper.
    return result, {"grouped_candidate_count": len(result), "n_ge_5_count": sum(x["shortlist_eligible"] for x in result),
                    "candidate_count_by_template": {t: sum(x["template_id"] == t for x in result) for t in conditions}}


def write_outputs(out: Path, additions: list[dict[str, Any]], base_summary: dict[str, Any],
                  history_audit: dict[str, Any], warehouse_audit: dict[str, Any], source_commit: str) -> dict[str, Any]:
    import pyarrow as pa
    import pyarrow.parquet as pq

    csv_path = out / "candidate_summary.csv"
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        existing = list(csv.DictReader(f))
    base._write_csv(out / "history_dependent_candidate_summary.csv", additions)
    pq.write_table(pa.Table.from_pylist(additions), out / "history_dependent_candidates.parquet", compression="zstd")
    combined_path = out / "combined_candidate_summary.csv"
    fields = list(existing[0]) if existing else list(additions[0]) if additions else []
    with combined_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader()
        for r in existing: w.writerow(r)
        for r in additions:
            if r["shortlist_eligible"]:
                w.writerow({k: base.canonical_json(v) if isinstance(v, (dict, list)) else v for k, v in r.items()})
    base._write_csv(out / "first_history_audit.csv", [{"audit": "summary", **{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in history_audit.items() if k != "blinker_mismatch_examples"}}])
    base._write_json(out / "first_history_audit.json", history_audit)
    surface_keys = ("sed_rows", "sed_reconciled_events", "sed_duplicate_groups_collapsed", "sed_conflict_groups",
                    "same_day_multi_race_horses_dates", "history_join_counts", "unknown_feature_rows", "identity_coverage")
    blinkers_keys = ("kyi_rows", "kyi_duplicate_groups_collapsed", "kyi_conflict_or_unjoined_groups", "blinker_chronology_count",
                     "blinker_code_1_count", "blinker_code_parity_mismatch_count", "blinker_mismatch_examples",
                     "blinker_code_distribution", "unknown_feature_rows")
    base._write_json(out / "first_surface_audit.json", {k: history_audit[k] for k in surface_keys})
    base._write_json(out / "first_blinker_audit.json", {k: history_audit[k] for k in blinkers_keys})

    family_counts = {fam: dict(info) for fam, info in base_summary["candidate_counts"]["by_family"].items()}
    for family in ("T4", "T5"):
        existing_family = family_counts.get(family, {})
        rows = [x for x in additions if x["family"] == family]
        existing_family["candidate_count_all"] = int(existing_family.get("candidate_count_all", 0)) + len(rows)
        existing_family["candidate_count_n_ge_5"] = int(existing_family.get("candidate_count_n_ge_5", 0)) + sum(x["shortlist_eligible"] for x in rows)
        existing_family["candidate_count_raw_n_lt_5"] = int(existing_family.get("candidate_count_raw_n_lt_5", 0)) + sum(not x["shortlist_eligible"] for x in rows)
        existing_family["positive_value_count"] = int(existing_family.get("positive_value_count", 0)) + sum(x["positive_value_eligible"] for x in rows)
        existing_family["negative_edge_count"] = int(existing_family.get("negative_edge_count", 0)) + sum(x["negative_value_eligible"] for x in rows)
        for field, extra in (("support_classes", Counter(x["support_class"] for x in rows)),
                             ("freshness_counts", Counter(x["freshness"] for x in rows if x["shortlist_eligible"])),
                             ("label_counts", Counter(label for x in rows if x["shortlist_eligible"] for label in x["research_labels"])),
                             ("positive_value_by_support_class", Counter(x["support_class"] for x in rows if x["positive_value_eligible"]))):
            current = existing_family.get(field, {})
            existing_family[field] = dict(Counter(current) + extra)
        existing_family["longshot_evidence_positive_count"] = int(existing_family.get("longshot_evidence_positive_count", 0)) + sum(x["positive_value_eligible"] and "LONGSHOT_EVIDENCE" in x["research_labels"] for x in rows)
        existing_family["positive_value_representatives_status"] = "not recalculated; inventory task retains existing-family representatives and all new candidates"
        existing_family["history_extension_by_template"] = {t: sum(x["template_id"] == t for x in rows) for t in FIRST_SPECS}
        family_counts[family] = existing_family
    base_summary["source_provenance"].update({"warehouse_research_run": WAREHOUSE_RUN, "warehouse_artifact_id": WAREHOUSE_ARTIFACT_ID,
                                              "warehouse_artifact_digest": WAREHOUSE_DIGEST, "instruction_source_commit": "a39cb1372c1446da457fba2f564e3b86bee2364b",
                                              "execution_source_commit": source_commit})
    base_summary["warehouse_verification"] = {k: v for k, v in warehouse_audit.items() if k != "manifest"}
    base_summary["history_derivation_audit"] = history_audit
    base_summary["template_families"].update({"T4_FIRST_DIRT": "PASS", "T4_FIRST_TURF": "PASS", "T5_FIRST_BLINKERS": "PASS_WITH_CODE_PARITY_AUDIT"})
    base_summary["candidate_counts"]["by_family"] = family_counts
    base_summary["candidate_counts"]["history_dependent_n_ge_5"] = sum(x["shortlist_eligible"] for x in additions)
    base_summary["candidate_counts"]["history_dependent_raw_n_lt_5"] = sum(not x["shortlist_eligible"] for x in additions)
    base_summary["candidate_counts"]["unified_n_ge_5_total"] = base_summary["candidate_counts"]["n_ge_5_total"] + sum(x["shortlist_eligible"] for x in additions)
    base_summary["candidate_counts"]["unified_raw_candidate_total"] = base_summary["candidate_counts"]["n_ge_5_total"] + base_summary["candidate_counts"]["n_lt_5_total"] + len(additions)
    base_summary["candidate_counts"]["n_ge_5_total"] = base_summary["candidate_counts"]["unified_n_ge_5_total"]
    base_summary["candidate_counts"]["n_lt_5_total"] += sum(not x["shortlist_eligible"] for x in additions)
    for field, extra in (("by_support_class", Counter(x["support_class"] for x in additions)),
                         ("by_freshness", Counter(x["freshness"] for x in additions if x["shortlist_eligible"])),
                         ("by_label", Counter(label for x in additions if x["shortlist_eligible"] for label in x["research_labels"]))):
        current = base_summary["candidate_counts"][field]
        base_summary["candidate_counts"][field] = dict(Counter(current) + extra)
    base_summary["value_gate"]["positive_value_count"] += sum(x["positive_value_eligible"] for x in additions)
    base_summary["value_gate"]["raw_n_ge_5_preserved"] = base_summary["candidate_counts"]["n_ge_5_total"]
    base_summary["value_gate"]["positive_value_by_family"] = {k: v.get("positive_value_count", 0) for k, v in family_counts.items()}
    base_summary["value_gate"]["negative_edge_count"] += sum(x["negative_value_eligible"] for x in additions)
    base_summary["recommendation"] = "PARTIAL_WITH_TOPOLOGY_BLOCKED"
    base_summary["status"] = "PASS_WITH_TOPOLOGY_BLOCKED"
    base._write_json(out / "combined_candidate_summary.json", {"existing_candidate_count": len(existing), "history_candidate_count": len(additions),
                                                               "combined_candidate_count": len(existing) + len(additions),
                                                               "families": family_counts, "warehouse_verification": base_summary["warehouse_verification"]})
    base._write_json(out / "t1_t6_summary.json", base_summary)
    return base_summary


def render_result(summary: dict[str, Any], additions: list[dict[str, Any]], history: dict[str, Any]) -> str:
    families = summary["candidate_counts"]["by_family"]
    lines = ["# EdgeDB v0.5 First Surface + First Blinkers Full-History Aggregation", "",
             "Status: PARTIAL_WITH_TOPOLOGY_BLOCKED", "",
             "## Input provenance", "",
             f"- Warehouse run {WAREHOUSE_RUN}, artifact ID {WAREHOUSE_ARTIFACT_ID}, digest `{WAREHOUSE_DIGEST}`; generation `{WAREHOUSE_GENERATION}`.",
             "- Feature Mart run 36116777782 / `sha256:19d713da2e6ebf57965de98952fbf18d79f9ddfd5c1996833af3267b1a53f725`.",
             "- Analysis run 36437363166 / `sha256:d159c2fca9959d9b144d55f9b3ba98228158cc38b85fcc730032a53f29252a55`.",
             f"- Instruction commit `a39cb1372c1446da457fba2f564e3b86bee2364b`; execution source commit `{summary['source_provenance'].get('execution_source_commit')}`.", "",
             "## Warehouse verification", "", "- 32/32 annual partitions verified against embedded SHA256 and byte sizes; KYI 16, SED 16; years 2010-2025.",
             f"- SED rows {history['sed_rows']:,}; reconciled events {history['sed_reconciled_events']:,}; duplicate groups collapsed {history['sed_duplicate_groups_collapsed']:,}; conflicting groups {history['sed_conflict_groups']:,}.",
             f"- KYI rows {history['kyi_rows']:,}; duplicate groups collapsed {history['kyi_duplicate_groups_collapsed']:,}; conflict/unjoined groups {history['kyi_conflict_or_unjoined_groups']:,}.",
             "- Canonical identity is blood registration number; target joins cross-check race_key_raw, horse_no, race_date and Feature Mart horse_id. Names are not used.",
             "- Any identity/surface conflict, same-day multi-race ambiguity, or left-boundary first observation remains UNKNOWN.",
             "- 2010-2025 gives at least 12 years of context for 2022-2025 target starts; normal JRA career ages are below that horizon. Identities first observed in 2010 are still explicitly censored to UNKNOWN, covering exceptional longevity or pre-2010 starts.", "",
             "## First surface audit", "",
             f"- FIRST_DIRT target rows: {sum(x['discovery_population_n'] for x in additions if x['template_id']=='T4_SIRE_FIRST_DIRT'):,} aggregate candidate memberships; UNKNOWN history rows: {history['unknown_feature_rows']['first_dirt']:,}.",
             f"- FIRST_TURF target rows: {sum(x['discovery_population_n'] for x in additions if x['template_id']=='T4_SIRE_FIRST_TURF'):,} aggregate candidate memberships; UNKNOWN history rows: {history['unknown_feature_rows']['first_turf']:,}.",
             f"- History join status: `{json.dumps(history['history_join_counts'], ensure_ascii=False, sort_keys=True)}`.",
             "- Flags use strict earlier race_date; the target row is excluded. Same-day duplicate/source rows are collapsed on canonical identity and conflicting/multiple-race dates are UNKNOWN.", "",
             "## First blinkers audit", "",
             f"- Chronology-derived active-first rows: {history['blinker_chronology_count']:,}; code==1 rows: {history['blinker_code_1_count']:,}; parity mismatches: {history['blinker_code_parity_mismatch_count']:,}.",
             f"- Warehouse code distribution: `{json.dumps(history['blinker_code_distribution'], ensure_ascii=False)}`.",
             f"- UNKNOWN blinkers target rows: {history['unknown_feature_rows']['first_blinkers']:,}. Mismatches are UNKNOWN for candidate membership; see `first_history_audit.json` for representative rows.",
             "- Active semantics are codes 1/2/3; blank and 0 mean no active blinkers on that start. Code 2 is re-wear and is not accepted as first use when codebook and chronology disagree.", "",
             "## Unified candidate counts", "", "| Family | All candidates | n>=5 | Positive Value | Negative Edge | Support classes | Freshness | LONGSHOT_EVIDENCE |", "|---|---:|---:|---:|---:|---|---|---:|"]
    for fam, row in sorted(families.items()):
        support = json.dumps(row.get("support_classes", {}), ensure_ascii=False, sort_keys=True)
        freshness = json.dumps(row.get("freshness_counts", {}), ensure_ascii=False, sort_keys=True)
        longshot = row.get("label_counts", {}).get("LONGSHOT_EVIDENCE", 0)
        lines.append(f"| {fam} | {row.get('candidate_count_all', 0)} | {row.get('candidate_count_n_ge_5', 0)} | {row.get('positive_value_count', 0)} | {row.get('negative_edge_count', 0)} | `{support}` | `{freshness}` | {longshot} |")
    lines.extend(["", f"Unified inventory: {summary['candidate_counts']['unified_raw_candidate_total']:,} raw candidates; {summary['candidate_counts']['unified_n_ge_5_total']:,} with n>=5.",
                  "Positive Value remains exactly `n >= 5 AND combined 2024-2025 place ROI >= 100%`; no threshold or support floor changed. No popularity, payout, or odds field defines candidate membership.", "",
                  "## History-dependent family counts", "", "| Template | Candidates | n>=5 | Positive Value | Negative Edge |", "|---|---:|---:|---:|---:|"])
    for t in FIRST_SPECS:
        rows = [x for x in additions if x["template_id"] == t]
        lines.append(f"| {t} | {len(rows)} | {sum(x['shortlist_eligible'] for x in rows)} | {sum(x['positive_value_eligible'] for x in rows)} | {sum(x['negative_value_eligible'] for x in rows)} |")
    lines += ["", "## Representative examples", ""]
    for template in FIRST_SPECS:
        rows = sorted((x for x in additions if x["template_id"] == template and x["positive_value_eligible"]), key=lambda x: (-x["metrics"]["overall_2024_2025"]["n"], x["candidate_id"]))
        if rows:
            c = rows[0]; m = c["metrics"]["overall_2024_2025"]
            lines.append(f"- {template}: {c['candidate_id']} — {c['memo']} (n={m['n']}, places={m['places']}, place ROI={m['place_roi']:.1f}%).")
        else: lines.append(f"- {template}: no positive Value example under the frozen gate.")
    micro = next((x for x in additions if x["support_class"] == "MICRO" and x["positive_value_eligible"]), None)
    lines.append(f"- MICRO longshot: {micro['candidate_id']} ({micro['memo']}, place ROI {micro['metrics']['overall_2024_2025']['place_roi']:.1f}%)." if micro else "- MICRO longshot: no qualifying example in the history-dependent families.")
    negative = next((x for x in additions if x["negative_value_eligible"]), None)
    lines.append(f"- Negative Edge: {negative['candidate_id']} ({negative['memo']})." if negative else "- Negative Edge: no history-dependent example met the unchanged conservative gate.")
    lines += ["", "## Existing-family parity", "", "PASS: the original aggregation ran unchanged on the same Feature Mart and Analysis artifacts; its candidate file and summary counts were preserved before appending history-dependent rows. The unified table contains those original rows plus the three added template families.", "",
              "## Recommendation", "", "`PARTIAL_WITH_TOPOLOGY_BLOCKED`. The original T1-T6 families plus FIRST_DIRT/FIRST_TURF/FIRST_BLINKERS are now on the same frozen rule set. Course topology remains blocked because no authoritative turn-count crosswalk exists. Production impact NONE.", ""]
    return "\n".join(lines)


def compare_baseline(current_csv: Path, baseline_root: Path) -> dict[str, Any]:
    baseline = baseline_root / "output" / "candidate_summary.csv"
    if not baseline.is_file():
        raise ValueError("merged PR #1871 baseline candidate_summary.csv is absent")
    def load(path: Path) -> dict[str, dict[str, Any]]:
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        return {r["candidate_id"]: r for r in rows}
    old, new = load(baseline), load(current_csv)
    if old.keys() != new.keys():
        raise ValueError(f"existing-family candidate ID parity failed: baseline={len(old)} current={len(new)}")
    compared = 0
    for cid, prior in old.items():
        now = new[cid]
        pm, nm = json.loads(prior["metrics"]), json.loads(now["metrics"])
        p = pm["overall_2024_2025"]; n = nm["overall_2024_2025"]
        if int(p["n"]) != int(n["n"]) or abs(float(p["place_roi"]) - float(n["place_roi"])) > 1e-9:
            raise ValueError(f"existing-family metric parity failed for {cid}")
        for key in ("positive_value_eligible", "negative_value_eligible"):
            if prior[key].lower() != now[key].lower():
                raise ValueError(f"existing-family eligibility parity failed for {cid}: {key}")
        compared += 1
    return {"status": "PASS", "baseline_run_id": 37590302135, "baseline_artifact": "data-storage-fallback-37590302135",
            "candidate_ids_compared": compared, "metrics_compared": ["n", "place_roi", "positive_value_eligible", "negative_value_eligible"]}


def run(args: argparse.Namespace) -> dict[str, Any]:
    import duckdb
    from jrdb_edge_feature_mart_parquet import resolve_current as resolve_feature

    warehouse_audit = verify_warehouse(args.warehouse_input)
    out = args.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    base_summary = base.run(feature_input=args.feature_input, analysis_input=args.analysis_input, out=out,
        feature_artifact_digest=args.feature_artifact_digest, analysis_artifact_digest=args.analysis_artifact_digest,
        feature_run=args.feature_run, analysis_run=args.analysis_run, source_commit=args.source_commit)
    parity = compare_baseline(out / "candidate_summary.csv", args.baseline_input)
    freport = resolve_feature(args.feature_input.resolve() / "canonical/feature_mart/v0.2")
    con = duckdb.connect()
    try:
        with tempfile.TemporaryDirectory(prefix="v05-first-history-") as td:
            enriched = Path(td) / "feature_history.parquet"
            history = build_history_features(con, args.warehouse_input.resolve(), Path(freport["fact_path"]), enriched)
            additions, _ = assemble_new_candidates(con, enriched, out)
            summary = write_outputs(out, additions, base_summary, history, warehouse_audit, args.source_commit)
            summary["existing_family_parity"] = parity
            base._write_json(out / "existing_family_parity_audit.json", parity)
            base._write_json(out / "t1_t6_summary.json", summary)
            report = render_result(summary, additions, history)
            (out / "first_surface_and_blinker_full_history_result.md").write_text(report, encoding="utf-8")
            (out / "unified_candidate_family_counts.csv").write_text("family,candidate_count_all,n_ge_5,positive_value,negative_edge\n" + "".join(
                f"{fam},{v.get('candidate_count_all',0)},{v.get('candidate_count_n_ge_5',0)},{v.get('positive_value_count',0)},{v.get('negative_edge_count',0)}\n"
                for fam, v in sorted(summary["candidate_counts"]["by_family"].items())), encoding="utf-8")
            return summary
    finally:
        con.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--feature-input", type=Path, required=True); p.add_argument("--analysis-input", type=Path, required=True)
    p.add_argument("--warehouse-input", type=Path, required=True); p.add_argument("--baseline-input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--feature-run", type=int, required=True); p.add_argument("--feature-artifact-digest", required=True)
    p.add_argument("--analysis-run", type=int, required=True); p.add_argument("--analysis-artifact-digest", required=True)
    p.add_argument("--source-commit", required=True)
    args = p.parse_args(); result = run(args)
    print(json.dumps({"status": result["status"], "recommendation": result["recommendation"],
                      "unified_n_ge_5": result["candidate_counts"]["unified_n_ge_5_total"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
