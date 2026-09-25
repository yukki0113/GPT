#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acquire paired PACI/SED inputs for RaceReviewDB updates safely."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import zipfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


class RaceReviewAcquireError(RuntimeError):
    """Raised when a requested RaceReviewDB input cannot be acquired."""


def _read_tsv(path: Path, kind: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) != 2:
            raise RaceReviewAcquireError(
                f"{path}: invalid TSV row: {raw!r}"
            )
        name, file_id = parts
        expected_prefix = kind.upper()
        if not name.upper().startswith(expected_prefix):
            raise RaceReviewAcquireError(
                f"{path}: unexpected {kind} name: {name}"
            )
        rows.append((name, file_id))
    if not rows:
        raise RaceReviewAcquireError(f"{path}: no {kind} rows")
    rows.sort()
    return rows


def _archive_date(name: str, kind: str) -> str:
    upper = name.upper()
    prefix = kind.upper()
    if not upper.startswith(prefix) or not upper.endswith(".ZIP"):
        raise RaceReviewAcquireError(
            f"unexpected {kind} archive name: {name}"
        )
    digits = upper[len(prefix) : -4]
    if len(digits) != 6 or not digits.isdigit():
        raise RaceReviewAcquireError(
            f"unexpected {kind} archive date: {name}"
        )
    return digits


def _zip_ok(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def _validate_members(kind: str, name: str, path: Path) -> int:
    date = _archive_date(name, kind)
    if kind == "PACI":
        required = {
            f"BAC{date}.txt",
            f"KYI{date}.txt",
        }
    else:
        required = {
            f"SED{date}.txt",
        }

    with zipfile.ZipFile(path) as archive:
        members = set(archive.namelist())

    missing = sorted(required - members)
    if missing:
        raise RaceReviewAcquireError(
            f"{name}: missing required ZIP members: {missing}"
        )
    return len(members)


def _run(
    command: Sequence[str],
    *,
    timeout_seconds: int,
) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return result.returncode, result.stdout[-4000:]
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return 124, str(output)[-4000:]


def _download(
    kind: str,
    name: str,
    file_id: str,
    target: Path,
) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    target.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, 3):
        target.unlink(missing_ok=True)
        code, output = _run(
            [
                "gdown",
                file_id,
                "-O",
                str(target),
            ],
            timeout_seconds=45,
        )
        attempts.append(
            {
                "method": "gdown",
                "attempt": attempt,
                "returncode": code,
                "output_tail": output,
            }
        )
        if (
            code == 0
            and target.is_file()
            and target.stat().st_size > 0
            and _zip_ok(target)
        ):
            member_count = _validate_members(
                kind,
                name,
                target,
            )
            return _success(
                kind,
                name,
                file_id,
                target,
                "gdown",
                member_count,
                attempts,
            )
        target.unlink(missing_ok=True)
        time.sleep(attempt * 2)

    urls = [
        (
            "driveusercontent",
            (
                "https://drive.usercontent.google.com/download"
                f"?id={file_id}&export=download&confirm=t"
            ),
        ),
        (
            "drive_uc",
            (
                "https://drive.google.com/uc"
                f"?export=download&id={file_id}&confirm=t"
            ),
        ),
    ]

    for label, url in urls:
        target.unlink(missing_ok=True)
        code, output = _run(
            [
                "curl",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--retry",
                "4",
                "--retry-all-errors",
                "--connect-timeout",
                "15",
                "--max-time",
                "90",
                url,
                "-o",
                str(target),
            ],
            timeout_seconds=120,
        )
        attempts.append(
            {
                "method": label,
                "attempt": 1,
                "returncode": code,
                "output_tail": output,
            }
        )
        if (
            code == 0
            and target.is_file()
            and target.stat().st_size > 0
            and _zip_ok(target)
        ):
            member_count = _validate_members(
                kind,
                name,
                target,
            )
            return _success(
                kind,
                name,
                file_id,
                target,
                label,
                member_count,
                attempts,
            )

    target.unlink(missing_ok=True)
    return {
        "ok": False,
        "kind": kind,
        "name": name,
        "file_id": file_id,
        "attempts": attempts,
    }


def _success(
    kind: str,
    name: str,
    file_id: str,
    target: Path,
    method: str,
    member_count: int,
    attempts: list[dict[str, object]],
) -> dict[str, object]:
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {
        "ok": True,
        "kind": kind,
        "name": name,
        "file_id": file_id,
        "path": str(target),
        "method": method,
        "size_bytes": target.stat().st_size,
        "sha256": digest,
        "member_count": member_count,
        "attempts": attempts,
    }


def acquire_pairs(
    *,
    paci_tsv: Path,
    sed_tsv: Path,
    output_root: Path,
    workers: int = 8,
) -> dict[str, object]:
    """Acquire and validate paired PACI/SED archives."""
    if workers < 1:
        raise ValueError("workers must be positive")

    paci_rows = _read_tsv(paci_tsv, "PACI")
    sed_rows = _read_tsv(sed_tsv, "SED")

    paci_dates = [_archive_date(name, "PACI") for name, _ in paci_rows]
    sed_dates = [_archive_date(name, "SED") for name, _ in sed_rows]
    if paci_dates != sed_dates:
        raise RaceReviewAcquireError(
            "PACI/SED date coverage mismatch"
        )

    output_root = Path(output_root).resolve()
    paci_root = output_root / "paci"
    sed_root = output_root / "sed"
    paci_root.mkdir(parents=True, exist_ok=True)
    sed_root.mkdir(parents=True, exist_ok=True)

    tasks: list[tuple[str, str, str, Path]] = []
    tasks.extend(
        (
            "PACI",
            name,
            file_id,
            paci_root / name,
        )
        for name, file_id in paci_rows
    )
    tasks.extend(
        (
            "SED",
            name,
            file_id,
            sed_root / name,
        )
        for name, file_id in sed_rows
    )

    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _download,
                kind,
                name,
                file_id,
                target,
            ): (kind, name)
            for kind, name, file_id, target in tasks
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(
        key=lambda row: (
            str(row.get("kind")),
            str(row.get("name")),
        )
    )

    failures = [
        row
        for row in results
        if not bool(row.get("ok"))
    ]
    successes = [
        row
        for row in results
        if bool(row.get("ok"))
    ]

    method_counts: dict[str, int] = {}
    for row in successes:
        method = str(row.get("method"))
        method_counts[method] = method_counts.get(method, 0) + 1

    return {
        "status": "PASS" if not failures else "FAIL",
        "paired_date_count": len(paci_dates),
        "paci_count": sum(
            1
            for row in successes
            if row.get("kind") == "PACI"
        ),
        "sed_count": sum(
            1
            for row in successes
            if row.get("kind") == "SED"
        ),
        "success_count": len(successes),
        "failure_count": len(failures),
        "method_counts": method_counts,
        "files": successes,
        "failures": failures,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire paired PACI/SED archives for RaceReviewDB."
        )
    )
    parser.add_argument("--paci-tsv", type=Path, required=True)
    parser.add_argument("--sed-tsv", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--summary-json", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = acquire_pairs(
        paci_tsv=args.paci_tsv,
        sed_tsv=args.sed_tsv,
        output_root=args.output_root,
        workers=args.workers,
    )

    if args.summary_json is not None:
        args.summary_json.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.summary_json.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "status": result["status"],
                "paired_date_count": result["paired_date_count"],
                "paci_count": result["paci_count"],
                "sed_count": result["sed_count"],
                "failure_count": result["failure_count"],
                "method_counts": result["method_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
