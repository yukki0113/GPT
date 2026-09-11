#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapt JRDB Edge matcher output for Newspaper ``特注メモ`` consumption.

The adapter is intentionally a display boundary. It never re-evaluates Edge
conditions, aggregates strength, or converts ROI into a score. Exact matcher
output is validated and normalized so the Newspaper layer can join it by
``race_key + race_horse_key + horse_no`` and render only the currently allowed
serving subset.

Current matcher compatibility:
- ``status`` is accepted as the legacy spelling of ``registry_status``.
- ``evidence.performance_signal`` is accepted when future top-level evidence
  fields are not present.
- Missing future fields remain ``None``; they are not silently fabricated.
- Legacy machine-oriented ``display_text`` is translated only at this display
  boundary from the already-published structured conditions. Matching itself
  is never repeated here.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

VERSION = "0.2.1"

ACTIVE_STATUS = "ACTIVE"
DISPLAY_PERFORMANCE_SIGNALS = {"POSITIVE", "NEGATIVE"}
KNOWN_PERFORMANCE_SIGNALS = {"POSITIVE", "NEGATIVE", "NEUTRAL"}
KNOWN_EVIDENCE_LEVELS = {"CONFIRMED", "SUGGESTIVE", "NONE"}
KNOWN_PRESENTATION_ROLES = {"PRIMARY", "SECONDARY", "CONFLICT"}
SIGNED_PREFIXES = ("＋", "+", "－", "-", "−", "±")

VENUE_LABELS = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}
SURFACE_LABELS = {"1": "芝", "2": "ダート", "3": "障害"}
TURN_LABELS = {"1": "右回り", "2": "左回り", "3": "直線"}
FRAME_ZONE_LABELS = {"INNER": "内枠", "MIDDLE": "中枠", "OUTER": "外枠"}
DISTANCE_CHANGE_LABELS = {
    "LARGE_SHORTEN": "大幅距離短縮",
    "SHORTEN": "距離短縮",
    "SAME_BAND": "同距離帯",
    "EXTEND": "距離延長",
    "LARGE_EXTEND": "大幅距離延長",
}
SURFACE_TRANSITION_LABELS = {
    "1->1": "芝継続",
    "1->2": "芝→ダート替わり",
    "2->1": "ダート→芝替わり",
    "2->2": "ダート継続",
}

# JRDB 系統コード表（keito_code）の表示名。突合キー自体は変更しない。
SIRE_LINE_LABELS = {
    "1101": "ノーザンダンサー系",
    "1102": "ニジンスキー系",
    "1103": "ヴァイスリージェント系",
    "1104": "リファール系",
    "1105": "ノーザンテースト系",
    "1106": "ダンジグ系",
    "1107": "ヌレイエフ系",
    "1108": "ストームバード系",
    "1109": "サドラーズウェルズ系",
    "1201": "ロイヤルチャージャー系",
    "1202": "ターントゥ系",
    "1203": "ヘイルトゥリーズン系",
    "1204": "サーゲイロード系",
    "1205": "ハビタット系",
    "1206": "ヘイロー系",
    "1207": "ロベルト系",
    "1301": "ナスルーラ系",
    "1302": "グレイソヴリン系",
    "1303": "ネヴァーベンド系",
    "1304": "プリンスリーギフト系",
    "1305": "ボールドルーラー系",
    "1306": "レッドゴッド系",
    "1307": "ゼダーン系",
    "1308": "カロ系",
    "1309": "ミルリーフ系",
    "1310": "リヴァーマン系",
    "1311": "シアトルスルー系",
    "1312": "ブラッシンググルーム系",
    "1401": "ネアルコ系",
    "1402": "ニアークティック系",
    "1403": "デリングドゥ系",
    "1501": "ネイティヴダンサー系",
    "1502": "シャーペンアップ系",
    "1503": "ミスタープロスペクター系",
    "1601": "フェアウェイ系",
    "1602": "バックパサー系",
    "1603": "ファラリス系",
    "1701": "ダマスカス系",
    "1702": "テディ系",
    "1801": "ハイペリオン系",
    "1802": "オリオール系",
    "1803": "ロックフェラ系",
    "1804": "テューダーミンストレル系",
    "1805": "オーエンテューダー系",
    "1806": "スターキングダム系",
    "1807": "フォルリ系",
    "1901": "エクリプス系",
    "1902": "ブランドフォード系",
    "1903": "ドンカスター系",
    "1904": "ドミノ系",
    "1905": "ヒムヤー系",
    "1906": "エルバジェ系",
    "1907": "ダークロナルド系",
    "1908": "ファイントップ系",
    "1909": "ゲインズボロー系",
    "1910": "ハーミット系",
    "1911": "アイシングラス系",
    "1912": "コングリーヴ系",
    "1913": "ロックサンド系",
    "2001": "セントサイモン系",
    "2002": "リボー系",
    "2003": "ヒズマジェスティ系",
    "2004": "グロースターク系",
    "2005": "トムロルフ系",
    "2006": "ワイルドリスク系",
    "2007": "チャウサー系",
    "2008": "プリンスローズ系",
    "2009": "プリンスキロ系",
    "2010": "ラウンドテーブル系",
    "2101": "マッチェム系",
    "2102": "フェアプレイ系",
    "2103": "ハリーオン系",
    "2104": "マンノウォー系",
    "2105": "インリアリティ系",
    "2201": "パーソロン系",
    "2202": "リュティエ系",
    "2203": "ジェベル系",
    "2204": "トウルビヨン系",
    "2205": "ザテトラーク系",
    "2206": "ヘロド系",
    "2301": "サンドリッジ系",
    "2401": "スウィンフォード系",
    "9901": "アラ系",
}

