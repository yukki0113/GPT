#!/usr/bin/env python3
"""Build an immutable, result-free RaceNote + Edge prediction freeze.

Bulk data stays inside deterministic code. The full payload is retained as an
artifact while normal LLM-facing outputs are summary.json, changed_races.csv,
anomalies.jsonl and freeze_manifest.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping

import racenote_edge_prediction_policy as edge_policy
import racenote_v02_reconstructed_control as control

VERSION = "racenote-edge-prediction-freeze-v0.1"
VENUE_CODE = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
    "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_canonical_json(path: Path, obj: Any) -> str:
    data = canonical_json_bytes(obj)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def load_request(path: Path) -> dict[str, Any]:
    request = json.loads(path.read_text(encoding="utf-8"))
    dates = request.get("dates")
    if not isinstance(dates, list) or not dates or dates != sorted(dates) or len(set(dates)) != len(dates):
        raise ValueError("dates must be a non-empty, unique, sorted list")
    if any(not isinstance(day, str) or len(day) != 8 or not day.isdigit() for day in dates):
        raise ValueError("dates must use YYYYMMDD")
    racenote = _require_mapping(request.get("racenote"), "racenote")
    if set(racenote) != set(dates):
        raise ValueError("racenote keys must exactly equal dates")
    _require_mapping(request.get("edge"), "edge")
    registry = _require_mapping(request.get("registry"), "registry")
    for field in ("run_id", "artifact_name", "active_sha256"):
        if field not in registry:
            raise ValueError(f"registry.{field} is required")
    return request


def _materialize(path_value: str, work: Path, label: str) -> tuple[Path, str | None]:
    path = Path(path_value)
    if not path.exists():
        raise ValueError(f"{label} path does not exist: {path}")
    if path.is_dir():
        return path, None
    if not zipfile.is_zipfile(path):
        raise ValueError(f"{label} must be a directory or ZIP: {path}")
    target = work / label
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"{label} ZIP corrupt member: {bad}")
        archive.extractall(target)
    return target, sha256_file(path)


def _find_one(root: Path, pattern: str, label: str) -> Path:
    matches = list(root.rglob(pattern))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label}; found {len(matches)}")
    return matches[0]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name}:{line_no} must be object")
        rows.append(value)
    return rows


def load_edge(root: Path, dates: list[str], registry: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    result_path = _find_one(root, "result.json", "Edge result.json")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("status") != "success" or result.get("result_data_used") is not False:
        raise ValueError("Edge upstream must be success with result_data_used=false")
    if result.get("evaluation_mode") != "PRE_RESULT_RECONSTRUCTION":
        raise ValueError("Edge upstream must be PRE_RESULT_RECONSTRUCTION")
    upstream_request = _require_mapping(result.get("request"), "edge result.request")
    if upstream_request.get("dates") != dates:
        raise ValueError("Edge upstream dates mismatch")
    if int(upstream_request.get("registry_run_id")) != int(registry["run_id"]):
        raise ValueError("Registry run_id mismatch")
    if str(upstream_request.get("registry_artifact_name")) != str(registry["artifact_name"]):
        raise ValueError("Registry artifact_name mismatch")
    if str(upstream_request.get("registry_sha256")) != str(registry["active_sha256"]):
        raise ValueError("Registry SHA mismatch")

    day_data: dict[str, Any] = {}
    result_days = _require_mapping(result.get("days"), "edge result.days")
    for day in dates:
        expected = _require_mapping(result_days.get(day), f"edge day {day}")
        matches_path = _find_one(root, f"days/{day}/edge_matches.jsonl", f"{day} edge_matches")
        facts_path = _find_one(root, f"days/{day}/current_facts.jsonl", f"{day} current_facts")
        if sha256_file(matches_path) != expected.get("matches_sha256"):
            raise ValueError(f"{day} edge_matches SHA mismatch")
        if sha256_file(facts_path) != expected.get("facts_sha256"):
            raise ValueError(f"{day} current_facts SHA mismatch")
        facts = _read_jsonl(facts_path)
        matches = _read_jsonl(matches_path)
        if len(facts) != int(expected.get("runner_rows")) or len(matches) != len(facts):
            raise ValueError(f"{day} Edge row count mismatch")
        fact_by_rhk: dict[str, dict[str, Any]] = {}
        match_by_rhk: dict[str, dict[str, Any]] = {}
        identity: dict[tuple[str, int, int], str] = {}
        for row in facts:
            rhk = str(row.get("race_horse_key") or "")
            key = (str(row.get("venue_code") or ""), int(row.get("race_no")), int(row.get("horse_no")))
            if not rhk or rhk in fact_by_rhk or key in identity:
                raise ValueError(f"{day} duplicate/invalid current_facts identity")
            fact_by_rhk[rhk] = row
            identity[key] = rhk
        for row in matches:
            key_obj = _require_mapping(row.get("key"), "edge match key")
            rhk = str(key_obj.get("race_horse_key") or "")
            if not rhk or rhk in match_by_rhk or rhk not in fact_by_rhk:
                raise ValueError(f"{day} duplicate/orphan edge match identity")
            match_by_rhk[rhk] = row
        if set(fact_by_rhk) != set(match_by_rhk):
            raise ValueError(f"{day} facts/matches key mismatch")
        day_data[day] = {"identity": identity, "facts": fact_by_rhk, "matches": match_by_rhk, "audit": dict(expected)}
    return result, day_data


def load_racenote_day(root: Path, day: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inner = _find_one(root, f"RaceNote_{day}.zip", f"RaceNote_{day}.zip")
    inner_sha = sha256_file(inner)
    with zipfile.ZipFile(inner) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"RaceNote {day} corrupt member: {bad}")
        manifest_names = [name for name in archive.namelist() if Path(name).name == "request_manifest.json"]
        if len(manifest_names) != 1:
            raise ValueError(f"RaceNote {day} must contain one request_manifest.json")
        manifest = json.loads(archive.read(manifest_names[0]))
        req = _require_mapping(manifest.get("request"), "RaceNote request")
        iso_day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        if req.get("target_date") != iso_day:
            raise ValueError(f"RaceNote {day} target_date mismatch")
        enrichment = _require_mapping(req.get("enrichment"), "RaceNote request.enrichment")
        if enrichment.get("as_of_exclusive") != iso_day:
            raise ValueError(f"RaceNote {day} request as_of_exclusive mismatch")
        bundle_names = sorted(name for name in archive.namelist() if Path(name).name.startswith("race_bundle_") and name.endswith(".json"))
        if len(bundle_names) != int(manifest.get("bundle_count")):
            raise ValueError(f"RaceNote {day} bundle_count mismatch")
        bundles = []
        for name in bundle_names:
            bundle = json.loads(archive.read(name))
            if bundle.get("schema_version") != "1.0":
                raise ValueError(f"RaceNote {day} unsupported schema_version")
            metadata = _require_mapping(bundle.get("metadata"), "RaceNote metadata")
            if metadata.get("data_phase") != "pre_race" or metadata.get("race_date") != iso_day:
                raise ValueError(f"RaceNote {day} is not the expected pre_race snapshot")
            hist = _require_mapping(metadata.get("history_enrichment"), "RaceNote history_enrichment")
            if hist.get("as_of_exclusive") != iso_day:
                raise ValueError(f"RaceNote {day} bundle as_of_exclusive mismatch")
            bundles.append(bundle)
    return bundles, {"inner_zip_sha256": inner_sha, "manifest": manifest}


def _marks_order(policy_result: Mapping[str, Any], policy_name: str) -> list[int]:
    return [int(row["horse_no"]) for row in policy_result[policy_name]["marks"]]


def _write_changed_csv(path: Path, rows: list[dict[str, Any]]) -> str:
    fields = ["date", "venue", "race_no", "confidence", "v0_2_order", "v1_0_R_order", "v1_1_P_order",
              "v1_0_any_order_change", "v1_0_axis_change", "v1_1_axis_change", "v0_2_axis", "v1_0_axis", "v1_1_axis"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return sha256_file(path)


def build_freeze(request: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    dates = request["dates"]
    output_dir.mkdir(parents=True, exist_ok=True)
    anomalies: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="racenote-freeze-") as temp:
        work = Path(temp)
        edge_req = _require_mapping(request["edge"], "edge")
        edge_root, edge_outer_sha = _materialize(str(edge_req["path"]), work, "edge")
        expected_edge_sha = edge_req.get("artifact_sha256")
        if expected_edge_sha and edge_outer_sha and edge_outer_sha != expected_edge_sha:
            raise ValueError("Edge outer artifact SHA mismatch")
        edge_result, edge_days = load_edge(edge_root, dates, request["registry"])

        race_records: list[dict[str, Any]] = []
        changed: list[dict[str, Any]] = []
        daily: dict[str, dict[str, int]] = {}
        total_runners = 0
        seen_edge_keys: dict[str, set[str]] = {day: set() for day in dates}
        racenote_provenance: dict[str, Any] = {}

        for day in dates:
            rn_req = _require_mapping(request["racenote"][day], f"racenote.{day}")
            rn_root, outer_sha = _materialize(str(rn_req["path"]), work, f"racenote-{day}")
            expected_outer = rn_req.get("artifact_sha256")
            if expected_outer and outer_sha and outer_sha != expected_outer:
                raise ValueError(f"RaceNote {day} outer artifact SHA mismatch")
            bundles, rn_meta = load_racenote_day(rn_root, day)
            racenote_provenance[day] = {
                "run_id": rn_req.get("run_id"), "artifact_name": rn_req.get("artifact_name"),
                "artifact_sha256": expected_outer or outer_sha, "inner_zip_sha256": rn_meta["inner_zip_sha256"],
                "bundle_count": len(bundles),
                "as_of_exclusive": rn_meta["manifest"]["request"]["enrichment"]["as_of_exclusive"],
            }
            counts = {"races": 0, "runners": 0, "v1_0_any_order_change": 0, "v1_0_axis_change": 0, "v1_1_axis_change": 0}
            for bundle in bundles:
                race = bundle["race"]
                venue = str(race.get("venue"))
                venue_code = VENUE_CODE.get(venue)
                if venue_code is None:
                    raise ValueError(f"unsupported JRA venue: {venue}")
                race_no = int(race.get("race_no"))
                scored = control.score_race_bundle(bundle)
                counts["races"] += 1
                counts["runners"] += len(scored["rows"])
                total_runners += len(scored["rows"])

                full_runner_rows = []
                edge_by_no: dict[int, list[dict[str, Any]]] = {}
                for score_row in scored["rows"]:
                    no = int(score_row["horse_no"])
                    rhk = edge_days[day]["identity"].get((venue_code, race_no, no))
                    if rhk is None:
                        raise ValueError(f"missing Edge identity {day} {venue}{race_no}R horse={no}")
                    fact = edge_days[day]["facts"][rhk]
                    if fact.get("horse_name") != score_row.get("horse_name"):
                        raise ValueError(f"horse_name mismatch {day} {venue}{race_no}R horse={no}")
                    matches = list(edge_days[day]["matches"][rhk].get("edge_matches") or [])
                    edge_by_no[no] = matches
                    seen_edge_keys[day].add(rhk)
                    full_runner_rows.append({**score_row, "race_horse_key": rhk,
                                             "edge_ids": [str(edge.get("edge_id")) for edge in matches if edge.get("edge_id")]})

                top_five = []
                for score_row in scored["top_five"]:
                    row = dict(score_row)
                    row["edge_matches"] = edge_by_no[int(row["horse_no"])]
                    top_five.append(row)
                policies = edge_policy.apply_policies(top_five)
                v02 = _marks_order(policies, "v0_2_control")
                v10 = _marks_order(policies, "v1_0_R_frozen")
                v11 = _marks_order(policies, "v1_1_P_candidate")
                v10_any, v10_axis, v11_axis = v10 != v02, v10[0] != v02[0], v11[0] != v02[0]
                counts["v1_0_any_order_change"] += int(v10_any)
                counts["v1_0_axis_change"] += int(v10_axis)
                counts["v1_1_axis_change"] += int(v11_axis)

                hist = (bundle.get("metadata") or {}).get("history_enrichment") or {}
                if int(hist.get("warning_count") or 0) > 0:
                    anomalies.append({"severity": "warning", "code": "RACENOTE_HISTORY_WARNING", "date": day,
                                      "venue": venue, "race_no": race_no, "warnings": list(hist.get("warnings") or [])})
                race_records.append({"date": day, "venue": venue, "venue_code": venue_code, "race_no": race_no,
                                     "confidence": scored["confidence"], "v0_2_runners": full_runner_rows, "policies": policies})
                if v10_any or v11_axis:
                    changed.append({"date": day, "venue": venue, "race_no": race_no, "confidence": scored["confidence"],
                                    "v0_2_order": "-".join(map(str, v02)), "v1_0_R_order": "-".join(map(str, v10)),
                                    "v1_1_P_order": "-".join(map(str, v11)), "v1_0_any_order_change": int(v10_any),
                                    "v1_0_axis_change": int(v10_axis), "v1_1_axis_change": int(v11_axis),
                                    "v0_2_axis": v02[0], "v1_0_axis": v10[0], "v1_1_axis": v11[0]})
            daily[day] = counts

        for day in dates:
            expected_keys = set(edge_days[day]["facts"])
            missing = expected_keys - seen_edge_keys[day]
            extra = seen_edge_keys[day] - expected_keys
            if missing or extra:
                raise ValueError(f"{day} RaceNote/Edge join not one-to-one: missing={len(missing)} extra={len(extra)}")

        race_records.sort(key=lambda row: (row["date"], row["venue_code"], row["race_no"]))
        changed.sort(key=lambda row: (row["date"], VENUE_CODE[row["venue"]], row["race_no"]))
        totals = {
            "races": sum(row["races"] for row in daily.values()), "runners": total_runners,
            "v1_0_any_order_change": sum(row["v1_0_any_order_change"] for row in daily.values()),
            "v1_0_axis_change": sum(row["v1_0_axis_change"] for row in daily.values()),
            "v1_1_axis_change": sum(row["v1_1_axis_change"] for row in daily.values()),
        }

        regression = None
        expectation = request.get("regression_expectation")
        if expectation is not None:
            expectation = _require_mapping(expectation, "regression_expectation")
            failures = []
            for key, expected in (expectation.get("total") or {}).items():
                if totals.get(key) != expected:
                    failures.append(f"total.{key}: expected={expected} actual={totals.get(key)}")
            for day, expected_day in (expectation.get("days") or {}).items():
                for key, expected in expected_day.items():
                    if daily.get(day, {}).get(key) != expected:
                        failures.append(f"days.{day}.{key}: expected={expected} actual={daily.get(day, {}).get(key)}")
            expected_axes = expectation.get("v1_0_axis_changes") or []
            if expected_axes:
                def axis_key(row: list[Any]) -> tuple[str, str, int, int, int]:
                    if len(row) != 5 or row[1] not in VENUE_CODE:
                        raise ValueError("invalid regression v1_0_axis_changes row")
                    return (str(row[0]), VENUE_CODE[str(row[1])], int(row[2]), int(row[3]), int(row[4]))
                actual_axes = [[row["date"], row["venue"], row["race_no"], row["v0_2_axis"], row["v1_0_axis"]]
                               for row in changed if row["v1_0_axis_change"]]
                if sorted(actual_axes, key=axis_key) != sorted(expected_axes, key=axis_key):
                    failures.append("v1_0_axis_changes exact set mismatch")
            regression = {"pass": not failures, "failures": failures, "expectation": expectation}
            if failures:
                raise ValueError("regression gate failed: " + "; ".join(failures))

        full_payload = {
            "freeze_version": VERSION, "control_version": control.VERSION, "edge_policy_version": edge_policy.VERSION,
            "status": "PRE_RESULT_PREDICTION_FREEZE", "result_data_used": False, "dates": dates,
            "registry": dict(request["registry"]),
            "edge_provenance": {"run_id": edge_req.get("run_id"), "artifact_name": edge_req.get("artifact_name"),
                                "artifact_sha256": expected_edge_sha or edge_outer_sha,
                                "upstream_head_sha": edge_result.get("head_sha"),
                                "days": {day: edge_days[day]["audit"] for day in dates}},
            "racenote_provenance": racenote_provenance, "races": race_records,
        }
        payload_sha = write_canonical_json(output_dir / "prediction_payload.json", full_payload)
        anomalies_path = output_dir / "anomalies.jsonl"
        with anomalies_path.open("w", encoding="utf-8") as handle:
            for row in anomalies:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        anomalies_sha = sha256_file(anomalies_path)
        changed_sha = _write_changed_csv(output_dir / "changed_races.csv", changed)
        summary = {
            "status": "success", "freeze_version": VERSION, "control_version": control.VERSION,
            "edge_policy_version": edge_policy.VERSION, "result_data_used": False, "dates": dates,
            "daily": daily, "total": totals, "join": {"missing": 0, "extra": 0}, "changed_rows": len(changed),
            "anomalies": len(anomalies), "regression": regression, "prediction_payload_sha256": payload_sha,
        }
        summary_sha = write_canonical_json(output_dir / "summary.json", summary)
        manifest = {
            "status": "FROZEN_BEFORE_RESULT_ACQUISITION", "result_data_used": False,
            "request_id": request.get("request_id"), "dates": dates, "control_version": control.VERSION,
            "edge_policy_version": edge_policy.VERSION, "registry": dict(request["registry"]),
            "edge_provenance": full_payload["edge_provenance"], "racenote_provenance": racenote_provenance,
            "files": {"prediction_payload.json": payload_sha, "summary.json": summary_sha,
                      "changed_races.csv": changed_sha, "anomalies.jsonl": anomalies_sha},
        }
        manifest_sha = write_canonical_json(output_dir / "freeze_manifest.json", manifest)
        (output_dir / "FREEZE_SHA256.txt").write_text(
            f"freeze_manifest_sha256={manifest_sha}\nprediction_payload_sha256={payload_sha}\n", encoding="utf-8")
        result = dict(summary)
        result["freeze_manifest_sha256"] = manifest_sha
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = build_freeze(load_request(Path(args.request_json)), Path(args.output_dir))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
