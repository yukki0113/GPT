"""Offline encryption, transport, and path-safety tests for the Drive/GPT/Actions bridge."""
import base64
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from drive_gpt_actions_bridge import encrypt_file, read_inputs, prepare_request, sha256
from drive_gpt_actions_inputs import validate_staged_inputs, download_staged_inputs


def make_keys():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_pem = key.private_bytes(serialization.Encoding.PEM,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode("ascii")
    return key.public_key(), private_pem


def envelope(data=b"private JRDB data", filename="PACI261024.zip", label="paci"):
    public, pem = make_keys()
    ciphertext, meta = encrypt_file(data, public)
    item = {"label": label, "filename": filename, "blob_sha": "a" * 40, **meta}
    return item, ciphertext, pem


def test_round_trip_staged_input(tmp_path, monkeypatch):
    item, cipher, pem = envelope()
    validate_staged_inputs([item], set())
    monkeypatch.setenv("GH_TOKEN", "fake-for-test")
    monkeypatch.setenv("DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM", pem)
    monkeypatch.setattr("drive_gpt_actions_inputs.get_git_blob", lambda *args: cipher)
    receipts = download_staged_inputs([item], "owner/repo", tmp_path)
    assert (tmp_path / "paci" / "PACI261024.zip").read_bytes() == b"private JRDB data"
    assert receipts[0]["integrity"] == "PASS"


def test_corrupted_ciphertext_rejected_before_decryption(tmp_path, monkeypatch):
    item, cipher, pem = envelope()
    monkeypatch.setenv("GH_TOKEN", "fake-for-test")
    monkeypatch.setenv("DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM", pem)
    monkeypatch.setattr("drive_gpt_actions_inputs.get_git_blob", lambda *args: cipher[:-1] + b"X")
    with pytest.raises(ValueError, match="ciphertext SHA-256 mismatch"):
        download_staged_inputs([item], "owner/repo", tmp_path)


def test_missing_secret_fails_closed(tmp_path, monkeypatch):
    item, _, _ = envelope()
    monkeypatch.setenv("GH_TOKEN", "fake-for-test")
    monkeypatch.delenv("DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        download_staged_inputs([item], "owner/repo", tmp_path)


@pytest.mark.parametrize("name", ["../x", "nested/x", ".hidden", ".."])
def test_filename_traversal_blocked(name):
    item, _, _ = envelope(filename=name)
    with pytest.raises(ValueError, match="unsafe staged filename"):
        validate_staged_inputs([item], set())


def test_inputs_reject_symlinks_and_duplicates(tmp_path):
    p = tmp_path / "sample.parquet"
    p.write_bytes(b"abc")
    assert len(read_inputs([f"sample={p}"])) == 1
    with pytest.raises(ValueError, match="duplicate"):
        read_inputs([f"sample={p}", f"sample={p}"])
    alias = tmp_path / "alias.parquet"
    alias.symlink_to(p)
    with pytest.raises(ValueError, match="symlink"):
        read_inputs([f"sample={alias}"])


def test_request_template_label_conflict(tmp_path):
    p = tmp_path / "input.zip"
    p.write_bytes(b"ok")
    with pytest.raises(ValueError, match="collides"):
        prepare_request({"steps": [], "input_artifacts":
                         [{"label": "source", "run_id": 1, "artifact_name": "x"}]},
                        read_inputs([f"source={p}"]))
