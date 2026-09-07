"""Pure validation and aggregation for ForwardTrial daily result imports.

This module deliberately has no Google authentication.  It produces the
normalized values that Chat/Work must verify before writing the native Sheet.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping


ALLOWED_FAILURE_LABELS = {
    "的中", "1号艇頭失敗", "2着候補2艇外", "内側1点選択ミス", "返還", "対象外"
}
PUBLISHED_CLASSES = {"有料", "無料"}


class LedgerValidationError(ValueError):
    """Raised when immutable daily source facts do not agree."""


@dataclass(frozen=True)
class Metrics:
    count: int
    hits: int
    investment: int
    payout: int

    @property
    def profit(self) -> int:
        return self.payout - self.investment

    @property
    def roi(self) -> float:
        return self.payout / self.investment if self.investment else 0.0


@dataclass(frozen=True)
class StructureKpi:
    target_count: int
    head_success: int
    pair_success: int
    inner_success: int

    @property
    def head_rate(self) -> float:
        return self.head_success / self.target_count if self.target_count else 0.0

    @property
    def pair_rate(self) -> float:
        return self.pair_success / self.head_success if self.head_success else 0.0

    @property
    def inner_rate(self) -> float:
        return self.inner_success / self.pair_success if self.pair_success else 0.0


def _article_date(article_id: str) -> str:
    if len(article_id) != 8 or not article_id.isdigit():
        raise LedgerValidationError("article_id must be YYYYMMDD")
    return date(int(article_id[:4]), int(article_id[4:6]), int(article_id[6:])).isoformat()


def _only(values: Iterable[str], name: str) -> str:
    unique = {value for value in values if value}
    if len(unique) != 1:
        raise LedgerValidationError(f"{name} must have exactly one source value: {sorted(unique)}")
    return unique.pop()


def resolve_immutable_facts(
    *, article_id: str, data_dates: Iterable[str], detail_dates: Iterable[str],
    prediction_freezes: Iterable[str], sales_freezes: Iterable[str]
) -> Mapping[str, str]:
    """Resolve day/freeze facts from source data only; never uses current time."""
    target_date = _article_date(article_id)
    if _only(data_dates, "data_date") != target_date or _only(detail_dates, "detail_date") != target_date:
        raise LedgerValidationError("article_id, data_date and detail_date must match; do not auto-correct")
    return {
        "target_date": target_date,
        "prediction_freeze": _only(prediction_freezes, "prediction_freeze"),
        "sales_freeze": _only(sales_freezes, "sales_freeze"),
    }


def classify_structure(row: Mapping[str, object]) -> Mapping[str, str]:
    """Classify one 2連単1点 row with conditional downstream eligibility."""
    if not row.get("target", False):
        return {"head": "×", "pair": "対象外", "inner": "対象外", "failure": "対象外"}
    if row.get("refunded", False):
        return {"head": "対象外", "pair": "対象外", "inner": "対象外", "failure": "返還"}

    first = int(row["actual_first"])
    second = int(row["actual_second"])
    axis = int(row["axis"])
    candidates = {int(row["second_main"]), int(row["second_backup"])}
    bet = tuple(int(value) for value in row["bet"])
    if first != axis:
        return {"head": "×", "pair": "対象外", "inner": "対象外", "failure": "1号艇頭失敗"}
    if second not in candidates:
        return {"head": "○", "pair": "×", "inner": "対象外", "failure": "2着候補2艇外"}
    if bet != (first, second):
        return {"head": "○", "pair": "○", "inner": "×", "failure": "内側1点選択ミス"}
    return {"head": "○", "pair": "○", "inner": "○", "failure": "的中"}


def _metrics(rows: Iterable[Mapping[str, object]]) -> Metrics:
    values = list(rows)
    return Metrics(
        count=len(values),
        hits=sum(classify_structure(row)["failure"] == "的中" for row in values),
        investment=sum(int(row.get("investment", 0)) for row in values),
        payout=sum(int(row.get("payout", 0)) for row in values),
    )


def build_update_plan(
    *, article_id: str, data_dates: Iterable[str], detail_dates: Iterable[str],
    prediction_freezes: Iterable[str], sales_freezes: Iterable[str], details: Iterable[Mapping[str, object]]
) -> Mapping[str, object]:
    """Return a normalized, Sheets-ready daily update plan and validate invariants."""
    facts = resolve_immutable_facts(
        article_id=article_id, data_dates=data_dates, detail_dates=detail_dates,
        prediction_freezes=prediction_freezes, sales_freezes=sales_freezes,
    )
    rows = list(details)
    paid = [row for row in rows if row.get("listing_class") == "有料" and row.get("target")]
    free = [row for row in rows if row.get("listing_class") == "無料" and row.get("target")]
    csv_only = [row for row in rows if row.get("listing_class") == "CSVのみ" and row.get("target")]
    published = paid + free
    target = published + csv_only
    if len(target) != sum(bool(row.get("target")) for row in rows):
        raise LedgerValidationError("target rows must be classified as paid, free, or CSVのみ")

    classifications = [classify_structure(row) for row in target]
    if any(item["failure"] not in ALLOWED_FAILURE_LABELS for item in classifications):
        raise LedgerValidationError("unexpected failure label")
    head = sum(item["head"] == "○" for item in classifications)
    pair = sum(item["pair"] == "○" for item in classifications)
    inner = sum(item["inner"] == "○" for item in classifications)
    kpi = StructureKpi(len(target), head, pair, inner)
    return {
        **facts,
        "paid": _metrics(paid),
        "free": _metrics(free),
        "published": _metrics(published),
        "csv_only": _metrics(csv_only),
        "all_target": _metrics(target),
        "structure": kpi,
        "detail_structure": classifications,
    }


def plan_as_json(plan: Mapping[str, object]) -> Mapping[str, object]:
    """Convert a plan into JSON-safe primitives for a Sheets update review."""
    def metrics(value: Metrics) -> Mapping[str, object]:
        return {"count": value.count, "hits": value.hits, "investment": value.investment,
                "payout": value.payout, "profit": value.profit, "roi": value.roi}

    kpi = plan["structure"]
    assert isinstance(kpi, StructureKpi)
    return {
        "target_date": plan["target_date"],
        "prediction_freeze": plan["prediction_freeze"],
        "sales_freeze": plan["sales_freeze"],
        "paid": metrics(plan["paid"]),
        "free": metrics(plan["free"]),
        "published": metrics(plan["published"]),
        "csv_only": metrics(plan["csv_only"]),
        "all_target": metrics(plan["all_target"]),
        "structure": {"target_count": kpi.target_count, "head_success": kpi.head_success,
                      "pair_success": kpi.pair_success, "inner_success": kpi.inner_success,
                      "head_rate": kpi.head_rate, "pair_rate": kpi.pair_rate,
                      "inner_rate": kpi.inner_rate},
        "detail_structure": plan["detail_structure"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a verified ForwardTrial daily-result update plan.")
    parser.add_argument("--input", required=True, help="JSON source facts and detail rows")
    parser.add_argument("--output", required=True, help="JSON update plan path")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as handle:
        source = json.load(handle)
    plan = build_update_plan(**source)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(plan_as_json(plan), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
