#!/usr/bin/env python3
"""Reject stale Current publication before any mutable Release write.

Separate personal and Momotaro release caches share date/revision ordering.
Reject same-revision replacement as well as an older target date; an intentional
correction must be emitted as a newer revision. Historic source files and
immutable revisions must never be rewritten to force this check to pass.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path


def release_identity(metadata: dict, name: str) -> tuple[date, int]:
    if not isinstance(metadata, dict):
        raise ValueError(f"{name} must be a JSON object")
    raw_date = metadata.get("date")
    if not isinstance(raw_date, str):
        raise ValueError(f"{name}.date must be YYYY-MM-DD")
    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError(f"{name}.date invalid: {raw_date!r}") from exc
    if parsed_date.isoformat() != raw_date:
        raise ValueError(f"{name}.date must use YYYY-MM-DD")
    revision = metadata.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError(f"{name}.revision must be a positive integer")
    return parsed_date, revision


def assert_current_advances(
    candidate: dict, existing: dict, expected_release_kind: str
) -> tuple[tuple[date, int], tuple[date, int]]:
    if existing.get("release_kind") != expected_release_kind:
        raise ValueError(
            f"existing current release_kind mismatch: "
            f"{existing.get('release_kind')!r} != {expected_release_kind!r}"
        )
    candidate_id = release_identity(candidate, "candidate")
    existing_id = release_identity(existing, "existing")
    if candidate_id <= existing_id:
        raise ValueError(
            f"stale Current publication rejected: candidate={candidate_id}, "
            f"existing={existing_id}; publish a newer date or revision"
        )
    return candidate_id, existing_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--expected-release-kind", required=True)
    args = parser.parse_args()
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    existing = json.loads(args.current.read_text(encoding="utf-8"))
    incoming, previous = assert_current_advances(
        candidate, existing, args.expected_release_kind
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "old_date": previous[0].isoformat(),
                "old_revision": previous[1],
                "new_date": incoming[0].isoformat(),
                "new_revision": incoming[1],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
