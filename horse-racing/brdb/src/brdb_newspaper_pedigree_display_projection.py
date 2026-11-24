#!/usr/bin/env python3
"""Project private BRDB going/relative research into Newspaper pedigree display candidates.

This does not mutate Newspaper JSON. It emits a private research projection that
matches the optional UI contract used by PR #2643. No score, rank, probability,
fit verdict, mark, RaceNote confidence, or purchase recommendation is produced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DISPLAY_VERSION = "brdb-newspaper-pedigree-display-v0.1-candidate"
PROJECTION_VERSION = "brdb-newspaper-pedigree-display-projection-v0.1-candidate"
V06_VERSION = "brdb-going-multilane-discovery-v0.6-candidate"
REL_VERSION = "brdb-m7-relatives-detail-v0.1-candidate"
NON_GOOD = ("稍重", "重", "不良")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha256_bytes(*chunks: bytes) -> str:
    h = hashlib.sha256()
    for chunk in chunks:
        h.update(chunk)
    return h.hexdigest()


def _status(starts: int) -> str:
    return "AVAILABLE" if starts > 0 else "NO_SAMPLE"


def _primary_records(horse: dict) -> list[dict]:
    rows = []
    for lane_name in ("sire", "broodmare_sire", "pairing"):
        lane = (horse.get("lanes") or {}).get(lane_name) or {}
        by_state = lane.get("primary_by_state") or {}
        for state in NON_GOOD:
            p = by_state.get(state)
            if not p:
                continue
            # Recover the full comparison row by evidence_id.
            full = None
            for scope in lane.get("scopes") or []:
                for comp in scope.get("state_comparisons") or []:
                    if comp.get("evidence_id") == p.get("evidence_id"):
                        full = comp
                        break
                if full:
                    break
            require(full is not None, "primary comparison detail missing")
            counts = full.get("state_counts") or {}
            starts, wins, top3 = counts.get("starts"), counts.get("wins"), counts.get("top3")
            require(all(type(x) is int for x in (starts, wins, top3)), "comparison counts invalid")
            require(0 <= wins <= top3 <= starts, "comparison counts inconsistent")
            rows.append({
                "label": f"{lane_name}:{state}:{p.get('scope_key')}",
                "starts": starts,
                "wins": wins,
                "top3": top3,
                "status": _status(starts),
                "source_label": f"BRDB v0.6 {p.get('tier')} / {p.get('direction')} / observation only",
            })
    return rows


def _relative_rows(relative_row: dict) -> list[dict]:
    out = []
    for rel in relative_row.get("relatives") or []:
        relation = rel.get("relationship")
        name = rel.get("horse_name")
        stats = rel.get("scope_stats") or {}
        scopes = ("VENUE_COURSE_EXACT", "VENUE_DISTANCE", "VENUE_BAND",
                  "ALL_VENUES_DISTANCE", "ALL_VENUES_BAND")
        require(set(stats) == set(scopes), "relative scope set mismatch")
        parts = []
        for scope in scopes:
            cell = stats[scope]
            require(isinstance(cell, dict), "relative scope invalid")
            starts, wins, top3 = (cell.get(k) for k in ("starts", "wins", "top3"))
            require(all(type(x) is int for x in (starts, wins, top3)), "relative counts invalid")
            require(0 <= wins <= top3 <= starts, "relative counts inconsistent")
            parts.append(f"{scope}: {starts}走・3着以内{top3}回" if starts
                         else f"{scope}: 該当出走なし")
        note = " / ".join(parts) + "（scope重複あり・合算不可 / 馬場状態未確認 / historical as-of未検証）"
        out.append({
            "name": name,
            "relationship": relation,
            "note": note,
        })
    return out


def build(v06: dict, relatives: dict, source_sha256: str) -> dict:
    require(v06.get("contract_version") == V06_VERSION, "v0.6 contract")
    require(v06.get("release_status") == "RESEARCH_ONLY", "v0.6 release")
    policy = v06.get("policy") or {}
    require(policy.get("prediction_safe") is False, "v0.6 prediction flag")
    require(policy.get("production_authorized") is False, "v0.6 production flag")
    require(policy.get("display_authorized") is False, "v0.6 display flag")

    require(relatives.get("contract_version") == REL_VERSION, "relative detail contract")
    require(relatives.get("research_only") is True, "relative research flag")
    require(relatives.get("prediction_safe") is False, "relative prediction flag")
    require(relatives.get("historical_asof_status") == "AS_OF_UNVERIFIED", "relative as-of flag")

    race = v06.get("race") or {}
    race_key = race.get("race_key")
    target_date = race.get("target_date")
    require(isinstance(race_key, str) and len(race_key) == 8 and race_key.isdigit(), "race key")
    require((relatives.get("source_metadata") or {}).get("as_of_exclusive") == target_date, "relative as-of mismatch")

    vh = v06.get("horses")
    rh = relatives.get("horses")
    require(isinstance(vh, list) and isinstance(rh, list), "horse rows missing")
    require(len(vh) == len(rh) == race.get("field_size"), "cohort size mismatch")

    rel_by_key = {}
    for row in rh:
        key = (row.get("horse_no"), row.get("horse_id"))
        require(key not in rel_by_key, "duplicate relative identity")
        rel_by_key[key] = row

    projected = []
    seen = set()
    for horse in vh:
        key = (horse.get("horse_no"), horse.get("horse_id"))
        require(key not in seen, "duplicate v0.6 identity")
        seen.add(key)
        require(key in rel_by_key, "relative identity mismatch")
        require(isinstance(key[0], int) and key[0] >= 1, "horse no")
        require(isinstance(key[1], str) and len(key[1]) == 8 and key[1].isdigit(), "horse id")
        projected.append({
            "contract_version": DISPLAY_VERSION,
            "release_status": "RESEARCH_PREVIEW_ONLY",
            "research_only": True,
            "prediction_safe": False,
            "production_authorized": False,
            "as_of_status": "AS_OF_UNVERIFIED",
            "race_key": race_key,
            "horse_no": key[0],
            "horse_id": key[1],
            "source_sha256": source_sha256,
            "score": None,
            "rank": None,
            "probability": None,
            "crosses": [],
            "condition_records": _primary_records(horse),
            "reviews": [],
            "relatives": _relative_rows(rel_by_key[key]),
            "tips": [],
        })

    require(set(rel_by_key) == seen, "relative cohort mismatch")
    return {
        "projection_version": PROJECTION_VERSION,
        "release_status": "PRIVATE_RESEARCH_PREVIEW_ONLY",
        "race_key": race_key,
        "target_date": target_date,
        "horse_count": len(projected),
        "source_sha256": source_sha256,
        "policy": {
            "prediction_safe": False,
            "production_authorized": False,
            "newspaper_mutation_authorized": False,
            "pwa_publication_authorized": False,
            "natural_language_review_authorized": False,
            "fit_verdict_authorized": False,
            "betting_recommendation_authorized": False,
        },
        "horses": projected,
    }


def run(v06_path: Path, relative_path: Path, output_path: Path) -> dict:
    v06_bytes = v06_path.read_bytes()
    rel_bytes = relative_path.read_bytes()
    source_sha = sha256_bytes(v06_bytes, b"\0", rel_bytes)
    result = build(
        json.loads(v06_bytes.decode("utf-8")),
        json.loads(rel_bytes.decode("utf-8")),
        source_sha,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v06-input", required=True)
    ap.add_argument("--relative-detail", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    result = run(Path(a.v06_input), Path(a.relative_detail), Path(a.output))
    print(json.dumps({
        "status": result["release_status"],
        "horse_count": result["horse_count"],
        "output": "PRIVATE_NOT_FOR_GIT_OR_PUBLIC_ARTIFACT",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
