"""Decrypt/validate staged local Drive inputs in a GitHub Actions fallback run.

Only ciphertext is stored as GitHub Git blobs. Plaintext is materialized in
Actions ephemeral runner storage and never uploaded as an output artifact.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

LABEL = re.compile(r"[A-Za-z0-9_-]{1,40}")
FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}")
HEX_SHA = re.compile(r"[a-f0-9]{40}")
HEX_256 = re.compile(r"[a-f0-9]{64}")
MAX_INPUT_BYTES = 32 * 1024 * 1024


def validate_staged_inputs(items, reserved_labels: set[str]) -> set[str]:
    if not isinstance(items, list) or len(items) > 8:
        raise ValueError("staged_inputs must be an array of at most 8 items")
    labels = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("staged input must be an object")
        label, filename = item.get("label"), item.get("filename")
        if not isinstance(label, str) or not LABEL.fullmatch(label) or label in reserved_labels | labels:
            raise ValueError("invalid or duplicate staged input label")
        if not isinstance(filename, str) or not FILENAME.fullmatch(filename) or filename in (".", ".."):
            raise ValueError("unsafe staged filename")
        if not isinstance(item.get("blob_sha"), str) or not HEX_SHA.fullmatch(item["blob_sha"]):
            raise ValueError("invalid staged blob SHA")
        for name in ("plaintext_sha256", "ciphertext_sha256"):
            if not isinstance(item.get(name), str) or not HEX_256.fullmatch(item[name]):
                raise ValueError("invalid staged SHA-256")
        if type(item.get("size_bytes")) is not int or not 0 <= item["size_bytes"] <= MAX_INPUT_BYTES:
            raise ValueError("invalid staged input size")
        for name in ("wrapped_key_b64", "nonce_b64"):
            try:
                val = base64.b64decode(item[name], validate=True)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid staged {name}") from exc
            if name == "nonce_b64" and len(val) != 12:
                raise ValueError("invalid AES-GCM nonce")
            if name == "wrapped_key_b64" and not 256 <= len(val) <= 1024:
                raise ValueError("invalid wrapped key length")
        labels.add(label)
    return labels


def get_git_blob(repo: str, sha: str, token: str) -> bytes:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/git/blobs/{sha}",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            response = json.load(res)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"staged blob download failed: HTTP {exc.code}") from exc
    if response.get("encoding") != "base64" or response.get("sha") != sha:
        raise ValueError("unrecognized Git blob response")
    # Git blob API JSON uses base64 with optional newlines.
    cipher = base64.b64decode(response["content"], validate=False)
    if len(cipher) > MAX_INPUT_BYTES + 16:
        raise ValueError("staged blob exceeds size limit")
    return cipher


def download_staged_inputs(items: list[dict], repository: str, destination: Path) -> list[dict]:
    if not items:
        return []
    token = os.environ.get("GH_TOKEN")
    pem = os.environ.get("DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM")
    if not token:
        raise RuntimeError("GH_TOKEN missing for staged input retrieval")
    if not pem:
        raise RuntimeError("DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM secret not configured")
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = load_pem_private_key(pem.encode("ascii"), password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 3072:
        raise RuntimeError("invalid bridge private key")
    audits = []
    for item in items:
        cipher = get_git_blob(repository, item["blob_sha"], token)
        if hashlib.sha256(cipher).hexdigest() != item["ciphertext_sha256"]:
            raise ValueError("staged ciphertext SHA-256 mismatch")
        aes_key = key.decrypt(base64.b64decode(item["wrapped_key_b64"]),
                              padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                           algorithm=hashes.SHA256(), label=None))
        raw = AESGCM(aes_key).decrypt(base64.b64decode(item["nonce_b64"]), cipher, None)
        if len(raw) != item["size_bytes"] or hashlib.sha256(raw).hexdigest() != item["plaintext_sha256"]:
            raise ValueError("staged plaintext size/SHA-256 mismatch")
        parent = destination / item["label"]
        parent.mkdir(parents=True, exist_ok=False)
        target = parent / item["filename"]
        with target.open("xb") as f:
            f.write(raw)
        audits.append({"label": item["label"], "filename": item["filename"],
                       "blob_sha": item["blob_sha"], "size_bytes": len(raw),
                       "plaintext_sha256": item["plaintext_sha256"], "integrity": "PASS"})
    return audits
