"""Tests for PACI-to-annual JRDB raw bundling."""
from __future__ import annotations

import datetime as dt
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import bundle_jrdb_paci_year as bundler  # noqa: E402


def _write_paci(path: Path, members: dict[str, bytes]) -> None:
    """Write one synthetic PACI daily ZIP."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def test_bundle_extracts_requested_kinds_without_changing_bytes(tmp_path: Path) -> None:
    """PACI members are copied unchanged into annual kind ZIPs."""
    source = tmp_path / "paci"
    output = tmp_path / "raw"
    _write_paci(
        source / "PACI260104.zip",
        {
            "BAC260104.txt": b"bac-0104\n",
            "nested/KYI260104.txt": b"kyi-0104\n",
            "UKC260104.txt": b"ukc-0104\n",
            "CHA260104.txt": b"cha-0104\n",
            "CYB260104.txt": b"cyb-0104\n",
            "JOA260104.txt": b"ignored\n",
        },
    )
    _write_paci(
        source / "PACI260105.zip",
        {
            "BAC260105.txt": b"bac-0105\n",
            "KYI260105.txt": b"kyi-0105\n",
            "UKC260105.txt": b"ukc-0105\n",
            "CHA260105.txt": b"cha-0105\n",
            "CYB260105.txt": b"cyb-0105\n",
        },
    )

    result = bundler.bundle(
        source_dir=source,
        output_root=output,
        year=2026,
        kinds=bundler.DEFAULT_KINDS,
        start_date=dt.date(2026, 1, 4),
        end_date=dt.date(2026, 1, 5),
    )

    assert result["status"] == "success"
    assert result["common"]["daily_archive_count"] == 2
    assert result["common"]["ignored_member_count"] == 1
    for kind in bundler.DEFAULT_KINDS:
        annual = output / kind / f"{kind}_2026.zip"
        assert annual.exists()
        first_member = f"{kind}260104.TXT"
        second_member = f"{kind}260105.TXT"
        with zipfile.ZipFile(annual) as archive:
            assert archive.namelist() == [first_member, second_member]
            assert archive.read(first_member) == f"{kind.lower()}-0104\n".encode()
            assert archive.read(second_member) == f"{kind.lower()}-0105\n".encode()


def test_bundle_fails_on_member_date_mismatch(tmp_path: Path) -> None:
    """A PACI member whose date differs from its container fails closed."""
    source = tmp_path / "paci"
    _write_paci(
        source / "PACI260104.zip",
        {
            "BAC260105.txt": b"wrong-date\n",
            "KYI260104.txt": b"kyi\n",
            "UKC260104.txt": b"ukc\n",
            "CHA260104.txt": b"cha\n",
            "CYB260104.txt": b"cyb\n",
        },
    )

    with pytest.raises(ValueError, match="member date mismatch"):
        bundler.bundle(
            source_dir=source,
            output_root=tmp_path / "raw",
            year=2026,
            kinds=bundler.DEFAULT_KINDS,
            start_date=None,
            end_date=None,
        )


def test_bundle_fails_when_requested_kind_is_absent(tmp_path: Path) -> None:
    """Missing requested kind coverage fails rather than silently emitting an empty ZIP."""
    source = tmp_path / "paci"
    _write_paci(
        source / "PACI260104.zip",
        {
            "BAC260104.txt": b"bac\n",
            "KYI260104.txt": b"kyi\n",
            "UKC260104.txt": b"ukc\n",
            "CHA260104.txt": b"cha\n",
        },
    )

    with pytest.raises(ValueError, match="no canonical members"):
        bundler.bundle(
            source_dir=source,
            output_root=tmp_path / "raw",
            year=2026,
            kinds=bundler.DEFAULT_KINDS,
            start_date=None,
            end_date=None,
        )
