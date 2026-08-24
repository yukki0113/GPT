#!/usr/bin/env python3
"""Fetch a JRDB PACI ZIP, then create one RaceNote v0.2 race bundle.

The downloader remains the single owner of authentication and ZIP validation.
This wrapper never imports, prints, or writes JRDB credentials.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_FETCH_SCRIPT = HERE / "fetch_jrdb_paci.py"
DEFAULT_CONVERTER = HERE / "racenote_jrdb.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="JRDB PACI取得→RaceNote 1R JSON変換",
    )
    parser.add_argument("--date", required=True, help="対象日 YYYYMMDD (例: 20260816)")
    parser.add_argument("--race", required=True, help="例: 札幌11 / 札幌11R")
    parser.add_argument("--output", type=Path, default=Path("output"), help="出力親フォルダ")
    parser.add_argument("--fetch-script", type=Path, default=DEFAULT_FETCH_SCRIPT, help="fetch_jrdb_paci.py のパス")
    parser.add_argument("--converter", type=Path, default=DEFAULT_CONVERTER, help="racenote_jrdb.py のパス")
    parser.add_argument("--base-url", default=None, help="必要時のみPACI配布ベースURLを明示指定")
    parser.add_argument("--timeout", type=int, default=30, help="取得HTTP timeout秒")
    parser.add_argument("--force-fetch", action="store_true", help="正常キャッシュがあっても再取得")
    return parser.parse_args()


def validate_date(value: str) -> None:
    try:
        if datetime.strptime(value, "%Y%m%d").strftime("%Y%m%d") != value:
            raise ValueError
    except ValueError as exc:
        raise SystemExit(f"--date は YYYYMMDD 形式で指定してください: {value}") from exc


def main() -> int:
    args = parse_args()
    validate_date(args.date)
    if not args.fetch_script.is_file():
        raise SystemExit(f"取得Pythonが見つかりません: {args.fetch_script}")
    if not args.converter.is_file():
        raise SystemExit(f"変換Pythonが見つかりません: {args.converter}")

    paci_dir = args.output / "PACI"
    paci_name = f"PACI{args.date[2:]}.zip"
    paci_path = paci_dir / paci_name
    fetch_cmd = [sys.executable, str(args.fetch_script.resolve()), "--date", args.date, "--out-dir", str(paci_dir.resolve()), "--timeout", str(args.timeout)]
    if args.base_url:
        fetch_cmd.extend(["--base-url", args.base_url])
    if args.force_fetch:
        fetch_cmd.append("--force")

    # cwd を取得Pythonの配置先に固定し、既存の jrdb_secret.py fallback を維持する。
    subprocess.run(fetch_cmd, cwd=args.fetch_script.resolve().parent, check=True)
    if not paci_path.is_file():
        raise SystemExit(f"取得後ZIPが見つかりません: {paci_path}")

    convert_cmd = [sys.executable, str(args.converter.resolve()), str(paci_path.resolve()), "--race", args.race, "--output", str(args.output.resolve()), "--format", "json"]
    subprocess.run(convert_cmd, check=True)
    print(f"RaceNote JSON: {args.output / f'RaceNote_{args.date}' }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
