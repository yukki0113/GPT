from __future__ import annotations

import csv
from pathlib import Path

from .models import HorseRecord


FIELDNAMES = ["date", "venue", "race_no", "horse_no", "eval"]


def write_csv(path: str | Path, records: list[HorseRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())
