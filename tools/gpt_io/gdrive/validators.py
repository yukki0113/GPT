"""Optional validators for downloaded stored-file bytes."""
from pathlib import Path
from zipfile import BadZipFile, ZipFile

def validate_file(path: Path, kind: str | None) -> dict[str, object]:
    if not kind:
        return {"format_validation": "not_requested"}
    if kind not in {"zip", "xlsx"}:
        raise ValueError(f"Unsupported format validation: {kind}")
    try:
        with ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"ZIP CRC failure: {bad}")
            names = set(archive.namelist())
            if kind == "xlsx" and "xl/workbook.xml" not in names:
                raise ValueError("XLSX workbook structure is missing")
    except BadZipFile as exc:
        raise ValueError("Invalid ZIP structure") from exc
    return {"format_validation": kind, "format_valid": True}
