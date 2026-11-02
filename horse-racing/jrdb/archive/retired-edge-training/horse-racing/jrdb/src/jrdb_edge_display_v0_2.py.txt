#!/usr/bin/env python3
"""Human-readable display rendering for JRDB Edge Registry v0.2.

Matching keeps canonical JRDB codes. This module is presentation-only: it
resolves those codes to Japanese labels when the v0.2 Registry is built so
consumer projects never need to expose machine-oriented ``field=value`` text.
"""
from __future__ import annotations

from typing import Any, Mapping

VENUE_LABELS = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
SURFACE_LABELS = {"1": "芝", "2": "ダート", "3": "障害"}
TURN_LABELS = {"1": "右回り", "2": "左回り", "3": "直線"}
FRAME_ZONE_LABELS = {"INNER": "内枠", "MIDDLE": "中枠", "OUTER": "外枠"}
TRACK_CONDITION_LABELS = {"1": "良", "2": "稍重", "3": "重", "4": "不良"}
UPTREND_LABELS = {"1": "AA", "2": "A", "3": "B", "4": "C", "5": "?"}
TRAINING_ARROW_LABELS = {
    "1": "デキ抜群", "2": "上昇", "3": "平行線", "4": "やや下降気味", "5": "下降",
}
STABLE_EVALUATION_LABELS = {"1": "超強気", "2": "強気", "3": "現状維持", "4": "弱気"}
DISTANCE_CHANGE_LABELS = {
    "LARGE_SHORTEN": "大幅距離短縮",
    "SHORTEN": "距離短縮",
    "SAME_BAND": "同距離帯",
    "EXTEND": "距離延長",
    "LARGE_EXTEND": "大幅距離延長",
}
SURFACE_TRANSITION_LABELS = {
    "1->1": "芝継続", "1->2": "芝→ダート替わり",
    "2->1": "ダート→芝替わり", "2->2": "ダート継続",
}
SIRE_LINE_LABELS = {
    "1101": "ノーザンダンサー系", "1102": "ニジンスキー系", "1103": "ヴァイスリージェント系",
    "1104": "リファール系", "1105": "ノーザンテースト系", "1106": "ダンジグ系",
    "1107": "ヌレイエフ系", "1108": "ストームバード系", "1109": "サドラーズウェルズ系",
    "1201": "ロイヤルチャージャー系", "1202": "ターントゥ系", "1203": "ヘイルトゥリーズン系",
    "1204": "サーゲイロード系", "1205": "ハビタット系", "1206": "ヘイロー系", "1207": "ロベルト系",
    "1301": "ナスルーラ系", "1302": "グレイソヴリン系", "1303": "ネヴァーベンド系",
    "1304": "プリンスリーギフト系", "1305": "ボールドルーラー系", "1306": "レッドゴッド系",
    "1307": "ゼダーン系", "1308": "カロ系", "1309": "ミルリーフ系", "1310": "リヴァーマン系",
    "1311": "シアトルスルー系", "1312": "ブラッシンググルーム系", "1401": "ネアルコ系",
    "1402": "ニアークティック系", "1403": "デリングドゥ系", "1501": "ネイティヴダンサー系",
    "1502": "シャーペンアップ系", "1503": "ミスタープロスペクター系", "1601": "フェアウェイ系",
    "1602": "バックパサー系", "1603": "ファラリス系", "1701": "ダマスカス系", "1702": "テディ系",
    "1801": "ハイペリオン系", "1802": "オリオール系", "1803": "ロックフェラ系",
    "1804": "テューダーミンストレル系", "1805": "オーエンテューダー系", "1806": "スターキングダム系",
    "1807": "フォルリ系", "1901": "エクリプス系", "1902": "ブランドフォード系", "1903": "ドンカスター系",
    "1904": "ドミノ系", "1905": "ヒムヤー系", "1906": "エルバジェ系", "1907": "ダークロナルド系",
    "1908": "ファイントップ系", "1909": "ゲインズボロー系", "1910": "ハーミット系",
    "1911": "アイシングラス系", "1912": "コングリーヴ系", "1913": "ロックサンド系",
    "2001": "セントサイモン系", "2002": "リボー系", "2003": "ヒズマジェスティ系",
    "2004": "グロースターク系", "2005": "トムロルフ系", "2006": "ワイルドリスク系",
    "2007": "チャウサー系", "2008": "プリンスローズ系", "2009": "プリンスキロ系",
    "2010": "ラウンドテーブル系", "2101": "マッチェム系", "2102": "フェアプレイ系",
    "2103": "ハリーオン系", "2104": "マンノウォー系", "2105": "インリアリティ系",
    "2201": "パーソロン系", "2202": "リュティエ系", "2203": "ジェベル系", "2204": "トウルビヨン系",
    "2205": "ザテトラーク系", "2206": "ヘロド系", "2301": "サンドリッジ系",
    "2401": "スウィンフォード系", "9901": "アラ系",
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _required(value: str | None, context: str) -> str:
    if value is None:
        raise ValueError(f"v0.2 Edge display cannot resolve {context}")
    return value


def _distance(value: Any) -> str:
    try:
        distance = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"v0.2 Edge display has invalid distance: {value!r}") from exc
    if distance <= 0:
        raise ValueError(f"v0.2 Edge display has invalid distance: {value!r}")
    return f"{distance}m"


