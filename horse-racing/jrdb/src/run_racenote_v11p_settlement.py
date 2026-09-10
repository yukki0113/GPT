#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Settle the frozen RaceNote v1.1-P blind block after PRE_HJC freeze.

This runner is intentionally mechanical. It consumes the immutable prediction
freeze plus already-acquired JRDB HJC/SED artifacts, normalizes result-side
cache files, and writes race-level settlement records. It does not compute or
interpret aggregate model metrics; that is a later pipeline stage.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from jrdb_raw import Parser, read_fixed_records  # noqa: E402
from settle_racenote_backtest import Ticket, payout_for_ticket  # noqa: E402

VERSION = "racenote-v11p-settlement-1.0"
EXPECTED_DATES = ("20260704", "20260725", "20260726")
FREEZE_MANIFEST = "RaceNote_v1_1_Polarity_Gated_20260704_25_26_PRE_HJC_FREEZE.json"
POLICIES = {
    "v0_2_control": "v0_2_control",
    "v1_0_R_frozen": "v1_0_R_historical_reference",
    "v1_1_P_candidate": "v1_1_P_candidate",
}
WAGERS = ("win", "place", "frame_quinella", "quinella", "wide", "exacta", "trio", "trifecta")
UNIT_STAKE_JPY = 100


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha256_file(path)


def day_iso(day: str) -> str:
    return f"{day[:4]}-{day[4:6]}-{day[6:8]}"


def find_unique(root: Path, name: str) -> Path:
    matches = [p for p in root.rglob(name) if p.is_file()]
    require(len(matches) == 1, f"expected exactly one {name} under {root}; found {len(matches)}")
    return matches[0]


