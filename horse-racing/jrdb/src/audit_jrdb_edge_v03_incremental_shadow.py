#!/usr/bin/env python3
"""JRDB Edge v0.3 shadow parent-relative metric audit from normalized Warehouse.

This is a research-only Stage-B audit. It reads the accepted immutable JRDB
Warehouse and the frozen v0.2 STANDARD serving catalog, but it does not mutate
Registry status, thresholds, matcher semantics, or production serving.

For selected semantic hierarchies it compares each served child condition with
its nearest parent-complement, so broad/lower-order effects are not counted as
independent niche evidence merely because the child is more specific.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION = "0.1.0"
TARGET_TEMPLATES = {
    "COURSE_FRAME_V1",
    "COURSE_EXACT_FRAME_V2",
    "SIRE_SURFACE_DISTANCE_V1",
    "SIRE_TURN_DISTANCE_V1",
    "SIRE_VENUE_SURFACE_DISTANCE_V2",
}
PM = {"POSITIVE", "NEGATIVE"}


class ShadowAuditError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ShadowAuditError(f"JSON object required: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ShadowAuditError(f"{path}:{number}: object required")
        rows.append(value)
    return rows


def _metric(n: int, hits: int, payout: float) -> dict[str, Any]:
    return {
        "n": int(n),
        "place_hits": int(hits),
        "place_rate": (hits / n) if n else None,
        "place_roi": (payout / (100.0 * n)) if n else None,
        "place_payout_sum": float(payout),
    }


def _residual(child: Mapping[str, Any], parent: Mapping[str, Any]) -> dict[str, Any]:
    child_n = int(child["n"])
    parent_n = int(parent["n"])
    complement_n = parent_n - child_n
    if complement_n < 0:
        raise ShadowAuditError("child n exceeds parent n")
    complement_hits = int(parent["place_hits"]) - int(child["place_hits"])
    complement_payout = float(parent["place_payout_sum"]) - float(child["place_payout_sum"])
    if complement_hits < 0 or complement_payout < -1e-9:
        raise ShadowAuditError("child outcomes exceed parent outcomes")
    complement = _metric(complement_n, complement_hits, max(0.0, complement_payout))

    child_rate = child.get("place_rate")
    comp_rate = complement.get("place_rate")
    child_roi = child.get("place_roi")
    comp_roi = complement.get("place_roi")

    rate_diff = (
        float(child_rate) - float(comp_rate)
        if child_rate is not None and comp_rate is not None
        else None
    )
    rate_ratio = (
        float(child_rate) / float(comp_rate)
        if child_rate is not None and comp_rate not in (None, 0)
        else None
    )
    roi_diff = (
        float(child_roi) - float(comp_roi)
        if child_roi is not None and comp_roi is not None
        else None
    )
    roi_ratio = (
        float(child_roi) / float(comp_roi)
        if child_roi is not None and comp_roi not in (None, 0)
        else None
    )
    return {
        "child": dict(child),
        "parent": dict(parent),
        "parent_complement": complement,
        "incremental_place_rate_diff": rate_diff,
        "incremental_place_rate_ratio": rate_ratio,
        "incremental_place_roi_diff": roi_diff,
        "incremental_place_roi_ratio": roi_ratio,
        "incremental_performance_direction": (
            "POSITIVE" if rate_diff is not None and rate_diff > 0
            else "NEGATIVE" if rate_diff is not None and rate_diff < 0
            else "NEUTRAL" if rate_diff == 0
            else "UNASSESSED"
        ),
        "incremental_value_direction": (
            "POSITIVE" if roi_diff is not None and roi_diff > 0
            else "NEGATIVE" if roi_diff is not None and roi_diff < 0
            else "NEUTRAL" if roi_diff == 0
            else "UNASSESSED"
        ),
    }


def _frame_zone(frame_no: Any) -> str | None:
    try:
        value = int(frame_no)
    except (TypeError, ValueError):
        return None
    if not 1 <= value <= 8:
        return None
    if value <= 3:
        return "INNER"
    if value <= 6:
        return "MIDDLE"
    return "OUTER"


def _condition_values(edge: Mapping[str, Any]) -> dict[str, Any]:
    conditions = edge.get("conditions")
    if not isinstance(conditions, Mapping):
        return {}
    out: dict[str, Any] = {}
    for bucket in ("anchor", "modifiers"):
        values = conditions.get(bucket)
        if isinstance(values, Mapping):
            out.update({str(key): value for key, value in values.items()})
    return out


def _template(edge: Mapping[str, Any]) -> str:
    conditions = edge.get("conditions")
    return str(conditions.get("template_id") or "") if isinstance(conditions, Mapping) else ""


def _pm_served_edges(path: Path) -> list[dict[str, Any]]:
    rows = []
    for edge in _load_jsonl(path):
        template = _template(edge)
        if template not in TARGET_TEMPLATES:
            continue
        signal = str(edge.get("performance_signal") or "NEUTRAL").upper()
        level = str(edge.get("performance_evidence_level") or "NONE").upper()
        if signal not in PM:
            continue
        if level not in {"CONFIRMED", "SUGGESTIVE"}:
            continue
        rows.append(edge)
    return rows


def _find_assets(
    manifest: Mapping[str, Any],
    family_roots: Mapping[str, Path],
    families: Iterable[str],
) -> dict[str, list[Path]]:
    wanted = {value.lower() for value in families}
    by_name: dict[str, list[Path]] = {}
    for family, root in family_roots.items():
        found = list(Path(root).rglob("*.parquet"))
        by_name[family.lower()] = found

    output: dict[str, list[Path]] = {family: [] for family in wanted}
    for asset in manifest.get("assets") or []:
        if not isinstance(asset, Mapping):
            continue
        family = str(asset.get("family") or "").lower()
        if family not in wanted:
            continue
        expected_sha = str(asset.get("sha256") or "")
        expected_size = int(asset.get("size_bytes") or 0)
        candidates = [
            path
            for path in by_name.get(family, [])
            if path.name == f"{expected_sha}.parquet"
        ]
        if len(candidates) != 1:
            raise ShadowAuditError(
                f"{family}/{asset.get('year')}: expected one local asset {expected_sha}.parquet, "
                f"found {len(candidates)}"
            )
        path = candidates[0]
        if path.stat().st_size != expected_size:
            raise ShadowAuditError(f"size mismatch: {path}")
        if _sha256(path) != expected_sha:
            raise ShadowAuditError(f"SHA mismatch: {path}")
        output[family].append(path)

    for family in wanted:
        if len(output[family]) != 16:
            raise ShadowAuditError(
                f"{family}: expected 16 accepted year assets, got {len(output[family])}"
            )
    return output


def _sql_file_list(paths: Iterable[Path]) -> str:
    return "[" + ",".join(
        "'" + str(path.resolve()).replace("'", "''") + "'" for path in paths
    ) + "]"


def _create_fact_view(connection: Any, assets: Mapping[str, list[Path]]) -> None:
    for family in ("bac", "kyi", "sed", "ukc"):
        connection.execute(
            f"CREATE VIEW {family}_raw AS SELECT * FROM "
            f"read_parquet({_sql_file_list(assets[family])}, union_by_name=true)"
        )

    connection.execute(
        """
        CREATE VIEW bac AS
        SELECT * EXCLUDE(rn) FROM (
          SELECT *,
            row_number() OVER (
              PARTITION BY race_key_raw
              ORDER BY source_member, source_record_ordinal
            ) AS rn
          FROM bac_raw
        ) WHERE rn=1
        """
    )
    connection.execute(
        """
        CREATE VIEW kyi AS
        SELECT * EXCLUDE(rn) FROM (
          SELECT *,
            row_number() OVER (
              PARTITION BY race_key_raw, horse_no
              ORDER BY source_member, source_record_ordinal
            ) AS rn
          FROM kyi_raw
        ) WHERE rn=1
        """
    )
    connection.execute(
        """
        CREATE VIEW sed AS
        SELECT * EXCLUDE(rn) FROM (
          SELECT *,
            row_number() OVER (
              PARTITION BY race_key_raw, horse_no
              ORDER BY source_member, source_record_ordinal
            ) AS rn
          FROM sed_raw
        ) WHERE rn=1
        """
    )
    connection.execute(
        """
        CREATE VIEW ukc AS
        SELECT * EXCLUDE(rn) FROM (
          SELECT *,
            row_number() OVER (
              PARTITION BY horse_id, COALESCE(data_date_iso, data_date)
              ORDER BY source_member, source_record_ordinal
            ) AS rn
          FROM ukc_raw
        ) WHERE rn=1
        """
    )

    connection.execute(
        """
        CREATE TEMP TABLE edge_v03_fact AS
        WITH runners AS (
          SELECT
            b.race_key_raw AS race_key,
            CAST(k.horse_no AS INTEGER) AS horse_no,
            b.race_date,
            b.venue_code,
            CAST(b.distance_raw AS INTEGER) AS distance_m,
            b.surface_code,
            b.turn_code,
            CAST(k.frame_no AS INTEGER) AS frame_no,
            CASE
              WHEN CAST(k.frame_no AS INTEGER) BETWEEN 1 AND 3 THEN 'INNER'
              WHEN CAST(k.frame_no AS INTEGER) BETWEEN 4 AND 6 THEN 'MIDDLE'
              WHEN CAST(k.frame_no AS INTEGER) BETWEEN 7 AND 8 THEN 'OUTER'
              ELSE NULL
            END AS frame_zone,
            k.blood_registration_no AS horse_id,
            CAST(s.finish AS INTEGER) AS finish,
            COALESCE(s.abnormal_code,'') AS abnormal_code,
            CAST(COALESCE(s.place_payout,0) AS DOUBLE) AS place_payout
          FROM bac b
          JOIN kyi k ON k.race_key_raw=b.race_key_raw
          JOIN sed s
            ON s.race_key_raw=k.race_key_raw
           AND CAST(s.horse_no AS INTEGER)=CAST(k.horse_no AS INTEGER)
          WHERE b.surface_code IN ('1','2')
        )
        SELECT
          r.*,
          hp.sire_name,
          CASE WHEN r.place_payout > 0 THEN 1 ELSE 0 END AS place_hit
        FROM runners r
        ASOF LEFT JOIN (
          SELECT
            horse_id,
            COALESCE(data_date_iso, data_date) AS profile_date,
            sire_name
          FROM ukc
          WHERE horse_id IS NOT NULL
            AND COALESCE(data_date_iso, data_date) IS NOT NULL
        ) hp
          ON r.horse_id=hp.horse_id
         AND r.race_date>=hp.profile_date
        WHERE r.finish IS NOT NULL
          AND trim(COALESCE(r.abnormal_code,'')) IN ('','0')
        """
    )


def _rows_to_metric_dict(
    rows: Iterable[tuple[Any, ...]],
    key_size: int,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    output: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[:key_size])
        output[key] = _metric(int(row[key_size]), int(row[key_size + 1]), float(row[key_size + 2]))
    return output


def _aggregates(connection: Any) -> dict[str, dict[tuple[Any, ...], dict[str, Any]]]:
    metric = "COUNT(*), SUM(place_hit), SUM(place_payout)"
    queries = {
        "course_zone": (
            f"SELECT venue_code,surface_code,distance_m,frame_zone,{metric} "
            "FROM edge_v03_fact WHERE frame_zone IS NOT NULL "
            "GROUP BY 1,2,3,4",
            4,
        ),
        "course_exact": (
            f"SELECT venue_code,surface_code,distance_m,frame_zone,frame_no,{metric} "
            "FROM edge_v03_fact WHERE frame_zone IS NOT NULL AND frame_no IS NOT NULL "
            "GROUP BY 1,2,3,4,5",
            5,
        ),
        "sire_distance": (
            f"SELECT sire_name,distance_m,{metric} "
            "FROM edge_v03_fact WHERE sire_name IS NOT NULL AND trim(sire_name)<>'' "
            "GROUP BY 1,2",
            2,
        ),
        "sire_surface": (
            f"SELECT sire_name,distance_m,surface_code,{metric} "
            "FROM edge_v03_fact WHERE sire_name IS NOT NULL AND trim(sire_name)<>'' "
            "GROUP BY 1,2,3",
            3,
        ),
        "sire_turn": (
            f"SELECT sire_name,distance_m,turn_code,{metric} "
            "FROM edge_v03_fact WHERE sire_name IS NOT NULL AND trim(sire_name)<>'' "
            "AND turn_code IS NOT NULL AND trim(turn_code)<>'' GROUP BY 1,2,3",
            3,
        ),
        "sire_venue_surface": (
            f"SELECT sire_name,distance_m,surface_code,venue_code,{metric} "
            "FROM edge_v03_fact WHERE sire_name IS NOT NULL AND trim(sire_name)<>'' "
            "GROUP BY 1,2,3,4",
            4,
        ),
    }
    return {
        name: _rows_to_metric_dict(connection.execute(sql).fetchall(), key_size)
        for name, (sql, key_size) in queries.items()
    }


def _key_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _key_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _evaluate_edge(
    edge: Mapping[str, Any],
    agg: Mapping[str, dict[tuple[Any, ...], dict[str, Any]]],
) -> dict[str, Any]:
    template = _template(edge)
    c = _condition_values(edge)
    child: dict[str, Any] | None = None
    parent: dict[str, Any] | None = None
    hierarchy = ""

    if template == "COURSE_FRAME_V1":
        key = (_key_text(c.get("venue_code")), _key_text(c.get("surface_code")),
               _key_int(c.get("distance_m")), _key_text(c.get("frame_zone")))
        child = agg["course_zone"].get(key)
        parent = None
        hierarchy = "COURSE_FRAME_CONTEXT"
    elif template == "COURSE_EXACT_FRAME_V2":
        zone = _frame_zone(c.get("frame_no"))
        base = (_key_text(c.get("venue_code")), _key_text(c.get("surface_code")),
                _key_int(c.get("distance_m")), zone)
        child = agg["course_exact"].get(base + (_key_int(c.get("frame_no")),))
        parent = agg["course_zone"].get(base)
        hierarchy = "COURSE_EXACT_WITHIN_ZONE"
    elif template == "SIRE_SURFACE_DISTANCE_V1":
        base = (_key_text(c.get("sire_name")), _key_int(c.get("distance_m")))
        child = agg["sire_surface"].get(base + (_key_text(c.get("surface_code")),))
        parent = agg["sire_distance"].get(base)
        hierarchy = "SIRE_SURFACE_WITHIN_DISTANCE"
    elif template == "SIRE_TURN_DISTANCE_V1":
        base = (_key_text(c.get("sire_name")), _key_int(c.get("distance_m")))
        child = agg["sire_turn"].get(base + (_key_text(c.get("turn_code")),))
        parent = agg["sire_distance"].get(base)
        hierarchy = "SIRE_TURN_WITHIN_DISTANCE"
    elif template == "SIRE_VENUE_SURFACE_DISTANCE_V2":
        base = (_key_text(c.get("sire_name")), _key_int(c.get("distance_m")),
                _key_text(c.get("surface_code")))
        child = agg["sire_venue_surface"].get(base + (_key_text(c.get("venue_code")),))
        parent = agg["sire_surface"].get(base)
        hierarchy = "SIRE_VENUE_WITHIN_SURFACE_DISTANCE"
    else:
        raise ShadowAuditError(f"unexpected template: {template}")

    payload = {
        "edge_id": edge.get("edge_id"),
        "template_id": template,
        "hierarchy": hierarchy,
        "current_performance_signal": edge.get("performance_signal"),
        "current_performance_evidence_level": edge.get("performance_evidence_level"),
        "current_value_signal": edge.get("value_signal"),
        "current_value_evidence_level": edge.get("value_evidence_level"),
        "conditions": edge.get("conditions"),
    }
    if child is None:
        return {**payload, "shadow_class": "INSUFFICIENT", "reason": "CHILD_GROUP_NOT_FOUND"}
    if template == "COURSE_FRAME_V1":
        return {
            **payload,
            "shadow_class": "CONTEXT_ONLY",
            "reason": "LOWER_ORDER_CONTEXT",
            "metrics": {"child": child},
        }
    if parent is None:
        return {**payload, "shadow_class": "INSUFFICIENT", "reason": "PARENT_GROUP_NOT_FOUND"}

    residual = _residual(child, parent)
    if residual["parent_complement"]["n"] <= 0:
        return {
            **payload,
            "shadow_class": "INSUFFICIENT",
            "reason": "EMPTY_PARENT_COMPLEMENT",
            "metrics": residual,
        }
    perf = residual["incremental_performance_direction"]
    value = residual["incremental_value_direction"]
    return {
        **payload,
        "shadow_class": "RAW_INCREMENTAL_METRIC",
        "reason": "THRESHOLD_NOT_YET_APPLIED",
        "metrics": residual,
        "direction_alignment": {
            "performance_matches_current": perf == str(edge.get("performance_signal") or "").upper(),
            "value_matches_current": (
                value == str(edge.get("value_signal") or "").upper()
                if str(edge.get("value_signal") or "").upper() in PM
                else None
            ),
        },
    }


def run(
    *,
    warehouse_manifest: Path,
    bac_root: Path,
    kyi_root: Path,
    sed_root: Path,
    ukc_root: Path,
    serving_catalog: Path,
    output_jsonl: Path,
    output_summary: Path,
) -> dict[str, Any]:
    manifest = _load_json(warehouse_manifest)
    if manifest.get("status") != "PASS":
        raise ShadowAuditError("Warehouse manifest is not PASS")
    if manifest.get("generation_id") != "jrdb_normalized_warehouse_v1_2010_2025_g20260921":
        raise ShadowAuditError(f"unexpected Warehouse generation: {manifest.get('generation_id')}")

    assets = _find_assets(
        manifest,
        {"bac": bac_root, "kyi": kyi_root, "sed": sed_root, "ukc": ukc_root},
        ("bac", "kyi", "sed", "ukc"),
    )
    edges = _pm_served_edges(serving_catalog)

    try:
        import duckdb
    except ImportError as exc:
        raise ShadowAuditError("duckdb is required") from exc

    connection = duckdb.connect(":memory:")
    try:
        _create_fact_view(connection, assets)
        fact_count = int(connection.execute("SELECT COUNT(*) FROM edge_v03_fact").fetchone()[0])
        fact_min, fact_max = connection.execute(
            "SELECT MIN(race_date),MAX(race_date) FROM edge_v03_fact"
        ).fetchone()
        agg = _aggregates(connection)
    finally:
        connection.close()

    rows = [_evaluate_edge(edge, agg) for edge in edges]
    with output_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    template_counts = Counter(str(row["template_id"]) for row in rows)
    classes = Counter(str(row["shadow_class"]) for row in rows)
    align = Counter()
    sample_bins = Counter()
    for row in rows:
        metrics = row.get("metrics")
        if not isinstance(metrics, Mapping):
            continue
        comp = metrics.get("parent_complement")
        if isinstance(comp, Mapping):
            n = int(comp.get("n") or 0)
            sample_bins[
                "0" if n == 0 else "<20" if n < 20 else "20-49" if n < 50 else
                "50-99" if n < 100 else "100+"
            ] += 1
        direction = row.get("direction_alignment")
        if isinstance(direction, Mapping):
            align[
                "performance_same" if direction.get("performance_matches_current")
                else "performance_opposite"
            ] += 1

    summary = {
        "status": "PASS",
        "version": VERSION,
        "mode": "SHADOW_ONLY",
        "warehouse_generation_id": manifest.get("generation_id"),
        "warehouse_manifest_sha256": _sha256(warehouse_manifest),
        "serving_catalog_sha256": _sha256(serving_catalog),
        "fact_rows": fact_count,
        "fact_period_from": fact_min,
        "fact_period_to": fact_max,
        "served_performance_edges_evaluated": len(rows),
        "template_counts": dict(sorted(template_counts.items())),
        "shadow_class_counts": dict(sorted(classes.items())),
        "parent_complement_sample_bins": dict(sorted(sample_bins.items())),
        "raw_incremental_performance_alignment": dict(sorted(align.items())),
        "threshold_policy": "NOT_APPLIED",
        "note": (
            "Stage-B1 raw parent-relative metrics only. No q/bootstrap/temporal gate, "
            "no v0.3 promotion, and no production serving change."
        ),
    }
    output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warehouse-manifest", type=Path, required=True)
    parser.add_argument("--bac-root", type=Path, required=True)
    parser.add_argument("--kyi-root", type=Path, required=True)
    parser.add_argument("--sed-root", type=Path, required=True)
    parser.add_argument("--ukc-root", type=Path, required=True)
    parser.add_argument("--serving-catalog", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        warehouse_manifest=args.warehouse_manifest,
        bac_root=args.bac_root,
        kyi_root=args.kyi_root,
        sed_root=args.sed_root,
        ukc_root=args.ukc_root,
        serving_catalog=args.serving_catalog,
        output_jsonl=args.output_jsonl,
        output_summary=args.output_summary,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
