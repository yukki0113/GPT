#!/usr/bin/env python3
"""Secure GPT-side staging of local Drive downloads for data-storage Actions.

The GitHub repository may be PUBLIC. Raw bytes and decryption keys never enter
Issues, git trees, workflow inputs, or logs. Git blobs contain AES-GCM ciphertext.
A configured Actions secret holds the RSA private key.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import urllib.error
import urllib.request

MAX_INPUT_BYTES = 32 * 1024 * 1024
LABEL = re.compile(r"[A-Za-z0-9_-]{1,40}")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def github_request(repo: str, resource: str, token: str, payload: dict) -> dict:
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    req = urllib.request.Request(
        "https://api.github.com/repos/" + repo + resource,
        data=data,
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Never include request body or credentials in errors.
        raise RuntimeError(f"GitHub {resource} failed: HTTP {exc.code}") from exc


def load_public_key(path: Path):
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = load_pem_public_key(path.read_bytes())
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072:
        raise ValueError("bridge public key must be RSA >=3072 bits")
    return key


def encrypt_file(data: bytes, key):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes
    aes_key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    cipher = AESGCM(aes_key).encrypt(nonce, data, None)
    wrapped = key.encrypt(
        aes_key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    return cipher, {
        "wrapped_key_b64": base64.b64encode(wrapped).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "plaintext_sha256": sha256(data),
        "ciphertext_sha256": sha256(cipher),
        "size_bytes": len(data),
    }


def read_inputs(definitions: list[str]) -> list[tuple[str, Path, bytes]]:
    if not definitions:
        raise ValueError("at least one --input LABEL=PATH is required")
    if len(definitions) > 8:
        raise ValueError("at most 8 staged inputs")
    result = []
    seen = set()
    for definition in definitions:
        if "=" not in definition:
            raise ValueError("input must be LABEL=PATH")
        label, raw = definition.split("=", 1)
        if not LABEL.fullmatch(label) or label in seen:
            raise ValueError("invalid or duplicate input label")
        candidate = Path(raw)
        if candidate.is_symlink():
            raise ValueError("input must not be a symlink")
        path = candidate.resolve(strict=True)
        if not path.is_file():
            raise ValueError("input must be a regular, non-symlink file")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}", path.name) or path.name in (".", ".."):
            raise ValueError("unsafe input filename")
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError(f"input {label} exceeds 32 MiB; use an approved artifact route")
        data = path.read_bytes()
        result.append((label, path, data))
        seen.add(label)
    return result


def prepare_request(template: dict, inputs: list[tuple[str, Path, bytes]]) -> dict:
    if not isinstance(template, dict) or not isinstance(template.get("steps"), list):
        raise ValueError("request template must contain steps")
    if template.get("staged_inputs"):
        raise ValueError("template cannot define staged_inputs")
    reserved = {item["label"] for name in ("input_artifacts", "public_drive_inputs")
                for item in template.get(name, [])}
    if reserved.intersection(label for label, _, _ in inputs):
        raise ValueError("staged label collides with existing input")
    return dict(template)


def submit(args) -> dict:
    if not REPO.fullmatch(args.repo):
        raise ValueError("invalid repository name")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN or GITHUB_TOKEN is required for GitHub API writes")
    key = load_public_key(args.public_key)
    inputs = read_inputs(args.input)
    template = prepare_request(json.loads(args.request_json.read_text(encoding="utf-8")), inputs)
    staged = []
    # No remote action occurs until all local preflight checks have passed.
    for label, path, raw in inputs:
        cipher, metadata = encrypt_file(raw, key)
        blob = github_request(args.repo, "/git/blobs", token, {
            "content": base64.b64encode(cipher).decode("ascii"),
            "encoding": "base64",
        })
        blob_sha = blob["sha"]
        if not re.fullmatch(r"[a-f0-9]{40}", blob_sha):
            raise RuntimeError("invalid staged Git blob response")
        staged.append({"label": label, "filename": path.name, "blob_sha": blob_sha, **metadata})
    template["staged_inputs"] = staged
    title = "[DATA_STORAGE_FALLBACK] " + args.request_id
    if args.request_id:
        template["request_id"] = args.request_id
    issue = github_request(args.repo, "/issues", token, {
        "title": title, "body": json.dumps(template, ensure_ascii=False, separators=(",", ":"))
    })
    return {"status": "SUBMITTED", "issue_number": issue["number"],
            "issue_url": issue["html_url"], "labels": [r["label"] for r in staged]}


def keygen(args) -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    if args.private_key_out.exists() or args.public_key_out.exists():
        raise FileExistsError("refusing to overwrite an existing bridge key")
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    secret = private.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    pub = private.public_key().public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    fd = os.open(args.private_key_out, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(secret)
    args.public_key_out.write_bytes(pub)
    print(json.dumps({"status": "KEY_GENERATED", "private_key": str(args.private_key_out),
                      "public_key": str(args.public_key_out),
                      "next": "set GitHub Actions secret DATA_STORAGE_BRIDGE_PRIVATE_KEY_PEM from private_key"},
                     ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("keygen")
    gen.add_argument("--private-key-out", type=Path, required=True)
    gen.add_argument("--public-key-out", type=Path, required=True)
    push = sub.add_parser("submit")
    push.add_argument("--repo", required=True)
    push.add_argument("--public-key", type=Path, required=True)
    push.add_argument("--request-json", type=Path, required=True)
    push.add_argument("--request-id", default="drive-gpt-actions")
    push.add_argument("--input", action="append", default=[], help="LABEL=/path/downloaded-from-Drive")
    args = parser.parse_args()
    try:
        if args.command == "keygen":
            keygen(args)
        else:
            print(json.dumps(submit(args), ensure_ascii=False))
        return 0
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
