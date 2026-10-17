#!/usr/bin/env python3
"""Light pre-Freeze quality guard for RaceNote v0.5.5 lean Decision Core."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

GATE_VERSION = "racenote-v055-authoring-quality-gate-0.3"

_EVIDENCE = re.compile(
    r"(?:IDM|RRDB|SRB|KYI|上がり|先行|差し|逃げ|追込|調教|状態|"
    r"馬場|時計|距離|同距離|短縮|延長|前走|直近|休み明け|好位|"
    r"芝|ダート|障害|着差|ペース|末脚|位置取り|持続力|クラス|"
    r"昇級|勝ち|連勝|[0-9０-９]+(?:m|ｍ|着|走|秒|馬身|kg|キロ))"
)
_GENERIC = (
    "勝ち切り評価で最上位",
    "総合的に最上位",
    "展開が向けば勝てる",
    "相手なりに走れる",
)
_MARKER = re.compile(r"[0-9０-９]+")


def _normal(text: str) -> str:
    return re.sub(r"\s+", "", _MARKER.sub("#", text))


def inspect(cores: list[dict], *, strict: bool = True) -> dict:
    errors: list[str] = []
    prose_seen: list[tuple[str, str]] = []
    counts = {
        "honmei_win_specificity_pass": 0,
        "risk_specificity_pass": 0,
        "boundary_specificity_pass": 0,
        "shot_specificity_pass": 0,
        "reader_facing_reason_safety_pass": 0,
        "reader_facing_translation_pass": 0,
        "reader_internal_term_violations": 0,
        "template_similarity_violations": 0,
    }
    for core in cores:
        label = f"{core.get('venue')}:{core.get('race_no')}"
        honmei = core.get("honmei_win") or {}
        evidence = str(honmei.get("evidence") or "")
        risk = str(honmei.get("main_risk") or "")
        if len(evidence.strip()) >= 18 and _EVIDENCE.search(evidence) and not any(x in evidence for x in _GENERIC):
            counts["honmei_win_specificity_pass"] += 1
        else:
            errors.append(f"{label} honmei_win.evidence: generic or insufficiently specific")

        if len(risk.strip()) >= 10 and not any(x in risk for x in _GENERIC):
            counts["risk_specificity_pass"] += 1
        else:
            errors.append(f"{label} honmei_win.main_risk: generic or too short")

        sel = core.get("candidate_selection") or {}
        if sel.get("decision") == "NO_EXTERNAL_CHALLENGER":
            counts["boundary_specificity_pass"] += 1
        else:
            reason = str(sel.get("boundary_reason") or "")
            if len(reason.strip()) >= 16 and _EVIDENCE.search(reason):
                counts["boundary_specificity_pass"] += 1
            else:
                errors.append(f"{label} candidate_selection.boundary_reason: insufficiently specific")

        shot = str((core.get("shot_case") or {}).get("case") or "")
        if len(shot.strip()) >= 12 and _EVIDENCE.search(shot) and not any(x in shot for x in _GENERIC):
            counts["shot_specificity_pass"] += 1
        else:
            errors.append(f"{label} shot_case.case: generic or insufficiently specific")

        prose = str(core.get("reader_facing_reason") or "").strip()
        safe = 12 <= len(prose) <= 240 and "\n" not in prose
        norm = _normal(prose)
        for prev_label, prev in prose_seen:
            if len(norm) >= 18 and SequenceMatcher(None, norm, prev).ratio() >= 0.94:
                errors.append(f"{label} reader_facing_reason: near duplicate of {prev_label}")
                counts["template_similarity_violations"] += 1
                safe = False
                break
        prose_seen.append((label, norm))
        if safe:
            counts["reader_facing_reason_safety_pass"] += 1
        else:
            errors.append(f"{label} reader_facing_reason: operational prose accident")

    n = len(cores)
    valid = not errors and all(
        counts[k] == n for k in (
            "honmei_win_specificity_pass", "risk_specificity_pass",
            "boundary_specificity_pass", "shot_specificity_pass",
            "reader_facing_reason_safety_pass",
        )
    )
    return {
        "gate_version": GATE_VERSION,
        "status": "PASS" if valid else "FAIL",
        "race_count": n,
        **counts,
        "violations": errors,
    }


def require_pass(cores: list[dict]) -> dict:
    report = inspect(cores)
    if report["status"] != "PASS":
        raise ValueError("authoring quality gate FAIL: " + "; ".join(report["violations"][:8]))
    return report
