#!/usr/bin/env python3
"""Build a reversible GPT reader view from a RaceNote v1.0 bundle.

The authoritative RaceNote bundle remains unchanged. Reader View v0.1 only:
- hoists repeated statistic context shared by every statistic node;
- hoists repeated historical-profile context shared by every non-null profile;
- serializes compact JSON for transport/LLM reading.

No observation is dropped and no prediction/scoring logic is applied.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Iterator

VIEW_VERSION = "0.1"
SOURCE_SCHEMA_VERSION = "1.0"
STAT_SUMMARY_KEYS = ("starts", "wins", "top3")
STAT_CONTEXT_KEYS = (
    "period",
    "as_of_exclusive",
    "track_condition_scope",
    "source",
)
HISTORICAL_PROFILE_CONTEXT_KEYS = (
    "source",
    "source_window_start",
    "as_of_exclusive",
)


class ReaderViewError(ValueError):
    """Reader View cannot be produced or safely expanded."""


def semantic_sha256(value: Any) -> str:
    """Return a deterministic semantic hash independent of JSON formatting/key order."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _walk_summary_nodes(value: Any) -> Iterator[dict[str, Any]]:
    """Yield summary-like objects under a stats/trends subtree."""
    if isinstance(value, dict):
        if all(key in value for key in STAT_SUMMARY_KEYS):
            yield value
        for child in value.values():
            yield from _walk_summary_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_summary_nodes(child)


def _iter_stat_nodes(bundle: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield statistic summaries that carry shared Stats Mart/Analysis context."""
    race = bundle.get("race")
    if isinstance(race, dict):
        trends = race.get("race_trends")
        if isinstance(trends, dict):
            yield from _walk_summary_nodes(trends)

    horses = bundle.get("horses")
    if isinstance(horses, list):
        for horse in horses:
            if not isinstance(horse, dict):
                continue
            stats = horse.get("stats")
            if isinstance(stats, dict):
                yield from _walk_summary_nodes(stats)


def _uniform_context(
    nodes: Iterable[dict[str, Any]],
    keys: tuple[str, ...],
) -> dict[str, Any] | None:
    """Return context only when every node carries exactly the same values."""
    materialized = list(nodes)
    if not materialized:
        return None
    if any(not all(key in node for key in keys) for node in materialized):
        return None
    first = {key: materialized[0][key] for key in keys}
    if any(any(node[key] != first[key] for key in keys) for node in materialized[1:]):
        return None
    return first


def _iter_historical_profiles(bundle: dict[str, Any]) -> Iterator[dict[str, Any]]:
    horses = bundle.get("horses")
    if not isinstance(horses, list):
        return
    for horse in horses:
        if not isinstance(horse, dict):
            continue
        profile = horse.get("historical_profile")
        if isinstance(profile, dict):
            yield profile


def _strip_context(nodes: Iterable[dict[str, Any]], context: dict[str, Any]) -> None:
    for node in nodes:
        if all(node.get(key) == value for key, value in context.items()):
            for key in context:
                node.pop(key, None)


def _restore_context(nodes: Iterable[dict[str, Any]], context: dict[str, Any]) -> None:
    for node in nodes:
        for key, value in context.items():
            if key in node and node[key] != value:
                raise ReaderViewError(f"context conflict while restoring {key}")
            node.setdefault(key, copy.deepcopy(value))


def build_reader_view(bundle: dict[str, Any]) -> dict[str, Any]:
    """Return reversible Reader View v0.1 for one authoritative v1.0 bundle."""
    if not isinstance(bundle, dict):
        raise ReaderViewError("RaceNote bundle must be an object")
    if bundle.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise ReaderViewError(
            f"Reader View v{VIEW_VERSION} requires RaceNote schema {SOURCE_SCHEMA_VERSION}"
        )
    if not isinstance(bundle.get("race"), dict) or not isinstance(bundle.get("horses"), list):
        raise ReaderViewError("RaceNote bundle is missing race/horses")

    source_hash = semantic_sha256(bundle)
    working = copy.deepcopy(bundle)
    working.pop("schema_version", None)

    shared_context: dict[str, Any] = {}

    stat_context = _uniform_context(_iter_stat_nodes(working), STAT_CONTEXT_KEYS)
    if stat_context is not None:
        _strip_context(_iter_stat_nodes(working), stat_context)
        shared_context["stats"] = stat_context

    profile_context = _uniform_context(
        _iter_historical_profiles(working),
        HISTORICAL_PROFILE_CONTEXT_KEYS,
    )
    if profile_context is not None:
        _strip_context(_iter_historical_profiles(working), profile_context)
        shared_context["historical_profile"] = profile_context

    return {
        "view_version": VIEW_VERSION,
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "source_semantic_sha256": source_hash,
        "view_policy": {
            "lossless": True,
            "prediction_logic": False,
            "field_omission": False,
            "context_hoist": True,
        },
        "shared_context": shared_context,
        **working,
    }


def expand_reader_view(view: dict[str, Any], *, validate_hash: bool = True) -> dict[str, Any]:
    """Reconstruct the authoritative semantic bundle from Reader View v0.1."""
    if not isinstance(view, dict) or view.get("view_version") != VIEW_VERSION:
        raise ReaderViewError(
            "Unsupported Reader View version: "
            f"{view.get('view_version') if isinstance(view, dict) else None}"
        )
    if view.get("source_schema_version") != SOURCE_SCHEMA_VERSION:
        raise ReaderViewError("Reader View source schema is not supported")

    working = copy.deepcopy(view)
    source_hash = working.pop("source_semantic_sha256", None)
    working.pop("view_version", None)
    source_schema = working.pop("source_schema_version", None)
    working.pop("view_policy", None)
    shared_context = working.pop("shared_context", {})
    if not isinstance(shared_context, dict):
        raise ReaderViewError("shared_context must be an object")

    bundle = {"schema_version": source_schema, **working}

    stat_context = shared_context.get("stats")
    if stat_context is not None:
        if not isinstance(stat_context, dict):
            raise ReaderViewError("shared_context.stats must be an object")
        _restore_context(_iter_stat_nodes(bundle), stat_context)

    profile_context = shared_context.get("historical_profile")
    if profile_context is not None:
        if not isinstance(profile_context, dict):
            raise ReaderViewError("shared_context.historical_profile must be an object")
        _restore_context(_iter_historical_profiles(bundle), profile_context)

    if validate_hash:
        if not isinstance(source_hash, str) or len(source_hash) != 64:
            raise ReaderViewError("source_semantic_sha256 is missing or invalid")
        actual = semantic_sha256(bundle)
        if actual != source_hash:
            raise ReaderViewError(
                f"expanded semantic hash mismatch: expected={source_hash} actual={actual}"
            )
    return bundle


def write_reader_view(path: Path, view: dict[str, Any], *, pretty: bool = False) -> None:
    """Write compact JSON by default; pretty form is for human debugging."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        text = json.dumps(view, ensure_ascii=False, indent=2) + "\n"
    else:
        text = json.dumps(view, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reversible RaceNote Reader View v0.1")
    parser.add_argument("bundle", type=Path, help="RaceNote v1.0 bundle JSON")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print instead of compact JSON")
    parser.add_argument("--verify-roundtrip", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    view = build_reader_view(bundle)
    if args.verify_roundtrip:
        expand_reader_view(view, validate_hash=True)
    write_reader_view(args.output, view, pretty=args.pretty)
    print(
        json.dumps(
            {
                "status": "success",
                "view_version": VIEW_VERSION,
                "source_semantic_sha256": view["source_semantic_sha256"],
                "output": str(args.output),
                "bytes": args.output.stat().st_size,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())