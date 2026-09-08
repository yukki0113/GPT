#!/usr/bin/env python3
"""Preflight validation for GPT-created GitHub Issue requests.

The validator intentionally runs before an Issue is created so malformed request
bodies and stale/broken unified diffs do not consume an Actions run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Iterable


FAILURE_CLASS = "REQUEST_INVALID"
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,100}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")

PROTECTED_EXACT = {".env", "jrdb_secret.py"}
PROTECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
PROTECTED_NAME_PARTS = {"secret", "credential", "password"}
PROTECTED_PREFIXES = (".github/workflows/", ".git/")


class PreflightError(ValueError):
    """A request failed deterministic preflight validation."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def parse_key_value_body(body: str) -> dict[str, str]:
    """Parse simple `key: value` lines from an Issue body."""
    values: dict[str, str] = {}
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key:
            values[key] = value
    return values


def require_keys(values: dict[str, str], keys: Iterable[str]) -> None:
    """Require non-empty keys in a parsed key/value request body."""
    missing = [key for key in keys if not values.get(key)]
    if missing:
        joined = ", ".join(missing)
        raise PreflightError("MISSING_REQUIRED_FIELD", f"missing required field(s): {joined}")


def validate_repo_path(path_text: str, allow_workflows: bool = False) -> str:
    """Validate a repository-relative path against the common security boundary."""
    path_text = path_text.strip().replace("\\", "/")
    if not path_text:
        raise PreflightError("INVALID_PATH", "repository path is empty")
    if path_text.startswith("/"):
        raise PreflightError("INVALID_PATH", "absolute paths are not allowed")

    path = PurePosixPath(path_text)
    if ".." in path.parts:
        raise PreflightError("INVALID_PATH", "parent traversal is not allowed")

    normalized = path.as_posix()
    lowered = normalized.lower()
    base_name = path.name.lower()

    if normalized in PROTECTED_EXACT or base_name in PROTECTED_EXACT:
        raise PreflightError("PROTECTED_PATH", f"protected path: {normalized}")
    if not allow_workflows and lowered.startswith(PROTECTED_PREFIXES):
        raise PreflightError("PROTECTED_PATH", f"protected path: {normalized}")
    if any(part in lowered for part in PROTECTED_NAME_PARTS):
        raise PreflightError("PROTECTED_PATH", f"credential-like path is not allowed: {normalized}")
    if path.suffix.lower() in PROTECTED_SUFFIXES:
        raise PreflightError("PROTECTED_PATH", f"credential file is not allowed: {normalized}")
    return normalized


def extract_diff(body: str) -> str:
    """Extract the single fenced unified diff required by gpt-git-update."""
    matches = re.findall(r"```diff\s*\n(.*?)```", body, flags=re.DOTALL | re.IGNORECASE)
    if len(matches) != 1:
        raise PreflightError("INVALID_DIFF_FENCE", "exactly one fenced ```diff block is required")
    patch = matches[0]
    if not patch.endswith("\n"):
        patch += "\n"
    return patch


def diff_paths(patch: str) -> list[str]:
    """Return target paths from unified diff headers."""
    paths: list[str] = []
    old_path: str | None = None
    for line in patch.splitlines():
        if line.startswith("--- "):
            old_path = line[4:].split("\t", 1)[0].strip()
            continue
        if not line.startswith("+++ "):
            continue
        new_path = line[4:].split("\t", 1)[0].strip()
        if new_path != "/dev/null":
            candidate = new_path
        else:
            candidate = old_path
        if candidate is None or candidate == "/dev/null":
            continue
        if candidate.startswith("a/") or candidate.startswith("b/"):
            candidate = candidate[2:]
        paths.append(validate_repo_path(candidate))
    if not paths:
        raise PreflightError("INVALID_DIFF_HEADERS", "unified diff has no usable file headers")
    if "@@" not in patch:
        raise PreflightError("INVALID_DIFF_HUNK", "unified diff has no @@ hunk header")
    return paths