def validate_freeze(freeze_root: Path, request: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest_path = freeze_root / FREEZE_MANIFEST
    require(manifest_path.is_file(), f"freeze manifest missing: {manifest_path}")
    freeze_spec = request["freeze"]
    require(sha256_file(manifest_path) == freeze_spec["manifest_sha256"], "freeze manifest SHA mismatch")
    manifest = load_json(manifest_path)
    require(manifest.get("freeze_stage") == "PRE_HJC", "freeze_stage must be PRE_HJC")
    require(manifest.get("result_data_used") is False, "freeze must declare result_data_used=false")
    require(tuple(manifest.get("dates") or []) == EXPECTED_DATES, "freeze date set mismatch")
    outputs = manifest.get("outputs")
    require(isinstance(outputs, Mapping), "freeze manifest outputs missing")
    require(outputs.get("combined_canonical_payload_sha256") == freeze_spec["combined_canonical_payload_sha256"],
            "freeze canonical payload SHA mismatch")

    day_payloads: dict[str, dict[str, Any]] = {}
    day_files = outputs.get("days") or {}
    for day in EXPECTED_DATES:
        meta = day_files.get(day)
        require(isinstance(meta, Mapping), f"freeze manifest missing day_files.{day}")
        path = freeze_root / str(meta.get("file") or "")
        require(path.is_file(), f"freeze day file missing for {day}")
        require(sha256_file(path) == meta.get("sha256"), f"freeze day file SHA mismatch: {day}")
        payload = load_json(path)
        require(payload.get("freeze_stage") == "PRE_HJC", f"freeze day {day}: invalid stage")
        require(payload.get("result_data_used") is False, f"freeze day {day}: result_data_used must be false")
        require(payload.get("date") == day_iso(day), f"freeze day {day}: date mismatch")
        races = payload.get("races")
        require(isinstance(races, list) and len(races) == 36, f"freeze day {day}: expected 36 races")
        day_payloads[day] = payload
    return manifest, day_payloads


def validate_raw_day(raw_root: Path, day: str, spec: Mapping[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    day_root = raw_root / day
    require(day_root.is_dir(), f"raw artifact directory missing for {day}: {day_root}")
    manifest_path = find_unique(day_root, "manifest.json")
    manifest = load_json(manifest_path)
    require(manifest.get("status") == "success" and manifest.get("date") == day, f"raw manifest invalid for {day}")
    by_kind = {str(row.get("kind")): row for row in manifest.get("files") or [] if isinstance(row, Mapping)}
    for kind in ("HJC", "SED"):
        require(kind in by_kind, f"raw manifest {day}: missing {kind}")
    hjc = find_unique(day_root, f"HJC{day[2:]}.zip")
    sed = find_unique(day_root, f"SED{day[2:]}.zip")
    require(sha256_file(hjc) == spec["hjc_sha256"], f"HJC SHA mismatch for {day}")
    require(sha256_file(sed) == spec["sed_sha256"], f"SED SHA mismatch for {day}")
    require(by_kind["HJC"].get("sha256") == spec["hjc_sha256"], f"raw manifest HJC SHA mismatch for {day}")
    require(by_kind["SED"].get("sha256") == spec["sed_sha256"], f"raw manifest SED SHA mismatch for {day}")
    return hjc, sed, manifest


def parse_hjc(archive: Path, day: str, parser: Parser) -> dict[str, dict[str, Any]]:
    member_name = f"HJC{day[2:]}.txt"
    out: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(archive) as zf:
        member = next((n for n in zf.namelist() if Path(n).name.upper() == member_name.upper()), None)
        require(member is not None, f"{member_name} missing from {archive}")
        for record in read_fixed_records(zf, member, "HJC"):
            parsed = parser.hjc(record)
            key = str(parsed.get("race_key_raw") or "")
            require(key and key not in out, f"duplicate/blank HJC race key: {key!r}")
            out[key] = {"parsed": parsed, "record_sha256": hashlib.sha256(record).hexdigest()}
    return out


def parse_sed(archive: Path, day: str, parser: Parser) -> dict[str, dict[int, dict[str, Any]]]:
    member_name = f"SED{day[2:]}.txt"
    out: dict[str, dict[int, dict[str, Any]]] = {}
    with zipfile.ZipFile(archive) as zf:
        member = next((n for n in zf.namelist() if Path(n).name.upper() == member_name.upper()), None)
        require(member is not None, f"{member_name} missing from {archive}")
        for record in read_fixed_records(zf, member, "SED"):
            parsed = parser.sed(record)
            race_key = str(parsed.get("race_key_raw") or "")
            horse_no = parsed.get("horse_no")
            require(race_key and isinstance(horse_no, int) and horse_no > 0, "invalid SED race/horse key")
            race = out.setdefault(race_key, {})
            require(horse_no not in race, f"duplicate SED horse row: {race_key}/{horse_no}")
            race[horse_no] = {
                "horse_no": horse_no,
                "horse_name": parsed.get("horse_name"),
                "finish_position": parsed.get("finish"),
                "abnormality_code": parsed.get("abnormal_code"),
                "record_sha256": hashlib.sha256(record).hexdigest(),
            }
    return out


def positive_slots(parsed_hjc: Mapping[str, Any], wager: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slot in parsed_hjc.get(wager) or []:
        if not isinstance(slot, Mapping):
            continue
        nums = slot.get("numbers") or []
        payout = slot.get("payout")
        if isinstance(payout, int) and payout > 0 and all(isinstance(x, int) and x > 0 for x in nums):
            rows.append({"numbers": list(nums), "payout_jpy": payout})
    return rows


def cache_cell(slots: Sequence[Mapping[str, Any]]) -> str:
    return ";".join(f"{'-'.join(str(x) for x in row['numbers'])}:{row['payout_jpy']}" for row in slots)


def extract_roles(marks: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    require(isinstance(marks, Sequence) and len(marks) >= 5, "policy marks must contain at least five rows")
    singles: dict[str, int] = {}
    deltas: list[int] = []
    for row in marks:
        mark = row.get("mark")
        horse_no = row.get("horse_no")
        require(isinstance(horse_no, int) and horse_no > 0, f"invalid horse_no in marks: {horse_no!r}")
        if mark in {"◎", "○", "▲"} and mark not in singles:
            singles[str(mark)] = horse_no
        elif mark == "△":
            deltas.append(horse_no)
    require(all(m in singles for m in ("◎", "○", "▲")) and len(deltas) >= 2, "marks missing ◎/○/▲/△1/△2")
    roles = {"honmei": singles["◎"], "taikou": singles["○"], "tanana": singles["▲"], "delta1": deltas[0], "delta2": deltas[1]}
    require(len(set(roles.values())) == 5, "top-five marks must be five distinct horses")
    return roles


def build_policy_tickets(marks: Sequence[Mapping[str, Any]]) -> dict[str, list[Ticket]]:
    m = extract_roles(marks)
    axis = m["honmei"]
    opponents = [m["taikou"], m["tanana"], m["delta1"], m["delta2"]]
    q2 = [
        Ticket("Q2", "quinella", tuple(sorted((axis, m["taikou"])))),
        Ticket("Q2", "quinella", tuple(sorted((axis, m["tanana"])))),
    ]
    q4 = [Ticket("Q4", "quinella", tuple(sorted((axis, x)))) for x in opponents]
    a6 = [Ticket("Trio_A6", "trio", tuple(sorted((axis, a, b)))) for a, b in itertools.combinations(opponents, 2)]
    omitted = tuple(sorted((axis, m["delta1"], m["delta2"])))
    b5 = [Ticket("Trio_B5", "trio", t.horses) for t in a6 if t.horses != omitted]
    require(len(q2) == 2 and len(q4) == 4 and len(a6) == 6 and len(b5) == 5, "ticket construction invariant failed")
    return {"win": [Ticket("win", "win", (axis,))], "Q2": q2, "Q4": q4, "Trio_A6": a6, "Trio_B5": b5}


def settle_ticket_set(tickets: Sequence[Ticket], parsed_hjc: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ticket in tickets:
        payout = payout_for_ticket(ticket, dict(parsed_hjc))
        out.append({"wager": ticket.wager, "horses": list(ticket.horses), "stake_jpy": UNIT_STAKE_JPY,
                    "payout_jpy": payout, "hit": payout > 0})
    return out


def policy_marks(race: Mapping[str, Any], policy: str) -> list[dict[str, Any]]:
    source_key = POLICIES[policy]
    block = race.get(source_key)
    require(isinstance(block, Mapping), f"race missing policy block: {source_key}")
    marks = block.get("marks")
    require(isinstance(marks, list), f"race {source_key}: marks missing")
    return [dict(row) for row in marks]


def settle_day(day: str, freeze_payload: Mapping[str, Any], hjc_map: Mapping[str, Mapping[str, Any]],
               sed_map: Mapping[str, Mapping[int, Mapping[str, Any]]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    settled_races: list[dict[str, Any]] = []
    payout_cache: list[dict[str, Any]] = []
    finish_cache: list[dict[str, Any]] = []

    for race in freeze_payload["races"]:
        meta = race.get("race") or {}
        race_key = str(meta.get("race_key") or "")
        require(race_key in hjc_map, f"freeze race missing from HJC: {race_key}")
        require(race_key in sed_map, f"freeze race missing from SED: {race_key}")
        hjc = hjc_map[race_key]
        parsed_hjc = hjc["parsed"]
        sed_horses = sed_map[race_key]

        frozen_horses = {int(row["horse_no"]) for row in race["v0_2_control"]["all_runners"]}
        require(frozen_horses.issubset(set(sed_horses)), f"SED runner coverage mismatch: {race_key}")
        for horse_no in sorted(sed_horses):
            row = sed_horses[horse_no]
            finish_cache.append({
                "date": day_iso(day), "venue": meta.get("venue"), "race_no": meta.get("race_no"), "race_key_raw": race_key,
                "horse_no": horse_no, "horse_name": row.get("horse_name"), "finish_position": row.get("finish_position"),
                "abnormality_code": row.get("abnormality_code"), "sed_record_sha256": row.get("record_sha256"),
            })

        slots = {w: positive_slots(parsed_hjc, w) for w in WAGERS}
        payout_cache.append({
            "date": day_iso(day), "venue": meta.get("venue"), "race_no": meta.get("race_no"), "race_key_raw": race_key,
            **{w: cache_cell(slots[w]) for w in WAGERS},
        })

        policies: dict[str, Any] = {}
        for policy in POLICIES:
            marks = policy_marks(race, policy)
            roles = extract_roles(marks)
            axis_result = sed_horses[roles["honmei"]]
            ticket_sets = build_policy_tickets(marks)
            policies[policy] = {
                "marks": [{"mark": row.get("mark"), "horse_no": row.get("horse_no"), "horse_name": row.get("horse_name")} for row in marks],
                "roles": roles,
                "axis_finish_position": axis_result.get("finish_position"),
                "axis_abnormality_code": axis_result.get("abnormality_code"),
                "tickets": {name: settle_ticket_set(tickets, parsed_hjc) for name, tickets in ticket_sets.items()},
            }

        settled_races.append({
            "date": day_iso(day), "venue": meta.get("venue"), "venue_code": meta.get("venue_code"), "race_no": meta.get("race_no"),
            "race_key_raw": race_key, "hjc_record_sha256": hjc.get("record_sha256"),
            "runner_results": [dict(sed_horses[n]) for n in sorted(sed_horses)],
            "policies": policies,
        })

    require(len(set(r["race_key_raw"] for r in settled_races)) == 36, f"settlement day {day}: expected 36 unique races")
    return {
        "date": day_iso(day), "status": "SETTLED_AFTER_FREEZE", "settlement_runner_version": VERSION,
        "race_count": len(settled_races), "races": settled_races,
    }, payout_cache, finish_cache


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return sha256_file(path)


def normalize_request(raw: Any) -> dict[str, Any]:
    require(isinstance(raw, dict), "request must be object")
    require(raw.get("request_id"), "request_id required")
    freeze = raw.get("freeze")
    results = raw.get("results")
    require(isinstance(freeze, dict) and isinstance(results, dict), "freeze/results objects required")
    for key in ("freeze_commit", "manifest_sha256", "combined_canonical_payload_sha256"):
        require(freeze.get(key), f"freeze.{key} required")
    for day in EXPECTED_DATES:
        spec = results.get(day)
        require(isinstance(spec, dict), f"results.{day} required")
        for key in ("run_id", "artifact_name", "hjc_sha256", "sed_sha256"):
            require(spec.get(key) not in (None, ""), f"results.{day}.{key} required")
    return raw


def run(request_path: Path, freeze_root: Path, raw_root: Path, output_root: Path, *, run_id: str, head_sha: str) -> dict[str, Any]:
    request = normalize_request(load_json(request_path))
    freeze_manifest, freeze_days = validate_freeze(freeze_root, request)
    parser = Parser()
    all_payout_rows: list[dict[str, Any]] = []
    all_finish_rows: list[dict[str, Any]] = []
    day_files: dict[str, Any] = {}
    source: dict[str, Any] = {}

    for day in EXPECTED_DATES:
        hjc_zip, sed_zip, _ = validate_raw_day(raw_root, day, request["results"][day])
        hjc_map = parse_hjc(hjc_zip, day, parser)
        sed_map = parse_sed(sed_zip, day, parser)
        day_payload, payout_rows, finish_rows = settle_day(day, freeze_days[day], hjc_map, sed_map)
        day_payload["source"] = {
            "freeze_day_file_sha256": (freeze_manifest["day_files"][day])["sha256"],
            "raw_run_id": int(request["results"][day]["run_id"]),
            "raw_artifact_name": request["results"][day]["artifact_name"],
            "hjc_sha256": request["results"][day]["hjc_sha256"],
            "sed_sha256": request["results"][day]["sed_sha256"],
        }
        out_name = f"RaceNote_v1_1_Polarity_Gated_{day}_SETTLEMENT.json"
        out_path = output_root / "settlement_runs" / out_name
        day_sha = dump_json(out_path, day_payload)
        day_files[day] = {"file": out_name, "sha256": day_sha, "races": 36, "sed_rows": len(finish_rows)}
        source[day] = day_payload["source"]
        all_payout_rows.extend(payout_rows)
        all_finish_rows.extend(finish_rows)

    require(len(all_payout_rows) == 108, "expected 108 payout cache rows")
    payout_name = "RaceNote_v1_1_Polarity_Gated_20260704_25_26_HJC_Payouts.csv"
    payout_sha = write_csv(
        output_root / "result_cache" / payout_name,
        all_payout_rows,
        ("date", "venue", "race_no", "race_key_raw", *WAGERS),
    )
    finish_name = "RaceNote_v1_1_Polarity_Gated_20260704_25_26_SED_Finish.csv"
    finish_sha = write_csv(
        output_root / "result_cache" / finish_name,
        all_finish_rows,
        ("date", "venue", "race_no", "race_key_raw", "horse_no", "horse_name", "finish_position", "abnormality_code", "sed_record_sha256"),
    )

    manifest = {
        "status": "SETTLED_AFTER_FREEZE",
        "request_id": request["request_id"],
        "settlement_runner_version": VERSION,
        "run_id": int(run_id),
        "head_sha": head_sha,
        "freeze": {
            "freeze_commit": request["freeze"]["freeze_commit"],
            "manifest_sha256": request["freeze"]["manifest_sha256"],
            "combined_canonical_payload_sha256": request["freeze"]["combined_canonical_payload_sha256"],
        },
        "sources": source,
        "day_files": day_files,
        "result_cache": {
            "hjc_payouts": {"file": payout_name, "sha256": payout_sha, "rows": len(all_payout_rows)},
            "sed_finish": {"file": finish_name, "sha256": finish_sha, "rows": len(all_finish_rows)},
        },
        "audit": {
            "race_count": 108,
            "policies": list(POLICIES),
            "aggregate_model_metrics_computed": False,
            "prediction_freeze_modified": False,
        },
    }
    manifest_path = output_root / "settlement_runs" / "RaceNote_v1_1_Polarity_Gated_20260704_25_26_SETTLEMENT_MANIFEST.json"
    manifest_sha = dump_json(manifest_path, manifest)
    result = {
        "status": "success", "request_id": request["request_id"], "run_id": int(run_id), "head_sha": head_sha,
        "settlement_manifest_sha256": manifest_sha, "race_count": 108,
        "day_files": day_files, "result_cache": manifest["result_cache"],
        "aggregate_model_metrics_computed": False,
    }
    dump_json(output_root / "result.json", result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--request-json", type=Path, required=True)
    ap.add_argument("--freeze-root", type=Path, required=True)
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--head-sha", required=True)
    args = ap.parse_args()
    try:
        result = run(args.request_json, args.freeze_root, args.raw_root, args.output_root, run_id=args.run_id, head_sha=args.head_sha)
    except Exception as exc:
        print(json.dumps({"status": "failure", "failure_class": "DOMAIN_VALIDATION_FAILED", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
