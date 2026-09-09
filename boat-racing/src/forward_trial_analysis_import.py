"""Build the ForwardTrial analysis ledger from immutable daily Freeze CSVs.

The module has no Google authentication.  It validates and normalizes source
assets, produces all FT2 sheet payloads, and fails closed on conflicting keys,
dates, or Freeze facts.  Google Sheets writes remain a Work-side operation.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence


RULE_VERSION = "ForwardTrial_Ver0.1"
PUBLISHED_CLASSES = {"有料", "無料"}
TARGET_VALUE = "対象"
NON_TARGET_VALUE = "対象外"
GENUINE = "GENUINE"
CONTAMINATED = "CONTAMINATED"
PENDING_AUDIT = "PENDING_AUDIT"
IMPORT_IN_PROGRESS = "取込中"
AGGREGATION_PENDING = "集計再生成待ち"
NEEDS_REVIEW = "要確認"
IMPORT_COMPLETE = "完了"
IMPORT_ERROR = "エラー"
GRADE_CATEGORIES = {"一般", "G2", "G1", "SG", "その他", "未分類"}
INITIAL_BACKFILL_DATES = {
    "2026-09-01",
    "2026-09-02",
    "2026-09-03",
    "2026-09-05",
    "2026-09-06",
    "2026-09-07",
    "2026-09-08",
}


class ForwardTrialValidationError(ValueError):
    """Raised when immutable source facts do not reconcile."""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_date(value: str) -> str:
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    raise ForwardTrialValidationError(f"unsupported date: {value!r}")


def as_int(value: object, default: int | None = None) -> int | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return default
    return int(float(text.replace(",", "")))


def as_float(value: object, default: float | None = None) -> float | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return default
    return float(text.replace(",", ""))


def yes(value: object) -> bool:
    return str(value).strip() in {"○", "あり", "はい", "TRUE", "True", "true", "1"}


def ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def format_ratio(value: float | None) -> str:
    """Format optional rates safely for sparse daily sales classes."""
    return f"{value:.1%}" if value is not None else "-"


def key_of(row: Mapping[str, object]) -> tuple[str, str, int]:
    return normalize_date(str(row["日付"])), str(row["会場"]).strip(), int(row["R"])


def stable_key(day: str, venue: str, race_no: int, rule: str = RULE_VERSION) -> str:
    return f"{normalize_date(day).replace('-', '')}_{venue}_{race_no}_{rule}"


def unique_index(rows: Iterable[Mapping[str, object]], name: str) -> dict[tuple[str, str, int], Mapping[str, object]]:
    result: dict[tuple[str, str, int], Mapping[str, object]] = {}
    for row in rows:
        key = key_of(row)
        if key in result:
            raise ForwardTrialValidationError(f"duplicate {name} key: {key}")
        result[key] = row
    return result


def grade_category(value: object) -> str:
    """Normalize an official event grade without guessing from an event name."""
    text = str(value or "").strip().upper().replace("Ⅰ", "I")
    aliases = {"一般": "一般", "IPPAN": "一般", "G2": "G2", "GII": "G2",
               "G1": "G1", "GI": "G1", "SG": "SG", "G3": "その他", "その他": "その他"}
    return aliases.get(text, "未分類")


def read_grade_meta(path: Path, day: str) -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    for row in read_csv(path):
        row_day = normalize_date(str(row.get("対象日") or row.get("日付") or ""))
        if row_day != day:
            continue
        venue = str(row.get("会場", "")).strip()
        key = (row_day, venue)
        if not venue or key in result:
            raise ForwardTrialValidationError(f"duplicate/blank grade metadata key: {key}")
        source = str(row.get("source", "")).strip()
        if "BOAT RACE" not in source.upper():
            raise ForwardTrialValidationError(f"grade metadata must use BOAT RACE official source: {key}")
        category = grade_category(row.get("グレード大分類") or row.get("開催グレード区分"))
        result[key] = {
            "開催グレード": str(row.get("開催グレード", "")).strip(),
            "グレード大分類": category,
            "source": source,
            "source_file": str(row.get("source_file") or row.get("source URL") or "").strip(),
            "備考": str(row.get("備考", "")).strip(),
        }
    return result


def upsert_rows(existing: Sequence[Mapping[str, object]], incoming: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Idempotent stable-key upsert; differing duplicates are conflicts."""
    by_id = {str(row["FT2_ID"]): dict(row) for row in existing}
    for row in incoming:
        row_id = str(row["FT2_ID"])
        candidate = dict(row)
        if row_id in by_id and by_id[row_id] != candidate:
            raise ForwardTrialValidationError(f"conflicting FT2_ID: {row_id}")
        by_id[row_id] = candidate
    return [by_id[key] for key in sorted(by_id)]


def validate_source_dates(expected: str, *datasets: tuple[str, Sequence[Mapping[str, object]]]) -> None:
    expected = normalize_date(expected)
    for name, rows in datasets:
        actual = {normalize_date(str(row["日付"])) for row in rows}
        if actual != {expected}:
            raise ForwardTrialValidationError(f"{name} date mismatch: expected {expected}, got {sorted(actual)}")


def file_freeze(rows: Sequence[Mapping[str, object]], column: str, source_name: str) -> str:
    values = {str(row.get(column, "")).strip() for row in rows if str(row.get(column, "")).strip()}
    if len(values) != 1:
        raise ForwardTrialValidationError(f"{source_name} must have exactly one {column}: {sorted(values)}")
    return values.pop()