def git_apply_check(patch: str, repo_root: Path) -> None:
    """Run `git apply --check` against the caller's latest working tree."""
    if not (repo_root / ".git").exists():
        raise PreflightError("REPO_ROOT_INVALID", f"not a Git working tree: {repo_root}")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".diff", delete=False) as handle:
        handle.write(patch)
        patch_path = Path(handle.name)
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "apply", "--check", str(patch_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        patch_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git apply --check failed"
        raise PreflightError("PATCH_INVALID_OR_STALE", detail)


def validate_git_update(body: str, repo_root: Path | None) -> dict[str, object]:
    """Validate a `[gpt-git-update]` request."""
    values = parse_key_value_body(body)
    require_keys(values, ["commit_message"])
    patch = extract_diff(body)
    paths = diff_paths(patch)
    if repo_root is not None:
        git_apply_check(patch, repo_root)
    return {"protocol": "gpt-git-update", "paths": paths, "git_apply_checked": repo_root is not None}


def validate_binary_read(body: str) -> dict[str, object]:
    """Validate a `[gpt-git-binary-read]` request."""
    values = parse_key_value_body(body)
    require_keys(values, ["path"])
    path = validate_repo_path(values["path"], allow_workflows=True)
    request_id = values.get("request_id")
    if request_id and not REQUEST_ID_PATTERN.fullmatch(request_id):
        raise PreflightError("INVALID_REQUEST_ID", "request_id must use 1-100 ASCII letters, digits, dot, underscore or hyphen")
    return {"protocol": "gpt-git-binary-read", "path": path}


def validate_binary_update(body: str) -> dict[str, object]:
    """Validate a `[gpt-git-binary-update]` request body before chunk upload."""
    values = parse_key_value_body(body)
    require_keys(values, ["target_path", "commit_message", "sha256", "size_bytes", "chunks", "encoding"])
    path = validate_repo_path(values["target_path"])
    if not SHA256_PATTERN.fullmatch(values["sha256"]):
        raise PreflightError("INVALID_SHA256", "sha256 must be exactly 64 hexadecimal characters")
    try:
        size_bytes = int(values["size_bytes"])
        chunks = int(values["chunks"])
    except ValueError as exc:
        raise PreflightError("INVALID_NUMERIC_FIELD", "size_bytes and chunks must be integers") from exc
    if size_bytes < 0:
        raise PreflightError("INVALID_SIZE", "size_bytes must be zero or greater")
    if chunks < 1:
        raise PreflightError("INVALID_CHUNK_COUNT", "chunks must be at least 1")
    if values["encoding"].lower() != "base64":
        raise PreflightError("INVALID_ENCODING", "encoding must be base64")
    return {"protocol": "gpt-git-binary-update", "path": path, "size_bytes": size_bytes, "chunks": chunks}


def validate_generic_key_value(body: str, required_keys: list[str]) -> dict[str, object]:
    """Validate project-specific simple key/value requests without duplicating a parser."""
    if not required_keys:
        raise PreflightError("NO_GENERIC_CONTRACT", "generic mode requires at least one --required-key")
    values = parse_key_value_body(body)
    require_keys(values, required_keys)
    return {"protocol": "generic-key-value", "required_keys": required_keys}


def infer_protocol(title: str) -> str:
    """Infer a supported protocol from an Issue title prefix."""
    if title.startswith("[gpt-git-update]"):
        return "git-update"
    if title.startswith("[gpt-git-binary-read]"):
        return "binary-read"
    if title.startswith("[gpt-git-binary-update]"):
        return "binary-update"
    return "generic"


def validate_request(
    title: str,
    body: str,
    protocol: str = "auto",
    repo_root: Path | None = None,
    required_keys: list[str] | None = None,
) -> dict[str, object]:
    """Validate one Issue title/body pair and return machine-readable details."""
    if protocol == "auto":
        selected = infer_protocol(title)
    else:
        selected = protocol
    required_keys = required_keys or []

    if selected == "git-update":
        if not title.startswith("[gpt-git-update]"):
            raise PreflightError("TITLE_PREFIX_MISMATCH", "title must start with [gpt-git-update]")
        return validate_git_update(body, repo_root)
    if selected == "binary-read":
        if not title.startswith("[gpt-git-binary-read]"):
            raise PreflightError("TITLE_PREFIX_MISMATCH", "title must start with [gpt-git-binary-read]")
        return validate_binary_read(body)
    if selected == "binary-update":
        if not title.startswith("[gpt-git-binary-update]"):
            raise PreflightError("TITLE_PREFIX_MISMATCH", "title must start with [gpt-git-binary-update]")
        return validate_binary_update(body)
    if selected == "generic":
        return validate_generic_key_value(body, required_keys)
    raise PreflightError("UNKNOWN_PROTOCOL", f"unsupported protocol: {selected}")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Validate a GPT-created GitHub Issue request before creating the Issue.")
    parser.add_argument("--title", required=True, help="Prospective GitHub Issue title")
    body_group = parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="Prospective GitHub Issue body")
    body_group.add_argument("--body-file", type=Path, help="UTF-8 file containing the prospective Issue body")
    parser.add_argument(
        "--protocol",
        choices=["auto", "git-update", "binary-read", "binary-update", "generic"],
        default="auto",
        help="Validation protocol; auto infers the three common GPT-Git prefixes",
    )
    parser.add_argument("--repo-root", type=Path, help="Git working tree used for git apply --check in git-update mode")
    parser.add_argument("--required-key", action="append", default=[], help="Required body key for generic key/value mode; repeat as needed")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    body = args.body
    if args.body_file is not None:
        body = args.body_file.read_text(encoding="utf-8")
    assert body is not None

    resolved_repo_root = None
    if args.repo_root is not None:
        resolved_repo_root = args.repo_root.resolve()

    try:
        details = validate_request(
            title=args.title,
            body=body,
            protocol=args.protocol,
            repo_root=resolved_repo_root,
            required_keys=args.required_key,
        )
    except PreflightError as exc:
        payload = {
            "status": "failure",
            "failure_class": FAILURE_CLASS,
            "error_code": exc.error_code,
            "message": str(exc),
            "retryable": False,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    payload = {"status": "success", "preflight": details}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
