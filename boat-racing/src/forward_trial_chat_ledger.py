"""Build a connector-neutral, idempotent daily ledger transaction for Chat.

The module owns no credentials. It accepts immutable daily FT2 payloads plus
current Google Sheets values, rebuilds every FT2 aggregate and the legacy sales
views, and emits raw ``spreadsheets.batchUpdate`` requests. A separate adapter
performs authenticated Drive/Sheets I/O and the post-write audit.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

from forward_trial_analysis_import import (
    AGGREGATE_AUDIT_HEADERS, FT2_HEADERS, GENUINE, IMPORT_COMPLETE, NEEDS_REVIEW,
    ForwardTrialValidationError, aggregate_audit_checks, aggregate_audit_rows,
    as_float, as_int, class_metric, daily_aggregate, grade_aggregate,
    group_aggregate, metric_block, published_metric, records_to_sheet,
    sales_validation, score_validation, structure_aggregate,
)

AUDIT_HEADERS = [
    "FT2_ID", "対象日", "会場", "R", "締切予定日時", "予想確定日時",
    "販売選別確定日時", "freeze監査対象日時", "freeze監査結果",
    "forward_status", "genuine_forward_flag", "監査備考",
]

ARTICLE_HEADERS = [
    "記事ID", "対象日", "記事タイトル", "公開日時", "記事価格", "無料掲載本数", "有料掲載本数",
    "CSV収録レース数", "非掲載レース数", "中止レース数", "対象会場", "販売本数", "売上総額",
    "手数料", "売上手取", "記事状態", "販売ルールVer", "予想確定日時", "販売選別確定日時",
    "備考", "結果登録状態", "有料予想購入レース数", "有料予想的中数", "有料予想的中率",
    "有料予想投資額", "有料予想払戻額", "有料予想収支", "有料予想回収率",
    "無料予想購入レース数", "無料予想的中数", "無料予想的中率", "無料予想投資額",
    "無料予想払戻額", "無料予想収支", "無料予想回収率", "全掲載予想投資額",
    "全掲載予想払戻額", "全掲載予想収支", "全掲載予想回収率",
]

LEGACY_DETAIL_HEADERS = [
    "データID", "記事ID", "データ区分", "日付", "会場", "R", "開催日目", "レース種別",
    "販売ルールVer", "正式判定", "1着軸", "連軸", "2着本線", "2着押さえ", "逆転候補",
    "3着候補", "主推奨券種", "主推奨買い目", "主推奨点数", "保険券種", "保険買い目",
    "保険点数", "判定理由", "予想確定日時", "内部販売評価", "note表示評価", "掲載区分",
    "掲載順位", "軸信頼度", "相手明確度", "展開単純度", "進入安定度", "今節裏付け",
    "販売説明力", "選別理由", "懸念項目", "除外理由", "販売選別確定日時", "結果登録状態",
    "確定着順", "主推奨的中", "主推奨払戻", "保険的中", "保険払戻", "返還額",
    "掲載対象投資額", "掲載対象払戻額", "掲載対象収支", "掲載対象回収率", "実購入有無",
    "実購入金額", "実払戻額", "実収支", "備考", "2連単1点対象", "販売スコア",
    "2着候補分離度", "2連単1点相手", "2連単1点買い目", "2連単1点的中",
    "2連単1点投資額", "2連単1点的中払戻額", "2連単1点返還額", "2連単1点回収額",
    "2連単1点収支", "2連単1点回収率", "1号艇頭成功", "2着候補2艇カバー",
    "内側1点成功", "ForwardTrial失敗構造", "軸警戒", "比較支持項目数",
]

FROZEN_COLUMNS = (
    "正式判定", "1着軸", "2着本線", "2着押さえ", "主推奨買い目", "予想確定日時",
    "2連単1点対象", "販売スコア", "2着候補分離度", "2連単1点買い目", "販売順位",
    "掲載区分", "販売選別確定日時", "確定着順", "2連単公式払戻",
    "prediction_source_file_id", "sales_source_file_id", "result_source_file_id",
)
PROVENANCE_REBIND_COLUMNS = {
    "prediction_source_file_id", "sales_source_file_id", "result_source_file_id",
}


def sheet_rows(sheet: Mapping[str, object]) -> list[dict[str, object]]:
    """Convert a header/rows payload to dictionaries."""
    headers = list(sheet["headers"])
    return [dict(zip(headers, values)) for values in sheet["rows"]]


def values_rows(values: Sequence[Sequence[object]]) -> list[dict[str, object]]:
    """Convert a Sheets values export to dictionaries and skip blank keys."""
    if not values:
        return []
    headers = list(values[0])
    output: list[dict[str, object]] = []
    for value_row in values[1:]:
        padded = list(value_row) + [""] * (len(headers) - len(value_row))
        row = dict(zip(headers, padded))
        if str(row.get(headers[0], "")).strip():
            output.append(row)
    return output


def upsert_daily_detail(existing: Sequence[Mapping[str, object]],
                        incoming: Sequence[Mapping[str, object]],
                        allow_provenance_rebind: bool = False) -> list[dict[str, object]]:
    """Replace a repeated day only when every immutable frozen value agrees."""
    by_id = {str(row["FT2_ID"]): dict(row) for row in existing}
    for source in incoming:
        candidate = dict(source)
        row_id = str(candidate["FT2_ID"])
        current = by_id.get(row_id)
        if current:
            conflicts = [column for column in FROZEN_COLUMNS
                         if not equivalent_value(current.get(column), candidate.get(column))]
            if allow_provenance_rebind:
                conflicts = [column for column in conflicts if column not in PROVENANCE_REBIND_COLUMNS]
            if conflicts:
                raise ForwardTrialValidationError(f"frozen FT2 conflict {row_id}: {conflicts}")
        by_id[row_id] = candidate
    return [by_id[key] for key in sorted(by_id)]


def source_snapshot(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    nonblank = [row for row in rows if str(row.get("FT2_ID", "")).strip()]
    genuine = [row for row in nonblank if row.get("forward_status") == GENUINE]
    return {
        "raw": len(nonblank),
        "genuine": len(genuine),
        "contaminated": sum(row.get("forward_status") == "CONTAMINATED" for row in nonblank),
        "exacta": metric_block(genuine)["R数"],
        "max_date": max((str(row["対象日"]) for row in nonblank), default=""),
        "date_set": {str(row["対象日"]) for row in nonblank},
        "daily_genuine": {
            day: sum(row.get("forward_status") == GENUINE for row in nonblank if str(row["対象日"]) == day)
            for day in {str(row["対象日"]) for row in nonblank}
        },
    }


def previous_completed_snapshot(audit_rows: Sequence[Mapping[str, object]]) -> tuple[str, dict[str, object] | None]:
    """Read the last normal completed source baseline from aggregate audit rows."""
    candidates = [row for row in audit_rows
                  if str(row.get("検証状態", "")) == "OK"
                  and str(row.get("non_regression_check", "OK")) == "OK"]
    if not candidates:
        return "", None
    latest = max(candidates, key=lambda row: (str(row.get("更新日時", "")), str(row.get("aggregate_generation_id", ""))))
    fields = {
        "raw": as_int(latest.get("source_raw_R"), 0) or 0,
        "genuine": as_int(latest.get("source_genuine_R"), 0) or 0,
        "contaminated": as_int(latest.get("source_contaminated_R"), 0) or 0,
        "exacta": as_int(latest.get("source_exacta_R"), 0) or 0,
        "max_date": str(latest.get("source_max_date", "")),
    }
    return str(latest.get("aggregate_generation_id", "")), fields


def non_regression_audit(existing: Sequence[Mapping[str, object]], current: Sequence[Mapping[str, object]],
                         incoming: Sequence[Mapping[str, object]], execution_mode: str,
                         previous_generation_id: str = "", repair_reason: str = "",
                         repair_operator: str = "forward_trial_chat_ledger",
                         previous_snapshot: Mapping[str, object] | None = None) -> dict[str, object]:
    """Compare the rebuilt source detail with the previous completed snapshot."""
    observed_before, after = source_snapshot(existing), source_snapshot(current)
    # A caller may supply the prior completed audit values.  This catches a
    # stale or already-truncated current-detail export before it is accepted as
    # the next daily baseline.  Date-level checks still use observed detail.
    before = dict(observed_before)
    if previous_snapshot:
        for name in ("raw", "genuine", "contaminated", "exacta", "max_date"):
            if previous_snapshot.get(name) not in (None, ""):
                before[name] = previous_snapshot[name]
    new_rows = [row for row in incoming if str(row["対象日"]) not in before["date_set"]]
    new = source_snapshot(new_rows)
    missing = sorted(before["date_set"] - after["date_set"])
    regressed = sorted(
        day for day, count in before["daily_genuine"].items()
        if after["daily_genuine"].get(day, 0) < count
    )
    expected_raw = int(before["raw"]) + new["raw"]
    expected_genuine = int(before["genuine"]) + new["genuine"]
    expected_exacta = int(before["exacta"]) + new["exacta"]
    normal_ok = (
        after["raw"] >= int(before["raw"])
        and after["genuine"] >= int(before["genuine"])
        and after["exacta"] >= int(before["exacta"])
        and not missing and not regressed
        and (not new_rows or after["max_date"] >= str(before["max_date"]))
        and after["raw"] == expected_raw
        and after["genuine"] == expected_genuine
        and after["exacta"] == expected_exacta
    )
    before_by_id = {str(row["FT2_ID"]): row for row in existing}
    incoming_ids = {str(row["FT2_ID"]) for row in incoming}
    changed = sorted(str(row["FT2_ID"]) for row in current if str(row["FT2_ID"]) in incoming_ids
                     and (str(row["FT2_ID"]) not in before_by_id or row != before_by_id[str(row["FT2_ID"])]))
    count_decreased = (after["raw"] < int(before["raw"]) or after["genuine"] < int(before["genuine"])
                       or after["exacta"] < int(before["exacta"]))
    if count_decreased:
        status = "NON_REGRESSION_VIOLATION"
    elif missing:
        status = "MISSING_DATES"
    elif not normal_ok:
        status = "INCREMENT_MISMATCH"
    else:
        status = "OK"
    repair_ok = execution_mode == "repair_rebuild" and bool(repair_reason.strip())
    return {
        "previous_generation_id": previous_generation_id,
        "previous_source_raw_R": before["raw"], "previous_source_genuine_R": before["genuine"],
        "previous_source_contaminated_R": before["contaminated"], "previous_source_exacta_R": before["exacta"],
        "previous_max_target_date": before["max_date"],
        "current_day_raw_R": source_snapshot(incoming)["raw"],
        "current_day_genuine_R": source_snapshot(incoming)["genuine"],
        "current_day_exacta_R": source_snapshot(incoming)["exacta"],
        "expected_current_raw_R": expected_raw, "expected_current_genuine_R": expected_genuine,
        "expected_current_exacta_R": expected_exacta, "missing_dates": ",".join(missing),
        "regressed_dates": ",".join(regressed), "non_regression_check": "OK" if (normal_ok or repair_ok) else status,
        "date_row_count_check": "DATE_ROW_COUNT_REGRESSION" if regressed else "OK",
        "execution_mode": execution_mode, "repair_reason": repair_reason,
        "repair_before": f"raw={before['raw']};genuine={before['genuine']};exacta={before['exacta']}",
        "repair_after": f"raw={after['raw']};genuine={after['genuine']};exacta={after['exacta']}",
        "repair_changed_stable_keys": ",".join(changed), "repair_operator": repair_operator,
        "normal_ok": normal_ok, "completion_ok": normal_ok or repair_ok,
    }


def equivalent_value(left: object, right: object) -> bool:
    """Compare Sheets scalars without treating ``1`` and ``1.0`` as different."""
    if left in (None, "") and right in (None, ""):
        return True
    try:
        left_number = as_float(left)
        right_number = as_float(right)
    except ValueError:
        left_number = right_number = None
    if left_number is not None and right_number is not None:
        return left_number == right_number
    return str(left).strip() == str(right).strip()


def keyed_upsert(existing: Sequence[Mapping[str, object]], incoming: Sequence[Mapping[str, object]],
                 key_columns: Sequence[str]) -> list[dict[str, object]]:
    """Idempotently replace mutable ledger rows by an explicit stable key."""
    by_key = {tuple(str(row.get(column, "")) for column in key_columns): dict(row) for row in existing}
    for row in incoming:
        key = tuple(str(row.get(column, "")) for column in key_columns)
        by_key[key] = dict(row)
    return [by_key[key] for key in sorted(by_key)]


def dashboard_rows(rows: Sequence[Mapping[str, object]],
                   venue_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Build the dashboard directly from genuine detail rows."""
    genuine = [row for row in rows if row["forward_status"] == GENUINE]
    total = metric_block(genuine)
    output = [
        {"セクション": "累計 genuine forward", "指標": "全R件数", "値": len(genuine), "注記": ""},
        {"セクション": "累計 genuine forward", "指標": "2連単1点対象数", "値": total["R数"], "注記": ""},
        {"セクション": "累計 genuine forward", "指標": "2連単1点産出率",
         "値": total["R数"] / len(genuine) if genuine else None, "注記": ""},
    ]
    for key in ("的中数", "的中率", "投資", "回収", "収支", "ROI", "1号艇頭率", "2艇カバー率", "内側率"):
        output.append({"セクション": "累計 genuine forward", "指標": key, "値": total[key], "注記": ""})
    groups = (("有料", class_metric(genuine, "有料")), ("無料", class_metric(genuine, "無料")),
              ("CSVのみ", class_metric(genuine, "CSVのみ")), ("掲載", published_metric(genuine)))
    for label, values in groups:
        hit_rate = "-" if values["的中率"] is None else f"{values['的中率']:.1%}"
        roi = "-" if values["ROI"] is None else f"{values['ROI']:.1%}"
        output.append({"セクション": "販売", "指標": f"{label} R / 的中率 / ROI",
                       "値": f"{values['R数']}R / {hit_rate} / {roi}", "注記": ""})
    rankings = (
        ("サンプル数上位", lambda row: row["全R数"], False),
        ("2連単対象産出率上位", lambda row: row["2連単1点産出率"] or -1, True),
        ("2艇カバー率上位", lambda row: row["全適格_2艇カバー率"] or -1, True),
        ("ROI上位", lambda row: row["全適格_ROI"] or -1, True),
    )
    for label, getter, is_rate in rankings:
        for rank, item in enumerate(sorted(venue_rows, key=getter, reverse=True)[:5], 1):
            value = f"{item['会場']} / {getter(item):.1%}" if is_rate else f"{item['会場']} / {getter(item)}R"
            output.append({"セクション": "会場", "指標": f"{label} {rank}位", "値": value,
                           "注記": "少数標本" if int(item["2連単1点対象数"]) < 5 else ""})
    return output


