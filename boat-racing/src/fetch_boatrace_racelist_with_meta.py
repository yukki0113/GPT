#!/usr/bin/env python3
"""BOAT RACE公式出走表を取得し、公式開催メタデータまで付与する標準入口。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """既存fetcher成功後に開催グレード・開催名を付与する。"""
    parser = argparse.ArgumentParser(description="BOAT RACE公式出走表を開催メタデータ付きCSVへ保存")
    parser.add_argument("--config", required=True, help="出走表取得設定JSON")
    args = parser.parse_args()

    source_dir = Path(__file__).resolve().parent
    fetcher = source_dir / "fetch_boatrace_racelist.py"
    enricher = source_dir / "enrich_boatrace_racelist_metadata.py"

    fetched = subprocess.run(
        [sys.executable, str(fetcher), "--config", args.config],
        check=False,
    )
    if fetched.returncode != 0:
        return fetched.returncode

    enriched = subprocess.run(
        [sys.executable, str(enricher), "--config", args.config],
        check=False,
    )
    return enriched.returncode


if __name__ == "__main__":
    raise SystemExit(main())
