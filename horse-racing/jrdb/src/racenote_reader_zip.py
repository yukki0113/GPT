#!/usr/bin/env python3
"""Decorate a RaceNote request ZIP with reversible Reader View v0.1 files.

This is a GPT-side consumer adapter. It never changes the authoritative
race_bundle_*.json bytes and never adds prediction/scoring logic.
"""
from __future__ import annotations

import argparse
import copy
import json
import zipfile
from pathlib import Path
from typing import Any

import racenote_reader_view as reader_view


class ReaderZipError(ValueError):
    """RaceNote request ZIP cannot be decorated safely."""


def reader_view_name(bundle_name: str) -> str:
    """Map an authoritative bundle filename to its Reader View filename."""
    if not bundle_name.startswith("race_bundle_") or not bundle_name.endswith(".json"):
        raise ReaderZipError(f"Unexpected RaceNote bundle filename: {bundle_name}")
    return bundle_name.replace("race_bundle_", "reader_view_", 1)


def _view_payload(bundle_name: str, bundle_bytes: bytes) -> tuple[str, bytes, dict[str, Any]]:
    try:
        bundle = json.loads(bundle_bytes.decode("utf-8"))
        view = reader_view.build_reader_view(bundle)
        reader_view.expand_reader_view(view, validate_hash=True)
    except (UnicodeDecodeError, json.JSONDecodeError, reader_view.ReaderViewError) as exc:
        raise ReaderZipError(f"Reader View failed for {bundle_name}: {exc}") from exc

    payload = (
        json.dumps(view, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    view_name = reader_view_name(bundle_name)
    report = {
        "view_version": reader_view.VIEW_VERSION,
        "source_bundle": bundle_name,
        "reader_view": view_name,
        "source_semantic_sha256": view["source_semantic_sha256"],
        "roundtrip_validation": "PASS",
        "bytes": len(payload),
    }
    return view_name, payload, report


def decorate_request_zip(source_zip: Path, output_zip: Path) -> dict[str, Any]:
    """Create a new ZIP with Reader Views while preserving authoritative bundles byte-for-byte."""
    if not source_zip.is_file():
        raise ReaderZipError(f"RaceNote ZIP not found: {source_zip}")
    if source_zip.resolve() == output_zip.resolve():
        raise ReaderZipError("Reader View ZIP output must differ from source ZIP")

    try:
        with zipfile.ZipFile(source_zip, "r") as source:
            names = source.namelist()
            if "request_manifest.json" not in names:
                raise ReaderZipError("RaceNote ZIP is missing request_manifest.json")

            bundle_names = sorted(
                name
                for name in names
                if "/" not in name
                and name.startswith("race_bundle_")
                and name.endswith(".json")
            )
            if not bundle_names:
                raise ReaderZipError("RaceNote ZIP contains no authoritative race bundles")

            try:
                manifest = json.loads(source.read("request_manifest.json").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ReaderZipError(f"Invalid request_manifest.json: {exc}") from exc
            if not isinstance(manifest, dict):
                raise ReaderZipError("request_manifest.json must be an object")

            generated = [
                _view_payload(bundle_name, source.read(bundle_name))
                for bundle_name in bundle_names
            ]
            updated_manifest = copy.deepcopy(manifest)
            updated_manifest["reader_view_version"] = reader_view.VIEW_VERSION
            updated_manifest["reader_view_count"] = len(generated)
            updated_manifest["reader_views"] = [
                report for _name, _payload, report in generated
            ]
            manifest_bytes = (
                json.dumps(updated_manifest, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")

            output_zip.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for info in source.infolist():
                    if info.filename == "request_manifest.json":
                        continue
                    if (
                        "/" not in info.filename
                        and info.filename.startswith("reader_view_")
                        and info.filename.endswith(".json")
                    ):
                        continue
                    target.writestr(info, source.read(info.filename))
                target.writestr("request_manifest.json", manifest_bytes)
                for view_name, payload, _report in generated:
                    target.writestr(view_name, payload)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReaderZipError(f"Could not decorate RaceNote ZIP: {exc}") from exc

    return {
        "status": "success",
        "view_version": reader_view.VIEW_VERSION,
        "source_zip": str(source_zip),
        "output_zip": str(output_zip),
        "reader_view_count": len(generated),
        "reader_views": [report for _name, _payload, report in generated],
    }


def default_output(source_zip: Path) -> Path:
    return source_zip.with_name(f"{source_zip.stem}_reader{source_zip.suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add reversible Reader View v0.1 files to a RaceNote request ZIP"
    )
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output if args.output is not None else default_output(args.source_zip)
    report = decorate_request_zip(args.source_zip, output)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
