#!/usr/bin/env python3
"""One-command bridge for GitHub-managed binary files.

This CLI wraps the repository's existing Issue -> GitHub Actions protocols:

- read:   GitHub main -> Actions artifact -> local real file
- update: local real file -> Base64 Issue payload -> verified commit on main

It intentionally keeps Issue/Actions as the audited execution layer while hiding
protocol details from day-to-day ChatGPT / Work usage.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_REPOSITORY = "yukki0113/GPT"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_CHUNK_SIZE = 48_000
READ_RESULT_MARKER = "GIT_BINARY_READ_RESULT"
READ_TITLE_PREFIX = "[gpt-git-binary-read]"
UPDATE_TITLE_PREFIX = "[gpt-git-binary-update]"
UPDATE_COMMIT_MARKER = "[gpt-git-binary-commit]"


class GitBinaryToolError(RuntimeError):
    """Raised when the bridge cannot complete a requested operation."""


def run_gh(arguments: list[str], input_text: str | None = None) -> str:
    """Run GitHub CLI and return stdout, raising a readable error on failure."""
    command = ["gh"] + arguments
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        command_text = " ".join(command)
        error_text = result.stderr.strip() or result.stdout.strip()
        raise GitBinaryToolError(f"GitHub CLI failed: {command_text}\n{error_text}")
    return result.stdout


def ensure_gh_available() -> None:
    """Verify that GitHub CLI exists and has an authenticated session."""
    if shutil.which("gh") is None:
        raise GitBinaryToolError("GitHub CLI 'gh' is not installed or not on PATH.")
    run_gh(["auth", "status"])


def normalize_repository_path(path_text: str) -> str:
    """Validate a repository-relative path before sending it to GitHub."""
    path = PurePosixPath(path_text)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise GitBinaryToolError(f"Unsafe repository path: {path_text}")
    return path.as_posix()


def calculate_sha256(path: Path) -> str:
    """Calculate SHA-256 for a local file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while True:
            block = file_handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def create_issue(repository: str, title: str, body: str) -> tuple[int, str]:
    """Create a GitHub Issue and return its number and URL."""
    payload = json.dumps({"title": title, "body": body}, ensure_ascii=False)
    response_text = run_gh(
        ["api", "--method", "POST", f"repos/{repository}/issues", "--input", "-"],
        input_text=payload,
    )
    response = json.loads(response_text)
    issue_number = int(response["number"])
    issue_url = str(response["html_url"])
    return issue_number, issue_url


def post_issue_comment(repository: str, issue_number: int, body: str) -> None:
    """Post one Issue comment using stdin so large Base64 chunks stay safe."""
    payload = json.dumps({"body": body}, ensure_ascii=False)
    run_gh(
        [
            "api",
            "--method",
            "POST",
            f"repos/{repository}/issues/{issue_number}/comments",
            "--input",
            "-",
        ],
        input_text=payload,
    )


def fetch_issue_comments(repository: str, issue_number: int) -> list[dict[str, Any]]:
    """Fetch every comment on an Issue, including requests with many chunks."""
    response_text = run_gh(
        [
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repository}/issues/{issue_number}/comments?per_page=100",
        ]
    )
    pages = json.loads(response_text)
    comments: list[dict[str, Any]] = []
    for page in pages:
        for comment in page:
            comments.append(comment)
    return comments


def parse_read_result(comment_body: str) -> dict[str, Any] | None:
    """Extract the structured readback result JSON from a success comment."""
    marker_position = comment_body.find(READ_RESULT_MARKER)
    if marker_position < 0:
        return None

    trailing_text = comment_body[marker_position + len(READ_RESULT_MARKER) :]
    match = re.search(r"```json\s*(\{.*?\})\s*```", trailing_text, flags=re.DOTALL)
    if match is None:
        return None
    result = json.loads(match.group(1))
    if result.get("status") != "success":
        return None
    return result


