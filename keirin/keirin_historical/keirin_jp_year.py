"""Sequential low-rate annual KEIRIN.JP historical audit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

from .keirin_jp_month import run_month

KNOWN_SUMMARIES: dict[tuple[int, int], dict[str, Any]] = {
    (2016, 1): {
        "status": "success",
        "provider": "keirin.jp",
        "policy_status": "personal_research_approved",
        "year": 2016,
        "month": 1,
        "schedule_http_status": 200,
        "discovered_events": 60,
        "successful_events": 60,
        "failed_events": 0,
        "coverage": 1.0,
        "delay_seconds": 3.0,
        "total_event_bytes": 2698910,
        "source": "verified_issue_1185",
    }
}


def run_year(
    *,
    year: int,
    start_month: int,
    end_month: int,
    output_dir: Path,
    audit_dir: Path,
    delay_seconds: float = 3.0,
    inter_month_delay_seconds: float = 10.0,
) -> dict[str, Any]:
    if not 1 <= start_month <= end_month <= 12:
        raise ValueError("require 1 <= start_month <= end_month <= 12")
    if delay_seconds < 2.0:
        raise ValueError("delay_seconds must be >= 2.0")
    if inter_month_delay_seconds < 0:
        raise ValueError("inter_month_delay_seconds must be >= 0")

    audit_dir.mkdir(parents=True, exist_ok=True)
    months: list[dict[str, Any]] = []

    for month in range(start_month, end_month + 1):
        known = KNOWN_SUMMARIES.get((year, month))
        if known is not None:
            months.append(dict(known))
            continue

        try:
            summary = run_month(
                year=year,
                month=month,
                output_dir=output_dir,
                audit_dir=audit_dir,
                delay_seconds=delay_seconds,
            )
        except Exception as exc:
            summary = {
                "status": "failure",
                "provider": "keirin.jp",
                "policy_status": "personal_research_approved",
                "year": year,
                "month": month,
                "discovered_events": 0,
                "successful_events": 0,
                "failed_events": 0,
                "coverage": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
            }
        months.append(summary)

        if month < end_month and inter_month_delay_seconds:
            time.sleep(inter_month_delay_seconds)

    discovered = sum(int(m.get("discovered_events", 0)) for m in months)
    successful = sum(int(m.get("successful_events", 0)) for m in months)
    failed = sum(int(m.get("failed_events", 0)) for m in months)
    failed_months = [int(m["month"]) for m in months if m.get("status") != "success"]
    zero_coverage_months = [int(m["month"]) for m in months if float(m.get("coverage", 0.0)) == 0.0]
    overall_coverage = successful / discovered if discovered else 0.0

    annual = {
        "status": "success" if not failed_months else "partial_failure",
        "provider": "keirin.jp",
        "policy_status": "personal_research_approved",
        "year": year,
        "start_month": start_month,
        "end_month": end_month,
        "months_audited": len(months),
        "discovered_events": discovered,
        "successful_events": successful,
        "failed_events": failed,
        "overall_coverage": overall_coverage,
        "failed_months": failed_months,
        "zero_coverage_months": zero_coverage_months,
        "delay_seconds": delay_seconds,
        "inter_month_delay_seconds": inter_month_delay_seconds,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "months": months,
    }

    (audit_dir / f"{year:04d}_annual_summary.json").write_text(
        json.dumps(annual, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return annual


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sequential annual KEIRIN.JP historical audit")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--start-month", type=int, default=1)
    parser.add_argument("--end-month", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=3.0)
    parser.add_argument("--inter-month-delay-seconds", type=float, default=10.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_year(
        year=args.year,
        start_month=args.start_month,
        end_month=args.end_month,
        output_dir=args.output_dir,
        audit_dir=args.audit_dir,
        delay_seconds=args.delay_seconds,
        inter_month_delay_seconds=args.inter_month_delay_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
