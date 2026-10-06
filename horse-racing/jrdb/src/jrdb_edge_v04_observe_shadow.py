#!/usr/bin/env python3
"""Pre-result cohort matching, freeze validation, and post-result observation.

Input JSONL is an adapter contract: facts must be normal JRDB pre-race feature
values keyed by the canonical Edge v0.4 dimension names. Result JSONL is
produced only after a PASS freeze through the normal post-result route.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path

from jrdb_edge_v04_observe_cohort import ALLOWED, canonical_bytes, fingerprint, validate as validate_cohort

LEAK = frozenset("result settlement payout payback return odds popularity market label_win_hit label_place_hit label_win_payout label_place_payout win_hit place_hit win_payout place_payout finish_position rank win_roi place_roi".split())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_jsonl(path, rows):
    Path(path).write_bytes(b"".join(canonical_bytes(r) + b"\n" for r in rows))


def no_leak(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            low = key.lower()
            if low in LEAK or low.startswith("label_") or "payout" in low or "result" in low or "settlement" in low:
                raise ValueError("result/market field in pre-race freeze: " + key)
            no_leak(value)
    elif isinstance(obj, list):
        for value in obj:
            no_leak(value)


def no_result_fields(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            low = key.lower()
            if low.startswith("label_") or "payout" in low or "result" in low or "settlement" in low or low in {"win_hit", "place_hit", "finish_position", "rank"}:
                raise ValueError("result field in pre-race source: " + key)
            no_result_fields(value)
    elif isinstance(obj, list):
        for value in obj:
            no_result_fields(value)


def match_day(cohort, facts, target_date, asof, source_identity):
    validate_cohort(cohort)
    if not source_identity.get("sha256"):
        raise ValueError("pre-race source SHA required")
    at = dt.datetime.fromisoformat(asof.replace("Z", "+00:00"))
    if at.tzinfo is None or at.date().isoformat() != target_date:
        raise ValueError("as-of must be dated, timezone-aware, and on target day")
    seen = set()
    matches = []
    for item in sorted(facts, key=lambda x: (x["race_id"], x["horse_id"])):
        required = {"race_date", "race_id", "horse_id", "facts", "source"}
        if not required <= set(item) or item["race_date"] != target_date:
            raise ValueError("invalid pre-race fact identity")
        key = (item["race_id"], item["horse_id"])
        if key in seen:
            raise ValueError("duplicate horse facts")
        seen.add(key)
        no_result_fields(item)
        no_leak({k: v for k, v in item.items() if k != "market"})
        if not isinstance(item["facts"], dict) or set(item["facts"]) - ALLOWED:
            raise ValueError("noncanonical fact dimension")
        for row in cohort["rows"]:
            # C1 compares PyArrow-cast strings; absent/null values never match.
            if all(item["facts"].get(c["feature"]) is not None and str(item["facts"][c["feature"]]) == c["value"] for c in row["conditions"]):
                matches.append({"race_date": target_date, "race_id": item["race_id"], "horse_id": item["horse_id"],
                                "cohort_id": row["cohort_id"], "family": row["family"], "candidate_id": row["candidate_id"],
                                "matched_conditions": row["conditions"], "match_asof": asof,
                                "fact_provenance": item["source"], "result_opened": False, "market_used_for_match": False})
    matches.sort(key=lambda x: (x["race_id"], x["horse_id"], x["cohort_id"]))
    return matches, {"race_count": len({r["race_id"] for r in facts}), "horse_count": len(facts)}


def freeze(cohort_path, fact_path, target_date, asof, source_identity, out_dir):
    cohort = json.loads(Path(cohort_path).read_text())
    facts = read_jsonl(fact_path)
    if digest(fact_path) != source_identity["sha256"]:
        raise ValueError("source hash mismatch")
    matches, counts = match_day(cohort, facts, target_date, asof, source_identity)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    match_path = out / "matches.jsonl"
    write_jsonl(match_path, matches)
    manifest = {"schema_version": "observe-only-freeze/v0.1", "target_date": target_date,
                "freeze_at": asof, "cohort_version": cohort["schema_version"], "cohort_sha256": digest(cohort_path),
                "cohort_fingerprint_set_sha256": cohort["fingerprint_set_sha256"],
                "pre_race_sources": [source_identity], **counts, "raw_match_count": len(matches),
                "unique_matched_horse_count": len({(m["race_id"], m["horse_id"]) for m in matches}),
                "family_match_counts": dict(sorted(Counter(m["family"] for m in matches).items())),
                "no_result_leakage": "PASS", "match_output_sha256": digest(match_path),
                "production_impact": "NONE"}
    validate_freeze(manifest, matches, cohort)
    (out / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


def validate_freeze(manifest, matches, cohort):
    validate_cohort(cohort)
    ids = {r["cohort_id"]: r for r in cohort["rows"]}
    if manifest["no_result_leakage"] != "PASS" or manifest["cohort_fingerprint_set_sha256"] != cohort["fingerprint_set_sha256"] or manifest["raw_match_count"] != len(matches):
        raise ValueError("freeze manifest mismatch")
    if manifest["unique_matched_horse_count"] != len({(m["race_id"], m["horse_id"]) for m in matches}) or manifest["family_match_counts"] != dict(sorted(Counter(m["family"] for m in matches).items())):
        raise ValueError("freeze counts changed")
    for m in matches:
        no_leak({k: v for k, v in m.items() if k not in {"result_opened", "market_used_for_match"}})
        row = ids.get(m["cohort_id"])
        if not row or m["candidate_id"] != row["candidate_id"] or m["family"] != row["family"] or m["matched_conditions"] != row["conditions"]:
            raise ValueError("match is outside frozen membership")
        if m["result_opened"] is not False or m["market_used_for_match"] is not False or m["race_date"] != manifest["target_date"] or m["match_asof"] != manifest["freeze_at"]:
            raise ValueError("pre-result invariant failed")


def metric(rows):
    n = len(rows)
    if not n:
        return {"n": 0}
    wins = sum(bool(r["win_hit"]) for r in rows)
    places = sum(bool(r["place_hit"]) for r in rows)
    out = {"n": n, "win_hits": wins, "place_hits": places,
           "win_rate": wins / n, "place_rate": places / n,
           "distinct_race_days": len({r["race_date"] for r in rows}),
           "distinct_races": len({(r["race_date"], r["race_id"]) for r in rows}),
           "context_counts": {k: dict(sorted(Counter(str(r.get(k)) for r in rows).items())) for k in ("venue_code", "race_class", "surface_code", "distance_m")},
           "race_day_hits": {d: {"win": sum(bool(r["win_hit"]) for r in rows if r["race_date"] == d), "place": sum(bool(r["place_hit"]) for r in rows if r["race_date"] == d)} for d in sorted({r["race_date"] for r in rows})},
           "market_popularity_diagnostic": {"popularity": dict(sorted(Counter(str(r.get("popularity")) for r in rows).items()))}}
    for lane in ("win", "place"):
        payouts = sorted((float(r[lane + "_payout"]) for r in rows), reverse=True)
        total = sum(payouts)
        out[lane + "_roi"] = total / n
        out[lane + "_top1_contribution"] = payouts[0] / total if total else None
        out[lane + "_roi_ex_top1"] = (total - sum(payouts[:1])) / n
        out[lane + "_roi_ex_top3"] = (total - sum(payouts[:3])) / n
        out[lane + "_top3_contribution"] = sum(payouts[:3]) / total if total else None
    return out


def evaluate(manifest_paths, result_path, opened_at, result_source):
    if not result_source or "JRDB" not in result_source.upper():
        raise ValueError("normal JRDB result source required")
    result_rows = read_jsonl(result_path)
    result_map = {}
    for r in result_rows:
        key = (r["race_date"], r["race_id"], r["horse_id"])
        if key in result_map:
            raise ValueError("duplicate result identity")
        result_map[key] = r
    joined = []
    for path in manifest_paths:
        p = Path(path)
        manifest = json.loads(p.read_text())
        match_path = p.with_name("matches.jsonl")
        if manifest.get("no_result_leakage") != "PASS" or manifest.get("production_impact") != "NONE":
            raise ValueError("freeze has not passed validation")
        if digest(match_path) != manifest["match_output_sha256"] or dt.datetime.fromisoformat(opened_at.replace("Z", "+00:00")) <= dt.datetime.fromisoformat(manifest["freeze_at"].replace("Z", "+00:00")):
            raise ValueError("results cannot be opened before PASS freeze")
        for m in read_jsonl(match_path):
            no_leak({k: v for k, v in m.items() if k in {"fact_provenance", "matched_conditions"}})
            key = (m["race_date"], m["race_id"], m["horse_id"])
            if key not in result_map:
                raise ValueError("missing matched-horse result")
            joined.append({**result_map[key], "family": m["family"], "cohort_id": m["cohort_id"]})
    def unique(rows):
        return list({(r["race_date"], r["race_id"], r["horse_id"]): r for r in rows}.values())
    families = sorted({r["family"] for r in joined})
    cohorts = sorted({r["cohort_id"] for r in joined})
    days = sorted({r["race_date"] for r in joined})
    return {"status": "TRUE_FORWARD_OBSERVATION_RECORDED", "result_source": result_source,
            "results_opened_at": opened_at, "raw_match_view": metric(joined),
            "unique_horse_view": metric(unique(joined)),
            "by_family": {k: {"raw": metric([r for r in joined if r["family"] == k]), "unique": metric(unique([r for r in joined if r["family"] == k]))} for k in families},
            "by_cohort_id": {k: metric([r for r in joined if r["cohort_id"] == k]) for k in cohorts},
            "by_race_day": {k: {"raw": metric([r for r in joined if r["race_date"] == k]), "unique": metric(unique([r for r in joined if r["race_date"] == k]))} for k in days},
            "overlapping_roi_not_additive": True, "production_impact": "NONE"}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    m = sub.add_parser("freeze")
    for arg in ("cohort", "facts", "target-date", "asof", "source-id", "output-dir"):
        m.add_argument("--" + arg, required=True)
    v = sub.add_parser("validate")
    v.add_argument("--cohort", required=True)
    v.add_argument("--manifest", required=True)
    e = sub.add_parser("evaluate")
    e.add_argument("--manifest", action="append", required=True)
    e.add_argument("--results", required=True)
    e.add_argument("--results-opened-at", required=True)
    e.add_argument("--result-source", required=True)
    e.add_argument("--output", required=True)
    a = p.parse_args()
    if a.command == "freeze":
        result = freeze(a.cohort, a.facts, a.target_date, a.asof,
                        {"source_id": a.source_id, "sha256": digest(a.facts)}, a.output_dir)
    elif a.command == "validate":
        manifest = json.loads(Path(a.manifest).read_text())
        cohort = json.loads(Path(a.cohort).read_text())
        match_path = Path(a.manifest).with_name("matches.jsonl")
        if digest(a.cohort) != manifest["cohort_sha256"] or digest(match_path) != manifest["match_output_sha256"]:
            raise ValueError("frozen bytes changed")
        validate_freeze(manifest, read_jsonl(match_path), cohort)
        result = {"status": "PASS"}
    else:
        result = evaluate(a.manifest, a.results, a.results_opened_at, a.result_source)
        Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