# field=value 形式に加え、旧表示層が生成した「系統1206」も機械表示扱いにする。
MACHINE_DISPLAY_PATTERN = re.compile(
    r"(?:venue_code|surface_code|distance_m|turn_code|frame_zone|"
    r"sire_line_code|broodmare_sire_line_code|distance_change_bucket|"
    r"surface_transition|frame_transition)=|系統\d+"
)


class NewspaperEdgeAdapterError(ValueError):
    """Raised when Edge matcher input is unsafe or structurally ambiguous."""


def _text(value: Any) -> str | None:
    """Return normalized non-empty text without inventing missing values."""
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized


def _required_text(value: Any, field: str, context: str) -> str:
    """Read a required text value with a useful validation error."""
    normalized = _text(value)
    if normalized is None:
        raise NewspaperEdgeAdapterError(f"{context}: {field} is required")
    return normalized


def _positive_int(value: Any, field: str, context: str) -> int:
    """Read a positive integer identity value."""
    if isinstance(value, bool):
        raise NewspaperEdgeAdapterError(
            f"{context}: {field} must be a positive integer"
        )
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise NewspaperEdgeAdapterError(
            f"{context}: {field} must be a positive integer"
        ) from exc
    if normalized < 1:
        raise NewspaperEdgeAdapterError(
            f"{context}: {field} must be a positive integer"
        )
    return normalized


def _upper_optional(value: Any) -> str | None:
    """Normalize optional enum-like text."""
    normalized = _text(value)
    if normalized is None:
        return None
    return normalized.upper()


def _performance_signal(match: Mapping[str, Any]) -> str | None:
    """Resolve performance direction without using outer mixed polarity."""
    direct = _upper_optional(match.get("performance_signal"))
    if direct is not None:
        return direct

    evidence = match.get("evidence")
    if isinstance(evidence, Mapping):
        nested = _upper_optional(evidence.get("performance_signal"))
        if nested is not None:
            return nested
    return None


def _registry_status(match: Mapping[str, Any]) -> str | None:
    """Resolve future ``registry_status`` with legacy ``status`` fallback."""
    status = _upper_optional(match.get("registry_status"))
    if status is not None:
        return status
    return _upper_optional(match.get("status"))


def _validate_optional_enum(
    value: str | None,
    allowed: set[str],
    field: str,
    context: str,
) -> None:
    """Fail closed when a supplied future enum has unknown semantics."""
    if value is None:
        return
    if value not in allowed:
        raise NewspaperEdgeAdapterError(
            f"{context}: unsupported {field}={value!r}"
        )


def _strip_display_sign(display_text: str) -> str:
    """Remove one leading display sign and surrounding whitespace."""
    stripped = display_text.strip()
    for prefix in SIGNED_PREFIXES:
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return stripped