def wait_for_read_result(
    repository: str,
    issue_number: int,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    """Wait until the binary-read Action posts a success or failure comment."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        comments = fetch_issue_comments(repository, issue_number)
        for comment in comments:
            body = str(comment.get("body") or "")
            result = parse_read_result(body)
            if result is not None:
                return result
            if "❌ Git binary readback failed." in body:
                raise GitBinaryToolError(
                    f"Binary readback failed. Inspect Issue #{issue_number}."
                )
        time.sleep(poll_interval_seconds)

    raise GitBinaryToolError(
        f"Timed out waiting for binary readback on Issue #{issue_number}."
    )


def extract_update_success(comment_body: str) -> dict[str, str] | None:
    """Extract final path/SHA/commit fields from a binary-update success comment."""
    if "✅ Binary Git update reconstructed, verified, and pushed" not in comment_body:
        return None

    result: dict[str, str] = {}
    patterns = {
        "target_path": r"(?m)^Path:\s*`(.+?)`\s*$",
        "size": r"(?m)^Size:\s*`(.+?)`\s*$",
        "sha256": r"(?m)^SHA-256:\s*`([0-9a-fA-F]{64})`\s*$",
        "commit_sha": r"(?m)^Commit:\s*`([0-9a-fA-F]{40})`\s*$",
    }
    for name, pattern in patterns.items():
        match = re.search(pattern, comment_body)
        if match is None:
            raise GitBinaryToolError(
                f"Binary update success comment is missing '{name}'."
            )
        result[name] = match.group(1)
    return result


def wait_for_update_result(
    repository: str,
    issue_number: int,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, str]:
    """Wait until the binary-update Action posts its final success/failure comment."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        comments = fetch_issue_comments(repository, issue_number)
        for comment in comments:
            body = str(comment.get("body") or "")
            result = extract_update_success(body)
            if result is not None:
                return result
            if "❌ Binary Git update was not pushed." in body:
                raise GitBinaryToolError(
                    f"Binary update failed. Inspect Issue #{issue_number}."
                )
        time.sleep(poll_interval_seconds)

    raise GitBinaryToolError(
        f"Timed out waiting for binary update on Issue #{issue_number}."
    )


def download_read_artifact(
    repository: str,
    run_id: int,
    artifact_name: str,
    destination: Path,
) -> None:
    """Download and extract one named Actions artifact using GitHub CLI."""
    destination.mkdir(parents=True, exist_ok=True)
    run_gh(
        [
            "run",
            "download",
            str(run_id),
            "--repo",
            repository,
            "--name",
            artifact_name,
            "--dir",
            str(destination),
        ]
    )


def load_manifest(directory: Path) -> dict[str, Any]:
    """Load the manifest bundled with a binary-read artifact."""
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        raise GitBinaryToolError("Readback artifact does not contain manifest.json.")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def verify_readback(
    directory: Path,
    action_result: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    """Verify artifact manifest, file size, and SHA-256 before exposing the file."""
    manifest = load_manifest(directory)
    file_name = str(manifest.get("file_name") or "")
    if not file_name:
        raise GitBinaryToolError("Readback manifest is missing file_name.")

    source_file = directory / file_name
    if not source_file.exists() or not source_file.is_file():
        raise GitBinaryToolError(f"Readback artifact is missing file: {file_name}")

    actual_size = source_file.stat().st_size
    actual_sha256 = calculate_sha256(source_file)
    expected_size = int(manifest["size_bytes"])
    expected_sha256 = str(manifest["sha256"]).lower()

    if actual_size != expected_size:
        raise GitBinaryToolError(
            f"Readback size mismatch: expected {expected_size}, actual {actual_size}."
        )
    if actual_sha256 != expected_sha256:
        raise GitBinaryToolError(
            f"Readback SHA-256 mismatch: expected {expected_sha256}, actual {actual_sha256}."
        )

    if int(action_result["size_bytes"]) != actual_size:
        raise GitBinaryToolError("Action result and artifact manifest disagree on size.")
    if str(action_result["sha256"]).lower() != actual_sha256:
        raise GitBinaryToolError("Action result and artifact manifest disagree on SHA-256.")

    return source_file, manifest


def build_request_id(prefix: str) -> str:
    """Create a compact request identifier accepted by the Actions workflow."""
    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    random_suffix = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}-{random_suffix}"


def copy_verified_file(source: Path, destination: Path, force: bool) -> None:
    """Copy a verified readback file to its caller-visible destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        raise GitBinaryToolError(
            f"Destination already exists: {destination}. Use --force to overwrite."
        )
    shutil.copy2(source, destination)


def execute_read(arguments: argparse.Namespace) -> dict[str, Any]:
    """Run the complete GitHub-main -> local-file readback workflow."""
    repository = str(arguments.repo)
    repository_path = normalize_repository_path(str(arguments.path))
    request_id = str(arguments.request_id or build_request_id("binary-read"))

    body = f"path: {repository_path}\nrequest_id: {request_id}\n"
    title = f"{READ_TITLE_PREFIX} tool read {PurePosixPath(repository_path).name}"
    issue_number, issue_url = create_issue(repository, title, body)

    action_result = wait_for_read_result(
        repository,
        issue_number,
        int(arguments.timeout),
        float(arguments.poll_interval),
    )

    with tempfile.TemporaryDirectory(prefix="gpt-git-binary-read-") as temporary_text:
        temporary_directory = Path(temporary_text)
        download_read_artifact(
            repository,
            int(action_result["run_id"]),
            str(action_result["artifact_name"]),
            temporary_directory,
        )
        source_file, manifest = verify_readback(temporary_directory, action_result)

        output_path = Path(arguments.output).expanduser().resolve()
        copy_verified_file(source_file, output_path, bool(arguments.force))

    return {
        "status": "success",
        "operation": "read",
        "repository": repository,
        "repository_path": repository_path,
        "local_path": str(output_path),
        "issue_number": issue_number,
        "issue_url": issue_url,
        "run_id": int(action_result["run_id"]),
        "artifact_name": str(action_result["artifact_name"]),
        "size_bytes": int(manifest["size_bytes"]),
        "sha256": str(manifest["sha256"]),
        "source_commit": str(manifest["source_commit"]),
    }


def split_base64_payload(file_path: Path, chunk_size: int) -> tuple[str, list[str]]:
    """Encode a file as Base64 and split it into Issue-safe comment chunks."""
    if chunk_size < 1:
        raise GitBinaryToolError("chunk_size must be at least 1.")
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    chunks = [
        encoded[index : index + chunk_size]
        for index in range(0, len(encoded), chunk_size)
    ]
    if not chunks:
        chunks = [""]
    return encoded, chunks


def execute_update(arguments: argparse.Namespace) -> dict[str, Any]:
    """Run the complete local-file -> GitHub-main binary update workflow."""
    repository = str(arguments.repo)
    repository_path = normalize_repository_path(str(arguments.path))
    local_path = Path(arguments.file).expanduser().resolve()
    if not local_path.exists() or not local_path.is_file():
        raise GitBinaryToolError(f"Local file not found: {local_path}")

    chunk_size = int(arguments.chunk_size)
    _, chunks = split_base64_payload(local_path, chunk_size)
    file_size = local_path.stat().st_size
    file_sha256 = calculate_sha256(local_path)

    body = (
        f"target_path: {repository_path}\n"
        f"commit_message: {arguments.message}\n"
        f"sha256: {file_sha256}\n"
        f"size_bytes: {file_size}\n"
        f"chunks: {len(chunks)}\n"
        "encoding: base64\n"
    )
    title = f"{UPDATE_TITLE_PREFIX} tool update {PurePosixPath(repository_path).name}"
    issue_number, issue_url = create_issue(repository, title, body)

    total_chunks = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        comment = (
            f"[gpt-git-binary-chunk {index}/{total_chunks}]\n"
            "```base64\n"
            f"{chunk}\n"
            "```"
        )
        post_issue_comment(repository, issue_number, comment)

    post_issue_comment(repository, issue_number, UPDATE_COMMIT_MARKER)

    action_result = wait_for_update_result(
        repository,
        issue_number,
        int(arguments.timeout),
        float(arguments.poll_interval),
    )

    if action_result["target_path"] != repository_path:
        raise GitBinaryToolError("Update result path does not match the requested path.")
    if action_result["sha256"].lower() != file_sha256:
        raise GitBinaryToolError("Update result SHA-256 does not match the local file.")

    return {
        "status": "success",
        "operation": "update",
        "repository": repository,
        "repository_path": repository_path,
        "local_path": str(local_path),
        "issue_number": issue_number,
        "issue_url": issue_url,
        "commit_sha": action_result["commit_sha"],
        "size_bytes": file_size,
        "sha256": file_sha256,
        "chunks": total_chunks,
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for read and update operations."""
    parser = argparse.ArgumentParser(
        description="One-command GitHub binary read/update bridge via Issue + Actions."
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPOSITORY,
        help=f"GitHub repository in owner/name form (default: {DEFAULT_REPOSITORY}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Maximum seconds to wait for the Actions result.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Seconds between Issue-result checks.",
    )

    subparsers = parser.add_subparsers(dest="operation", required=True)

    read_parser = subparsers.add_parser(
        "read",
        help="Materialize one GitHub-main binary file into the local environment.",
    )
    read_parser.add_argument("--path", required=True, help="Repository-relative file path.")
    read_parser.add_argument("--output", required=True, help="Local destination file path.")
    read_parser.add_argument(
        "--request-id",
        default=None,
        help="Optional stable request_id. A unique value is generated when omitted.",
    )
    read_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the local destination if it already exists.",
    )

    update_parser = subparsers.add_parser(
        "update",
        help="Commit one local binary file to GitHub main through the verified Issue route.",
    )
    update_parser.add_argument("--file", required=True, help="Local source file path.")
    update_parser.add_argument("--path", required=True, help="Repository-relative target path.")
    update_parser.add_argument("--message", required=True, help="Git commit message.")
    update_parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Base64 characters per Issue comment (default: {DEFAULT_CHUNK_SIZE}).",
    )

    return parser


def main() -> int:
    """Run the requested bridge operation and emit one machine-readable JSON result."""
    parser = build_parser()
    arguments = parser.parse_args()

    try:
        ensure_gh_available()
        if arguments.operation == "read":
            result = execute_read(arguments)
        else:
            result = execute_update(arguments)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (GitBinaryToolError, OSError, ValueError, json.JSONDecodeError) as error:
        failure = {
            "status": "failure",
            "operation": getattr(arguments, "operation", None),
            "error": str(error),
        }
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
