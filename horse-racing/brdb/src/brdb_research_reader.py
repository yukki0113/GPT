"""Explicit, as-of guarded access to an immutable BRDB research candidate."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from brdb_pedigree_reader import BloodReviewReader, BloodReviewReaderError, _sha256


class ResearchPedigreeReader:
    def __init__(self, generation_path: Path) -> None:
        self._reader = BloodReviewReader(generation_path, research_generation=True)
        manifest = self._reader.manifest
        expected = manifest["output_sha256"].get("added_104.json")
        path = Path(generation_path) / "added_104.json"
        if not isinstance(expected, str) or _sha256(path) != expected:
            raise BloodReviewReaderError("research added-ID audit mismatch")
        rows = json.loads(path.read_text(encoding="utf-8"))
        if len(rows) != 104 or len({x["horse_id"] for x in rows}) != 104:
            raise BloodReviewReaderError("research added-ID audit must contain 104 unique IDs")
        self.first_seen = {x["horse_id"]: x["first_observed_archive_date"] for x in rows}

    @property
    def generation_id(self) -> str:
        return self._reader.generation_id

    def _available(self, horse_id: str, as_of: str) -> bool:
        if not re.fullmatch(r"\d{8}", as_of):
            raise ValueError("as_of must be YYYYMMDD")
        datetime.strptime(as_of, "%Y%m%d")
        return horse_id not in self.first_seen or self.first_seen[horse_id] <= as_of

    def horse_pedigree(self, horse_id: str, *, as_of: str):
        if not self._available(horse_id, as_of):
            return None
        return self._reader.horse_pedigree(horse_id)

    def profiles_for_horses(self, horse_ids, *, as_of: str):
        ids = [horse_id for horse_id in horse_ids if self._available(horse_id, as_of)]
        return self._reader.profiles_for_horses(ids)
