#!/usr/bin/env python3
"""Build an immutable PRE_HJC RaceNote v1.1-P prediction freeze.

The runner consumes only already-frozen pre-result artifacts:
- RaceNote historical bundles generated with as_of_exclusive == target_date
- the fixed Phase1 Edge pre-result reconstruction artifact

It never downloads or reads HJC, SED, finish, payout, final odds or final
popularity.  All prediction logic is delegated to the committed v0.2 control
and v1.1-P policy modules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import racenote_edge_prediction_policy as edge_policy
import racenote_v02_reconstructed as control

VERSION = "racenote-v11p-blind-freeze-1.0"
FREEZE_STAGE = "PRE_HJC"
EXPECTED_DATES = ("20260704", "20260725", "20260726")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: JSONL row must be an object")
            rows.append(value)
    return rows


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def compact_date(value: str) -> str:
    text = str(value).strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = text.replace("-", "")
    require(len(text) == 8 and text.isdigit(), f"invalid date: {value}")
    date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    return text


def iso_date(value: str) -> str:
    text = compact_date(value)
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def parse_expiry(raw: Any) -> date | None:
    if raw in (None, ""):
        return None
    text = str(raw).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"invalid evidence.expires_at: {raw}") from exc


def active_unexpired(edge: Mapping[str, Any], target: date) -> bool:
    if str(edge.get("status", "")) != "ACTIVE":
        return False
    evidence = edge.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ValueError(f"ACTIVE Edge missing evidence: {edge.get('edge_id')}")
    expiry = parse_expiry(evidence.get("expires_at"))
    return expiry is None or target <= expiry


def eligible_edge_ids(matches: Sequence[Mapping[str, Any]], target: date, signal_field: str) -> list[str]:
    ids: list[str] = []
    for edge in matches:
        if not active_unexpired(edge, target):
            continue
        evidence = edge.get("evidence") or {}
        signal = str(evidence.get(signal_field) or "").upper()
        if signal not in {"POSITIVE", "NEGATIVE"}:
            continue
        edge_id = str(edge.get("edge_id") or "")
        require(bool(edge_id), f"eligible {signal_field} Edge missing edge_id")
        ids.append(edge_id)
    return sorted(set(ids))


def filtered_matches(matches: Sequence[Mapping[str, Any]], target: date) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    expired = 0
    for raw in matches:
        if not isinstance(raw, Mapping):
            raise ValueError("edge_matches entry must be an object")
        if str(raw.get("status", "")) != "ACTIVE":
            continue
        evidence = raw.get("evidence")
        if not isinstance(evidence, Mapping):
            raise ValueError(f"ACTIVE Edge missing evidence: {raw.get('edge_id')}")
        expiry = parse_expiry(evidence.get("expires_at"))
        if expiry is not None and target > expiry:
            expired += 1
            continue
        kept.append(dict(raw))
    return kept, expired


def normalize_request(raw: Any) -> dict[str, Any]:
    require(isinstance(raw, dict), "request must be a JSON object")
    request_id = str(raw.get("request_id") or "").strip()
    require(bool(request_id), "request_id is required")
    dates = tuple(compact_date(item) for item in raw.get("dates") or [])
    require(dates == EXPECTED_DATES, f"dates must be exactly {list(EXPECTED_DATES)}")

    edge = raw.get("edge")
    racenote = raw.get("racenote")
    require(isinstance(edge, dict), "edge object is required")
    require(isinstance(racenote, dict), "racenote object is required")
    for key in ("run_id", "artifact_name", "registry_sha256", "analysis_sha256"):
        require(edge.get(key) not in (None, ""), f"edge.{key} is required")
    require(len(str(edge["registry_sha256"])) == 64, "edge.registry_sha256 must be SHA-256")
    require(len(str(edge["analysis_sha256"])) == 64, "edge.analysis_sha256 must be SHA-256")

    for day in dates:
        spec = racenote.get(day)
        require(isinstance(spec, dict), f"racenote.{day} is required")
        for key in ("run_id", "artifact_name", "inner_zip_sha256"):
            require(spec.get(key) not in (None, ""), f"racenote.{day}.{key} is required")
        require(len(str(spec["inner_zip_sha256"])) == 64, f"racenote.{day}.inner_zip_sha256 must be SHA-256")
    return raw


def validate_racenote_manifest(manifest: Mapping[str, Any], day: str) -> None:
    request = manifest.get("request")
    require(isinstance(request, Mapping), f"RaceNote {day}: manifest.request missing")
    expected_iso = iso_date(day)
    require(request.get("target_date") == expected_iso, f"RaceNote {day}: target_date mismatch")
    require(request.get("temporal_mode") == "past", f"RaceNote {day}: temporal_mode must be past")
    require(request.get("base_backend") == "paci", f"RaceNote {day}: base_backend must be paci")
    enrichment = request.get("enrichment")
    require(isinstance(enrichment, Mapping), f"RaceNote {day}: enrichment missing")
    require(enrichment.get("analysis") is True, f"RaceNote {day}: analysis enrichment required")
    require(enrichment.get("stats_mart") is True, f"RaceNote {day}: stats_mart enrichment required")
    require(enrichment.get("as_of_exclusive") == expected_iso, f"RaceNote {day}: as_of_exclusive mismatch")
    require(int(manifest.get("bundle_count", -1)) == 36, f"RaceNote {day}: bundle_count must be 36")
    bundles = manifest.get("bundles")
    require(isinstance(bundles, list) and len(bundles) == 36, f"RaceNote {day}: bundles must contain 36 entries")


def load_racenote_day(root: Path, day: str, spec: Mapping[str, Any]) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any], str]]]:
    day_root = root / day
    require(day_root.is_dir(), f"RaceNote artifact directory missing: {day_root}")
    outer_manifest_path = day_root / "request_manifest.json"
    inner_zip_path = day_root / f"RaceNote_{day}.zip"
    require(outer_manifest_path.is_file(), f"RaceNote {day}: outer request_manifest.json missing")
    require(inner_zip_path.is_file(), f"RaceNote {day}: inner ZIP missing")

    actual_zip_sha = sha256_file(inner_zip_path)
    require(actual_zip_sha == spec["inner_zip_sha256"], f"RaceNote {day}: inner ZIP SHA mismatch")
    outer_manifest = load_json(outer_manifest_path)
    validate_racenote_manifest(outer_manifest, day)

    bundles: list[tuple[str, dict[str, Any], str]] = []
    with zipfile.ZipFile(inner_zip_path) as archive:
        names = set(archive.namelist())
        require("request_manifest.json" in names, f"RaceNote {day}: inner request_manifest missing")
        inner_manifest = json.loads(archive.read("request_manifest.json").decode("utf-8"))
        validate_racenote_manifest(inner_manifest, day)
        require(inner_manifest.get("request") == outer_manifest.get("request"), f"RaceNote {day}: outer/inner request mismatch")
        expected_names = list(inner_manifest["bundles"])
        for name in expected_names:
            require(name in names, f"RaceNote {day}: bundle missing from ZIP: {name}")
            raw_bytes = archive.read(name)
            bundle = json.loads(raw_bytes.decode("utf-8"))
            require(bundle.get("race", {}).get("date") == iso_date(day), f"RaceNote {day}: bundle date mismatch: {name}")
            bundles.append((name, bundle, sha256_bytes(raw_bytes)))
    require(len(bundles) == 36, f"RaceNote {day}: loaded bundle count mismatch")
    return dict(outer_manifest), bundles


def validate_edge_artifact(root: Path, request: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    result_path = root / "result.json"
    require(result_path.is_file(), "Edge result.json missing")
    result = load_json(result_path)
    edge_spec = request["edge"]
    require(result.get("status") == "success", "Edge upstream status is not success")
    require(result.get("evaluation_mode") == "PRE_RESULT_RECONSTRUCTION", "Edge artifact is not pre-result reconstruction")
    require(result.get("result_data_used") is False, "Edge artifact indicates result data usage")
    require(int(result.get("run_id", -1)) == int(edge_spec["run_id"]), "Edge run_id mismatch")
    upstream_request = result.get("request") or {}
    require(upstream_request.get("registry_sha256") == edge_spec["registry_sha256"], "Edge registry SHA mismatch")
    require(upstream_request.get("analysis_sha256") == edge_spec["analysis_sha256"], "Edge Analysis SHA mismatch")
    require(tuple(upstream_request.get("dates") or []) == EXPECTED_DATES, "Edge target dates mismatch")

    day_data: dict[str, dict[str, Any]] = {}
    for day in EXPECTED_DATES:
        day_result = (result.get("days") or {}).get(day)
        require(isinstance(day_result, Mapping), f"Edge result missing day {day}")
        facts_path = root / "days" / day / "current_facts.jsonl"
        matches_path = root / "days" / day / "edge_matches.jsonl"
        require(facts_path.is_file() and matches_path.is_file(), f"Edge {day}: current_facts/edge_matches missing")
        facts_sha = sha256_file(facts_path)
        matches_sha = sha256_file(matches_path)
        require(facts_sha == day_result.get("facts_sha256"), f"Edge {day}: current_facts SHA mismatch")
        require(matches_sha == day_result.get("matches_sha256"), f"Edge {day}: edge_matches SHA mismatch")
        facts = load_jsonl(facts_path)
        match_rows = load_jsonl(matches_path)
        require(len(facts) == int(day_result.get("runner_rows", -1)), f"Edge {day}: runner row count mismatch")
        require(len(match_rows) == int(day_result.get("runner_rows", -1)), f"Edge {day}: Edge row count mismatch")
        matched_runners = sum(1 for row in match_rows if row.get("edge_matches"))
        require(matched_runners == int(day_result.get("matched_runners", -1)),
                f"Edge {day}: matched runner count mismatch")
        total_matches = sum(len(row.get("edge_matches") or []) for row in match_rows)
        require(total_matches == int(day_result.get("matches", -1)), f"Edge {day}: Edge match count mismatch")
        day_data[day] = {
            "result": dict(day_result),
            "facts": facts,
            "match_rows": match_rows,
            "facts_sha256": facts_sha,
            "matches_sha256": matches_sha,
        }
    return result, day_data


def group_facts_by_race(facts: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in facts:
        race_key = str(row.get("race_key") or "")
        require(bool(race_key), "current_fact missing race_key")
        grouped[race_key].append(dict(row))
    return dict(grouped)


def find_fact_race(bundle: Mapping[str, Any], grouped: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[str, list[dict[str, Any]]]:
    race = bundle.get("race") or {}
    race_no = int(race["race_no"])
    horses = bundle.get("horses") or []
    bundle_pairs = {(int(h["basic"]["horse_no"]), str(h["basic"].get("horse_name") or "")) for h in horses}
    exact: list[tuple[str, list[dict[str, Any]]]] = []
    for race_key, rows in grouped.items():
        if not rows or int(rows[0].get("race_no", -1)) != race_no:
            continue
        fact_pairs = {(int(row["horse_no"]), str(row.get("horse_name") or "")) for row in rows}
        if fact_pairs == bundle_pairs:
            exact.append((race_key, [dict(row) for row in rows]))
    require(len(exact) == 1, f"could not uniquely map RaceNote bundle to Edge race: {race.get('venue')} {race_no}R; candidates={len(exact)}")
    return exact[0]


def match_map(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    mapped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = row.get("key") or {}
        race_horse_key = str(key.get("race_horse_key") or "")
        require(bool(race_horse_key), "edge match row missing race_horse_key")
        require(race_horse_key not in mapped, f"duplicate edge match race_horse_key: {race_horse_key}")
        matches = row.get("edge_matches") or []
        require(isinstance(matches, list), f"edge match row {race_horse_key}: edge_matches must be list")
        mapped[race_horse_key] = [dict(edge) for edge in matches]
    return mapped


def polarity_label(value: int) -> str:
    return "POSITIVE" if value > 0 else "NEGATIVE" if value < 0 else "NEUTRAL"


def shadow_value_role(policy_result: Mapping[str, Any]) -> dict[str, Any]:
    """Reconstruct the frozen v1.0-V rule as a shadow-only diagnostic."""
    v10_marks = policy_result["v1_0_R_frozen"]["marks"]
    order = [int(row["horse_no"]) for row in v10_marks]
    diagnostics = {int(row["horse_no"]): row for row in policy_result["horses"]}
    baseline_triangle = order[2]
    candidates: list[tuple[int, int, int, int]] = []
    for rank, horse_no in enumerate(order[2:], 3):
        diag = diagnostics[horse_no]
        value_tier = int(diag["value_edge_tier"])
        performance_tier = int(diag["performance_edge_tier"])
        if value_tier >= 1 and performance_tier >= 0:
            candidates.append((-value_tier, -performance_tier, rank, horse_no))
    candidates.sort()
    selected = candidates[0][3] if candidates else baseline_triangle
    shadow_order = order[:2] + [selected] + [horse_no for horse_no in order[2:] if horse_no != selected]
    return {
        "rule": "v1.0-V-shadow",
        "mark_effect_on_v1_1_P": False,
        "baseline_triangle_horse_no": baseline_triangle,
        "selected_triangle_horse_no": selected,
        "would_change_triangle": selected != baseline_triangle,
        "marks": [{"mark": edge_policy.MARKS[idx], "horse_no": horse_no} for idx, horse_no in enumerate(shadow_order)],
    }


def build_race_record(
    *,
    day: str,
    bundle_name: str,
    bundle_sha256: str,
    bundle: Mapping[str, Any],
    fact_groups: Mapping[str, Sequence[Mapping[str, Any]]],
    matches_by_key: Mapping[str, Sequence[Mapping[str, Any]]],
    source_provenance: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    race_key, facts = find_fact_race(bundle, fact_groups)
    facts_by_horse = {int(row["horse_no"]): row for row in facts}
    require(len(facts_by_horse) == len(facts), f"{race_key}: duplicate horse_no in current facts")
    scorer = control.score_race_bundle(bundle)
    target = date.fromisoformat(iso_date(day))

    policy_input: list[dict[str, Any]] = []
    edge_details: list[dict[str, Any]] = []
    expired_count = 0
    for top in scorer["top5"]:
        horse_no = int(top["horse_no"])
        fact = facts_by_horse.get(horse_no)
        require(fact is not None, f"{race_key}: v0.2 top-five horse missing current_fact: {horse_no}")
        raw_matches = matches_by_key.get(str(fact["race_horse_key"]), [])
        active_matches, expired = filtered_matches(raw_matches, target)
        expired_count += expired
        row = dict(top)
        row["edge_matches"] = active_matches
        policy_input.append(row)
        edge_details.append({
            "horse_no": horse_no,
            "horse_name": top.get("horse_name"),
            "race_horse_key": fact["race_horse_key"],
            "raw_match_count": len(raw_matches),
            "active_unexpired_match_count": len(active_matches),
            "eligible_performance_edge_ids": eligible_edge_ids(active_matches, target, "performance_signal"),
            "eligible_value_edge_ids": eligible_edge_ids(active_matches, target, "value_signal"),
        })

    policy_result = edge_policy.apply_policies(policy_input)
    diagnostics = {int(row["horse_no"]): row for row in policy_result["horses"]}
    for item in edge_details:
        diag = diagnostics[item["horse_no"]]
        item.update({
            "performance_family_votes": diag["performance_family_votes"],
            "family_vote_sum": diag["family_vote_sum"],
            "performance_edge_tier_historical_reference": diag["performance_edge_tier"],
            "performance_edge_polarity": polarity_label(int(diag["performance_edge_polarity"])),
            "performance_edge_polarity_order": int(diag["performance_edge_polarity"]),
            "value_family_votes": diag["value_family_votes"],
            "value_edge_tier_shadow": int(diag["value_edge_tier"]),
            "base_good": float(scorer["top5"][0]["good"]),
            "good_gap_from_base_axis": float(diag["good_gap_from_base_axis"]),
            "axis_eligible": bool(diag["axis_eligible"]),
            "displayed_supporting_edge_id": diag["supporting_edge_id"],
            "displayed_opposing_edge_id": diag["opposing_edge_id"],
        })

    base_axis = int(policy_result["v0_2_control"]["axis_horse_no"])
    selected_axis = int(policy_result["v1_1_P_candidate"]["axis_horse_no"])
    base_pol = int(diagnostics[base_axis]["performance_edge_polarity"])
    selected_pol = int(diagnostics[selected_axis]["performance_edge_polarity"])

    race_record = {
        "race": {
            **scorer["race"],
            "race_key": race_key,
            "venue_code": str(facts[0]["venue_code"]),
        },
        "source": {
            **dict(source_provenance),
            "racenote_bundle": bundle_name,
            "racenote_bundle_sha256": bundle_sha256,
        },
        "v0_2_control": {
            "control_version": scorer["control_version"],
            "confidence": scorer["confidence"],
            "p1_p2_good_gap": scorer["p1_p2_good_gap"],
            "all_runners": scorer["runners"],
            "top5": [{key: value for key, value in row.items() if key != "edge_matches"} for row in scorer["top5"]],
            "marks": policy_result["v0_2_control"]["marks"],
            "axis_horse_no": base_axis,
        },
        "edge_diagnostics": edge_details,
        "v1_0_R_historical_reference": policy_result["v1_0_R_frozen"],
        "value_shadow": shadow_value_role(policy_result),
        "v1_1_P_candidate": {
            **policy_result["v1_1_P_candidate"],
            "base_axis_polarity": polarity_label(base_pol),
            "selected_axis_polarity": polarity_label(selected_pol),
            "confidence": scorer["confidence"],
        },
        "result_data_used": False,
    }
    audit = {
        "axis_changed": int(selected_axis != base_axis),
        "base_negative": int(base_pol < 0),
        "base_neutral": int(base_pol == 0),
        "base_positive": int(base_pol > 0),
        "selected_negative": int(selected_pol < 0),
        "selected_neutral": int(selected_pol == 0),
        "selected_positive": int(selected_pol > 0),
        "confidence_A": int(scorer["confidence"] == "A"),
        "confidence_B": int(scorer["confidence"] == "B"),
        "confidence_C": int(scorer["confidence"] == "C"),
        "top5_with_any_edge": sum(1 for item in edge_details if item["raw_match_count"] > 0),
        "expired_edges_excluded": expired_count,
        "value_shadow_changes": int(race_record["value_shadow"]["would_change_triangle"]),
    }
    return race_record, audit


def add_audit(target: Counter[str], values: Mapping[str, int]) -> None:
    for key, value in values.items():
        target[key] += int(value)


def write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return sha256_file(path)


def run(args: argparse.Namespace) -> dict[str, Any]:
    request_path = Path(args.request_json).resolve()
    edge_root = Path(args.edge_root).resolve()
    racenote_root = Path(args.racenote_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    request = normalize_request(load_json(request_path))
    edge_result, edge_days = validate_edge_artifact(edge_root, request)

    output_dir.mkdir(parents=True, exist_ok=True)
    day_payloads: list[dict[str, Any]] = []
    day_outputs: dict[str, Any] = {}
    overall_audit: Counter[str] = Counter()
    per_day_audit: dict[str, Any] = {}
    racenote_provenance: dict[str, Any] = {}

    for day in EXPECTED_DATES:
        rn_spec = request["racenote"][day]
        rn_manifest, bundles = load_racenote_day(racenote_root, day, rn_spec)
        facts = edge_days[day]["facts"]
        grouped = group_facts_by_race(facts)
        by_key = match_map(edge_days[day]["match_rows"])
        audit_counter: Counter[str] = Counter()
        races: list[dict[str, Any]] = []
        source_provenance = {
            "racenote_run_id": int(rn_spec["run_id"]),
            "racenote_artifact_name": rn_spec["artifact_name"],
            "racenote_inner_zip_sha256": rn_spec["inner_zip_sha256"],
            "edge_run_id": int(request["edge"]["run_id"]),
            "edge_artifact_name": request["edge"]["artifact_name"],
            "edge_current_facts_sha256": edge_days[day]["facts_sha256"],
            "edge_matches_sha256": edge_days[day]["matches_sha256"],
            "paci_sha256_upstream_verified": edge_days[day]["result"]["paci_sha256"],
            "registry_sha256": request["edge"]["registry_sha256"],
            "analysis_sha256": request["edge"]["analysis_sha256"],
            "as_of_exclusive": iso_date(day),
        }
        for bundle_name, bundle, bundle_sha in bundles:
            record, race_audit = build_race_record(
                day=day,
                bundle_name=bundle_name,
                bundle_sha256=bundle_sha,
                bundle=bundle,
                fact_groups=grouped,
                matches_by_key=by_key,
                source_provenance=source_provenance,
            )
            races.append(record)
            add_audit(audit_counter, race_audit)
            add_audit(overall_audit, race_audit)
        races.sort(key=lambda row: (row["race"]["venue_code"], int(row["race"]["race_no"])))
        require(len(races) == 36, f"{day}: expected 36 frozen races")

        day_payload = {
            "schema_version": VERSION,
            "freeze_stage": FREEZE_STAGE,
            "result_data_used": False,
            "request_id": request["request_id"],
            "date": iso_date(day),
            "control_version": control.VERSION,
            "policy_version": edge_policy.VERSION,
            "provenance": {
                "racenote": {
                    "run_id": int(rn_spec["run_id"]),
                    "artifact_name": rn_spec["artifact_name"],
                    "inner_zip_sha256": rn_spec["inner_zip_sha256"],
                    "manifest_request": rn_manifest["request"],
                },
                "edge": {
                    "run_id": int(request["edge"]["run_id"]),
                    "artifact_name": request["edge"]["artifact_name"],
                    "facts_sha256": edge_days[day]["facts_sha256"],
                    "matches_sha256": edge_days[day]["matches_sha256"],
                    "paci_sha256": edge_days[day]["result"]["paci_sha256"],
                    "registry_sha256": request["edge"]["registry_sha256"],
                    "analysis_sha256": request["edge"]["analysis_sha256"],
                },
            },
            "races": races,
        }
        day_file = output_dir / f"RaceNote_v1_1_Polarity_Gated_{day}_PRE_HJC.json"
        day_sha = write_json(day_file, day_payload)
        day_payloads.append(day_payload)
        per_day_audit[day] = {"races": 36, **dict(sorted(audit_counter.items()))}
        day_outputs[day] = {
            "file": day_file.name,
            "sha256": day_sha,
            "canonical_payload_sha256": sha256_bytes(canonical_bytes(day_payload)),
            "races": 36,
        }
        racenote_provenance[day] = {
            "run_id": int(rn_spec["run_id"]),
            "artifact_name": rn_spec["artifact_name"],
            "inner_zip_sha256": rn_spec["inner_zip_sha256"],
        }

    require(sum(item["races"] for item in day_outputs.values()) == 108, "freeze must contain exactly 108 races")
    combined_payload_sha = sha256_bytes(canonical_bytes(day_payloads))
    source_hashes = {
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "control_source_sha256": sha256_file(HERE / "racenote_v02_reconstructed.py"),
        "policy_source_sha256": sha256_file(HERE / "racenote_edge_prediction_policy.py"),
    }
    manifest = {
        "schema_version": VERSION,
        "status": "success",
        "freeze_stage": FREEZE_STAGE,
        "result_data_used": False,
        "request_id": request["request_id"],
        "run_id": int(args.run_id),
        "head_sha": args.head_sha,
        "dates": list(EXPECTED_DATES),
        "control_version": control.VERSION,
        "policy_version": edge_policy.VERSION,
        "source_hashes": source_hashes,
        "upstream": {
            "edge": {
                "run_id": int(request["edge"]["run_id"]),
                "artifact_name": request["edge"]["artifact_name"],
                "registry_sha256": request["edge"]["registry_sha256"],
                "analysis_sha256": request["edge"]["analysis_sha256"],
                "head_sha": edge_result.get("head_sha"),
                "result_data_used": False,
            },
            "racenote": racenote_provenance,
        },
        "outputs": {
            "days": day_outputs,
            "combined_canonical_payload_sha256": combined_payload_sha,
            "race_count": 108,
        },
        "audit": {
            "overall": {"races": 108, **dict(sorted(overall_audit.items()))},
            "by_day": per_day_audit,
        },
        "leakage_guard": {
            "allowed": ["pre-race PACI", "as-of-exclusive RaceNote history", "fixed ACTIVE Edge Registry/matches"],
            "forbidden_and_not_read": ["HJC", "SED", "finish", "payout", "final odds", "final popularity", "later-dated history"],
        },
    }
    manifest_path = output_dir / "RaceNote_v1_1_Polarity_Gated_20260704_25_26_PRE_HJC_FREEZE.json"
    manifest_sha = write_json(manifest_path, manifest)
    result = {
        "status": "success",
        "freeze_stage": FREEZE_STAGE,
        "result_data_used": False,
        "request_id": request["request_id"],
        "run_id": int(args.run_id),
        "head_sha": args.head_sha,
        "race_count": 108,
        "axis_changes": int(overall_audit["axis_changed"]),
        "by_day": {day: {"axis_changes": int(per_day_audit[day].get("axis_changed", 0))} for day in EXPECTED_DATES},
        "combined_canonical_payload_sha256": combined_payload_sha,
        "manifest_file": manifest_path.name,
        "manifest_sha256": manifest_sha,
        "day_files": day_outputs,
        "source_hashes": source_hashes,
        "audit": manifest["audit"],
    }
    write_json(output_dir / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--edge-root", required=True)
    parser.add_argument("--racenote-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        print(json.dumps({"status": "failure", "failure_class": "DOMAIN_VALIDATION_FAILED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