def parse_timestamp(value: str) -> datetime:
    text = value.strip().replace(" JST", "+09:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", text):
        return datetime.fromisoformat(text)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}[+-]\d{2}:\d{2}", text):
        return datetime.fromisoformat(text)
    raise ForwardTrialValidationError(f"unsupported timestamp: {value!r}")


def cutoff_timestamp(day: str, hhmm: str) -> str:
    if not re.fullmatch(r"\d{2}:\d{2}", hhmm.strip()):
        return ""
    return f"{normalize_date(day)} {hhmm.strip()}:00+09:00"


def audit_freeze(prediction_freeze: str, sales_freeze: str, cutoff: str) -> tuple[str, str, bool, str]:
    if not cutoff:
        return "", "締切時刻未確認", False, PENDING_AUDIT
    latest = max(parse_timestamp(prediction_freeze), parse_timestamp(sales_freeze))
    limit = parse_timestamp(cutoff)
    if latest < limit:
        return latest.isoformat(sep=" "), "締切前", True, GENUINE
    return latest.isoformat(sep=" "), "締切後", False, CONTAMINATED


def parse_finish(value: str) -> tuple[int | None, int | None]:
    boats = [as_int(item) for item in str(value).split("-") if item.strip()]
    return (boats[0] if boats else None, boats[1] if len(boats) > 1 else None)


def parse_bet(value: str) -> tuple[int, int] | None:
    boats = [as_int(item) for item in re.split(r"→|-", str(value).strip()) if item.strip()]
    if len(boats) != 2 or boats[0] is None or boats[1] is None:
        return None
    return int(boats[0]), int(boats[1])


def parse_boat_set(value: str) -> set[int]:
    return {int(item) for item in re.findall(r"[1-6]", str(value))}


def parse_reason_int(reason: str, label: str) -> int | None:
    match = re.search(rf"{re.escape(label)}\s*[=＝]\s*(\d+)", reason)
    return int(match.group(1)) if match else None


def normalize_warning(value: str, reason: str) -> str:
    text = value.strip()
    if text in {"あり", "なし"}:
        return text
    match = re.search(r"軸警戒\s*[=＝]\s*(あり|なし)", reason)
    return match.group(1) if match else ""


def rank_from_sales(row: Mapping[str, object]) -> int | None:
    direct = as_int(row.get("販売順位"))
    if direct is not None:
        return direct
    match = re.search(r"販売順位\s*(\d+)位", str(row.get("選別理由", "")))
    return int(match.group(1)) if match else None


def structure_result(*, target: bool, refunded: bool, first: int | None, second: int | None,
                     axis: int | None, second_main: int | None, second_backup: int | None,
                     bet: tuple[int, int] | None) -> tuple[str, str, str, str, str]:
    if not target:
        return NON_TARGET_VALUE, NON_TARGET_VALUE, NON_TARGET_VALUE, NON_TARGET_VALUE, NON_TARGET_VALUE
    if refunded:
        return "返還", NON_TARGET_VALUE, NON_TARGET_VALUE, NON_TARGET_VALUE, "返還"
    if first != 1:
        return "×", "×", NON_TARGET_VALUE, NON_TARGET_VALUE, "1号艇頭失敗"
    if second not in {second_main, second_backup}:
        return "×", "○", "×", NON_TARGET_VALUE, "2着候補2艇外"
    if bet != (first, second):
        return "×", "○", "○", "×", "内側1点選択ミス"
    return "○", "○", "○", "○", "的中"


FT2_HEADERS = [
    "FT2_ID", "対象日", "会場", "会場CD", "R", "開催何日目", "レース種別", "開催グレード", "グレード大分類", "ルールVer",
    "正式判定", "1着軸", "2着本線", "2着押さえ", "追加3着候補", "主推奨券種", "主推奨買い目", "主推奨点数", "軸警戒", "比較支持項目数", "判定理由", "予想確定日時", "prediction_source_file", "prediction_source_file_id",
    "予想軸評価対象", "予想軸1着成功", "2着候補評価対象_全R", "2着候補2艇カバー_全R", "主推奨的中_参考", "主推奨払戻_参考",
    "2連単1点対象", "販売スコア", "2着候補分離度", "2連単1点相手", "2連単1点買い目", "2連単相手2to4", "2連単相手本線一致", "販売順位", "掲載区分", "内部販売評価", "note表示評価", "販売選別確定日時", "sales_source_file", "sales_source_file_id",
    "確定着順", "実1着", "実2着", "2連単公式払戻", "返還有無", "result_source_file", "result_source_file_id",
    "2連単1点的中", "2連単1点投資額", "2連単1点的中払戻額", "2連単1点返還額", "2連単1点回収額", "2連単1点収支", "2連単1点回収率", "1号艇頭成功", "2着候補2艇カバー", "内側1点成功", "ForwardTrial失敗構造",
    "締切予定日時", "freeze監査対象日時", "freeze監査結果", "forward_status", "genuine_forward_flag", "監査備考",
]


