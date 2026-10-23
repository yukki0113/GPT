"""Archive helper regression tests for staged inputs."""
import io
from pathlib import Path
import sys
import tarfile
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from safe_unpack_staged_archive import safe_unpack


def test_safe_extract_valid_xz_analysis_archive(tmp_path):
    p = tmp_path / "analysis.tar.xz"
    payload = b"PAR1example"
    with tarfile.open(p, "w:xz") as tar:
        info = tarfile.TarInfo("objects/fact/year=2025/example.parquet")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    output = tmp_path / "unpacked"
    result = safe_unpack(p, output)
    assert result["status"] == "PASS"
    assert (output / "objects/fact/year=2025/example.parquet").read_bytes() == payload


def test_reject_tar_traversal(tmp_path):
    p = tmp_path / "escape.tar"
    with tarfile.open(p, "w") as tar:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"X"))
    with pytest.raises(ValueError, match="unsafe"):
        safe_unpack(p, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_reject_tar_symlink(tmp_path):
    p = tmp_path / "links.tar"
    with tarfile.open(p, "w") as tar:
        info = tarfile.TarInfo("linked")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)
    with pytest.raises(ValueError, match="links/devices"):
        safe_unpack(p, tmp_path / "out")


def test_reject_zip_traversal(tmp_path):
    p = tmp_path / "escape.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("../escape.txt", b"X")
    with pytest.raises(ValueError, match="unsafe"):
        safe_unpack(p, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()