def legacy_detail_row(row: Mapping[str, object]) -> dict[str, object]:
    """Map one FT2 row into the existing sales-detail schema."""
    published = row["掲載区分"] in {"有料", "無料"} and row["2連単1点対象"] == "対象"
    investment = as_int(row["2連単1点投資額"], 0) if published else 0
    payout = as_int(row["2連単1点回収額"], 0) if published else 0
    result = {header: "" for header in LEGACY_DETAIL_HEADERS}
    result.update({
        "データID": row["FT2_ID"], "記事ID": str(row["対象日"]).replace("-", ""),
        "データ区分": "前向き試行", "日付": row["対象日"], "会場": row["会場"], "R": row["R"],
        "開催日目": row["開催何日目"], "レース種別": row["レース種別"], "販売ルールVer": row["ルールVer"],
        "正式判定": row["正式判定"], "1着軸": row["1着軸"], "2着本線": row["2着本線"],
        "2着押さえ": row["2着押さえ"], "3着候補": row["追加3着候補"], "主推奨券種": row["主推奨券種"],
        "主推奨買い目": row["主推奨買い目"], "主推奨点数": row["主推奨点数"], "判定理由": row["判定理由"],
        "予想確定日時": row["予想確定日時"], "内部販売評価": row["内部販売評価"],
        "note表示評価": row["note表示評価"], "掲載区分": row["掲載区分"], "掲載順位": row["販売順位"],
        "販売選別確定日時": row["販売選別確定日時"], "結果登録状態": "登録済", "確定着順": row["確定着順"],
        "主推奨的中": row["主推奨的中_参考"], "主推奨払戻": row["主推奨払戻_参考"],
        "返還額": row["2連単1点返還額"], "掲載対象投資額": investment, "掲載対象払戻額": payout,
        "掲載対象収支": payout - investment, "掲載対象回収率": payout / investment if investment else 0,
        "2連単1点対象": row["2連単1点対象"], "販売スコア": row["販売スコア"],
        "2着候補分離度": row["2着候補分離度"], "2連単1点相手": row["2連単1点相手"],
        "2連単1点買い目": row["2連単1点買い目"], "2連単1点的中": row["2連単1点的中"],
        "2連単1点投資額": row["2連単1点投資額"], "2連単1点的中払戻額": row["2連単1点的中払戻額"],
        "2連単1点返還額": row["2連単1点返還額"], "2連単1点回収額": row["2連単1点回収額"],
        "2連単1点収支": row["2連単1点収支"], "2連単1点回収率": row["2連単1点回収率"],
        "1号艇頭成功": row["1号艇頭成功"], "2着候補2艇カバー": row["2着候補2艇カバー"],
        "内側1点成功": row["内側1点成功"], "ForwardTrial失敗構造": row["ForwardTrial失敗構造"],
        "軸警戒": row["軸警戒"], "比較支持項目数": row["比較支持項目数"],
    })
    return result


