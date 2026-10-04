#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create lossless semantic chunks from market-blind RaceNote Readers.

The chunker never summarizes or drops Reader fields. It separates the top-level
race context from whole horse objects, packs horse objects on horse boundaries,
and verifies that reassembly is semantically identical to the source Reader.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

VERSION = "racenote-reader-chunker-0.4.5"
DEFAULT_TARGET_BYTES = 24000


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def load_manifest(prep: Path) -> tuple[dict, dict]:
    handoff = json.loads((prep / "day_prep_handoff.json").read_text(encoding="utf-8"))
    raw = (prep / "reader_stripped_manifest.json").read_bytes()
    manifest = json.loads(raw)
    if digest(raw) != handoff.get("reader_stripped_manifest_sha256"):
        raise ValueError("clean Reader manifest digest mismatch")
    if handoff.get("market_blind") is not True or handoff.get("result_opened") is not False:
        raise ValueError("chunking requires clean market-blind pre-result Reader")
    if manifest.get("market_blind") is not True or manifest.get("result_opened") is not False:
        raise ValueError("clean Reader manifest firewall failed")
    return handoff, manifest


def pack_horses(horses: list[dict], target_bytes: int) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_size = 2
    for horse in horses:
        size = len(canonical(horse)) + 1
        if current and current_size + size > target_bytes:
            chunks.append(current)
            current = []
            current_size = 2
        current.append(horse)
        current_size += size
    if current:
        chunks.append(current)
    return chunks


def chunk_reader(path: Path, expected_sha: str, out_root: Path, target_bytes: int) -> dict:
    raw = path.read_bytes()
    if digest(raw) != expected_sha:
        raise ValueError(f"Reader digest mismatch: {path.name}")
    reader = json.loads(raw)
    race = reader.get("race") or {}
    venue = str(race.get("venue") or "")
    race_no = int(race.get("race_no"))
    horses = reader.get("horses")
    if not isinstance(horses, list) or not horses:
        raise ValueError(f"{path.name}: horses missing")

    context = copy.deepcopy(reader)
    context.pop("horses", None)
    horse_chunks = pack_horses(copy.deepcopy(horses), target_bytes)

    race_dir = out_root / f"{venue}{race_no:02d}R"
    if race_dir.exists():
        raise FileExistsError(f"chunk race directory already exists: {race_dir}")
    race_dir.mkdir(parents=True)

    context_bytes = canonical(context) + b"\n"
    (race_dir / "race_context.json").write_bytes(context_bytes)

    chunk_meta = []
    rebuilt_horses: list[dict] = []
    for idx, chunk in enumerate(horse_chunks, 1):
        payload = {
            "chunk_version": VERSION,
            "source_reader_file": path.name,
            "source_reader_sha256": expected_sha,
            "chunk_index": idx,
            "chunk_total": len(horse_chunks),
            "horse_nos": [int(h["basic"]["horse_no"]) for h in chunk],
            "horses": chunk,
        }
        data = canonical(payload) + b"\n"
        name = f"chunk_{idx:03d}.json"
        (race_dir / name).write_bytes(data)
        chunk_meta.append({
            "file": name,
            "sha256": digest(data),
            "horse_nos": payload["horse_nos"],
            "size_bytes": len(data),
        })
        rebuilt_horses.extend(chunk)

    rebuilt = copy.deepcopy(context)
    rebuilt["horses"] = rebuilt_horses
    source_semantic = digest(canonical(reader))
    rebuilt_semantic = digest(canonical(rebuilt))
    if source_semantic != rebuilt_semantic:
        raise ValueError(f"{path.name}: chunk reassembly semantic mismatch")

    race_manifest = {
        "chunker_version": VERSION,
        "source_reader_file": path.name,
        "source_reader_sha256": expected_sha,
        "source_reader_semantic_sha256": source_semantic,
        "reassembled_semantic_sha256": rebuilt_semantic,
        "venue": venue,
        "race_no": race_no,
        "horse_count": len(horses),
        "context_file": "race_context.json",
        "context_sha256": digest(context_bytes),
        "chunk_count": len(chunk_meta),
        "chunks": chunk_meta,
        "status": "PASS",
    }
    mbytes = json.dumps(race_manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    (race_dir / "manifest.json").write_bytes(mbytes)
    return {
        "venue": venue,
        "race_no": race_no,
        "directory": race_dir.name,
        "manifest_sha256": digest(mbytes),
        "source_reader_sha256": expected_sha,
        "source_reader_semantic_sha256": source_semantic,
        "horse_count": len(horses),
        "chunk_count": len(chunk_meta),
    }


def build(prep: Path, output: Path, target_bytes: int) -> dict:
    if output.exists():
        raise FileExistsError(f"chunk output already exists: {output}")
    handoff, manifest = load_manifest(prep)
    output.mkdir(parents=True)

    expected = manifest.get("reader_sha256") or {}
    paths = sorted((prep / "reader").glob("*.json"))
    if set(expected) != {p.name for p in paths}:
        raise ValueError("clean Reader file set mismatch")

    races = [chunk_reader(p, expected[p.name], output, target_bytes) for p in paths]
    if len(races) != int(handoff["race_count"]):
        raise ValueError("chunked race count mismatch")
    total_horses = sum(x["horse_count"] for x in races)
    top = {
        "chunker_version": VERSION,
        "selection_id": handoff["selection_id"],
        "target_date": handoff["target_date"],
        "market_blind": True,
        "result_opened": False,
        "source_reader_manifest_sha256": handoff["reader_stripped_manifest_sha256"],
        "target_chunk_bytes": target_bytes,
        "race_count": len(races),
        "horse_count": total_horses,
        "races": sorted(races, key=lambda x: (x["venue"], x["race_no"])),
        "status": "PASS",
    }
    data = json.dumps(top, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    (output / "manifest.json").write_bytes(data)
    return top


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--target-bytes", type=int, default=DEFAULT_TARGET_BYTES)
    args = ap.parse_args()
    if args.target_bytes < 4096:
        raise ValueError("--target-bytes must be >= 4096")
    result = build(args.prep_root, args.output_root, args.target_bytes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
