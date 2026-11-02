"""A01: historical golden RRDB must remain pinned to an archived generation."""
from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "horse-racing/jrdb/config/public_drive/racenote_historical_golden_20251228_v1.json"
sys.path.insert(0, str(ROOT / "tools/gpt_io/public_drive"))
from fetch import FetchError, fetch, read_manifest  # noqa: E402

GOLDEN_ID = "golden_20"
ARCHIVE_FILE_ID = "1qP-LQwELUTZsEPBxCAVoIO8e-rphchLC"
MUTABLE_CURRENT_FILE_ID = "1UwNfrupMTHRPhkzULPvClGre4MWz2TFg"
EXPECTED_SHA = "a46eb35f2525cada2ae42ec4e0f2d783e5cb7ed24db5eb2d9b7c07e2322099f9"
EXPECTED_SIZE = 47410583
EXPECTED_GENERATION = "jrdb_race_review_v0_1_incremental_g38052055588"


def test_historical_golden_uses_archived_rrdb_generation_not_mutable_current():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["transport"] == "public_google_drive"
    rows = [r for r in read_manifest(MANIFEST) if r["artifact_id"] == GOLDEN_ID]
    assert len(rows) == 1
    row = rows[0]
    assert row["file_id"] == ARCHIVE_FILE_ID
    assert row["file_id"] != MUTABLE_CURRENT_FILE_ID
    assert (row["expected_size"], row["sha256"]) == (EXPECTED_SIZE, EXPECTED_SHA)
    assert row["destination"] == row["expected_name"] == "rrdb.zip"
    # The golden archive is reproduced as rrdb.zip for both historical consumers.
    for consumer in (
        ".github/workflows/racenote_historical_v052_equivalence.yml",
        ".github/workflows/racenote_btday_v052_prepare.yml",
    ):
        content = (ROOT / consumer).read_text(encoding="utf-8")
        assert MANIFEST.relative_to(ROOT).as_posix() in content
        assert "rrdb.zip" in content


def test_historical_golden_fails_closed_on_replaced_current_bytes(tmp_path):
    """A valid name/size is insufficient if the snapshot's content changes."""
    row = next(r for r in read_manifest(MANIFEST) if r["artifact_id"] == GOLDEN_ID)
    # Simulates a replaced CURRENT with exactly the accepted archive's size.
    def mismatching_downloader(file_id, output):
        assert file_id == ARCHIVE_FILE_ID
        Path(output).write_bytes(b"X" * EXPECTED_SIZE)
        return str(output)

    with pytest.raises(FetchError, match="download/integrity failed"):
        fetch(MANIFEST, tmp_path, selected=GOLDEN_ID, downloader=mismatching_downloader)
    assert not (tmp_path / row["destination"]).exists()
