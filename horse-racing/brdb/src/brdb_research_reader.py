"""Explicit, fail-closed as-of access to an immutable BRDB research candidate.

The candidate Parquet stores the latest daily profile, not every historical
snapshot. Before its selected source observation date, suppress that profile
rather than expose future information. Historical reconstruction is NOT
implemented by this reader.
"""
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

        def verified_json(name: str):
            expected = manifest["output_sha256"].get(name)
            path = Path(generation_path) / name
            if not isinstance(expected, str) or not path.is_file() or _sha256(path) != expected:
                raise BloodReviewReaderError(f"research {name} audit mismatch")
            return json.loads(path.read_text(encoding="utf-8"))

        rows = verified_json("added_104.json")
        if len(rows) != 104 or len({x["horse_id"] for x in rows}) != 104:
            raise BloodReviewReaderError("research added-ID audit must contain 104 unique IDs")
        self.first_seen = {x["horse_id"]: x["first_observed_archive_date"] for x in rows}

        # The source Parquet is a latest-profile snapshot. We cannot safely
        # show it between first sighting and the selected latest observation.
        # Use the SHA-pinned observation history already in the v0.1 artifact.
        history = verified_json("observation_history.json")
        selected = {}
        for observation in history:
            if observation.get("selected") is not True:
                continue
            horse_id = observation["horse_id"]
            if horse_id in selected:
                raise BloodReviewReaderError(f"duplicate selected profile: {horse_id}")
            selected[horse_id] = observation["archive_date"]
        if set(selected) != set(self.first_seen):
            raise BloodReviewReaderError("selected history does not match added IDs")
        for horse_id, archive_date in selected.items():
            if (not re.fullmatch(r"\d{8}", archive_date)
                    or archive_date < self.first_seen[horse_id]):
                raise BloodReviewReaderError(f"invalid selected profile date: {horse_id}")
            datetime.strptime(archive_date, "%Y%m%d")
        self.latest_profile_available_from = selected

    @property
    def generation_id(self) -> str:
        return self._reader.generation_id

    def _available(self, horse_id: str, as_of: str) -> bool:
        if not re.fullmatch(r"\d{8}", as_of):
            raise ValueError("as_of must be YYYYMMDD")
        datetime.strptime(as_of, "%Y%m%d")
        # For daily additions, latest Parquet data is not point-in-time
        # historical data. Return no row until its selected source was observed.
        return horse_id not in self.latest_profile_available_from or (
            self.latest_profile_available_from[horse_id] <= as_of)

    def horse_pedigree(self, horse_id: str, *, as_of: str):
        if not self._available(horse_id, as_of):
            return None
        return self._reader.horse_pedigree(horse_id)

    def profiles_for_horses(self, horse_ids, *, as_of: str):
        ids = [horse_id for horse_id in horse_ids if self._available(horse_id, as_of)]
        return self._reader.profiles_for_horses(ids)
