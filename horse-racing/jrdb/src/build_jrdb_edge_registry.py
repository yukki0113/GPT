#!/usr/bin/env python3
"""Build the persistent JRDB Edge Registry from validated discovery candidates."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from jrdb_edge_temporal_validator import validate_candidate
from jrdb_edge_validation import load_policy_catalog

VERSION = "0.1.0"
DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_edge_registry_schema_v0_1.sql"


def _edge_id(candidate_id: str) -> str:
    if candidate_id.startswith("EDGE-CAND-"):
        return candidate_id.replace("EDGE-CAND-", "EDGE-", 1)
    return "EDGE-" + hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:20].upper()


def _anchor_parts(candidate: Mapping[str, Any]) -> tuple[str, str]:
    anchor = candidate["anchor"]
    anchor_id = json.dumps(anchor, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    anchor_name = " / ".join(str(value) for value in anchor.values())
    return anchor_id, anchor_name


def _display_text(candidate: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    anchor = candidate["anchor"]
    modifiers = candidate["modifiers"]
    if candidate["anchor_type"] == "sire" and anchor.get("sire_name"):
        head = f"{anchor['sire_name']}産駒"
    elif candidate["anchor_type"] == "sire_line" and anchor.get("sire_line_code"):
        head = f"系統{anchor['sire_line_code']}"
    else:
        head = " / ".join(f"{key}={value}" for key, value in anchor.items())
    tail = ", ".join(f"{key}={value}" for key, value in modifiers.items())
    prefix = "＋" if result["polarity"] == "POSITIVE" else ("－" if result["polarity"] == "NEGATIVE" else "±")
    return f"{prefix} {head}" + (f" / {tail}" if tail else "")


def _strength_score(result: Mapping[str, Any]) -> float | None:
    metrics = result["overall"]
    components = []
    for key in ("performance_lift", "place_roi_vs_baseline"):
        value = metrics.get(key)
        if value is not None:
            components.append(abs(float(value) - 1.0))
    if not components:
        return None
    return min(100.0, round(max(components) * 1000.0, 2))


def _confidence_band(result: Mapping[str, Any]) -> str:
    if result["status"] == "PROVISIONAL":
        return "P"
    if result["status"] == "WATCH":
        return "W"
    if result["status"] == "DECAYING":
        return "D"
    if result["status"] != "ACTIVE":
        return "R"
    sample_n = int(result["overall"]["sample_n"])
    return "A" if sample_n >= 240 else "B"


def _prefilter_candidate(candidate: Mapping[str, Any], policy: Mapping[str, Any]) -> bool:
    minimum_n = int(policy["watch_min_n"]) if policy["validation_class"] == "EMERGING" else int(policy["min_total_n"])
    if int(candidate.get("sample_n", 0)) < minimum_n:
        return False
    if int(candidate.get("unique_horses", 0)) < int(policy.get("min_unique_horses", 0)):
        return False
    if int(candidate.get("unique_races", 0)) < int(policy.get("min_unique_races", 0)):
        return False
    approx = candidate.get("largest_return_share_approx")
    if approx is not None and float(approx) > float(policy.get("max_single_return_share", 1.0)):
        return False
    return True


def _decision_for_event(status: str) -> str:
    return {
        "ACTIVE": "ACTIVATE",
        "PROVISIONAL": "PROVISIONAL",
        "WATCH": "WATCH",
        "DECAYING": "DECAY",
        "REJECTED": "REJECT",
    }[status]


def build_registry(
    mart_path: str | Path,
    candidates: list[Mapping[str, Any]],
    output_path: str | Path,
    schema_path: str | Path,
    policy_catalog: Mapping[str, Any],
    registry_version: str,
    *,
    source_scope: str = "jrdb_jra_history",
    source_manifest: Mapping[str, Any] | None = None,
    include_rejected: bool = False,
) -> dict[str, Any]:
    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite Edge Registry: {output}")
    connection = sqlite3.connect(output)
    now = datetime.now(timezone.utc).isoformat()
    try:
        connection.executescript(Path(schema_path).read_text(encoding="utf-8"))
        connection.execute(
            """INSERT INTO edge_registry_meta(
              registry_version,policy_version,generated_at,source_scope,source_manifest_json,status,message
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                registry_version,
                policy_catalog.get("policy_version", "unknown"),
                now,
                source_scope,
                json.dumps(source_manifest, ensure_ascii=False, sort_keys=True) if source_manifest else None,
                "BUILDING",
                None,
            ),
        )

        counts: dict[str, int] = {}
        validation_rows: list[dict[str, Any]] = []
        stored_edges = 0
        prefiltered_out = 0
        for candidate in candidates:
            policy = policy_catalog["policies"][candidate["policy_id"]]
            if not _prefilter_candidate(candidate, policy):
                prefiltered_out += 1
                continue
            result = validate_candidate(mart_path, candidate, policy_catalog)
            validation_rows.append({**result, "candidate": dict(candidate)})
            status = result["status"]
            counts[status] = counts.get(status, 0) + 1
            if status == "REJECTED" and not include_rejected:
                continue

            edge_id = _edge_id(candidate["candidate_id"])
            anchor_id, anchor_name = _anchor_parts(candidate)
            last_validated_at = candidate["as_of_date"]
            last_date = date.fromisoformat(last_validated_at)
            next_review_at = (last_date + timedelta(days=int(policy["review_days"]))).isoformat()
            expires_at = None
            if policy.get("expiry_days") is not None:
                expires_at = (last_date + timedelta(days=int(policy["expiry_days"]))).isoformat()
            conditions = {
                "template_id": candidate["template_id"],
                "template_version": candidate["template_version"],
                "anchor": candidate["anchor"],
                "modifiers": candidate["modifiers"],
                "baseline": candidate["baseline"],
            }
            connection.execute(
                """INSERT INTO edge_definition(
                  edge_id,registry_version,family,anchor_type,anchor_id,anchor_name,
                  validation_class,policy_id,polarity,performance_signal,value_signal,status,
                  conditions_json,display_text,edge_cluster,parent_edge_id,specificity,
                  first_observed_date,last_observed_date,last_validated_at,next_review_at,expires_at,
                  strength_score,confidence_band,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    edge_id,
                    registry_version,
                    candidate["family"],
                    candidate["anchor_type"],
                    anchor_id,
                    anchor_name,
                    result["validation_class"],
                    candidate["policy_id"],
                    result["polarity"],
                    result["performance_signal"],
                    result["value_signal"],
                    status,
                    json.dumps(conditions, ensure_ascii=False, sort_keys=True),
                    _display_text(candidate, result),
                    candidate["template_id"],
                    None,
                    len(candidate["modifiers"]),
                    candidate["first_observed_date"],
                    candidate["last_observed_date"],
                    last_validated_at,
                    next_review_at,
                    expires_at,
                    _strength_score(result),
                    _confidence_band(result),
                    now,
                    now,
                ),
            )

            snapshots = [("ALL", "all", result["overall"])]
            slice_kind = (
                "SEGMENT"
                if result["validation_class"] in {"STRUCTURAL", "LIFECYCLE"}
                else "ROLLING_WINDOW"
            )
            snapshots.extend((slice_kind, item["slice_label"], item) for item in result["slices"])
            for kind, label, metrics in snapshots:
                snapshot_id = hashlib.sha256(
                    f"{edge_id}|{last_validated_at}|{kind}|{label}".encode("utf-8")
                ).hexdigest()[:20]
                direction = (
                    1 if result["polarity"] == "POSITIVE" else (-1 if result["polarity"] == "NEGATIVE" else 0)
                )
                connection.execute(
                    """INSERT INTO edge_metric_snapshot(
                      edge_id,snapshot_id,as_of_date,slice_kind,slice_label,period_start,period_end,
                      sample_n,unique_horses,unique_races,win_rate,place_rate,win_roi,place_roi,
                      baseline_win_rate,baseline_place_rate,performance_lift,largest_return_share,
                      top3_return_share,largest_horse_sample_share,direction,metrics_json
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        edge_id,
                        snapshot_id,
                        last_validated_at,
                        kind,
                        label,
                        metrics.get("period_start"),
                        metrics.get("period_end"),
                        metrics["sample_n"],
                        metrics.get("unique_horses"),
                        metrics.get("unique_races"),
                        metrics.get("win_rate"),
                        metrics.get("place_rate"),
                        metrics.get("win_roi"),
                        metrics.get("place_roi"),
                        None,
                        metrics.get("baseline_place_rate"),
                        metrics.get("performance_lift"),
                        metrics.get("largest_return_share"),
                        metrics.get("top3_return_share"),
                        metrics.get("largest_horse_sample_share"),
                        direction,
                        json.dumps(metrics, ensure_ascii=False, sort_keys=True),
                    ),
                )
            connection.execute(
                """INSERT INTO edge_validation_event(
                  edge_id,evaluated_at,policy_id,policy_version,decision,failure_reason,evidence_json
                ) VALUES(?,?,?,?,?,?,?)""",
                (
                    edge_id,
                    now,
                    candidate["policy_id"],
                    policy_catalog.get("policy_version", "unknown"),
                    _decision_for_event(status),
                    ",".join(result["failure_reasons"]) or None,
                    json.dumps(result, ensure_ascii=False, sort_keys=True),
                ),
            )
            stored_edges += 1

        connection.execute(
            "UPDATE edge_registry_meta SET status='VALID' WHERE registry_version=?",
            (registry_version,),
        )
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"Edge Registry integrity_check failed: {integrity}")
        return {
            "status": "PASS",
            "registry_version": registry_version,
            "candidate_count": len(candidates),
            "prefiltered_out": prefiltered_out,
            "validated_candidate_count": len(validation_rows),
            "stored_edges": stored_edges,
            "counts": counts,
            "integrity_check": integrity,
            "validation_rows": validation_rows,
        }
    finally:
        connection.close()


