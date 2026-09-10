"""ZIP and CSV schema validation for official NAR monthly files."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import io
import zipfile

from nar.schema import HORSELIST_COLUMNS, ODDS_COLUMNS, PAYBACK_COLUMNS, RACELIST_COLUMNS


class NarZipValidationError(ValueError):
    """Downloaded bytes do not match the expected NAR monthly ZIP contract."""


@dataclass(frozen=True)
class CsvEntryInfo:
    name: str
    size_bytes: int
    encoding: str
    columns: int


def _decode_csv(raw: bytes) -> tuple[str, str]:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    for encoding in ("utf-8", "cp932"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise NarZipValidationError("CSV encoding is neither UTF-8 nor CP932")


def _expected_files(kind: str, ym: str) -> dict[str, tuple[str, ...]]:
    if kind == "race":
        return {
            f"{ym}_racelist.csv": tuple(RACELIST_COLUMNS),
            f"{ym}_horselist.csv": tuple(HORSELIST_COLUMNS),
            f"{ym}_payback.csv": tuple(PAYBACK_COLUMNS),
        }
    if kind == "odds":
        return {f"{ym}_{part:02d}_odds.csv": tuple(ODDS_COLUMNS) for part in range(1, 4)}
    raise ValueError("kind must be 'race' or 'odds'")


def validate_monthly_zip(content: bytes, kind: str, year: int, month: int) -> list[CsvEntryInfo]:
    """Fail closed on file-name or header drift; return lightweight entry metadata."""
    ym = f"{year:04d}{month:02d}"
    expected = _expected_files(kind, ym)

    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise NarZipValidationError("response is not a readable ZIP file")

    infos: list[CsvEntryInfo] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = sorted(name for name in archive.namelist() if not name.endswith("/"))
        if names != sorted(expected):
            raise NarZipValidationError(
                f"unexpected ZIP members: expected={sorted(expected)!r}, actual={names!r}"
            )

        for name in names:
            raw = archive.read(name)
            text, encoding = _decode_csv(raw)
            reader = csv.reader(io.StringIO(text))
            try:
                header = tuple(next(reader))
            except StopIteration as exc:
                raise NarZipValidationError(f"CSV is empty: {name}") from exc
            if header != expected[name]:
                raise NarZipValidationError(
                    f"CSV header drift: {name}: expected {len(expected[name])} columns, "
                    f"got {len(header)}"
                )
            infos.append(CsvEntryInfo(name=name, size_bytes=len(raw), encoding=encoding, columns=len(header)))
    return infos


def entry_info_dicts(infos: list[CsvEntryInfo]) -> list[dict[str, object]]:
    return [asdict(info) for info in infos]