def article_row(day_rows: Sequence[Mapping[str, object]], current: Mapping[str, object] | None = None) -> dict[str, object]:
    """Build the daily article row while preserving unknown commercial facts."""
    first = day_rows[0]
    paid = class_metric(day_rows, "有料")
    free = class_metric(day_rows, "無料")
    published = published_metric(day_rows)
    row = {header: "" for header in ARTICLE_HEADERS}
    if current:
        row.update(current)
    row.update({
        "記事ID": str(first["対象日"]).replace("-", ""), "対象日": first["対象日"],
        "無料掲載本数": free["R数"], "有料掲載本数": paid["R数"],
        "CSV収録レース数": class_metric(day_rows, "CSVのみ")["R数"],
        "非掲載レース数": sum(item["掲載区分"] == "対象外" for item in day_rows),
        "対象会場": "、".join(sorted({str(item["会場"]) for item in day_rows})),
        "販売本数": published["R数"], "記事状態": row.get("記事状態") or "未確定",
        "販売ルールVer": first["ルールVer"], "予想確定日時": first["予想確定日時"],
        "販売選別確定日時": first["販売選別確定日時"], "結果登録状態": "登録済",
        "有料予想購入レース数": paid["R数"], "有料予想的中数": paid["的中数"],
        "有料予想的中率": paid["的中率"], "有料予想投資額": paid["投資"],
        "有料予想払戻額": paid["回収"], "有料予想収支": paid["収支"], "有料予想回収率": paid["ROI"],
        "無料予想購入レース数": free["R数"], "無料予想的中数": free["的中数"],
        "無料予想的中率": free["的中率"], "無料予想投資額": free["投資"],
        "無料予想払戻額": free["回収"], "無料予想収支": free["収支"], "無料予想回収率": free["ROI"],
        "全掲載予想投資額": published["投資"], "全掲載予想払戻額": published["回収"],
        "全掲載予想収支": published["収支"], "全掲載予想回収率": published["ROI"],
    })
    return row


