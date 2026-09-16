"""Active deterministic daily predictor for ForwardTrial_Ver0.2-alpha1.

This wrapper promotes the approved v0.2-alpha1 rule set for new, result-unseen
days while preserving the historical ForwardTrial_Ver0.1 control artifacts.
It keeps the standard three daily outputs (prediction / rationale / sales),
reuses the frozen v0.1 axis/judgment rules, applies OS-alpha1 to opponent
selection, Q0 + four-factor sales scoring, the v0.2 product-volume rule, and
excludes races already at/past official closing time from paid/free slots.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from forward_trial_deadline_gate import build_deadlines, parse_freeze
from forward_trial_predict import (
    PREDICTION_COLUMNS,
    RATIONALE_COLUMNS,
    SALES_COLUMNS,
    ForwardTrialValidationError,
    generate as generate_control,
)
from forward_trial_v02_alpha_shadow import (
    SHADOW_VERSION,
    generate_shadow,
    product_split,
)

RULE_VERSION = SHADOW_VERSION


def _key(row: Mapping[str, object]) -> tuple[str, int]:
    return str(row["会場"]), int(row["R"])


def _join_third(main: int, backup: int, third: int) -> str:
    return f"{main},{backup},{third}"


def _compat_internal_eval(listing: str) -> str:
    # Ver0.2-alpha1 does not define S/A/A- as a ranking input. Keep the legacy
    # column for schema compatibility but do not manufacture a new grade.
    return ""


def generate_active(
    rows: Sequence[Mapping[str, str]],
    columns: Sequence[str],
    prediction_time: str,
    sales_time: str | None = None,
) -> dict[str, object]:
    sales_time = sales_time or prediction_time
    control = generate_control(rows, columns, prediction_time, sales_time)
    shadow = generate_shadow(rows, columns, sales_time)

    if control["date"] != shadow["date"]:
        raise ForwardTrialValidationError("control/shadow date mismatch")

    shadow_by_key = {_key(row): row for row in shadow["rows"]}
    if len(shadow_by_key) != len(shadow["rows"]):
        raise ForwardTrialValidationError("duplicate alpha race key")

    prediction_by_key = {
        (str(row[1]), int(row[2])): row for row in control["predictions"]
    }
    sales_by_key = {_key(row): row for row in control["sales"]}

    # Replace only the layers changed by v0.2-alpha1.
    for key, alpha in shadow_by_key.items():
        if key not in prediction_by_key or key not in sales_by_key:
            raise ForwardTrialValidationError(f"missing control race for {key}")

        pred = prediction_by_key[key]
        pred[5] = RULE_VERSION
        judgment = str(alpha["正式判定"])
        axis = str(alpha["1着軸"] or "")

        if judgment == "C":
            pred[7] = ""
            pred[9] = pred[10] = pred[12] = ""
            pred[13] = pred[14] = pred[15] = ""
            pred[16] = 0
            pred[22] = (
                f"{RULE_VERSION}: A/B/C判定はVer0.1継承。C判定のため正式購入対象なし。"
            )
        else:
            main = int(alpha["2着本線"])
            backup = int(alpha["2着押さえ"])
            third = int(alpha["追加3着候補"])
            axis_i = int(axis)
            pred[7] = axis
            pred[9] = str(main)
            pred[10] = str(backup)
            pred[12] = _join_third(main, backup, third)
            pred[13] = "3連単"
            pred[14] = f"{axis_i}→{main},{backup}→{main},{backup},{third}"
            pred[15] = "／".join([
                f"{axis_i}→{main}→{backup}",
                f"{axis_i}→{main}→{third}",
                f"{axis_i}→{backup}→{main}",
                f"{axis_i}→{backup}→{third}",
            ])
            pred[16] = 4
            pred[22] = (
                f"{RULE_VERSION}: A/B/C・1着軸はVer0.1継承。"
                f"OS-alpha1で相手上位は{main}号艇、{backup}号艇、追加3着候補{third}号艇。"
            )

        sale = sales_by_key[key]
        sale["試行仕様Ver"] = RULE_VERSION
        sale["正式判定"] = judgment
        sale["1着軸"] = axis
        sale["2着本線"] = str(alpha["2着本線"] or "")
        sale["2着押さえ"] = str(alpha["2着押さえ"] or "")
        sale["2連単1点対象"] = str(alpha["2連単1点対象"])
        sale["2連単1点"] = str(alpha["2連単1点"] or "")
        sale["軸警戒"] = str(alpha["軸警戒"])
        sale["比較支持項目数"] = alpha["比較支持項目数"]
        sale["全国勝率差"] = alpha["全国勝率差"]
        sale["2着候補分離度"] = alpha["2着候補分離度"]
        sale["販売スコア"] = alpha["販売スコア"]
        sale["内部販売評価"] = ""
        sale["掲載区分"] = "対象外" if alpha["2連単1点対象"] != "対象" else "選別待ち"
        sale["選別理由"] = "2連単1点対象外" if alpha["2連単1点対象"] != "対象" else "v0.2-alpha1掲載選別待ち"
        sale["予想確定日時"] = prediction_time
        sale["販売選別確定日時"] = sales_time
        sale["結果参照状態"] = "未参照"

    # Update rationale flags so they describe the alpha1 opponent pair.
    for rat in control["rationales"]:
        key = (str(rat[1]), int(rat[2]))
        alpha = shadow_by_key[key]
        lane = int(rat[4])
        judgment = str(alpha["正式判定"])
        axis = int(alpha["1着軸"]) if alpha["1着軸"] != "" else None
        main = int(alpha["2着本線"]) if alpha["2着本線"] != "" else None
        backup = int(alpha["2着押さえ"]) if alpha["2着押さえ"] != "" else None
        third = int(alpha["追加3着候補"]) if alpha["追加3着候補"] != "" else None
        rat[12] = 1 if judgment != "C" and lane == axis else 0
        rat[13] = 1 if main is not None and lane == main else 0
        rat[14] = 1 if backup is not None and lane == backup else 0
        rat[16] = 1 if lane in {x for x in (main, backup, third) if x is not None} else 0
        rat[25] = prediction_time

    deadlines = build_deadlines(rows)
    freeze = parse_freeze(sales_time)
    venue_order: dict[str, int] = {}
    for row in rows:
        venue = str(row["会場"]).strip()
        if venue not in venue_order:
            venue_order[venue] = len(venue_order)

    eligible: list[dict[str, object]] = []
    expired: list[dict[str, object]] = []
    q0_rows: list[dict[str, object]] = []

    for key, alpha in shadow_by_key.items():
        sale = sales_by_key[key]
        if sale["2連単1点対象"] != "対象":
            continue
        if str(alpha["Q0_PairRisk"]) == "Q0":
            q0_rows.append(sale)
            sale["掲載区分"] = "非掲載"
            sale["選別理由"] = "Q0 Pair-risk Gate該当のためnote非掲載。"
            continue
        if key not in deadlines:
            raise ForwardTrialValidationError(f"missing deadline for {key}")
        if freeze >= deadlines[key]:
            expired.append(sale)
            sale["掲載区分"] = "非掲載"
            sale["選別理由"] = (
                f"締切済み掲載除外。公式締切={deadlines[key].strftime('%H:%M')}、"
                f"販売選別確定={freeze.strftime('%H:%M:%S')}。"
            )
            continue
        eligible.append(sale)

    eligible.sort(
        key=lambda row: (
            -int(row["販売スコア"]),
            -float(row["2着候補分離度"]),
            venue_order[str(row["会場"])],
            int(row["R"]),
        )
    )
    paid_count, free_count, sellable = product_split(len(eligible))
    for rank, sale in enumerate(eligible, start=1):
        if not sellable:
            listing = "販売見送り"
            reason = f"Q0通過・締切前候補{len(eligible)}R<=5のため通常販売見送り。"
        elif rank <= paid_count:
            listing = "有料"
            reason = f"Q0通過・締切前販売順位{rank}位・有料枠。"
        elif rank <= paid_count + free_count:
            listing = "無料"
            reason = f"Q0通過・締切前販売順位{rank}位・無料枠。"
        else:
            listing = "非掲載"
            reason = f"Q0通過だが日次掲載上限外（締切前販売順位{rank}位）。"
        sale["掲載区分"] = listing
        sale["内部販売評価"] = _compat_internal_eval(listing)
        sale["選別理由"] = reason

    predictions = list(control["predictions"])
    rationales = list(control["rationales"])
    sales = list(control["sales"])
    validate_active(predictions, rationales, sales, rows, sales_time)

    return {
        "date": control["date"],
        "venues": control["venues"],
        "predictions": predictions,
        "rationales": rationales,
        "sales": sales,
        "counts": Counter(row[6] for row in predictions),
        "target_count": sum(row["2連単1点対象"] == "対象" for row in sales),
        "q0_count": len(q0_rows),
        "expired_count": len(expired),
        "eligible_count": len(eligible),
        "paid_count": sum(row["掲載区分"] == "有料" for row in sales),
        "free_count": sum(row["掲載区分"] == "無料" for row in sales),
        "sellable": sellable,
    }


def validate_active(predictions, rationales, sales, racecard_rows, sales_time: str) -> None:
    if any(row[5] != RULE_VERSION for row in predictions):
        raise ForwardTrialValidationError("prediction version mismatch")
    if any(row.get("試行仕様Ver") != RULE_VERSION for row in sales):
        raise ForwardTrialValidationError("sales version mismatch")
    if any(row.get("結果参照状態") != "未参照" for row in sales):
        raise ForwardTrialValidationError("result state must remain 未参照")

    deadlines = build_deadlines(racecard_rows)
    freeze = parse_freeze(sales_time)
    for row in sales:
        if row.get("掲載区分") in {"有料", "無料"}:
            key = _key(row)
            if key not in deadlines or freeze >= deadlines[key]:
                raise ForwardTrialValidationError("paid/free contains expired race")
            if row.get("2連単1点対象") != "対象":
                raise ForwardTrialValidationError("paid/free contains non-target")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        if rows and isinstance(rows[0], dict):
            writer = csv.DictWriter(handle, fieldnames=list(columns))
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row.get(column, "") for column in columns})
        else:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows(rows)


def run(
    input_path: Path,
    output_dir: Path,
    prediction_time: str,
    sales_time: str | None = None,
    source_commit: str = "",
) -> dict[str, object]:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = list(reader.fieldnames or [])

    result = generate_active(rows, columns, prediction_time, sales_time)
    compact = str(result["date"]).replace("-", "")
    venue_part = "_".join(result["venues"])
    pred = output_dir / f"{compact}_事前予想_{venue_part}_{RULE_VERSION}.csv"
    rat = output_dir / f"{compact}_予想根拠明細_{venue_part}_{RULE_VERSION}.csv"
    sale = output_dir / f"{compact}_2連単1点販売選別_{venue_part}_{RULE_VERSION}.csv"
    manifest = output_dir / f"{compact}_ForwardTrial実行manifest_{venue_part}_{RULE_VERSION}.json"

    write_csv(pred, PREDICTION_COLUMNS, result["predictions"])
    write_csv(rat, RATIONALE_COLUMNS, result["rationales"])
    write_csv(sale, SALES_COLUMNS, result["sales"])

    source = Path(__file__).resolve()
    data = {
        "rule_version": RULE_VERSION,
        "source_commit": source_commit,
        "source_file": source.name,
        "source_file_sha256": sha256_file(source),
        "input_file": input_path.name,
        "input_sha256": sha256_file(input_path),
        "prediction_time": prediction_time,
        "sales_time": sales_time or prediction_time,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "races": len(result["predictions"]),
            "boats": len(result["rationales"]),
            "A": result["counts"].get("A", 0),
            "B": result["counts"].get("B", 0),
            "C": result["counts"].get("C", 0),
            "exacta_targets": result["target_count"],
            "q0": result["q0_count"],
            "deadline_expired": result["expired_count"],
            "eligible": result["eligible_count"],
            "paid": result["paid_count"],
            "free": result["free_count"],
            "sellable": result["sellable"],
        },
        "outputs": {
            pred.name: sha256_file(pred),
            rat.name: sha256_file(rat),
            sale.name: sha256_file(sale),
        },
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--prediction-time", required=True)
    parser.add_argument("--sales-time")
    parser.add_argument("--source-commit", default="")
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output_dir, args.prediction_time, args.sales_time, args.source_commit), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