def _frame_transition_label(value: Any) -> str | None:
    """Translate one canonical frame transition without changing semantics."""
    normalized = _text(value)
    if normalized is None or "->" not in normalized:
        return None
    previous, current = normalized.split("->", 1)
    previous_label = FRAME_ZONE_LABELS.get(previous)
    current_label = FRAME_ZONE_LABELS.get(current)
    if previous_label is None or current_label is None:
        return None
    return f"{previous_label}→{current_label}"


def _conditions_from_match(
    match: Mapping[str, Any],
) -> tuple[str | None, Mapping[str, Any], Mapping[str, Any]]:
    """Return template id, anchor, and modifiers from published evidence."""
    evidence = match.get("evidence")
    if not isinstance(evidence, Mapping):
        return None, {}, {}

    conditions = evidence.get("conditions")
    if not isinstance(conditions, Mapping):
        return _text(evidence.get("template_id")), {}, {}

    template_id = _text(evidence.get("template_id"))
    if template_id is None:
        template_id = _text(conditions.get("template_id"))

    anchor = conditions.get("anchor")
    modifiers = conditions.get("modifiers")
    if not isinstance(anchor, Mapping):
        anchor = {}
    if not isinstance(modifiers, Mapping):
        modifiers = {}
    return template_id, anchor, modifiers


def _sire_subject(anchor: Mapping[str, Any]) -> str | None:
    """Build a sire/sire-line subject from an already-published anchor."""
    sire_name = _text(anchor.get("sire_name"))
    if sire_name is not None:
        return f"{sire_name}産駒"

    sire_line_code = _text(anchor.get("sire_line_code"))
    if sire_line_code is None:
        return None

    sire_line_label = SIRE_LINE_LABELS.get(sire_line_code)
    if sire_line_label is not None:
        return f"父系{sire_line_label}"
    return f"系統{sire_line_code}"


def _distance_label(value: Any) -> str | None:
    """Format a canonical distance as a compact Japanese label."""
    if value is None or value == "":
        return None
    try:
        distance = int(value)
    except (TypeError, ValueError):
        return None
    if distance <= 0:
        return None
    return f"{distance}m"


def _course_anchor_label(anchor: Mapping[str, Any]) -> str | None:
    """Build a human-readable course anchor from published canonical fields."""
    venue = VENUE_LABELS.get(str(anchor.get("venue_code") or "").zfill(2))
    surface = SURFACE_LABELS.get(str(anchor.get("surface_code") or ""))
    distance = _distance_label(anchor.get("distance_m"))
    if venue is None or surface is None or distance is None:
        return None
    return f"{venue}{surface}{distance}"


def _human_condition_text(match: Mapping[str, Any]) -> str | None:
    """Translate known canonical Edge templates into a concise Japanese condition."""
    template_id, anchor, modifiers = _conditions_from_match(match)
    if template_id is None:
        return None

    subject = _sire_subject(anchor)

    if template_id == "COURSE_FRAME_V1":
        course = _course_anchor_label(anchor)
        frame = FRAME_ZONE_LABELS.get(str(modifiers.get("frame_zone") or ""))
        if course is not None and frame is not None:
            return f"{course}の{frame}"
        return None

    if template_id == "SIRE_TURN_DISTANCE_V1":
        turn = TURN_LABELS.get(str(modifiers.get("turn_code") or ""))
        distance = _distance_label(modifiers.get("distance_m"))
        if subject is not None and turn is not None and distance is not None:
            return f"{subject}は{turn}{distance}"
        return None

    if template_id == "SIRE_SURFACE_DISTANCE_V1":
        surface = SURFACE_LABELS.get(str(modifiers.get("surface_code") or ""))
        distance = _distance_label(modifiers.get("distance_m"))
        if subject is not None and surface is not None and distance is not None:
            return f"{subject}は{surface}{distance}"
        return None

    if template_id == "SIRE_LINE_TURN_DISTANCE_V1":
        turn = TURN_LABELS.get(str(modifiers.get("turn_code") or ""))
        distance = _distance_label(modifiers.get("distance_m"))
        if subject is not None and turn is not None and distance is not None:
            return f"{subject}は{turn}{distance}"
        return None

    if template_id == "SIRE_DISTANCE_CHANGE_V1":
        change = DISTANCE_CHANGE_LABELS.get(
            str(modifiers.get("distance_change_bucket") or "")
        )
        if subject is not None and change is not None:
            return f"{subject}は{change}"
        return None

    if template_id == "SIRE_SURFACE_TRANSITION_V1":
        transition = SURFACE_TRANSITION_LABELS.get(
            str(modifiers.get("surface_transition") or "")
        )
        if subject is not None and transition is not None:
            return f"{subject}は{transition}"
        return None

    if template_id == "SIRE_FRAME_TRANSITION_V1":
        transition = _frame_transition_label(modifiers.get("frame_transition"))
        if subject is not None and transition is not None:
            return f"{subject}は{transition}"
        return None

    return None