def _course(values: Mapping[str, Any]) -> str:
    venue_code = str(values.get("venue_code") or "").zfill(2)
    surface_code = str(values.get("surface_code") or "")
    venue = _required(VENUE_LABELS.get(venue_code), f"venue_code={venue_code!r}")
    surface = _required(SURFACE_LABELS.get(surface_code), f"surface_code={surface_code!r}")
    return f"{venue}{surface}{_distance(values.get('distance_m'))}"


def _surface_distance(values: Mapping[str, Any]) -> str:
    surface_code = str(values.get("surface_code") or "")
    surface = _required(SURFACE_LABELS.get(surface_code), f"surface_code={surface_code!r}")
    return f"{surface}{_distance(values.get('distance_m'))}"


def _sire_subject(anchor: Mapping[str, Any]) -> str:
    sire_name = _text(anchor.get("sire_name"))
    if sire_name is not None:
        return f"{sire_name}産駒"
    sire_line_code = _text(anchor.get("sire_line_code"))
    if sire_line_code is not None:
        label = _required(SIRE_LINE_LABELS.get(sire_line_code), f"sire_line_code={sire_line_code!r}")
        return f"父系{label}"
    raise ValueError("v0.2 Edge display cannot resolve sire subject")


def _frame_transition(value: Any) -> str:
    text = _text(value)
    if text is None or "->" not in text:
        raise ValueError(f"v0.2 Edge display has invalid frame_transition: {value!r}")
    previous, current = text.split("->", 1)
    previous_label = _required(FRAME_ZONE_LABELS.get(previous), f"frame zone={previous!r}")
    current_label = _required(FRAME_ZONE_LABELS.get(current), f"frame zone={current!r}")
    return f"{previous_label}→{current_label}"


def _rotation(value: Any) -> str:
    try:
        interval = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"v0.2 Edge display has invalid rotation_interval: {value!r}") from exc
    if interval < 0:
        raise ValueError(f"v0.2 Edge display has invalid rotation_interval: {value!r}")
    if interval == 0:
        return "休養明け初戦"
    return f"休養明け{interval + 1}走目"