def normalize_day(entry: Mapping[str, object], base: Path) -> tuple[list[dict[str, object]], dict[str, object], list[dict[str, object]]]:
    day = normalize_date(str(entry["date"]))
    assets = {name: entry[name] for name in ("prediction", "sales", "result", "racecard")}
    paths = {name: (base / str(asset["path"])).resolve() for name, asset in assets.items()}
    rows = {name: read_csv(path) for name, path in paths.items()}
    grade_asset = entry.get("grade_meta")
    grade_meta = read_grade_meta((base / str(grade_asset["path"])).resolve(), day) if grade_asset else {}
    validate_source_dates(day, *( (name, rows[name]) for name in rows ))
    expected_races = len(rows["prediction"])
    if expected_races == 0 or expected_races != len(rows["result"]):
        raise ForwardTrialValidationError(
            f"{day}: prediction/result row count mismatch: "
            f"prediction={expected_races}, result={len(rows['result'])}"
        )
    if len(rows["racecard"]) != expected_races * 6:
        raise ForwardTrialValidationError(
            f"{day}: racecard must contain {expected_races * 6} boat rows "
            f"for {expected_races} prediction races"
        )

    prediction = unique_index(rows["prediction"], "prediction")
    sales = unique_index(rows["sales"], "sales")
    result = unique_index(rows["result"], "result")
    racecards: dict[tuple[str, str, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows["racecard"]:
        racecards[key_of(row)].append(row)
    if len(racecards) != expected_races or any(len(values) != 6 for values in racecards.values()):
        raise ForwardTrialValidationError(
            f"{day}: racecard must resolve to {expected_races} races × 6 boats"
        )
    if set(prediction) != set(result) or set(prediction) != set(racecards):
        raise ForwardTrialValidationError(f"{day}: prediction/result/racecard keys do not match")
    if not set(sales).issubset(prediction):
        raise ForwardTrialValidationError(f"{day}: sales contains keys outside prediction")

    prediction_freeze = file_freeze(rows["prediction"], "予想確定日時", "prediction")
    sales_freeze = file_freeze(rows["sales"], "販売選別確定日時", "sales")
    output: list[dict[str, object]] = []
    venues: dict[str, dict[str, object]] = {}
    for key in sorted(prediction, key=lambda item: (item[1], item[2])):
        pred = prediction[key]
        sale = sales.get(key)
        res = result[key]
        card = racecards[key][0]
        venue, race_no = key[1], key[2]
        reason = str(pred.get("判定理由", ""))
        axis = as_int(pred.get("1着軸"))
        second_main = as_int(pred.get("2着本線"))
        second_backup = as_int(pred.get("2着押さえ"))
        formal = str(pred.get("判定", "")).strip()
        warning = normalize_warning(str((sale or {}).get("軸警戒", "")), reason)
        support = as_int((sale or {}).get("比較支持項目数"))
        if support is None:
            support = parse_reason_int(reason, "比較支持項目数")
        target = bool(sale) and str(sale.get("2連単1点対象", "")).strip() == TARGET_VALUE
        listing = str((sale or {}).get("掲載区分", "")).strip() if target else NON_TARGET_VALUE
        bet_text = str((sale or {}).get("2連単1点", "")).strip() if target else ""
        bet = parse_bet(bet_text) if target else None
        opponent = bet[1] if bet else None
        first, second = parse_finish(str(res.get("確定着順", "")))
        refunded_boats = parse_boat_set(str(res.get("返還艇", "")))
        cancelled = yes(res.get("中止")) or yes(res.get("不成立"))
        bet_refunded = bool(target and (cancelled or (bet and set(bet) & refunded_boats)))
        official_payout = as_int(res.get("公式2連単払戻"), 0) or 0
        hit = bool(target and not bet_refunded and bet == (first, second))
        investment = 100 if target else 0
        hit_payout = official_payout if hit else 0
        refund = 100 if bet_refunded else 0
        # Ledger acceptance controls keep refunds in a dedicated column.  The
        # ForwardTrial "回収" KPI is the hit payout only, matching the frozen
        # 0901-0908 historical controls (refunds are never hidden).
        recovery = hit_payout
        profit = recovery - investment
        hit_mark, head_mark, pair_mark, inner_mark, failure = structure_result(
            target=target, refunded=bet_refunded, first=first, second=second, axis=axis,
            second_main=second_main, second_backup=second_backup, bet=bet,
        )

        cutoff = cutoff_timestamp(day, str((sale or {}).get("公式締切予定時刻", "") or card.get("締切時刻", "")))
        audited_at, audit_result, genuine_flag, forward_status = audit_freeze(prediction_freeze, sales_freeze, cutoff)

        axis_target = axis is not None and first is not None
        axis_success = "○" if axis_target and first == axis else ("×" if axis_target else NON_TARGET_VALUE)
        second_target = axis_success == "○" and second_main is not None and second_backup is not None
        second_cover = "○" if second_target and second in {second_main, second_backup} else ("×" if second_target else NON_TARGET_VALUE)
        main_hit = "○" if str(res.get("主推奨的中", "")).strip() == "的中" else ("対象外" if str(res.get("主推奨的中", "")).strip() in {"", "対象なし"} else "×")
        ranking = rank_from_sales(sale or {}) if target else None
        venue_code = str(card.get("場コード", "")).strip()
        grade = grade_meta.get((day, venue), {
            "開催グレード": "", "グレード大分類": "未分類", "source": "",
            "source_file": "", "備考": "公式開催グレード未取得",
        })
        full_row = {
            "FT2_ID": stable_key(day, venue, race_no), "対象日": day, "会場": venue, "会場CD": venue_code,
            "R": race_no, "開催何日目": str(pred.get("開催日目", "")).strip(), "レース種別": str(pred.get("レース種別", "")).strip(),
            "開催グレード": grade["開催グレード"], "グレード大分類": grade["グレード大分類"], "ルールVer": str(pred.get("ルールVer", "")).strip(),
            "正式判定": formal, "1着軸": axis, "2着本線": second_main, "2着押さえ": second_backup,
            "追加3着候補": str(pred.get("3着候補", "")).strip(), "主推奨券種": str(pred.get("主推奨券種", "")).strip(),
            "主推奨買い目": str(pred.get("主推奨買い目展開後", "")).strip() or str(pred.get("主推奨買い目表記", "")).strip(),
            "主推奨点数": as_int(pred.get("主推奨点数"), 0), "軸警戒": warning, "比較支持項目数": support,
            "判定理由": reason, "予想確定日時": str(pred.get("予想確定日時", "")).strip(),
            "prediction_source_file": paths["prediction"].name, "prediction_source_file_id": str(assets["prediction"]["file_id"]),
            "予想軸評価対象": "○" if axis_target else NON_TARGET_VALUE, "予想軸1着成功": axis_success,
            "2着候補評価対象_全R": "○" if second_target else NON_TARGET_VALUE, "2着候補2艇カバー_全R": second_cover,
            "主推奨的中_参考": main_hit, "主推奨払戻_参考": as_int(res.get("主推奨払戻"), 0) or 0,
            "2連単1点対象": TARGET_VALUE if target else NON_TARGET_VALUE, "販売スコア": as_int((sale or {}).get("販売スコア")),
            "2着候補分離度": as_float((sale or {}).get("2着候補分離度")), "2連単1点相手": opponent,
            "2連単1点買い目": bet_text, "2連単相手2to4": ("2～4号艇" if opponent and 2 <= opponent <= 4 else ("5～6号艇" if opponent else NON_TARGET_VALUE)),
            "2連単相手本線一致": ("一致" if opponent is not None and opponent == second_main else ("非一致" if opponent is not None else NON_TARGET_VALUE)),
            "販売順位": ranking, "掲載区分": listing, "内部販売評価": str((sale or {}).get("内部販売評価", "")).strip(),
            "note表示評価": "", "販売選別確定日時": sales_freeze, "sales_source_file": paths["sales"].name,
            "sales_source_file_id": str(assets["sales"]["file_id"]), "確定着順": str(res.get("確定着順", "")).strip(),
            "実1着": first, "実2着": second, "2連単公式払戻": official_payout,
            "返還有無": "あり" if refunded_boats or cancelled else "なし", "result_source_file": paths["result"].name,
            "result_source_file_id": str(assets["result"]["file_id"]), "2連単1点的中": hit_mark,
            "2連単1点投資額": investment, "2連単1点的中払戻額": hit_payout, "2連単1点返還額": refund,
            "2連単1点回収額": recovery, "2連単1点収支": profit, "2連単1点回収率": ratio(recovery, investment),
            "1号艇頭成功": head_mark, "2着候補2艇カバー": pair_mark, "内側1点成功": inner_mark,
            "ForwardTrial失敗構造": failure, "締切予定日時": cutoff, "freeze監査対象日時": audited_at,
            "freeze監査結果": audit_result, "forward_status": forward_status, "genuine_forward_flag": genuine_flag,
            "監査備考": "" if forward_status == GENUINE else ("締切後Freezeを保持" if forward_status == CONTAMINATED else "締切時刻未確認"),
        }
        if full_row["ルールVer"] != RULE_VERSION:
            raise ForwardTrialValidationError(f"{key}: unexpected rule version {full_row['ルールVer']}")
        output.append(full_row)
        venues.setdefault(venue, {
            "対象日": day, "会場": venue, "会場CD": venue_code, "開催何日目": full_row["開催何日目"],
            "開催グレード": grade["開催グレード"], "グレード大分類": grade["グレード大分類"], "会場選別位置づけ": "会場選別後対象",
            "source": grade["source"], "source_file": grade["source_file"], "備考": grade["備考"],
        })

    duplicate_count = len(output) - len({row["FT2_ID"] for row in output})
    management = {
        "対象日": day, "予想ルールVer": RULE_VERSION, "対象会場数": len(venues), "対象会場一覧": "、".join(sorted(venues)),
        "全R予定件数": expected_races, "prediction_file": paths["prediction"].name, "prediction_file_id": str(assets["prediction"]["file_id"]),
        "prediction_freeze": prediction_freeze, "rationale_file": "", "rationale_file_id": "", "sales_file": paths["sales"].name,
        "sales_file_id": str(assets["sales"]["file_id"]), "sales_freeze": sales_freeze, "result_file": paths["result"].name,
        "result_file_id": str(assets["result"]["file_id"]), "racecard_file": paths["racecard"].name,
        "racecard_file_id": str(assets["racecard"]["file_id"]), "racecard有無": "あり", "prediction有無": "あり",
        "sales有無": "あり", "result有無": "あり", "取込行数": len(output),
        "2連単対象件数": sum(row["2連単1点対象"] == TARGET_VALUE for row in output),
        "genuine件数": sum(row["forward_status"] == GENUINE for row in output),
        "contaminated件数": sum(row["forward_status"] == CONTAMINATED for row in output),
        "duplicate件数": duplicate_count, "source整合性": "一致", "取込状態": AGGREGATION_PENDING, "取込実行日時": "", "備考": "",
    }
    return output, management, list(venues.values())


def target_rows(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return [row for row in rows if row["2連単1点対象"] == TARGET_VALUE]


def metric_block(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    targets = target_rows(rows)
    hits = sum(row["2連単1点的中"] == "○" for row in targets)
    investment = sum(int(row["2連単1点投資額"]) for row in targets)
    recovery = sum(int(row["2連単1点回収額"]) for row in targets)
    head = sum(row["1号艇頭成功"] == "○" for row in targets)
    pair = sum(row["2着候補2艇カバー"] == "○" for row in targets)
    inner = sum(row["内側1点成功"] == "○" for row in targets)
    return {
        "R数": len(targets), "的中数": hits, "的中率": ratio(hits, len(targets)), "投資": investment,
        "回収": recovery, "収支": recovery - investment, "ROI": ratio(recovery, investment),
        "1号艇頭成功": head, "1号艇頭率": ratio(head, len(targets)), "2艇カバー": pair,
        "2艇カバー率": ratio(pair, head), "内側成功": inner, "内側率": ratio(inner, pair),
    }


def all_r_block(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    count = len(rows)
    a = sum(row["正式判定"] == "A" for row in rows)
    b = sum(row["正式判定"] == "B" for row in rows)
    c = sum(row["正式判定"] == "C" for row in rows)
    one_a = sum(row["正式判定"] == "A" and row["1着軸"] == 1 for row in rows)
    non_one_a = sum(row["正式判定"] == "A" and row["1着軸"] not in {None, 1} for row in rows)
    axis_target = sum(row["予想軸評価対象"] == "○" for row in rows)
    axis_success = sum(row["予想軸1着成功"] == "○" for row in rows)
    pair_target = sum(row["2着候補評価対象_全R"] == "○" for row in rows)
    pair_success = sum(row["2着候補2艇カバー_全R"] == "○" for row in rows)
    eligible = sum(row["2連単1点対象"] == TARGET_VALUE for row in rows)
    return {
        "全R数": count, "A数": a, "A率": ratio(a, count), "B数": b, "B率": ratio(b, count), "C数": c, "C率": ratio(c, count),
        "1号艇A数": one_a, "1号艇A率": ratio(one_a, count), "非1号艇A数": non_one_a, "非1号艇A率": ratio(non_one_a, count),
        "予想軸評価対象数": axis_target, "予想軸1着成功数": axis_success, "予想軸1着成功率": ratio(axis_success, axis_target),
        "2着候補評価対象数": pair_target, "2着候補2艇カバー数": pair_success, "全R2着候補2艇カバー率": ratio(pair_success, pair_target),
        "2連単1点対象数": eligible, "2連単1点産出率": ratio(eligible, count),
    }


def class_metric(rows: Sequence[Mapping[str, object]], listing_class: str) -> dict[str, object]:
    selected = [row for row in rows if row["2連単1点対象"] == TARGET_VALUE and row["掲載区分"] == listing_class]
    return metric_block(selected)


def published_metric(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return metric_block([row for row in rows if row["2連単1点対象"] == TARGET_VALUE and row["掲載区分"] in PUBLISHED_CLASSES])


def daily_aggregate(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if row["forward_status"] == GENUINE:
            grouped[str(row["対象日"])].append(row)
    output = []
    for day in sorted(grouped):
        values = grouped[day]
        row = {"対象日": day, "対象会場数": len({item["会場"] for item in values}), **all_r_block(values)}
        for prefix, metrics in (("全適格", metric_block(values)), ("有料", class_metric(values, "有料")),
                                ("無料", class_metric(values, "無料")), ("掲載", published_metric(values)),
                                ("CSVのみ", class_metric(values, "CSVのみ"))):
            row.update({f"{prefix}_{key}": value for key, value in metrics.items()})
        output.append(row)
    return output


def group_aggregate(rows: Sequence[Mapping[str, object]], keys: Sequence[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if row["forward_status"] == GENUINE:
            grouped[tuple(row[key] for key in keys)].append(row)
    output = []
    for group_key in sorted(grouped, key=lambda item: tuple(str(value) for value in item)):
        values = grouped[group_key]
        base = {key: value for key, value in zip(keys, group_key)}
        base["開催日数"] = len({item["対象日"] for item in values})
        base.update(all_r_block(values))
        base.update({f"全適格_{key}": value for key, value in metric_block(values).items()})
        for label in ("有料", "無料", "CSVのみ"):
            metrics = class_metric(values, label)
            base[f"{label}採用数"] = metrics["R数"]
            base[f"{label}採用率"] = ratio(metrics["R数"], base["2連単1点対象数"])
            base[f"{label}的中率"] = metrics["的中率"]
            base[f"{label}ROI"] = metrics["ROI"]
        scores = [float(item["販売スコア"]) for item in target_rows(values) if item["販売スコア"] is not None]
        separations = [float(item["2着候補分離度"]) for item in target_rows(values) if item["2着候補分離度"] is not None]
        base["平均販売スコア"] = sum(scores) / len(scores) if scores else None
        base["平均2着候補分離度"] = sum(separations) / len(separations) if separations else None
        base["genuine対象日数"] = len({item["対象日"] for item in values})
        all_same_group = [item for item in rows if all(item[key] == value for key, value in zip(keys, group_key))]
        base["contaminated件数"] = sum(item["forward_status"] == CONTAMINATED for item in all_same_group)
        output.append(base)
    return output


def grade_aggregate(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    values = group_aggregate(rows, ["グレード大分類"])
    return [{
        "グレード大分類": row["グレード大分類"], "全R": row["全R数"], "A率": row["A率"],
        "1号艇A率": row["1号艇A率"], "非1号艇A率": row["非1号艇A率"], "2連単1点産出率": row["2連単1点産出率"],
        "2連単1点的中率": row["全適格_的中率"], "ROI": row["全適格_ROI"], "1号艇頭率": row["全適格_1号艇頭率"],
        "2艇カバー率": row["全適格_2艇カバー率"], "内側率": row["全適格_内側率"],
        "有料採用率": row["有料採用率"], "有料ROI": row["有料ROI"],
        "少数標本警告": "少数標本" if int(row["2連単1点対象数"]) < 30 else "",
    } for row in values]


def cumulative_acceptance(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    nonblank = [row for row in rows if str(row.get("FT2_ID", "")).strip()]
    genuine = [row for row in nonblank if row.get("forward_status") == GENUINE]
    metric = metric_block(genuine)
    actual = {"Raw全R": len(nonblank), "genuine全R": len(genuine), "genuine2連単": metric["R数"],
              "的中": metric["的中数"], "投資": metric["投資"], "回収": metric["回収"],
              "CONTAMINATED": sum(row.get("forward_status") == CONTAMINATED for row in nonblank),
              "重複": len(nonblank) - len({row["FT2_ID"] for row in nonblank})}
    expected = {"Raw全R": 396, "genuine全R": 393, "genuine2連単": 86, "的中": 29,
                "投資": 8600, "回収": 7910, "CONTAMINATED": 3, "重複": 0}
    if actual != expected:
        raise ForwardTrialValidationError(f"0901-0909 acceptance mismatch: actual={actual}, expected={expected}")
    return actual


def completion_state(*, checks: Mapping[str, bool], grade_unresolved: int = 0,
                     aggregation_error: Exception | None = None) -> str:
    """The management row may become complete only after every downstream gate."""
    if aggregation_error is not None:
        return IMPORT_ERROR
    if not all(checks.values()) or grade_unresolved:
        return NEEDS_REVIEW
    return IMPORT_COMPLETE


def structure_aggregate(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    genuine = [row for row in rows if row["forward_status"] == GENUINE]
    groups: list[tuple[str, str, list[Mapping[str, object]]]] = []
    for value in ("A", "B", "C"):
        groups.append(("正式判定", value, [row for row in genuine if row["正式判定"] == value]))
    groups.extend([
        ("A軸区分", "1号艇A", [row for row in genuine if row["正式判定"] == "A" and row["1着軸"] == 1]),
        ("A軸区分", "非1号艇A", [row for row in genuine if row["正式判定"] == "A" and row["1着軸"] not in {None, 1}]),
    ])
    for value in ("あり", "なし"):
        groups.append(("軸警戒", value, [row for row in genuine if row["軸警戒"] == value]))
    for value in range(6):
        groups.append(("比較支持項目数", str(value), [row for row in genuine if row["比較支持項目数"] == value]))
    output = []
    for dimension, value, selected in groups:
        full = all_r_block(selected)
        target = metric_block(selected)
        output.append({"集計軸": dimension, "区分": value, "全R件数": len(selected),
                       "予想軸評価対象": full["予想軸評価対象数"], "予想軸成功": full["予想軸1着成功数"],
                       "予想軸1着率": full["予想軸1着成功率"], "2着候補評価対象": full["2着候補評価対象数"],
                       "2着候補カバー": full["2着候補2艇カバー数"], "全R2着候補カバー率": full["全R2着候補2艇カバー率"],
                       **{f"適格_{key}": metric for key, metric in target.items()}})
    return output


def sales_validation(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    genuine = [row for row in rows if row["forward_status"] == GENUINE and row["2連単1点対象"] == TARGET_VALUE]
    groups = [
        ("販売群", "全適格", genuine),
        ("販売群", "掲載", [row for row in genuine if row["掲載区分"] in PUBLISHED_CLASSES]),
        ("販売群", "有料", [row for row in genuine if row["掲載区分"] == "有料"]),
        ("販売群", "無料", [row for row in genuine if row["掲載区分"] == "無料"]),
        ("販売群", "CSVのみ", [row for row in genuine if row["掲載区分"] == "CSVのみ"]),
    ]
    rank_bands = [("1～3位", 1, 3), ("4～6位", 4, 6), ("7～9位", 7, 9), ("10位以下", 10, 10**9)]
    for label, low, high in rank_bands:
        groups.append(("販売順位帯", label, [row for row in genuine if row["販売順位"] is not None and low <= int(row["販売順位"]) <= high]))
    return [{"集計軸": dimension, "区分": value, **metric_block(selected)} for dimension, value, selected in groups]


def score_validation(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    genuine = [row for row in rows if row["forward_status"] == GENUINE and row["2連単1点対象"] == TARGET_VALUE]
    groups: list[tuple[str, str, list[Mapping[str, object]]]] = []
    for score in sorted({row["販売スコア"] for row in genuine if row["販売スコア"] is not None}):
        groups.append(("販売スコア", str(score), [row for row in genuine if row["販売スコア"] == score]))
    buckets = [
        ("<0.08", lambda value: value is not None and float(value) < 0.08),
        ("0.08以上0.15未満", lambda value: value is not None and 0.08 <= float(value) < 0.15),
        ("0.15以上", lambda value: value is not None and float(value) >= 0.15),
    ]
    for label, predicate in buckets:
        groups.append(("2着候補分離度", label, [row for row in genuine if predicate(row["2着候補分離度"])]))
    for value in ("あり", "なし"):
        groups.append(("軸警戒", value, [row for row in genuine if row["軸警戒"] == value]))
    for value in range(6):
        groups.append(("比較支持項目数", str(value), [row for row in genuine if row["比較支持項目数"] == value]))
    for value in ("2～4号艇", "5～6号艇"):
        groups.append(("2連単相手", value, [row for row in genuine if row["2連単相手2to4"] == value]))
    for value in ("一致", "非一致"):
        groups.append(("本線一致", value, [row for row in genuine if row["2連単相手本線一致"] == value]))
    return [{"集計軸": dimension, "区分": value, **metric_block(selected)} for dimension, value, selected in groups]


def initial_backfill_rows(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Return only the immutable initial acceptance fixture rows."""
    return [row for row in rows if row.get("対象日") in INITIAL_BACKFILL_DATES]


def validate_initial_acceptance(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    rows = initial_backfill_rows(rows)
    raw = target_rows(rows)
    genuine_rows = [row for row in rows if row["forward_status"] == GENUINE]
    genuine = target_rows(genuine_rows)
    checks = {
        "全R": len(rows), "重複": len(rows) - len({row["FT2_ID"] for row in rows}), "Raw対象": len(raw),
        "Raw的中": sum(row["2連単1点的中"] == "○" for row in raw), "Raw投資": sum(int(row["2連単1点投資額"]) for row in raw),
        "Raw回収": sum(int(row["2連単1点回収額"]) for row in raw), "Genuine対象": len(genuine),
        "Genuine的中": sum(row["2連単1点的中"] == "○" for row in genuine),
        "Genuine投資": sum(int(row["2連単1点投資額"]) for row in genuine), "Genuine回収": sum(int(row["2連単1点回収額"]) for row in genuine),
        "Contaminated": sum(row["forward_status"] == CONTAMINATED for row in rows),
    }
    expected = {"全R": 336, "重複": 0, "Raw対象": 81, "Raw的中": 29, "Raw投資": 8100, "Raw回収": 7910,
                "Genuine対象": 78, "Genuine的中": 29, "Genuine投資": 7800, "Genuine回収": 7910, "Contaminated": 3}
    if checks != expected:
        raise ForwardTrialValidationError(f"initial acceptance mismatch: actual={checks}, expected={expected}")
    expected_classes = {
        "有料": (39, 19, 3900, 4930), "無料": (21, 4, 2100, 1210), "CSVのみ": (18, 6, 1800, 1770),
    }
    for label, expected_value in expected_classes.items():
        metrics = class_metric(genuine_rows, label)
        actual = (metrics["R数"], metrics["的中数"], metrics["投資"], metrics["回収"])
        if actual != expected_value:
            raise ForwardTrialValidationError(f"{label} acceptance mismatch: {actual} != {expected_value}")
    published = published_metric(genuine_rows)
    if (published["R数"], published["的中数"], published["投資"], published["回収"]) != (60, 23, 6000, 6140):
        raise ForwardTrialValidationError("published acceptance mismatch")
    structure = metric_block(genuine_rows)
    if (structure["1号艇頭成功"], structure["2艇カバー"], structure["内側成功"]) != (59, 38, 29):
        raise ForwardTrialValidationError("structure acceptance mismatch")
    day_0908 = metric_block([row for row in genuine_rows if row["対象日"] == "2026-09-08"])
    if (day_0908["R数"], day_0908["的中数"], day_0908["回収"], day_0908["1号艇頭成功"], day_0908["2艇カバー"], day_0908["内側成功"]) != (11, 7, 1660, 9, 8, 7):
        raise ForwardTrialValidationError("0908 acceptance mismatch")
    return checks


def records_to_sheet(records: Sequence[Mapping[str, object]], headers: Sequence[str] | None = None) -> dict[str, object]:
    if headers is None:
        headers = list(records[0]) if records else []
    return {"headers": list(headers), "rows": [[row.get(header) for header in headers] for row in records]}


def build_payload(manifest_path: Path, process_datetime: str = "") -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    all_rows: list[dict[str, object]] = []
    management: list[dict[str, object]] = []
    venue_meta: list[dict[str, object]] = []
    for entry in manifest["dates"]:
        day_rows, day_management, day_venues = normalize_day(entry, base)
        day_management["取込実行日時"] = process_datetime
        all_rows = upsert_rows(all_rows, day_rows)
        management.append(day_management)
        venue_meta.extend(day_venues)
    # The fixed 0901–0908 controls are verified when the complete initial
    # backfill is supplied.  A later ordinary daily import must not be forced
    # to include that historical source set.
    input_dates = {normalize_date(str(entry["date"])) for entry in manifest["dates"]}
    acceptance = (
        validate_initial_acceptance(all_rows)
        if INITIAL_BACKFILL_DATES.issubset(input_dates)
        else {"status": "skipped", "reason": "initial-backfill sources not included"}
    )
    daily = daily_aggregate(all_rows)
    venue = group_aggregate(all_rows, ["会場"])
    venue_day = group_aggregate(all_rows, ["会場", "開催何日目"])
    grade = grade_aggregate(all_rows)
    structure = structure_aggregate(all_rows)
    sales = sales_validation(all_rows)
    score = score_validation(all_rows)

    readme = [
        {"項目": "対象開始日", "内容": "2026-09-01"}, {"項目": "対象ルール", "内容": RULE_VERSION},
        {"項目": "基礎仕様", "内容": "競艇AI予想_事前予想仕様書_Ver1.2.1"},
        {"項目": "分析3階層", "内容": "全R / 2連単1点適格 / 販売選別後（有料・無料・CSVのみ）"},
        {"項目": "ROI対象", "内容": "2連単1点100円ROIは当時のFreeze原本で適格だったRだけを評価"},
        {"項目": "禁止", "内容": "全Rへ後付け仮想2連単買い目を作らない"},
        {"項目": "genuine forward", "内容": "max(予想確定日時, 販売選別確定日時) < 締切予定日時"},
        {"項目": "締切後Freeze", "内容": "行を削除せずCONTAMINATEDとして保持"},
        {"項目": "販売区分", "内容": "当時の有料・無料・CSVのみを歴史データとして保持し、後から組替えない"},
        {"項目": "集計デフォルト", "内容": "GENUINEのみ。ALL_FROZENは参考集計としてのみ使用可能"},
        {"項目": "原本", "内容": "Google Driveの日次Freeze資産"},
        {"項目": "現在日時", "内容": "対象日・Freeze生成元には使用しない。取込実行日時だけに使用可能"},
        {"項目": "初回バックフィル", "内容": "2026-09-01, 09-02, 09-03, 09-05, 09-06, 09-07, 09-08（336R）"},
        {"項目": "既知contamination", "内容": "2026-09-03 徳山1R～3R"},
    ]
    audit_headers = ["FT2_ID", "対象日", "会場", "R", "締切予定日時", "予想確定日時", "販売選別確定日時", "freeze監査対象日時", "freeze監査結果", "forward_status", "genuine_forward_flag", "監査備考"]
    genuine_rows = [r for r in all_rows if r["forward_status"] == GENUINE]
    total = metric_block(genuine_rows)
    dashboard = [
        {"セクション": "累計 genuine forward", "指標": "全R件数", "値": len(genuine_rows), "注記": ""},
        {"セクション": "累計 genuine forward", "指標": "2連単1点対象数", "値": total["R数"], "注記": ""},
        {"セクション": "累計 genuine forward", "指標": "2連単1点産出率", "値": ratio(total["R数"], len(genuine_rows)), "注記": ""},
    ]
    for key in ("的中数", "的中率", "投資", "回収", "収支", "ROI", "1号艇頭率", "2艇カバー率", "内側率"):
        dashboard.append({"セクション": "累計 genuine forward", "指標": key, "値": total[key], "注記": ""})
    for label, metrics in (("有料", class_metric(genuine_rows, "有料")), ("無料", class_metric(genuine_rows, "無料")),
                           ("CSVのみ", class_metric(genuine_rows, "CSVのみ")), ("掲載", published_metric(genuine_rows))):
        dashboard.append({"セクション": "販売", "指標": f"{label} R / 的中率 / ROI", "値": f"{metrics['R数']}R / {format_ratio(metrics['的中率'])} / {format_ratio(metrics['ROI'])}", "注記": ""})
    rankings = [
        ("サンプル数上位", lambda r: r["全R数"]), ("2連単対象産出率上位", lambda r: r["2連単1点産出率"] or -1),
        ("2艇カバー率上位", lambda r: r["全適格_2艇カバー率"] or -1), ("ROI上位", lambda r: r["全適格_ROI"] or -1),
    ]
    for label, getter in rankings:
        for rank, item in enumerate(sorted(venue, key=getter, reverse=True)[:5], 1):
            sample = int(item["2連単1点対象数"])
            dashboard.append({"セクション": "会場", "指標": f"{label} {rank}位", "値": f"{item['会場']} / {getter(item):.1%}" if "率" in label or label == "ROI上位" else f"{item['会場']} / {getter(item)}R", "注記": "少数標本" if sample < 5 else ""})

    sheets = {
        "FT2_README": records_to_sheet(readme),
        "FT2_取込管理": records_to_sheet(management),
        "FT2_開催メタ": records_to_sheet(venue_meta),
        "FT2_全R明細": records_to_sheet(all_rows, FT2_HEADERS),
        "FT2_日別集計": records_to_sheet(daily),
        "FT2_会場別集計": records_to_sheet(venue),
        "FT2_会場日目別集計": records_to_sheet(venue_day),
        "FT2_グレード別集計": records_to_sheet(grade),
        "FT2_判定構造別集計": records_to_sheet(structure),
        "FT2_販売選別検証": records_to_sheet(sales),
        "FT2_Score検証": records_to_sheet(score),
        "FT2_Freeze監査": records_to_sheet(all_rows, audit_headers),
        "FT2_ダッシュボード": records_to_sheet(dashboard),
    }
    latest_day = max(input_dates)
    unresolved = sum(row["グレード大分類"] == "未分類" for row in venue_meta)
    checks = {
        "FT2_ID重複0": len(all_rows) == len({row["FT2_ID"] for row in all_rows}),
        "日別当日行": any(row["対象日"] == latest_day for row in daily),
        "Freeze監査全R": len(sheets["FT2_Freeze監査"]["rows"]) == len(all_rows),
        "dashboard累計": dashboard[0]["値"] == sum(row["forward_status"] == GENUINE for row in all_rows),
        "会場別合計": sum(row["全R数"] for row in venue) == sum(row["forward_status"] == GENUINE for row in all_rows),
        "販売区分合計": sum(class_metric([r for r in all_rows if r["forward_status"] == GENUINE], label)["R数"]
                           for label in ("有料", "無料", "CSVのみ")) == metric_block(genuine_rows)["R数"],
        "掲載=有料+無料": published_metric(genuine_rows)["R数"] == (
            class_metric(genuine_rows, "有料")["R数"] + class_metric(genuine_rows, "無料")["R数"]),
        "grade解決": unresolved == 0,
        "既存販売台帳クロスチェック": bool(manifest.get("existing_sales_crosscheck", False)),
    }
    cumulative = cumulative_acceptance(all_rows) if latest_day == "2026-09-09" and len(all_rows) == 396 else {}
    state = completion_state(checks=checks, grade_unresolved=unresolved)
    for row in management:
        row["取込状態"] = state
        if state != IMPORT_COMPLETE:
            row["備考"] = "未完了ゲート: " + "、".join(name for name, ok in checks.items() if not ok)
    sheets["FT2_取込管理"] = records_to_sheet(management)
    return {"sheets": sheets, "acceptance": acceptance, "cumulative_acceptance": cumulative,
            "completion_checks": checks, "grade_unresolved": unresolved,
            "analysis": {"venues": venue, "venue_days": venue_day, "sales": sales}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FT2 normalized/detail and aggregate Google Sheets payloads.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--process-datetime", default="")
    args = parser.parse_args()
    payload = build_payload(Path(args.manifest), args.process_datetime)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