def legacy_metric(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Aggregate the existing sales-detail investment columns."""
    purchased = [row for row in rows if (as_int(row.get("掲載対象投資額"), 0) or 0) > 0]
    investment = sum(as_int(row.get("掲載対象投資額"), 0) or 0 for row in purchased)
    payout = sum(as_int(row.get("掲載対象払戻額"), 0) or 0 for row in purchased)
    hits = sum((as_int(row.get("掲載対象払戻額"), 0) or 0) > 0 for row in purchased)
    return {"対象レース数": len(rows), "購入レース数": len(purchased), "的中数": hits,
            "的中率": hits / len(purchased) if purchased else None, "投資額": investment, "払戻額": payout,
            "収支": payout - investment, "回収率": payout / investment if investment else 0}


def dimension_summary(rows: Sequence[Mapping[str, object]], column: str, header: str) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(column, ""))].append(row)
    return [{header: key, **legacy_metric(grouped[key])} for key in sorted(grouped) if key]


def venue_summary(rows: Sequence[Mapping[str, object]], column: str, header: str) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(column, ""))].append(row)
    output = []
    for key in sorted(grouped):
        values = grouped[key]
        metric = legacy_metric(values)
        output.append({header: key, "対象レース数": len(values),
                       "有料本数": sum(row.get("掲載区分") == "有料" for row in values),
                       "無料本数": sum(row.get("掲載区分") == "無料" for row in values),
                       "CSVのみ本数": sum(row.get("掲載区分") == "CSVのみ" for row in values),
                       "中止本数": sum(row.get("掲載区分") == "中止" for row in values),
                       "結果登録済レース数": sum(row.get("結果登録状態") == "登録済" for row in values),
                       **{name: metric[name] for name in ("購入レース数", "的中数", "的中率", "投資額", "払戻額", "収支", "回収率")}})
    return output


def article_month_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Rebuild monthly article totals from the article ledger itself."""
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        day = str(row.get("対象日", ""))
        month = day[:7] if len(day) >= 7 and day[4] == "-" else str(row.get("記事ID", ""))[:6]
        grouped[month].append(row)
    output = []
    for month in sorted(grouped):
        values = grouped[month]
        totals = {name: sum(as_int(row.get(name), 0) or 0 for row in values) for name in (
            "有料掲載本数", "無料掲載本数", "販売本数", "売上総額", "手数料", "売上手取",
            "有料予想投資額", "有料予想払戻額", "無料予想投資額", "無料予想払戻額",
            "全掲載予想投資額", "全掲載予想払戻額")}
        output.append({
            "対象月": month, "記事数": len(values), **totals,
            "有料予想収支": totals["有料予想払戻額"] - totals["有料予想投資額"],
            "有料予想回収率": totals["有料予想払戻額"] / totals["有料予想投資額"] if totals["有料予想投資額"] else 0,
            "無料予想収支": totals["無料予想払戻額"] - totals["無料予想投資額"],
            "無料予想回収率": totals["無料予想払戻額"] / totals["無料予想投資額"] if totals["無料予想投資額"] else 0,
            "全掲載予想収支": totals["全掲載予想払戻額"] - totals["全掲載予想投資額"],
            "全掲載予想回収率": totals["全掲載予想払戻額"] / totals["全掲載予想投資額"] if totals["全掲載予想投資額"] else 0,
        })
    return output


def forward_trial_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    genuine = [row for row in rows if row["forward_status"] == GENUINE]
    groups = [("全対象", genuine), ("有料", [row for row in genuine if row["掲載区分"] == "有料"]),
              ("無料", [row for row in genuine if row["掲載区分"] == "無料"]),
              ("有料+無料", [row for row in genuine if row["掲載区分"] in {"有料", "無料"}]),
              ("CSVのみ", [row for row in genuine if row["掲載区分"] == "CSVのみ"])]
    output = []
    for label, selected in groups:
        metric = metric_block(selected)
        output.append({"区分": label, "R数": metric["R数"], "的中数": metric["的中数"],
                       "的中率": metric["的中率"], "投資額": metric["投資"], "回収額": metric["回収"],
                       "収支": metric["収支"], "回収率": metric["ROI"], "1号艇頭成功": metric["1号艇頭成功"],
                       "1号艇頭成功率": metric["1号艇頭率"], "2着候補2艇カバー": metric["2艇カバー"],
                       "2着候補2艇カバー率": metric["2艇カバー率"], "内側1点成功": metric["内側成功"],
                       "内側1点成功率": metric["内側率"]})
    return output


def build_atomic_payload(existing_detail: Sequence[Mapping[str, object]], daily_payload: Mapping[str, object],
                         process_datetime: str, existing_sales_crosscheck: bool,
                         existing_management: Sequence[Mapping[str, object]] = (),
                         existing_meta: Sequence[Mapping[str, object]] = (),
                         existing_articles: Sequence[Mapping[str, object]] = (),
                         existing_legacy_detail: Sequence[Mapping[str, object]] = (),
                         execution_mode: str = "daily_append", repair_reason: str = "",
                         previous_generation_id: str = "", repair_operator: str = "forward_trial_chat_ledger",
                         previous_snapshot: Mapping[str, object] | None = None) -> dict[str, object]:
    """Upsert daily rows and rebuild the complete transaction from source detail."""
    incoming = sheet_rows(daily_payload["sheets"]["FT2_全R明細"])
    detail = upsert_daily_detail(existing_detail, incoming,
                                 allow_provenance_rebind=execution_mode == "repair_rebuild")
    latest_day = max(str(row["対象日"]) for row in incoming)
    daily = daily_aggregate(detail)
    venue = group_aggregate(detail, ["会場"])
    venue_day = group_aggregate(detail, ["会場", "開催何日目"])
    grade = grade_aggregate(detail)
    structure = structure_aggregate(detail)
    sales = sales_validation(detail)
    score = score_validation(detail)
    dashboard = dashboard_rows(detail, venue)
    sheets = {
        "FT2_全R明細": records_to_sheet(detail, FT2_HEADERS),
        "FT2_日別集計": records_to_sheet(daily), "FT2_会場別集計": records_to_sheet(venue),
        "FT2_会場日目別集計": records_to_sheet(venue_day), "FT2_グレード別集計": records_to_sheet(grade),
        "FT2_判定構造別集計": records_to_sheet(structure), "FT2_販売選別検証": records_to_sheet(sales),
        "FT2_Score検証": records_to_sheet(score), "FT2_Freeze監査": records_to_sheet(detail, AUDIT_HEADERS),
        "FT2_ダッシュボード": records_to_sheet(dashboard),
    }
    audit = aggregate_audit_rows(rows=detail, sheets=sheets, process_datetime=process_datetime)
    regression = non_regression_audit(
        existing_detail, detail, incoming, execution_mode, previous_generation_id, repair_reason,
        repair_operator, previous_snapshot,
    )
    for row in audit:
        row.update({key: value for key, value in regression.items() if key != "normal_ok"})
        if not regression["completion_ok"]:
            row["検証状態"] = "NG"
            row["エラー内容"] = regression["non_regression_check"]
    sheets["FT2_集計監査"] = records_to_sheet(audit, AGGREGATE_AUDIT_HEADERS)

    management_sheet = daily_payload["sheets"].get("FT2_取込管理")
    meta_sheet = daily_payload["sheets"].get("FT2_開催メタ")
    management = list(existing_management)
    if management_sheet:
        incoming_management = sheet_rows(management_sheet)
        for row in incoming_management:
            row["取込実行日時"] = process_datetime
        management = keyed_upsert(existing_management, incoming_management, ["対象日"])
    meta = list(existing_meta)
    if meta_sheet:
        meta = keyed_upsert(existing_meta, sheet_rows(meta_sheet), ["対象日", "会場"])
    if management_sheet:
        sheets["FT2_取込管理"] = records_to_sheet(management, list(management_sheet["headers"]))
    if meta_sheet:
        sheets["FT2_開催メタ"] = records_to_sheet(meta, list(meta_sheet["headers"]))

    # Rebuild the legacy mirrors from all FT2 source rows, never from a partial
    # day payload.  This is what makes a reconstructed source self-consistent.
    legacy_incoming = [legacy_detail_row(row) for row in detail]
    legacy_detail = legacy_incoming
    article_by_id = {str(row.get("記事ID")): row for row in existing_articles}
    # The existing-sales ledger retains the day even if every race is correctly
    # classified as contaminated. Genuine-only filtering belongs to the FT2
    # performance aggregates, not to the stable daily article key.
    articles = [article_row([row for row in detail if row["対象日"] == day],
                            article_by_id.get(day.replace("-", "")))
                for day in sorted({str(row["対象日"]) for row in detail})]
    sheets.update({
        "販売記事台帳": records_to_sheet(articles, ARTICLE_HEADERS),
        "販売掲載明細": records_to_sheet(legacy_detail, LEGACY_DETAIL_HEADERS),
        "掲載区分別集計": records_to_sheet(dimension_summary(legacy_detail, "掲載区分", "掲載区分")),
        "内部評価別集計": records_to_sheet(dimension_summary(legacy_detail, "内部販売評価", "内部評価")),
        "note表示別集計": records_to_sheet(dimension_summary(legacy_detail, "note表示評価", "note表示")),
        "販売会場別集計": records_to_sheet(venue_summary(legacy_detail, "会場", "会場")),
        "販売開催日目別集計": records_to_sheet(venue_summary(legacy_detail, "開催日目", "開催日目")),
        "販売月別集計": records_to_sheet(article_month_summary(articles)),
        "ForwardTrial集計": records_to_sheet(forward_trial_summary(detail)),
    })

    genuine = [row for row in detail if row["forward_status"] == GENUINE]
    checks = {
        "FT2_ID重複0": len(detail) == len({row["FT2_ID"] for row in detail}),
        "日別当日行": any(row["対象日"] == latest_day for row in daily),
        "Freeze監査全R": len(sheets["FT2_Freeze監査"]["rows"]) == len(detail),
        "dashboard累計": dashboard[0]["値"] == len(genuine),
        "会場別合計": sum(row["全R数"] for row in venue) == len(genuine),
        "会場日目別合計": sum(row["全R数"] for row in venue_day) == len(genuine),
        "判定構造合計": sum(row["全R件数"] for row in structure if row["集計軸"] == "正式判定") == len(genuine),
        "グレード別合計": sum(row["全R"] for row in grade) == len(genuine),
        "販売区分合計": sum(class_metric(genuine, label)["R数"] for label in ("有料", "無料", "CSVのみ")) == metric_block(genuine)["R数"],
        "掲載=有料+無料": published_metric(genuine)["R数"] == class_metric(genuine, "有料")["R数"] + class_metric(genuine, "無料")["R数"],
        "grade解決": all(row["グレード大分類"] != "未分類" for row in incoming),
        "既存販売台帳クロスチェック": existing_sales_crosscheck and len(legacy_incoming) == len(detail),
    }
    checks.update(aggregate_audit_checks(audit))
    checks["Non-Regression Guard"] = regression["completion_ok"]
    checks["過去日消失0"] = not regression["missing_dates"]
    checks["同日件数縮退0"] = not regression["regressed_dates"]
    checks["期待累計値一致"] = (
        regression["current_day_raw_R"] == 0
        or execution_mode == "repair_rebuild"
        or (
            regression["expected_current_raw_R"] == len(detail)
            and regression["expected_current_genuine_R"] == len(genuine)
            and regression["expected_current_exacta_R"] == metric_block(genuine)["R数"]
        )
    )
    state = IMPORT_COMPLETE if all(checks.values()) else NEEDS_REVIEW
    incoming_management_dates = {
        str(row.get("対象日")) for row in sheet_rows(management_sheet)
    } if management_sheet else set()
    for row in management:
        if str(row.get("対象日")) in incoming_management_dates:
            row["取込状態"] = state
            row["備考"] = "" if state == IMPORT_COMPLETE else "未完了ゲート: " + "、".join(name for name, ok in checks.items() if not ok)
    if management_sheet:
        sheets["FT2_取込管理"] = records_to_sheet(management, list(management_sheet["headers"]))
    return {"target_date": latest_day, "state": state, "sheets": sheets, "completion_checks": checks,
            "aggregate_generation_id": audit[0]["aggregate_generation_id"], "non_regression": regression}


def cell_value(value: object) -> dict[str, object]:
    """Convert a scalar into Google Sheets userEnteredValue."""
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, (int, float)):
        return {"numberValue": value}
    return {"stringValue": "" if value is None else str(value)}


