#!/usr/bin/env python3
"""Read-only consumer contract for BRDB pedigree CURRENT.

The Reader validates a CURRENT pointer, immutable generation manifest, required
objects, and SHA-256 values before exposing horse_id-only queries. Horse names
are descriptive only and are never accepted as identity fallback.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

CURRENT_FILENAME = "current.json"
REQUIRED_FILES = (
    "pedigree_fact.parquet",
    "parent_relation.parquet",
    "pedigree_name_alias.parquet",
    "lineage_code_master.parquet",
    "audit.json",
)
SUPPORTED_SCHEMA_VERSIONS = {"v0.1"}
READER_CONTRACT_VERSION = "v0.1"


class BloodReviewReaderError(RuntimeError):
    """Raised when BRDB CURRENT cannot satisfy the consumer contract."""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BloodReviewReaderError(f"unreadable BRDB JSON: {path}") from exc
    if not isinstance(value, dict):
        raise BloodReviewReaderError(f"BRDB JSON object required: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise BloodReviewReaderError(f"invalid relative path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise BloodReviewReaderError(f"path escapes BRDB root: {relative}") from exc
    return candidate


class BloodReviewReader:
    """Query one validated BRDB pedigree CURRENT root through DuckDB."""

    def __init__(self, root: Path, *, verify_hashes: bool = True) -> None:
        self.root = Path(root).resolve()
        current = _read_json(self.root / CURRENT_FILENAME)

        if current.get("status") != "CURRENT":
            raise BloodReviewReaderError("BRDB current pointer is not CURRENT")
        if current.get("artifact_type") != "brdb_pedigree":
            raise BloodReviewReaderError("unexpected BRDB artifact type")
        if current.get("reader_contract_version") != READER_CONTRACT_VERSION:
            raise BloodReviewReaderError("unsupported BRDB reader contract version")

        manifest_ref = current.get("manifest")
        if not isinstance(manifest_ref, str):
            raise BloodReviewReaderError("BRDB current has no manifest")
        manifest_path = _safe_relative(self.root, manifest_ref)
        if not manifest_path.is_file():
            raise BloodReviewReaderError("BRDB manifest is missing")

        self.manifest = _read_json(manifest_path)
        if self.manifest.get("artifact_type") != "brdb_pedigree":
            raise BloodReviewReaderError("unexpected BRDB manifest artifact type")
        if self.manifest.get("validation_status") != "PASS":
            raise BloodReviewReaderError("BRDB manifest is not PASS")
        if self.manifest.get("generation_id") != current.get("generation_id"):
            raise BloodReviewReaderError("BRDB current/manifest generation mismatch")

        self.generation_id = _text(self.manifest.get("generation_id"))
        self.schema_version = _text(self.manifest.get("schema_version"))
        self.builder_version = _text(self.manifest.get("builder_version"))
        self.alias_version = _text(self.manifest.get("alias_version"))
        self.source_min_data_date = _text(self.manifest.get("source_min_data_date"))
        self.source_max_data_date = _text(self.manifest.get("source_max_data_date"))
        if not self.generation_id:
            raise BloodReviewReaderError("BRDB generation_id is empty")
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise BloodReviewReaderError(
                f"unsupported BRDB schema version: {self.schema_version}"
            )

        hashes = self.manifest.get("output_sha256")
        if not isinstance(hashes, Mapping):
            raise BloodReviewReaderError("BRDB manifest has no output_sha256")

        self._paths: dict[str, Path] = {}
        for filename in REQUIRED_FILES:
            expected = hashes.get(filename)
            if not isinstance(expected, str) or len(expected) != 64:
                raise BloodReviewReaderError(
                    f"BRDB manifest hash missing/invalid: {filename}"
                )
            path = _safe_relative(self.root, filename)
            if not path.is_file():
                raise BloodReviewReaderError(f"BRDB object missing: {filename}")
            if verify_hashes and _sha256(path) != expected:
                raise BloodReviewReaderError(f"BRDB SHA-256 mismatch: {filename}")
            self._paths[filename] = path

        row_counts = self.manifest.get("row_counts")
        if not isinstance(row_counts, Mapping):
            raise BloodReviewReaderError("BRDB manifest has no row_counts")
        pedigree_rows = row_counts.get("pedigree_fact")
        relation_rows = row_counts.get("parent_relation")
        if not isinstance(pedigree_rows, int) or pedigree_rows < 1:
            raise BloodReviewReaderError("invalid pedigree_fact row count")
        if relation_rows != pedigree_rows * 3:
            raise BloodReviewReaderError(
                "parent_relation row count must equal 3 x pedigree_fact"
            )

    @staticmethod
    def _rows(cursor: Any) -> list[dict[str, object]]:
        names = [item[0] for item in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    @staticmethod
    def _require_horse_id(horse_id: object) -> str:
        value = _text(horse_id)
        if not value:
            raise ValueError("horse_id is required")
        return value

    def _connect(self):
        try:
            import duckdb
        except ImportError as exc:
            raise BloodReviewReaderError("BRDB reader requires duckdb") from exc
        return duckdb.connect(database=":memory:", read_only=False)

    def metadata(self) -> dict[str, object]:
        """Return stable provenance suitable for consumer logging."""
        return {
            "artifact_type": "brdb_pedigree",
            "generation_id": self.generation_id,
            "schema_version": self.schema_version,
            "builder_version": self.builder_version,
            "alias_version": self.alias_version,
            "source_min_data_date": self.source_min_data_date,
            "source_max_data_date": self.source_max_data_date,
            "row_counts": dict(self.manifest["row_counts"]),
            "reader_contract_version": READER_CONTRACT_VERSION,
            "name_fallback": False,
        }

    def horse_profile(self, horse_id: str) -> dict[str, object] | None:
        """Return one canonical pedigree fact row by JRDB horse_id."""
        horse_id = self._require_horse_id(horse_id)
        con = self._connect()
        try:
            cursor = con.execute(
                "SELECT * FROM read_parquet(?) WHERE horse_id = ? LIMIT 2",
                [str(self._paths["pedigree_fact.parquet"]), horse_id],
            )
            rows = self._rows(cursor)
        finally:
            con.close()
        if len(rows) > 1:
            raise BloodReviewReaderError(
                f"duplicate pedigree_fact horse_id: {horse_id}"
            )
        return rows[0] if rows else None

    def parent_relations(self, horse_id: str) -> list[dict[str, object]]:
        """Return sire/dam/BMS relation resolution rows for one horse."""
        horse_id = self._require_horse_id(horse_id)
        con = self._connect()
        try:
            cursor = con.execute(
                """
                SELECT *
                FROM read_parquet(?)
                WHERE child_horse_id = ?
                ORDER BY CASE role
                    WHEN 'sire' THEN 1
                    WHEN 'dam' THEN 2
                    WHEN 'broodmare_sire' THEN 3
                    ELSE 9
                END, role
                """,
                [str(self._paths["parent_relation.parquet"]), horse_id],
            )
            return self._rows(cursor)
        finally:
            con.close()

    def lineage(self, lineage_code: str) -> dict[str, object] | None:
        """Resolve one official JRDB lineage code."""
        code = _text(lineage_code)
        if not code:
            return None
        con = self._connect()
        try:
            cursor = con.execute(
                "SELECT * FROM read_parquet(?) WHERE lineage_code = ? LIMIT 2",
                [str(self._paths["lineage_code_master.parquet"]), code],
            )
            rows = self._rows(cursor)
        finally:
            con.close()
        if len(rows) > 1:
            raise BloodReviewReaderError(
                f"duplicate lineage_code: {code}"
            )
        return rows[0] if rows else None

    def horse_pedigree(self, horse_id: str) -> dict[str, object] | None:
        """Return stable v0.1 consumer projection for one horse."""
        profile = self.horse_profile(horse_id)
        if profile is None:
            return None
        relations = self.parent_relations(horse_id)
        relation_map = {str(row.get("role")): row for row in relations}
        return {
            "horse_id": profile.get("horse_id"),
            "horse_name": profile.get("horse_name"),
            "birth_date": profile.get("birth_date"),
            "sire": {
                "name": profile.get("sire_name"),
                "birth_year": profile.get("sire_birth_year"),
                "lineage_code": profile.get("sire_line_code"),
                "lineage": self.lineage(_text(profile.get("sire_line_code"))),
                "relation": relation_map.get("sire"),
            },
            "dam": {
                "name": profile.get("dam_name"),
                "birth_year": profile.get("dam_birth_year"),
                "relation": relation_map.get("dam"),
            },
            "broodmare_sire": {
                "name": profile.get("broodmare_sire_name"),
                "birth_year": profile.get("broodmare_sire_birth_year"),
                "lineage_code": profile.get("broodmare_sire_line_code"),
                "lineage": self.lineage(
                    _text(profile.get("broodmare_sire_line_code"))
                ),
                "relation": relation_map.get("broodmare_sire"),
            },
            "coverage": {
                "sire": bool(profile.get("sire_name")),
                "dam": bool(profile.get("dam_name")),
                "broodmare_sire": bool(profile.get("broodmare_sire_name")),
            },
            "provenance": self.metadata(),
        }

    def profiles_for_horses(
        self,
        horse_ids: Iterable[str],
    ) -> dict[str, dict[str, object]]:
        """Return canonical profile rows keyed by horse_id; missing IDs omitted."""
        ids = [self._require_horse_id(value) for value in horse_ids]
        if not ids:
            return {}
        unique_ids = list(dict.fromkeys(ids))
        marks = ",".join("?" for _ in unique_ids)
        con = self._connect()
        try:
            cursor = con.execute(
                f"SELECT * FROM read_parquet(?) WHERE horse_id IN ({marks})",
                [str(self._paths["pedigree_fact.parquet"]), *unique_ids],
            )
            rows = self._rows(cursor)
        finally:
            con.close()
        output: dict[str, dict[str, object]] = {}
        for row in rows:
            horse_id = _text(row.get("horse_id"))
            if horse_id in output:
                raise BloodReviewReaderError(
                    f"duplicate pedigree_fact horse_id: {horse_id}"
                )
            output[horse_id] = row
        return output
