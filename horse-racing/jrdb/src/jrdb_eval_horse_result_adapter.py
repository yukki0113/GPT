#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Eval horse-result policy over the common JRDB Raw projection."""
from __future__ import annotations

from collections.abc import Mapping

from jrdb_eval_raw_adapter import parse_sed_horse_eval


def project_eval_horse_result(
    raw: bytes,
    venue_labels: Mapping[str, str],
    abnormality_labels: Mapping[str, str],
) -> dict[str, object]:
    """Return the legacy Eval horse-result row except source provenance fields."""
    base = parse_sed_horse_eval(raw)
    race_no = base.get("race_no")
    horse_no = base.get("horse_no")
    finish_position = base.get("finish_position")
    abnormality_code = str(base.get("abnormality_code") or "")

    if race_no is None:
        raise ValueError("SED race_no is blank")
    if horse_no is None:
        raise ValueError("SED horse_no is blank")
    if abnormality_code == "":
        raise ValueError("SED abnormality_code is blank")
    if abnormality_code not in abnormality_labels:
        raise ValueError(f"unknown SED abnormality_code={abnormality_code!r}")

    finish_position_raw: int | str = ""
    finish_position_eval: int | str = ""
    in_top3 = ""
    review_required = 0
    review_reason = ""

    if finish_position is not None:
        finish_position_raw = int(finish_position)

    if abnormality_code == "0":
        if finish_position is None or int(finish_position) <= 0:
            raise ValueError(f"normal SED row has invalid finish position: {finish_position!r}")
        finish_position_int = int(finish_position)
        finish_position_eval = finish_position_int if finish_position_int <= 3 else 4
        in_top3 = "○" if finish_position_int <= 3 else "×"
    else:
        review_required = 1
        review_reason = (
            "SED異常区分のため台帳着順を自動確定しない: "
            + abnormality_labels[abnormality_code]
        )

    venue_code = str(base["venue_code"])
    return {
        "race_date": base["race_date"],
        "venue_code": venue_code,
        "venue_name": venue_labels.get(venue_code, ""),
        "race_no": int(race_no),
        "horse_no": int(horse_no),
        "horse_name": base["horse_name"],
        "blood_registration_no": base["blood_registration_no"],
        "finish_position_raw": finish_position_raw,
        "finish_position_eval": finish_position_eval,
        "abnormality_code": abnormality_code,
        "abnormality_label": abnormality_labels[abnormality_code],
        "review_required": review_required,
        "review_reason": review_reason,
        "in_top3": in_top3,
        "place_payout": base["place_payout"],
        "final_place_odds_lower": base["final_place_odds_lower"],
        "final_place_odds_upper": "",
    }
