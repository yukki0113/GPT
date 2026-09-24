#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import requests

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def get(url: str, **kwargs):
    response = requests.get(url, timeout=120, **kwargs)
    response.raise_for_status()
    return response


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    request = json.load(open(args.request_json, encoding="utf-8"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    date = request["date"]
    spreadsheet_id = request["spreadsheet_id"]
    sheet_name = request.get("sheet_name", "イルカ明細")

    url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={quote(sheet_name)}"
    )
    rows = list(
        csv.DictReader(
            io.StringIO(get(url).content.decode("utf-8-sig"))
        )
    )
    selected = [row for row in rows if (row.get("日付") or "").strip() == date]
    if not selected:
        raise RuntimeError(f"no ledger rows for {date}")

    csv_path = output_dir / f"keibailuka_{date.replace('-', '')}_from_ledger.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = ["日付", "会場", "R", "馬名_raw", "コメント"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in selected:
            writer.writerow(
                {
                    "日付": row.get("日付", ""),
                    "会場": row.get("会場", ""),
                    "R": row.get("R", ""),
                    "馬名_raw": row.get("馬名_raw", ""),
                    "コメント": row.get("コメント", ""),
                }
            )

    paci_path = output_dir / f"PACI_{date.replace('-', '')}.zip"
    data = get(
        "https://drive.usercontent.google.com/download",
        params={
            "id": request["paci_drive_file_id"],
            "export": "download",
            "confirm": "t",
        },
    ).content
    if b"<html" in data[:200].lower():
        data = get(
            "https://drive.google.com/uc",
            params={"export": "download", "id": request["paci_drive_file_id"]},
        ).content
    paci_path.write_bytes(data)
    expected_size = request.get("paci_size_bytes")
    if expected_size is not None and paci_path.stat().st_size != int(expected_size):
        raise RuntimeError(
            f"PACI size mismatch expected={expected_size} actual={paci_path.stat().st_size}"
        )

    scorer = (
        REPOSITORY_ROOT
        / "horse-racing"
        / "fetch_keibailuka_blog"
        / "src"
        / "score_keibailuka_shadow_v01.py"
    )
    subprocess.run(
        [
            sys.executable,
            str(scorer),
            "--keibailuka-csv",
            str(csv_path),
            "--paci",
            str(paci_path),
            "--output-dir",
            str(output_dir / "score"),
        ],
        check=True,
    )
    result = json.loads(
        (output_dir / "score" / "shadow_result.json").read_text(encoding="utf-8")
    )
    result["ledger_rows"] = len(selected)
    (output_dir / "shadow_smoke_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
