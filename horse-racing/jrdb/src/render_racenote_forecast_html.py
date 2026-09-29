#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render frozen RaceNote forecast research records as a compact daily HTML report."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

VERSION = "racenote-forecast-html-0.1.0"


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        value = json.loads(path.read_text(encoding="utf-8"))
        rows = value if isinstance(value, list) else [value]
    if not rows:
        raise ValueError("no forecast records")
    return rows


def _horse_text(value: Any) -> str:
    if not isinstance(value, dict):
        return "—"
    no = value.get("horse_no")
    name = value.get("horse_name")
    if no in (None, "") and not name:
        return "—"
    return f"{no} {name or ''}".strip()


def _others_text(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "—"
    return " / ".join(_horse_text(item) for item in value)


def validate_daily_records(records: Iterable[dict[str, Any]]) -> tuple[str, str, str]:
    rows = list(records)
    dates = {str(r.get("identity", {}).get("target_date") or "") for r in rows}
    modes = {str(r.get("research", {}).get("evaluation_mode") or "") for r in rows}
    turns = {str(r.get("research", {}).get("turn_id") or "") for r in rows}
    if len(dates) != 1 or "" in dates:
        raise ValueError("daily HTML requires exactly one target_date")
    if len(modes) != 1 or "" in modes:
        raise ValueError("daily HTML requires exactly one evaluation_mode")
    if len(turns) != 1 or "" in turns:
        raise ValueError("daily HTML requires exactly one turn_id")
    for row in rows:
        audit = row.get("audit") or {}
        if audit.get("pre_result_guard") != "PASS":
            raise ValueError("pre_result_guard must be PASS")
        if audit.get("result_visible_at_freeze") is not False:
            raise ValueError("result_visible_at_freeze must be false")
        if not audit.get("prediction_hash") or not audit.get("frozen_at"):
            raise ValueError("record must be frozen before HTML rendering")
    return next(iter(dates)), next(iter(modes)), next(iter(turns))


def render_daily_html(records: list[dict[str, Any]]) -> str:
    date, mode, turn_id = validate_daily_records(records)
    versions = sorted({str(r.get("research", {}).get("logic_version") or "") for r in records})
    if "" in versions or len(versions) != 1:
        raise ValueError("daily HTML requires exactly one logic_version")
    logic_version = versions[0]

    by_venue: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_venue[str(row["identity"]["venue"])].append(row)
    for rows in by_venue.values():
        rows.sort(key=lambda r: int(r["identity"]["race_no"]))

    parts = [
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">",
        f"<title>RaceNote Forecast {html.escape(date)}</title>",
        """<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:24px;line-height:1.5;background:#fafafa;color:#222}
h1{margin-bottom:4px}.meta{color:#666;margin-bottom:24px}
section{margin:28px 0}table{width:100%;border-collapse:collapse;background:#fff}
th,td{border-bottom:1px solid #ddd;padding:8px;vertical-align:top;text-align:left}
th{background:#f2f2f2;position:sticky;top:0}
.r{white-space:nowrap;font-weight:700}.main{font-weight:800}.comment{min-width:260px}
.skip{color:#888;font-style:italic}
</style></head><body>""",
        f"<h1>{html.escape(date)} RaceNote予想</h1>",
        f"<div class=\"meta\">Turn: {html.escape(turn_id)} / Mode: {html.escape(mode)} / Logic: {html.escape(logic_version)} / Frozen</div>",
    ]

    for venue in sorted(by_venue):
        parts.append(f"<section><h2>{html.escape(venue)}</h2><table>")
        parts.append("<thead><tr><th>R</th><th>Race</th><th>◎</th><th>○</th><th>▲</th><th>△</th><th>Comment</th><th>Concern</th></tr></thead><tbody>")
        for row in by_venue[venue]:
            ident = row["identity"]
            pred = row.get("prediction") or {}
            marks = pred.get("marks") or {}
            race_name = ident.get("race_name") or "—"
            cond = " ".join(
                str(x) for x in [ident.get("surface"), ident.get("distance_m"), ident.get("class")]
                if x not in (None, "")
            )
            race_label = f"{race_name}" + (f" / {cond}" if cond else "")
            parts.append(
                "<tr>"
                f"<td class=\"r\">{html.escape(str(ident['race_no']))}R</td>"
                f"<td>{html.escape(race_label)}</td>"
                f"<td class=\"main\">{html.escape(_horse_text(marks.get('main') or pred.get('axis')))}</td>"
                f"<td>{html.escape(_horse_text(marks.get('second')))}</td>"
                f"<td>{html.escape(_horse_text(marks.get('third')))}</td>"
                f"<td>{html.escape(_others_text(marks.get('others')))}</td>"
                f"<td class=\"comment\">{html.escape(str(pred.get('axis_comment') or '—'))}</td>"
                f"<td>{html.escape(str(pred.get('concern') or '—'))}</td>"
                "</tr>"
            )
        parts.append("</tbody></table></section>")

    parts.append(f"<footer class=\"meta\">renderer: {VERSION}</footer></body></html>")
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = load_records(args.records)
    rendered = render_daily_html(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({"status": "PASS", "records": len(records), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
