"""RaceLap CURRENT resolver orchestration regression."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from jrdb_race_lap_contract import DATASET_SCHEMA_VERSION, LOGIC_VERSION
from jrdb_race_lap_current_resolver import (
    RaceLapCurrentResolverError,
    resolve_current,
)
from jrdb_race_lap_store import RaceLapStore
from test_jrdb_race_lap_dataset import archive, build_dataset, build_rows


def _current_bundle(tmp_path):
    source = archive(tmp_path)
    bundle = tmp_path / "current"
    bundle.mkdir()
    parquet = bundle / "race_lap.parquet"
    build_dataset([source], parquet, bundle / "audit.json")
    meta = RaceLapStore(parquet).metadata()
    digest = hashlib.sha256(parquet.read_bytes()).hexdigest()
    manifest = {
        "schema_version": "jrdb-race-lap-forward-current-0.1",
        "status": "CURRENT",
        "generation_id": "racelap-current-test",
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "shape_logic_version": LOGIC_VERSION,
        "period_from": meta["min_race_date"],
        "period_to": meta["max_race_date"],
        "race_count": meta["race_count"],
        "parquet_sha256": digest,
        "parquet_size_bytes": parquet.stat().st_size,
        "validation_status": "PASS",
    }
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return bundle, source, build_rows([source])[0]


def test_fresh_current_is_returned_without_update(tmp_path):
    bundle, _, baseline = _current_bundle(tmp_path)
    result = resolve_current(
        bundle,
        "2026-10-17",
        baseline["race_date"],
    )
    assert result["status"] == "CURRENT_READY"
    assert result["updated"] is False
    assert result["period_to"] == baseline["race_date"]
    assert result["network_access"] is False
    assert result["source_policy"] == "VERIFIED_EXISTING_CURRENT"


def test_stale_current_requires_explicit_canonical_sed(tmp_path):
    bundle, _, _ = _current_bundle(tmp_path)
    with pytest.raises(RaceLapCurrentResolverError, match="Explicit canonical SED"):
        resolve_current(
            bundle,
            "2026-10-17",
            "2026-10-13",
        )


def test_stale_current_refreshes_promotes_and_returns_ready(
    tmp_path,
    monkeypatch,
):
    import jrdb_race_lap_forward_refresh as refresh_module

    bundle, source, baseline = _current_bundle(tmp_path)
    newer = copy.deepcopy(baseline)
    newer["race_key"] = "05274501"
    newer["race_date"] = "2026-10-13"
    monkeypatch.setattr(refresh_module, "build_rows", lambda _: [newer])

    resolved = tmp_path / "resolved"
    result = resolve_current(
        bundle,
        "2026-10-17",
        "2026-10-13",
        sed_archives=[source],
        expected_dates=["2026-10-13"],
        work_root=tmp_path / "work",
        generation_id="racelap-resolved-test",
        resolved_bundle=resolved,
    )

    assert result["status"] == "CURRENT_READY"
    assert result["updated"] is True
    assert result["period_to"] == "2026-10-13"
    assert result["race_count"] == 2
    assert result["network_access"] is False
    assert result["source_policy"] == "EXPLICIT_LOCAL_CANONICAL_SED_ONLY"
    manifest = json.loads((resolved / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "CURRENT"
    assert manifest["generation_id"] == "racelap-resolved-test"


def test_resolver_rejects_analysis_cutoff_on_target_date(tmp_path):
    bundle, _, _ = _current_bundle(tmp_path)
    with pytest.raises(
        RaceLapCurrentResolverError,
        match="earlier than target date",
    ):
        resolve_current(
            bundle,
            "2026-10-17",
            "2026-10-17",
        )
