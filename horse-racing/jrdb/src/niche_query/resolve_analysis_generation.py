"""Pin and verify ONLY the manifest-listed JRDB Analysis v1.4 Parquet objects.

Safe archive extraction is owned by tools/data-storage/scripts/safe_unpack_staged_archive.py.
SHA calculation reuses data_storage.common, Parquet reads are delegated to data_storage.query.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path, PurePosixPath

from data_storage.common import sha256_file


class GenerationError(ValueError):
    pass


def _safe_relative(root: Path, raw: str) -> Path:
    if not isinstance(raw, str) or "\\" in raw or "\x00" in raw:
        raise GenerationError("Unsafe manifest path")
    rel = PurePosixPath(raw)
    if rel.is_absolute() or not rel.parts or any(c in ("", ".", "..") for c in rel.parts):
        raise GenerationError("Unsafe manifest path")
    unresolved = root / Path(*rel.parts)
    if any(part.is_symlink() for part in (unresolved, *unresolved.parents) if part != root and root in part.parents):
        raise GenerationError("Symlink in manifest path")
    path = unresolved.resolve()
    if not path.is_relative_to(root.resolve()):
        raise GenerationError("Manifest path escapes source")
    return path


def prepare_current_only(analysis_root: Path, snapshot_root: Path, start_year: int, end_year: int) -> dict:
    root, out = Path(analysis_root).resolve(), Path(snapshot_root).resolve()
    if root == out or root in out.parents or out in root.parents:
        raise GenerationError("Snapshot root cannot contain or equal source root")
    if not 2010 <= start_year <= end_year <= 2100:
        raise GenerationError("Invalid year selection")
    if not root.is_dir() or (out.exists() and any(out.iterdir())):
        raise GenerationError("Source unavailable or output not empty")
    pointer_path = root / "current.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("status") != "CURRENT":
        raise GenerationError("Not a CURRENT pointer")
    generation = pointer.get("generation_id")
    if not isinstance(generation, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", generation):
        raise GenerationError("Invalid generation ID")
    expected_manifest = f"generations/{generation}/manifest.json"
    if pointer.get("manifest") != expected_manifest:
        raise GenerationError("Manifest pointer mismatch")
    manifest = json.loads(_safe_relative(root, expected_manifest).read_text(encoding="utf-8"))
    fact = manifest.get("fact_table", {})
    if (manifest.get("generation_id") != generation or manifest.get("validation_status") != "PASS"
            or manifest.get("artifact_type") != "jrdb_analysis" or manifest.get("schema_version") != "v1.4"
            or manifest.get("storage_format") != "parquet" or fact.get("name") != "fact_entry_result_lite"):
        raise GenerationError("Analysis generation contract mismatch")
    parts = fact.get("partitions")
    if not isinstance(parts, list) or not parts:
        raise GenerationError("No partitions in manifest")
    chosen = []
    total_manifest_rows, known_years = 0, set()
    for p in parts:
        if not isinstance(p, dict):
            raise GenerationError("Invalid partition entry")
        year, size, rows, digest = p.get("year"), p.get("size_bytes"), p.get("rows"), p.get("sha256")
        if type(year) is not int or year in known_years or type(rows) is not int or rows < 0 or type(size) is not int or size <= 0:
            raise GenerationError("Invalid/duplicate year or partition sizes")
        known_years.add(year)
        if not isinstance(digest,str) or not re.fullmatch(r"[a-f0-9]{64}",digest):
            raise GenerationError("Invalid partition SHA")
        path = p.get("relative_path")
        if path != f"objects/fact_entry_result_lite/year={year}/{digest}.parquet":
            raise GenerationError("Partition path mismatches SHA/year")
        total_manifest_rows += rows
        if start_year <= year <= end_year:
            file = _safe_relative(root, path)
            if not file.is_file() or file.stat().st_size != size or sha256_file(file) != digest:
                raise GenerationError(f"Parquet size/SHA failed: {year}")
            chosen.append((year, file, p))
    if total_manifest_rows != manifest.get("total_rows"):
        raise GenerationError("Manifest row count inconsistent")
    if not chosen or set(range(start_year,end_year+1)) - set(known_years):
        raise GenerationError("Requested years not completely covered")
    out.mkdir(parents=True, exist_ok=True)
    audit_parts=[]
    for year, source, p in sorted(chosen):
        dest = out / f"year={year}" / source.name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)
        audit_parts.append({"year":year,"rows":p["rows"],"size_bytes":p["size_bytes"],"sha256":p["sha256"],"relative_path":p["relative_path"]})
    return {"generation_id":generation,"schema_version":"v1.4","period_to":manifest.get("period_to"),
            "period_from":manifest.get("period_from"),"manifest_sha256":sha256_file(_safe_relative(root,expected_manifest)),
            "selected_rows":sum(p["rows"] for _,_,p in chosen),"partitions":audit_parts,"dataset_path":str(out)}