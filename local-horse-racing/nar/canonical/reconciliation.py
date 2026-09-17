from __future__ import annotations

import csv
import io
import zipfile

from nar.schema import HORSELIST_COLUMNS, RACELIST_COLUMNS

from .parser import CanonicalBatch, CanonicalParseError, parse_monthly_race_zip


RaceKey = tuple[str, str, int]


def _csv_rows(raw: bytes, expected_header: tuple[str, ...], name: str) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != tuple(expected_header):
        raise CanonicalParseError(f"header mismatch: {name}")
    return list(reader)


def _race_key(row: dict[str, str]) -> RaceKey:
    venue = (row.get("競馬場") or "").strip()
    date_raw = (row.get("競走年月日") or "").strip()
    race_no_raw = (row.get("レース番号") or "").strip()
    if not venue or len(date_raw) != 8 or not date_raw.isdigit():
        raise CanonicalParseError("invalid historical race identity")
    try:
        race_no = int(race_no_raw)
    except ValueError as exc:
        raise CanonicalParseError("invalid historical race number") from exc
    return venue, date_raw, race_no


def _csv_payload(columns: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in columns})
    return stream.getvalue().encode("utf-8-sig")


def _reconcile_horselist_only_races(content: bytes) -> tuple[bytes, set[RaceKey]]:
    """Reconstruct only the race identity when historical horselist rows lack racelist rows.

    NAR historical archives contain a small number of cancelled meeting days where horselist
    rows remain but the corresponding racelist rows are absent. We add an in-memory racelist
    row containing only venue/date/race_no so the strict canonical parser can preserve runner
    rows. No distance, conditions, weather, prizes, or result fields are inferred.
    """

    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise CanonicalParseError("not a readable ZIP") from exc

    member_names = archive.namelist()
    racelist_candidates = [name for name in member_names if name.endswith("_racelist.csv")]
    if len(racelist_candidates) != 1:
        # Let the strict parser produce the canonical error for unsupported layouts.
        return content, set()

    yyyymm = racelist_candidates[0].rsplit("_racelist.csv", 1)[0][-6:]
    racelist_name = f"{yyyymm}_racelist.csv"
    horselist_name = f"{yyyymm}_horselist.csv"
    if racelist_name not in member_names or horselist_name not in member_names:
        return content, set()

    race_rows = _csv_rows(archive.read(racelist_name), RACELIST_COLUMNS, racelist_name)
    horse_rows = _csv_rows(archive.read(horselist_name), HORSELIST_COLUMNS, horselist_name)

    race_keys = {_race_key(row) for row in race_rows}
    horse_keys = {_race_key(row) for row in horse_rows}
    missing_keys = horse_keys - race_keys
    if not missing_keys:
        return content, set()

    for venue, date_raw, race_no in sorted(missing_keys):
        row = {name: "" for name in RACELIST_COLUMNS}
        row["競馬場"] = venue
        row["競走年月日"] = date_raw
        row["レース番号"] = str(race_no)
        race_rows.append(row)

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as rebuilt:
        for name in member_names:
            if name == racelist_name:
                rebuilt.writestr(name, _csv_payload(RACELIST_COLUMNS, race_rows))
            else:
                rebuilt.writestr(name, archive.read(name))
    return output.getvalue(), missing_keys


def parse_monthly_race_zip_reconciled(
    content: bytes, source_name: str = "monthly_race.zip"
) -> CanonicalBatch:
    """Parse a monthly race ZIP with fail-closed handling of known historical cancellations."""

    reconciled, missing_keys = _reconcile_horselist_only_races(content)
    batch = parse_monthly_race_zip(reconciled, source_name)
    if not missing_keys:
        return batch

    for status in batch.tables["control_race_status"]:
        key = (
            status["venue"],
            str(status["race_date"]).replace("-", ""),
            int(status["race_no"]),
        )
        if key not in missing_keys:
            continue

        finish_count = int(status.get("finish_count") or 0)
        payback_row_count = int(status.get("payback_row_count") or 0)
        if finish_count == 0 and payback_row_count == 0:
            status["status"] = "CANCELLED"
            status["reason"] = "racelist_missing_horselist_present"
        else:
            # If future data shows results/payback for a racelist-less race, do not silently
            # classify it as a valid training/return target.
            status["status"] = "DATA_MISSING"
            status["reason"] = "racelist_missing_horselist_present_with_result_or_payback"
        status["is_model_target"] = False
        status["is_return_target"] = False

    return batch
