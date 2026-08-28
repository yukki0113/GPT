#!/usr/bin/env python3
"""Resolve the newest compatible RaceNote Archive release asset for one month.

External storage discovery intentionally lives outside racenote_request.py.
The router only receives a resolved local Archive path.

This resolver uses immutable GitHub Release tags as an external distribution
index while keeping large SQLite shards outside the Git tree.  Compatibility
is decided from the downloaded SQLite metadata, not from tag names alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import urllib.error
import urllib.request

import racenote_archive as archive

TAG_PATTERN_TEMPLATE = r"^jrdb-racenote-archive-{month}-v(?P<major>\d+)\.(?P<minor>\d+)$"
ASSET_PATTERN_TEMPLATE = (
    r"^jrdb_racenote_archive_{month}_v(?P<major>\d+)_(?P<minor>\d+)\.sqlite$"
)


class ResolveError(RuntimeError):
    """Archive release discovery or validation failed unexpectedly."""


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Resolve a publishable RaceNote Archive GitHub Release asset"
    )
    parser.add_argument("--repo", required=True, help="owner/repository")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--result-json",
        type=Path,
        default=None,
        help="Optional machine-readable resolution report path",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable containing an optional GitHub token",
    )
    return parser.parse_args()


def validate_month(value: str) -> str:
    """Validate YYYYMM."""
    text = value.strip()
    if not re.fullmatch(r"\d{6}", text):
        raise ResolveError("--target-month must be YYYYMM")
    month = int(text[4:6])
    if not 1 <= month <= 12:
        raise ResolveError(f"Invalid target month: {text}")
    return text


def sha256_file(path: Path) -> str:
    """Return lowercase SHA-256 for a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request_json(url: str, token: str | None) -> object:
    """GET JSON from GitHub without logging credentials."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "RaceNote-Archive-Resolver/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ResolveError(f"GitHub API HTTP {exc.code}: {url}") from exc
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ResolveError(f"GitHub API request failed: {url}: {exc}") from exc


def download_asset(url: str, destination: Path, token: str | None) -> None:
    """Download one public/private-compatible release asset URL."""
    headers = {
        "Accept": "application/octet-stream",
        "User-Agent": "RaceNote-Archive-Resolver/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    if partial.exists():
        partial.unlink()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with partial.open("wb") as file:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    file.write(chunk)
    except urllib.error.HTTPError as exc:
        if partial.exists():
            partial.unlink()
        raise ResolveError(f"Release asset HTTP {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        if partial.exists():
            partial.unlink()
        raise ResolveError(f"Release asset download failed: {url}: {exc}") from exc
    if not partial.is_file() or partial.stat().st_size == 0:
        raise ResolveError("Downloaded release asset is empty")
    partial.replace(destination)


def release_candidates(releases: object, target_month: str) -> list[dict]:
    """Return non-draft/non-prerelease candidates ordered by schema version."""
    if not isinstance(releases, list):
        raise ResolveError("GitHub releases response must be a list")
    tag_pattern = re.compile(TAG_PATTERN_TEMPLATE.format(month=target_month))
    candidates: list[tuple[tuple[int, int], dict]] = []
    for release in releases:
        if not isinstance(release, dict):
            continue
        if release.get("draft") or release.get("prerelease"):
            continue
        tag_name = str(release.get("tag_name") or "")
        match = tag_pattern.fullmatch(tag_name)
        if match is None:
            continue
        version = (int(match.group("major")), int(match.group("minor")))
        candidates.append((version, release))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [release for _version, release in candidates]


def matching_asset(release: dict, target_month: str) -> dict | None:
    """Return the SQLite asset whose version matches the release tag."""
    tag_pattern = re.compile(TAG_PATTERN_TEMPLATE.format(month=target_month))
    asset_pattern = re.compile(ASSET_PATTERN_TEMPLATE.format(month=target_month))
    tag_match = tag_pattern.fullmatch(str(release.get("tag_name") or ""))
    if tag_match is None:
        return None
    expected_version = (
        int(tag_match.group("major")),
        int(tag_match.group("minor")),
    )
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_match = asset_pattern.fullmatch(str(asset.get("name") or ""))
        if asset_match is None:
            continue
        asset_version = (
            int(asset_match.group("major")),
            int(asset_match.group("minor")),
        )
        if asset_version == expected_version:
            return asset
    return None


def validate_candidate(path: Path, target_month: str) -> dict:
    """Validate SQLite integrity and production publication metadata."""
    connection = archive.open_archive(path)
    try:
        report = archive.validate_archive(connection, full_scan=False)
        metadata = archive.get_meta(connection)
    finally:
        connection.close()

    if report["target_month"] != target_month:
        raise ResolveError(
            f"Archive target month mismatch: {report['target_month']} != {target_month}"
        )
    if metadata.get("coverage_mode") != "full_month":
        raise ResolveError(
            f"Archive coverage_mode is not full_month: {metadata.get('coverage_mode')!r}"
        )
    if metadata.get("publication_status") != "publishable":
        raise ResolveError(
            "Archive publication_status is not publishable: "
            f"{metadata.get('publication_status')!r}"
        )
    if metadata.get("provenance_status") != "complete":
        raise ResolveError(
            f"Archive provenance_status is not complete: {metadata.get('provenance_status')!r}"
        )
    expected_count = metadata.get("expected_race_count")
    if expected_count is None or int(expected_count) != int(report["race_count"]):
        raise ResolveError(
            "Archive expected_race_count mismatch: "
            f"expected={expected_count!r} actual={report['race_count']}"
        )
    if not metadata.get("expected_index_sha256"):
        raise ResolveError("Archive expected_index_sha256 is missing")

    return {
        **report,
        "coverage_mode": metadata["coverage_mode"],
        "publication_status": metadata["publication_status"],
        "provenance_status": metadata["provenance_status"],
        "expected_race_count": int(expected_count),
        "expected_index_sha256": metadata["expected_index_sha256"],
        "converter_git_sha": metadata.get("converter_git_sha"),
    }


def write_result(path: Path | None, value: dict) -> None:
    """Write optional result JSON."""
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve(args: argparse.Namespace) -> dict:
    """Resolve, download and validate the newest compatible monthly shard."""
    target_month = validate_month(args.target_month)
    repo = args.repo.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ResolveError("--repo must be owner/repository")

    token = os.getenv(args.token_env) or None
    releases = request_json(
        f"https://api.github.com/repos/{repo}/releases?per_page=100",
        token,
    )
    candidates = release_candidates(releases, target_month)
    rejected: list[dict] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for release in candidates:
        tag_name = str(release.get("tag_name") or "")
        asset = matching_asset(release, target_month)
        if asset is None:
            rejected.append({"tag_name": tag_name, "reason": "sqlite_asset_missing"})
            continue

        asset_name = str(asset.get("name") or "")
        browser_download_url = str(asset.get("browser_download_url") or "")
        if not browser_download_url.startswith("https://"):
            rejected.append({"tag_name": tag_name, "reason": "asset_url_missing"})
            continue

        destination = args.output_dir / asset_name
        try:
            download_asset(browser_download_url, destination, token)
            validation = validate_candidate(destination, target_month)
        except (ResolveError, archive.RaceNoteArchiveError, sqlite3.Error, OSError) as exc:
            if destination.exists():
                destination.unlink()
            rejected.append({"tag_name": tag_name, "reason": str(exc)})
            continue

        return {
            "status": "resolved",
            "target_month": target_month,
            "repository": repo,
            "tag_name": tag_name,
            "asset_name": asset_name,
            "archive_path": str(destination),
            "archive_sha256": sha256_file(destination),
            "validation": validation,
            "rejected_candidates": rejected,
        }

    return {
        "status": "not_found",
        "target_month": target_month,
        "repository": repo,
        "archive_path": None,
        "rejected_candidates": rejected,
    }


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    try:
        result = resolve(args)
    except (ResolveError, archive.RaceNoteArchiveError, sqlite3.Error, OSError) as exc:
        result = {
            "status": "error",
            "target_month": str(args.target_month),
            "archive_path": None,
            "error": str(exc),
        }
        write_result(args.result_json, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    write_result(args.result_json, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