def export_registry(registry_path: str | Path, jsonl_path: str | Path, csv_path: str | Path) -> dict[str, int]:
    connection = sqlite3.connect(registry_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT d.*,m.sample_n,m.unique_horses,m.unique_races,m.place_rate,m.place_roi,
                      m.baseline_place_rate,m.performance_lift,m.largest_return_share,m.top3_return_share
               FROM edge_definition d
               JOIN edge_metric_snapshot m ON m.edge_id=d.edge_id AND m.slice_kind='ALL'
               WHERE d.status IN ('ACTIVE','PROVISIONAL','WATCH','DECAYING')
               ORDER BY CASE d.status WHEN 'ACTIVE' THEN 1 WHEN 'PROVISIONAL' THEN 2 WHEN 'WATCH' THEN 3 ELSE 4 END,
                        COALESCE(d.strength_score,0) DESC,d.edge_id"""
        ).fetchall()
        with Path(jsonl_path).open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                payload = dict(row)
                payload["conditions"] = json.loads(payload.pop("conditions_json"))
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        fieldnames = [
            "edge_id", "status", "family", "anchor_type", "anchor_name", "validation_class",
            "policy_id", "polarity", "performance_signal", "value_signal", "display_text",
            "sample_n", "unique_horses", "unique_races", "place_rate", "place_roi",
            "baseline_place_rate", "performance_lift", "largest_return_share", "top3_return_share",
            "strength_score", "confidence_band", "last_validated_at", "next_review_at", "expires_at",
        ]
        with Path(csv_path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
        return {"exported": len(rows)}
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mart", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-version", required=True)
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--policies")
    parser.add_argument("--source-manifest")
    parser.add_argument("--include-rejected", action="store_true")
    parser.add_argument("--export-jsonl")
    parser.add_argument("--export-csv")
    parser.add_argument("--audit-json")
    args = parser.parse_args()

    candidates = [
        json.loads(line)
        for line in Path(args.candidates).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    policies = load_policy_catalog(args.policies) if args.policies else load_policy_catalog()
    manifest = None
    if args.source_manifest:
        manifest = json.loads(Path(args.source_manifest).read_text(encoding="utf-8"))
    result = build_registry(
        args.mart,
        candidates,
        args.registry,
        args.schema,
        policies,
        args.registry_version,
        source_manifest=manifest,
        include_rejected=args.include_rejected,
    )
    if bool(args.export_jsonl) != bool(args.export_csv):
        raise ValueError("--export-jsonl and --export-csv must be specified together")
    if args.export_jsonl and args.export_csv:
        result["export"] = export_registry(args.registry, args.export_jsonl, args.export_csv)
    if args.audit_json:
        audit = {key: value for key, value in result.items() if key != "validation_rows"}
        audit["validation_rows"] = result["validation_rows"]
        Path(args.audit_json).write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    printable = {key: value for key, value in result.items() if key != "validation_rows"}
    print(json.dumps(printable, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