def build_batch_requests(payload: Mapping[str, object], metadata: Mapping[str, object],
                         excluded_sheets: Sequence[str] = ()) -> list[dict[str, object]]:
    """Create one coherent content-replacement batch and grow grids safely."""
    sheet_map = {item["title"]: item for item in metadata["sheets"]}
    requests: list[dict[str, object]] = []
    excluded = set(excluded_sheets)
    for title, sheet in payload["sheets"].items():
        if title in excluded:
            continue
        if title not in sheet_map:
            raise ForwardTrialValidationError(f"missing destination sheet: {title}")
        destination = sheet_map[title]
        headers = list(sheet["headers"])
        rows = [headers] + list(sheet["rows"])
        required_rows = len(rows)
        required_columns = len(headers)
        current_rows = int(destination["row_count"])
        current_columns = int(destination["column_count"])
        sheet_id = int(destination["sheet_id"])
        if required_rows > current_rows:
            requests.append({"appendDimension": {"sheetId": sheet_id, "dimension": "ROWS", "length": required_rows - current_rows}})
            current_rows = required_rows
        if required_columns > current_columns:
            requests.append({"appendDimension": {"sheetId": sheet_id, "dimension": "COLUMNS", "length": required_columns - current_columns}})
        requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0,
            "endRowIndex": current_rows, "startColumnIndex": 0, "endColumnIndex": required_columns},
            "cell": {}, "fields": "userEnteredValue"}})
        requests.append({"updateCells": {"range": {"sheetId": sheet_id, "startRowIndex": 0,
            "endRowIndex": required_rows, "startColumnIndex": 0, "endColumnIndex": required_columns},
            "rows": [{"values": [{"userEnteredValue": cell_value(value)} for value in row]} for row in rows],
            "fields": "userEnteredValue"}})
    return requests


