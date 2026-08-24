#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytesseract

from eval_ocr.csv_writer import write_csv
from eval_ocr.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OCR master_eval table image into CSV (PoC v0.1).")
    parser.add_argument("--image", required=True, help="Input JPEG/PNG path")
    parser.add_argument("--date", default="", help="Race date, e.g. 2026-08-22. Optional for structural tests.")
    parser.add_argument("--outdir", default="output", help="Output directory")
    parser.add_argument("--expected-venues", type=int, choices=[2, 3], default=None, help="Optional structural assertion")
    parser.add_argument("--tesseract-cmd", default=None, help="Optional path to tesseract executable")
    parser.add_argument("--debug", action="store_true", help="Write panel crops for debugging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd

    image_path = Path(args.image)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = image_path.stem
    csv_path = outdir / f"eval_ocr_{stem}.csv"
    report_path = outdir / f"eval_ocr_{stem}_validation.json"
    debug_dir = outdir / f"eval_ocr_{stem}_debug" if args.debug else None

    records, report, _ = run_pipeline(
        image_path=image_path,
        date=args.date,
        expected_venues=args.expected_venues,
        debug_dir=debug_dir,
    )
    write_csv(csv_path, records)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = report["summary"]
    print(f"status={report['status']}")
    print(f"venues={summary['detected_venues']} races={summary['race_panels']} horses={summary['horse_rows']}")
    print(f"csv={csv_path}")
    print(f"validation={report_path}")
    if report["errors"]:
        for error in report["errors"]:
            print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARN: {warning}")
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
