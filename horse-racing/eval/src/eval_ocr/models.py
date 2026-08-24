from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class PanelBox:
    venue_index: int
    row_in_venue: int
    col_index: int
    race_no: int
    x: int
    y: int
    width: int
    height: int
    venue: Optional[str] = None
    header_ocr: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HorseRecord:
    date: str
    venue: str
    race_no: int
    horse_no: int
    horse_name_ocr: str
    eval: Optional[int]

    def to_dict(self) -> dict:
        return asdict(self)
