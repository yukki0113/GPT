"""Stable JSON-compatible, consumer-facing JRDB leader race-lap evidence.

SRB is post-race evidence. For a prediction on date D, consumers must select
only source_race_date < D. This reader exposes that policy; it has no target
race date and performs no prediction, scoring or threshold classification.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jrdb_race_lap_contract import (
    EVIDENCE_SCHEMA_VERSION, LOGIC_VERSION, POLICY, SHAPE_COLUMNS, reconstruct_segments,
)
from jrdb_race_lap_store import RaceLapStore


class RaceLapReader:
    def __init__(self, store: RaceLapStore) -> None:
        self.store = store

    @classmethod
    def from_parquet(cls, parquet_path: Path) -> "RaceLapReader":
        return cls(RaceLapStore(parquet_path))

    @staticmethod
    def _context(row: dict[str, Any] | None) -> dict[str, object] | None:
        if row is None:
            return None
        distances = list(row["segment_distances_m"])
        times = list(row["lap_times_sec"])
        shape = {key: row[key] for key in SHAPE_COLUMNS}
        if row["coverage_status"] == "NO_LAPS":
            shape = dict.fromkeys(SHAPE_COLUMNS)
        return {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "logic_version": LOGIC_VERSION,
            "race": {key: row[key] for key in ("race_key", "race_date", "surface_code", "distance_m")},
            "coverage": {
                "status": row["coverage_status"],
                **{key: row[key] for key in ("lap_count", "comparable_200m_lap_count", "partial_first_segment",
                                             "early_late_delta_available", "optional_srb_context_available")},
            },
            "laps": {
                "basis": "LEADER_SECTIONALS", "individual_horse_sectionals": False,
                "segment_distances_m": distances, "lap_times_sec": times,
                "segments": reconstruct_segments(distances, times),
            },
            "shape": shape,
            "srb_context": {"track_bias": dict(row["track_bias_raw"]), "race_comment": row["race_comment"]},
            "provenance": {
                "source_kind": "JRDB_SRB", "archive": row["source_archive"],
                "sed_member": row["source_sed_member"], "srb_member": row["source_srb_member"],
                "dataset_schema_version": row["dataset_schema_version"],
            },
            "policy": dict(POLICY),
        }

    def get_race_context(self, race_key: str) -> dict[str, object] | None:
        return self._context(self.store.get(race_key))

    def get_race_contexts(self, race_keys: Iterable[str]) -> dict[str, dict[str, object] | None]:
        return {key: self._context(row) for key, row in self.store.get_many(race_keys).items()}