def _memo_text(
    match: Mapping[str, Any],
    display_text: str,
    performance_signal: str | None,
) -> tuple[str, str]:
    """Build user-facing condition/memo text without re-evaluating an Edge."""
    condition_text = _human_condition_text(match)

    if condition_text is None:
        fallback = _strip_display_sign(display_text)
        condition_text = fallback
        if display_text.lstrip().startswith(SIGNED_PREFIXES):
            return condition_text, display_text
        if performance_signal == "POSITIVE":
            return condition_text, f"＋ {display_text}"
        if performance_signal == "NEGATIVE":
            return condition_text, f"－ {display_text}"
        return condition_text, display_text

    # Existing human-authored display_text remains the publication authority.
    # Translation is used only for the legacy machine-oriented form.
    if not MACHINE_DISPLAY_PATTERN.search(display_text):
        human_display = _strip_display_sign(display_text)
        return human_display, display_text

    if performance_signal == "POSITIVE":
        return condition_text, f"＋ {condition_text}で好走傾向"
    if performance_signal == "NEGATIVE":
        return condition_text, f"－ {condition_text}で苦戦傾向"
    return condition_text, condition_text


def _serving_decision(
    *,
    registry_status: str | None,
    performance_signal: str | None,
    performance_evidence_level: str | None,
    presentation_role: str | None,
) -> tuple[bool, str]:
    """Apply only the Newspaper serving gate, never Edge condition logic."""
    if registry_status != ACTIVE_STATUS:
        return False, "REGISTRY_NOT_ACTIVE"
    if performance_signal not in DISPLAY_PERFORMANCE_SIGNALS:
        return False, "PERFORMANCE_NEUTRAL_OR_MISSING"

    if performance_evidence_level is not None:
        if performance_evidence_level != "CONFIRMED":
            return False, "PERFORMANCE_NOT_CONFIRMED"

    if presentation_role == "SECONDARY":
        return False, "SECONDARY_HIDDEN"

    if performance_evidence_level is None:
        return True, "LEGACY_ACTIVE_PERFORMANCE_SIGNAL"
    return True, "ACTIVE_CONFIRMED"


def normalize_match(match: Mapping[str, Any], *, context: str) -> dict[str, Any]:
    """Normalize one Edge match while retaining future-facing metadata."""
    if not isinstance(match, Mapping):
        raise NewspaperEdgeAdapterError(f"{context}: edge match must be an object")

    edge_id = _required_text(match.get("edge_id"), "edge_id", context)
    display_text = _required_text(match.get("display_text"), "display_text", context)
    registry_status = _registry_status(match)
    performance_signal = _performance_signal(match)
    performance_evidence_level = _upper_optional(
        match.get("performance_evidence_level")
    )
    value_evidence_level = _upper_optional(match.get("value_evidence_level"))
    presentation_role = _upper_optional(match.get("presentation_role"))

    _validate_optional_enum(
        performance_signal,
        KNOWN_PERFORMANCE_SIGNALS,
        "performance_signal",
        context,
    )
    _validate_optional_enum(
        performance_evidence_level,
        KNOWN_EVIDENCE_LEVELS,
        "performance_evidence_level",
        context,
    )
    _validate_optional_enum(
        value_evidence_level,
        KNOWN_EVIDENCE_LEVELS,
        "value_evidence_level",
        context,
    )
    _validate_optional_enum(
        presentation_role,
        KNOWN_PRESENTATION_ROLES,
        "presentation_role",
        context,
    )

    serving_eligible, serving_reason = _serving_decision(
        registry_status=registry_status,
        performance_signal=performance_signal,
        performance_evidence_level=performance_evidence_level,
        presentation_role=presentation_role,
    )
    condition_text, memo_text = _memo_text(
        match,
        display_text,
        performance_signal,
    )

    return {
        "edge_id": edge_id,
        "display_text": display_text,
        "condition_text": condition_text,
        "memo_text": memo_text,
        "polarity": _upper_optional(match.get("polarity")),
        "performance_signal": performance_signal,
        "registry_status": registry_status,
        "performance_evidence_level": performance_evidence_level,
        "value_evidence_level": value_evidence_level,
        "presentation_role": presentation_role,
        "serving_eligible": serving_eligible,
        "serving_reason": serving_reason,
        "strength_score": match.get("strength_score"),
        "confidence_band": match.get("confidence_band"),
        "registry_version": match.get("registry_version"),
        "evidence": match.get("evidence"),
    }


