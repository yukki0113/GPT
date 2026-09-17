from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def quote_identifier(name: str) -> str:
    if not name or "\x00" in name:
        raise ValueError("invalid identifier")
    return '"' + name.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def size_bytes(path: str | Path) -> int:
    target = Path(path)
    if target.is_file():
        return target.stat().st_size
    return sum(item.stat().st_size for item in target.rglob("*.parquet"))


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def parquet_glob(path: str | Path) -> str:
    raw = str(path)
    if any(token in raw for token in ("*", "?", "[")):
        return raw
    target = Path(raw).resolve()
    return str(target) if target.is_file() else str(target / "**" / "*.parquet")

