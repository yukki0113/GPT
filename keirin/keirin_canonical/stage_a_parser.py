"""Parse official embedded PC0201 and PJ0301 JSON; no network access."""

from datetime import date, datetime
import html
import json
import re


class ParseError(ValueError):
    pass


def embedded(raw, name):
    source = raw.decode("utf-8", errors="replace")
    marker = re.search(r"jsonData\s*\[\s*['\"]" + re.escape(name) + r"['\"]\s*\]\s*=\s*", source)
    if not marker:
        raise ParseError(f"missing_{name}_json")
    try:
        result, _ = json.JSONDecoder().raw_decode(source[marker.end():])
        return result
    except (ValueError, TypeError) as exc:
        raise ParseError(f"malformed_{name}_json") from exc


def meet_key(venue, start, sequence=None):
    key = f"{venue}|{start.isoformat()}"
    return f"{key}|{sequence}" if sequence is not None else key


def race_key(day, venue, number):
    return f"{day:%Y%m%d}|{venue}|{number}"


def actual_dates(days, selected):
    """Resolve displayed MM/DD against the explicitly dated selected day.

    A year boundary is resolved from the displayed month sequence, never by
    adding an ordinal or number of days to the meet start.
    """
    labels = []
    for item in days:
        value = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})\s*", str(item.get("txtEventDate", "")))
        if not value:
            raise ParseError("missing_actual_event_date")
        labels.append((int(value[1]), int(value[2])))
    anchors = [i for i, (m, d) in enumerate(labels) if (m, d) == (selected.month, selected.day)]
    if len(anchors) != 1:
        raise ParseError("ambiguous_selected_event_date")
    years = [None] * len(labels)
    years[anchors[0]] = selected.year
    for i in range(anchors[0] + 1, len(labels)):
        prev, curr = labels[i-1][0], labels[i][0]
        if curr < prev and not (prev == 12 and curr == 1):
            raise ParseError("nonmonotonic_event_month")
        years[i] = years[i-1] + (prev == 12 and curr == 1)
    for i in range(anchors[0] - 1, -1, -1):
        curr, nxt = labels[i][0], labels[i+1][0]
        if curr > nxt and not (curr == 12 and nxt == 1):
            raise ParseError("nonmonotonic_event_month")
        years[i] = years[i+1] - (curr == 12 and nxt == 1)
    try:
        dates = [date(year, month, day) for year, (month, day) in zip(years, labels)]
    except ValueError as exc:
        raise ParseError("invalid_actual_event_date") from exc
    if dates != sorted(set(dates)):
        raise ParseError("duplicate_or_unsorted_actual_event_date")
    return dates


def clean_label(value):
    return html.unescape(re.sub(r"<[^>]*>", "", str(value or ""))).strip() or None


def ruleset(label):
    if not label:
        return "unknown"
    if "ガールズ" in label or "女子" in label:
        return "girls_international_no_line"
    if "アドバンス" in label:
        return "advance_international_no_line"
    if re.search(r"[ＡAＳS]級|チャレンジ|ルーキーシリーズ|ヤンググランプリ|競輪祭|共同通信社杯|日本選手権|オールスター|高松宮記念|寬仁親王牌|全日本選抜|グランプリ|サマーナイト|ウィナーズカップ", label):
        return "standard_keirin_line"
    return "unknown"


def parse(raw, record):
    base = embedded(raw, "PC0201").get("C0201data")
    nav = embedded(raw, "PJ0301")
    if not isinstance(base, dict) or not isinstance(nav.get("raceDayDataList"), list):
        raise ParseError("missing_official_navigation")
    try:
        selected = datetime.strptime(str(base["selKaisai"]), "%Y%m%d").date()
        venue = str(base["selKjyoCd"])
        display_days = base["C0201kaisai"]
        race_days = nav["raceDayDataList"]
        if not display_days:
            raise ParseError("missing_event_days")
        dates = actual_dates(display_days, selected)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ParseError):
            raise
        raise ParseError("invalid_meet_identity") from exc
    meta = record.get("metadata") or {}
    if meta.get("venue_code") and str(meta["venue_code"]) != venue:
        raise ParseError("venue_code_mismatch")
    grade = clean_label(base.get("imgGradeAlt")) or meta.get("grade")
    meet = dict(meet_key=meet_key(venue, dates[0]), venue_code=venue,
                venue_name=meta.get("venue_name") or clean_label(base.get("joName")),
                meet_start_date=dates[0], meet_end_date=dates[-1], grade_raw=grade,
                grade_norm=grade if grade in {"F1", "F2", "G1", "G2", "G3", "GP"} else "unknown",
                event_name=clean_label(base.get("raceName")), scheduled_days=meta.get("schedule_colspan_days"),
                actual_days=len(dates), meet_status="unknown", source_updated_at=None)
    if not meet["venue_name"]:
        raise ParseError("missing_venue_name")
    races = []
    warnings = []
    aligned = []
    for nav_index, info in enumerate(race_days):
        label = clean_label(info.get("strRaceNitiji"))
        candidates = [i for i, entry in enumerate(display_days)
                      if label and clean_label(entry.get("txtDaily", "").strip("()（）")) == label]
        if len(race_days) == len(display_days):
            index = nav_index
        elif len(candidates) == 1:
            index = candidates[0]
        elif not info.get("raceNoDataList"):
            continue
        else:
            raise ParseError("ambiguous_event_day_navigation")
        aligned.append((index,dates[index],info))
    if len(aligned) < len(dates):
        warnings.append("event_day_navigation_partial")
    for index, day, info in aligned:
        rows = info.get("raceNoDataList") or []
        labels = []
        for block in info.get("raceEventDataList") or []:
            try:
                count = int(block["strColspan"])
            except (ValueError, TypeError, KeyError) as exc:
                raise ParseError("invalid_race_label_span") from exc
            if count < 1:
                raise ParseError("invalid_race_label_span")
            labels.extend([clean_label(block.get("strRaceEvent"))] * count)
        if labels and len(labels) != len(rows):
            warnings.append("race_label_span_mismatch")
            labels = [None] * len(rows)
        for pos, item in enumerate(rows):
            number = re.fullmatch(r"\s*(\d{1,2})R\s*", str(item.get("strRaceNo", "")))
            if not number:
                raise ParseError("invalid_race_no")
            no = int(number[1]); label = labels[pos] if labels else None
            if not 1 <= no <= 12:
                raise ParseError("invalid_race_no")
            kind = ruleset(label)
            races.append(dict(race_key=race_key(day, venue, no), meet_key=meet["meet_key"],
                              race_date=day, venue_code=venue, race_no=no, day_no=index+1,
                              day_label_raw=clean_label(info.get("strRaceNitiji")),
                              scheduled_start_time=None, race_label_raw=label,
                              class_category=None, race_stage=None, grade_raw=grade,
                              grade_norm=meet["grade_norm"], distance_m=None, laps=None,
                              starters_scheduled=None, competition_category=None,
                              race_ruleset=kind, cancellation_status=("cancelled" if str(info.get("strKaisaiFlg")) in {"1", "2"} else None),
                              detail_token=item.get("strLnkPrm") or None,
                              detail_disp=item.get("strLnkKBn") or None, source_updated_at=None))
    return meet, races, dates, warnings