def render_condition(
    candidate: Mapping[str, Any], *, jockey_labels: Mapping[str, str] | None = None
) -> str:
    """Render one enabled v0.2 template without exposing raw codes."""
    template_id = str(candidate.get("template_id") or "")
    anchor = candidate.get("anchor") or {}
    modifiers = candidate.get("modifiers") or {}
    if not isinstance(anchor, Mapping) or not isinstance(modifiers, Mapping):
        raise ValueError(f"invalid Edge candidate conditions: {template_id}")

    subject = None
    if "sire_name" in anchor or "sire_line_code" in anchor:
        subject = _sire_subject(anchor)

    if template_id == "COURSE_FRAME_V1":
        frame = _required(FRAME_ZONE_LABELS.get(str(modifiers.get("frame_zone") or "")), "frame_zone")
        return f"{_course(anchor)}の{frame}"
    if template_id == "COURSE_EXACT_FRAME_V2":
        frame_no = int(modifiers.get("frame_no"))
        return f"{_course(anchor)}の{frame_no}枠"
    if template_id in {"SIRE_TURN_DISTANCE_V1", "SIRE_LINE_TURN_DISTANCE_V1"}:
        turn_code = str(modifiers.get("turn_code") or "")
        turn = _required(TURN_LABELS.get(turn_code), f"turn_code={turn_code!r}")
        return f"{_required(subject, template_id)}は{turn}{_distance(modifiers.get('distance_m'))}"
    if template_id == "SIRE_SURFACE_DISTANCE_V1":
        return f"{_required(subject, template_id)}は{_surface_distance(modifiers)}"
    if template_id == "SIRE_BROODMARE_SIRE_V2":
        broodmare = _required(_text(modifiers.get("broodmare_sire_name")), "broodmare_sire_name")
        return f"{_required(subject, template_id)} × 母父{broodmare}"
    if template_id == "SIRE_AGE_V2":
        age = int(modifiers.get("horse_age"))
        return f"{_required(subject, template_id)}は{age}歳"
    if template_id == "SIRE_VENUE_SURFACE_DISTANCE_V2":
        return f"{_required(subject, template_id)}は{_course(modifiers)}"
    if template_id == "BROODMARE_SIRE_SURFACE_DISTANCE_V2":
        broodmare = _required(_text(anchor.get("broodmare_sire_name")), "broodmare_sire_name")
        return f"母父{broodmare}は{_surface_distance(modifiers)}"
    if template_id == "SIRE_TRACK_CONDITION_V2":
        surface_code = str(modifiers.get("surface_code") or "")
        track_code = str(modifiers.get("track_condition_bucket") or "")
        surface = _required(SURFACE_LABELS.get(surface_code), f"surface_code={surface_code!r}")
        track = _required(TRACK_CONDITION_LABELS.get(track_code), f"track_condition_bucket={track_code!r}")
        return f"{_required(subject, template_id)}は{surface}・{track}"
    if template_id == "SIRE_DISTANCE_CHANGE_V1":
        code = str(modifiers.get("distance_change_bucket") or "")
        change = _required(DISTANCE_CHANGE_LABELS.get(code), f"distance_change_bucket={code!r}")
        return f"{_required(subject, template_id)}は{change}"
    if template_id == "SIRE_SURFACE_TRANSITION_V1":
        code = str(modifiers.get("surface_transition") or "")
        transition = _required(SURFACE_TRANSITION_LABELS.get(code), f"surface_transition={code!r}")
        return f"{_required(subject, template_id)}は{transition}"
    if template_id == "SIRE_FRAME_TRANSITION_V1":
        return f"{_required(subject, template_id)}は{_frame_transition(modifiers.get('frame_transition'))}"
    if template_id == "RECENT_UPTREND_SURFACE_DISTANCE_V2":
        code = str(modifiers.get("uptrend_code") or "")
        label = _required(UPTREND_LABELS.get(code), f"uptrend_code={code!r}")
        return f"{_surface_distance(anchor)}・上昇度{label}"
    if template_id == "RECENT_TRAINING_ARROW_SURFACE_DISTANCE_V2":
        code = str(modifiers.get("training_arrow_code") or "")
        label = _required(TRAINING_ARROW_LABELS.get(code), f"training_arrow_code={code!r}")
        return f"{_surface_distance(anchor)}・調教{label}"
    if template_id == "RECENT_STABLE_EVAL_SURFACE_DISTANCE_V2":
        code = str(modifiers.get("stable_evaluation_code") or "")
        label = _required(STABLE_EVALUATION_LABELS.get(code), f"stable_evaluation_code={code!r}")
        return f"{_surface_distance(anchor)}・厩舎評価{label}"
    if template_id == "RECENT_ROTATION_SURFACE_DISTANCE_V2":
        return f"{_surface_distance(anchor)}・{_rotation(modifiers.get('rotation_interval'))}"
    if template_id == "JOCKEY_VENUE_DISTANCE_V2":
        code = _required(_text(anchor.get("jockey_code")), "jockey_code")
        labels = jockey_labels or {}
        jockey = _required(_text(labels.get(code)), f"jockey_name for code={code!r}")
        venue_code = str(modifiers.get("venue_code") or "").zfill(2)
        venue = _required(VENUE_LABELS.get(venue_code), f"venue_code={venue_code!r}")
        return f"{jockey}騎手 × {venue}{_distance(modifiers.get('distance_m'))}"

    raise ValueError(f"v0.2 Edge display has no renderer for template_id={template_id!r}")


def render_display_text(
    candidate: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    jockey_labels: Mapping[str, str] | None = None,
) -> str:
    """Render a signed human-facing Registry display string."""
    polarity = str(result.get("polarity") or "NEUTRAL")
    prefix = "±"
    if polarity == "POSITIVE":
        prefix = "＋"
    elif polarity == "NEGATIVE":
        prefix = "－"
    return f"{prefix} {render_condition(candidate, jockey_labels=jockey_labels)}"
