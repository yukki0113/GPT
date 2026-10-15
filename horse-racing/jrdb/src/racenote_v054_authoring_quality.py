#!/usr/bin/env python3
"""Deterministic, fail-closed pre-Freeze authoring quality gate for v0.5.4 r2.

Heuristics detect generic text and repetition; they cannot certify factual
support or genuine model provenance. Human review remains necessary.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

GATE_VERSION = "racenote-v054-authoring-quality-gate-0.1"
_EVIDENCE = re.compile(
    r"(?:[0-9０-９]+(?:m|ｍ|メートル|着|番手|走|秒|馬身|kg|キロ|ポイント|pt|F)|"
    r"IDM|ＲＲＤＢ|RRDB|SRB|KYI|上がり|脚質|先行|差し|逃げ|追込|"
    r"調教|追い切り|馬場|時計|持ち時計|距離|同距離|短縮|延長|"
    r"前走|近[１２３四五六]走|直近|休み明け|好位|枠順|不良|重馬場|"
    r"良馬場|阪神|東京|京都|中山|中京|新潟|小倉|福島|札幌|函館|"
    r"芝|ダート|障害|連対|着差|ペース|ハイペース|スロー|末脚|"
    r"長く脚|位置取り|加速|持続力|道悪|馬体重|クラス|昇級|降級)"
)
_BANNED = (
    "主線二頭に次ぐ能力・条件適性",
    "展開が噛み合えば圏内に届く余地",
    "五頭目を明確に上回る直接材料が不足",
    "勝ち切り評価で最上位",
)
_COMPARE = re.compile(r"(?:一方|対し|比べ|より|上回|劣|優先|差|反面|ただし|対抗|対比|対照)")
_MARKER = re.compile(r"[0-9０-９]+")
_FIELDS = ("mainline_cases", "boundary_review.reason", "candidate_compression.reason",
           "candidate_compression.external_challenger_case", "role_assignment.ranking_reason",
           "reader_facing_reason")

def _normal(text: str) -> str:
    return re.sub(r"\s+", "", _MARKER.sub("#", text))

def _texts(core: dict):
    for i, item in enumerate(core.get("mainline_cases", [])):
        yield f"mainline_cases[{i}].case", str(item.get("case") or "")
    for path in ("single_shot_case.case", "boundary_review.reason",
                 "candidate_compression.reason", "candidate_compression.external_challenger_case",
                 "role_assignment.honmei_win_case", "role_assignment.second_case",
                 "role_assignment.ranking_reason", "reader_facing_reason"):
        obj = core
        for part in path.split("."):
            obj = obj.get(part, {}) if isinstance(obj, dict) else {}
        yield path, str(obj or "")

def inspect(cores: list[dict], *, strict: bool = True) -> dict:
    """Return deterministic daily quality report, without modifying cores."""
    errors = []
    seen = {}
    counts = {"race_specific_case_count": 0, "generic_case_count": 0,
              "template_similarity_violations": 0, "boundary_specificity_pass": 0,
              "ranking_comparison_specificity_pass": 0,
              "reader_facing_reason_quality_pass": 0}
    for core in cores:
        label = f"{core.get('venue')}:{core.get('race_no')}"
        paths = dict(_texts(core))
        case_ok = True
        for path, value in paths.items():
            if path == "candidate_compression.external_challenger_case" and core.get("candidate_compression", {}).get("decision") == "NO_EXTERNAL_CHALLENGER":
                continue
            if path != "reader_facing_reason" and (len(value.strip()) < 15 or not _EVIDENCE.search(value) or any(b in value for b in _BANNED)):
                errors.append(f"{label} {path}: generic or unsupported-specificity candidate")
                counts["generic_case_count"] += 1
                case_ok = False
            if path in _FIELDS or path.startswith("mainline_cases["):
                normalized = _normal(value)
                if len(normalized) >= 18:
                    for previous_label, previous in seen.get(path.split("[")[0], []):
                        if SequenceMatcher(None, normalized, previous).ratio() >= 0.92:
                            errors.append(f"{label} {path}: near duplicate of {previous_label}")
                            counts["template_similarity_violations"] += 1
                            break
                    seen.setdefault(path.split("[")[0], []).append((label, normalized))
        if case_ok:
            counts["race_specific_case_count"] += 1
        comp = core.get("candidate_compression", {})
        boundary = paths["boundary_review.reason"]
        ordinary = comp.get("ordinary_five") or []
        anchors = {core.get("role_assignment", {}).get("honmei_horse_no"), core.get("role_assignment", {}).get("second_horse_no")}
        boundary_horse = next((horse for horse in reversed(ordinary) if horse not in anchors), None)
        # Five-runner races have no external horse to compare.
        if comp.get("decision") == "NO_EXTERNAL_CHALLENGER":
            counts["boundary_specificity_pass"] += 1
        elif (_COMPARE.search(boundary) and len(boundary) >= 35
              and re.search(rf"(?<![0-9]){comp.get('external_challenger_horse_no')}番(?![0-9])", boundary) is not None
              and re.search(rf"(?<![0-9]){boundary_horse}番(?![0-9])", boundary) is not None
              and _EVIDENCE.search(boundary)):
            counts["boundary_specificity_pass"] += 1
        else:
            errors.append(f"{label} boundary_review.reason: no concrete challenger/boundary comparison")
        ranking = paths["role_assignment.ranking_reason"]
        role = core.get("role_assignment", {})
        if (_COMPARE.search(ranking) and _EVIDENCE.search(ranking)
            and str(role.get("honmei_horse_no")) in ranking
            and str(role.get("second_horse_no")) in ranking):
            counts["ranking_comparison_specificity_pass"] += 1
        else:
            errors.append(f"{label} role_assignment.ranking_reason: comparative evidence missing")
        prose = paths["reader_facing_reason"]
        sentences = [x for x in re.split(r"[。！？]", prose) if x.strip()]
        if (2 <= len(sentences) <= 3 and 85 <= len(prose) <= 175
            and _EVIDENCE.search(prose) and _COMPARE.search(prose)
            and not any(b in prose for b in _BANNED)):
            counts["reader_facing_reason_quality_pass"] += 1
        else:
            errors.append(f"{label} reader_facing_reason: specific 2-3 sentence comparison missing")
    n = len(cores)
    valid = (not errors and counts["generic_case_count"] == 0
             and counts["template_similarity_violations"] == 0
             and all(counts[field] == n for field in (
                 "race_specific_case_count", "boundary_specificity_pass",
                 "ranking_comparison_specificity_pass", "reader_facing_reason_quality_pass")))
    return {"gate_version": GATE_VERSION, "status": "PASS" if valid else "FAIL",
            "race_count": n, **counts, "violations": errors}

def require_pass(cores: list[dict]) -> dict:
    report = inspect(cores)
    if report["status"] != "PASS":
        raise ValueError("authoring quality gate FAIL: " + "; ".join(report["violations"][:8]))
    return report
