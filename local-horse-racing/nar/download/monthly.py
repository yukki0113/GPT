"""CLI for immutable NAR monthly raw ZIP acquisition."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.message import Message
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile

from .client import fetch_monthly
from .unzip import entry_info_dicts, validate_monthly_zip

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def filename_from_content_disposition(value: str) -> str | None:
    """Extract a safe basename from Content-Disposition, if present."""
    if not value:
        return None
    message = Message()
    message["Content-Disposition"] = value
    filename = message.get_filename()
    if not filename:
        return None
    name = Path(filename).name
    if name != filename or not _SAFE_NAME.fullmatch(name) or not name.lower().endswith(".zip"):
        return None
    return name


def _write_immutable(path: Path, content: bytes) -> str:
    """Write new bytes atomically; never replace different bytes at the same raw path."""
    digest = sha256(content).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        current = sha256(path.read_bytes()).hexdigest()
        if current == digest:
            return "unchanged"
        raise FileExistsError(f"refusing to overwrite immutable raw ZIP with different content: {path}")

    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return "downloaded"


def acquire_month(
    *,
    kind: str,
    year: int,
    month: int,
    output_dir: Path,
    audit_dir: Path | None = None,
    timeout: float = 60.0,
) -> dict[str, object]:
    """Download, validate, immutably store and optionally audit one monthly ZIP."""
    response = fetch_monthly(kind, year, month, timeout=timeout)
    entries = validate_monthly_zip(response.content, kind, year, month)
    digest = sha256(response.content).hexdigest()
    official_name = filename_from_content_disposition(response.content_disposition)
    filename = official_name or f"{year:04d}{month:02d}_{kind}.zip"
    target = output_dir / filename
    status = _write_immutable(target, response.content)

    audit: dict[str, object] = {
        "status": status,
        "kind": kind,
        "year": year,
        "month": month,
        "source_url": response.final_url,
        "http_status": response.status_code,
        "content_type": response.content_type,
        "content_disposition": response.content_disposition,
        "filename": filename,
        "saved_path": str(target),
        "size_bytes": len(response.content),
        "sha256": digest,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "zip_entries": entry_info_dicts(entries),
    }

    if audit_dir is not None:
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = audit_dir / f"{filename}.audit.json"
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        audit["audit_path"] = str(audit_path)
    return audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download one NAR official monthly ZIP")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--kind", choices=("race", "odds"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = acquire_month(
        kind=args.kind,
        year=args.year,
        month=args.month,
        output_dir=args.output_dir,
        audit_dir=args.audit_dir,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