def main() -> None:
    """Run the Chat-side deterministic transaction builder."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-sheet-values", required=True,
                        help="JSON object mapping sheet title to Sheets values rows")
    parser.add_argument("--daily-payload", required=True)
    parser.add_argument("--process-datetime", required=True)
    parser.add_argument("--existing-sales-crosscheck", action="store_true")
    parser.add_argument("--execution-mode", choices=("daily_append", "repair_rebuild"), default="daily_append")
    parser.add_argument("--repair-reason", default="")
    parser.add_argument("--previous-generation-id", default="")
    parser.add_argument("--repair-operator", default="forward_trial_chat_ledger")
    parser.add_argument("--previous-source-snapshot-json",
                        help="optional JSON object from the prior completed aggregate audit")
    parser.add_argument("--sheet-metadata-json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    current = json.loads(Path(args.current_sheet_values).read_text(encoding="utf-8"))
    daily_payload = json.loads(Path(args.daily_payload).read_text(encoding="utf-8"))
    previous_snapshot = (json.loads(Path(args.previous_source_snapshot_json).read_text(encoding="utf-8"))
                         if args.previous_source_snapshot_json else None)

    def rows(title: str) -> list[dict[str, object]]:
        return values_rows(current.get(title, {}).get("values", []))

    audit_generation, audit_snapshot = previous_completed_snapshot(rows("FT2_集計監査"))
    if previous_snapshot is None:
        previous_snapshot = audit_snapshot
    if not args.previous_generation_id:
        args.previous_generation_id = audit_generation

    payload = build_atomic_payload(
        rows("FT2_全R明細"), daily_payload, args.process_datetime, args.existing_sales_crosscheck,
        rows("FT2_取込管理"), rows("FT2_開催メタ"), rows("販売記事台帳"), rows("販売掲載明細"),
        args.execution_mode, args.repair_reason, args.previous_generation_id,
        args.repair_operator, previous_snapshot,
    )
    if args.sheet_metadata_json:
        metadata = json.loads(Path(args.sheet_metadata_json).read_text(encoding="utf-8"))
        payload["batch_update_requests"] = build_batch_requests(payload, metadata)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