def normalize_row(row: Mapping[str, Any], *, line_no: int) -> dict[str, Any]:
    """Normalize one runner row from ``edge_matches.jsonl``."""
    context = f"edge_matches line {line_no}"
    if not isinstance(row, Mapping):
        raise NewspaperEdgeAdapterError(f"{context}: row must be an object")

    key = row.get("key")
    if not isinstance(key, Mapping):
        raise NewspaperEdgeAdapterError(f"{context}: key must be an object")

    normalized_key = {
        "race_key": _required_text(key.get("race_key"), "key.race_key", context),
        "race_horse_key": _required_text(
            key.get("race_horse_key"), "key.race_horse_key", context
        ),
        "horse_no": _positive_int(key.get("horse_no"), "key.horse_no", context),
        "horse_id": _text(key.get("horse_id")),
        "race_date": _text(key.get("race_date")),
    }

    raw_matches = row.get("edge_matches")
    if not isinstance(raw_matches, list):
        raise NewspaperEdgeAdapterError(f"{context}: edge_matches must be an array")

    normalized_matches: list[dict[str, Any]] = []
    for match_index, raw_match in enumerate(raw_matches, start=1):
        match_context = f"{context} match {match_index}"
        normalized_match = normalize_match(raw_match, context=match_context)
        normalized_matches.append(normalized_match)

    special_memos = [
        match for match in normalized_matches if match["serving_eligible"]
    ]

    return {
        "key": normalized_key,
        "edge_matches": normalized_matches,
        "special_memos": special_memos,
    }


def _sha256(path: Path) -> str:
    """Calculate the exact source-file SHA-256 for audit metadata."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_special_memo_index(
    path: str | Path,
) -> tuple[dict[tuple[str, str, int], dict[str, Any]], dict[str, Any]]:
    """Load EdgeDB JSONL into the Newspaper exact-join index.

    Duplicate ``race_key + race_horse_key + horse_no`` identities are rejected.
    The returned audit separates raw Edge occurrences from display-eligible
    ``特注メモ`` occurrences.
    """
    source_path = Path(path)
    index: dict[tuple[str, str, int], dict[str, Any]] = {}
    row_count = 0
    raw_match_count = 0
    special_memo_count = 0
    matched_runner_count = 0
    special_memo_runner_count = 0

    with source_path.open(encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                raw_row = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise NewspaperEdgeAdapterError(
                    f"edge_matches line {line_no}: invalid JSON"
                ) from exc

            row = normalize_row(raw_row, line_no=line_no)
            key_data = row["key"]
            key = (
                str(key_data["race_key"]),
                str(key_data["race_horse_key"]),
                int(key_data["horse_no"]),
            )
            if key in index:
                raise NewspaperEdgeAdapterError(
                    f"edge_matches line {line_no}: duplicate join key {key}"
                )

            index[key] = row
            row_count += 1
            raw_match_count += len(row["edge_matches"])
            special_memo_count += len(row["special_memos"])
            if row["edge_matches"]:
                matched_runner_count += 1
            if row["special_memos"]:
                special_memo_runner_count += 1

    audit = {
        "status": "PASS",
        "adapter_version": VERSION,
        "source_sha256": _sha256(source_path),
        "row_count": row_count,
        "raw_match_count": raw_match_count,
        "matched_runner_count": matched_runner_count,
        "special_memo_count": special_memo_count,
        "special_memo_runner_count": special_memo_runner_count,
    }
    return index, audit
