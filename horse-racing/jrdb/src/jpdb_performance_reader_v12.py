#!/usr/bin/env python3
"""JPDB P1.2: read-only 2023-2025 Parquet + pinned 2026 daily Raw SED Reader.

2026 source bytes stay in an approved *local* runtime. Drive acquisition and
canonical SED updates belong to the existing native Drive operation, not here.
SED decoding is delegated exclusively to the canonical JRDB Parser.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

from jpdb_history_reader import (
    JPDBHistoryReaderError, POLICY, SOURCE_GENERATION, sha256, validate_jockey,
    validate_target
)
from jpdb_performance_reader_v11 import JPDBPerformanceReader, _grouped
from jrdb_raw import Parser, BODY_LENGTHS, ymd

VERSION="jpdb-performance-reader-v1.2-candidate"
DAILY_MANIFEST_VERSION="jpdb-p12-daily-sed-pinned-v1"
DAILY_MIN_DATE=date(2026,1,1)
DAILY_MAX_DATE=date(2026,12,31)
ZIP_PATTERN=re.compile(r"SED(26[0-9]{4})\.zip")
CSV_FIELDS=("race_date","surface_code","jockey_code","abnormal_code",
            "finish","field_size","race_key_raw","horse_no")


def validate_extended_target(target: str, *, fresh_through: date) -> date:
    try:
        day=date.fromisoformat(target)
        if day.isoformat()!=target:
            raise ValueError("date format")
    except (ValueError,TypeError) as exc:
        raise JPDBHistoryReaderError("target_date must be ISO YYYY-MM-DD") from exc
    if day.year < 2026:
        return validate_target(target)
    if not DAILY_MIN_DATE<=day<=DAILY_MAX_DATE:
        raise JPDBHistoryReaderError("2026 daily source scope only")
    # Do not silently emit a historic-only response far beyond the last daily
    # snapshot: a new calendar/source inventory must be resolved first.
    if day > fresh_through+timedelta(days=7):
        raise JPDBHistoryReaderError("2026 daily source snapshot stale for requested target")
    return day


def verify_manifest(daily_root: Path, daily_manifest: Path) -> tuple[dict,list[dict]]:
    manifest=json.loads(Path(daily_manifest).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != DAILY_MANIFEST_VERSION:
        raise JPDBHistoryReaderError("unrecognized daily SED manifest schema")
    if manifest.get("asof_policy")!=POLICY or manifest.get("calendar_source")!="PACI_DRIVE_DATE_INVENTORY":
        raise JPDBHistoryReaderError("unexpected availability/calendar authority")
    entries=manifest.get("selected")
    expected=manifest.get("expected_race_dates")
    if not isinstance(entries,list) or not entries or not isinstance(expected,list):
        raise JPDBHistoryReaderError("empty/non-list 2026 inventory")
    dates=[x.get("race_date") for x in entries]
    if dates!=sorted(set(dates)) or expected!=dates:
        raise JPDBHistoryReaderError("missing/duplicate/unordered 2026 source days vs PACI calendar")
    if manifest.get("coverage_to_inclusive")!=dates[-1]:
        raise JPDBHistoryReaderError("coverage_to != latest daily SED date")
    for d in dates:
        if date.fromisoformat(d).year!=2026:
            raise JPDBHistoryReaderError("non-2026 race date in 2026 inventory")
    filenames=[x.get("name") for x in entries]
    for x in entries:
        name=x.get("name")
        match=ZIP_PATTERN.fullmatch(name or "")
        if (not match or "20"+match.group(1)[:2]+"-"+match.group(1)[2:4]
            +"-"+match.group(1)[4:6]!=x["race_date"]):
            raise JPDBHistoryReaderError("SED ZIP name/date mismatch")
        if (not re.fullmatch(r"[0-9a-f]{64}",x.get("zip_sha256",""))
            or not re.fullmatch(r"[0-9a-f]{64}",x.get("sed_member_sha256",""))
            or not isinstance(x.get("size"),int) or x["size"]<=0
            or not isinstance(x.get("sed_rows"),int) or x["sed_rows"]<=0):
            raise JPDBHistoryReaderError("missing pinned SED size/SHA/row count")
    local_names=sorted(p.name for p in Path(daily_root).glob("SED26????.zip"))
    if local_names!=sorted(filenames):
        raise JPDBHistoryReaderError("2026 local source files diverge from pinned manifest")
    return manifest,entries


def raw_sed_rows(daily_root: Path, receipts: list[dict]):
    """Yield a small canonical field projection, never a reimplemented parser."""
    parser=Parser()
    seen=set()
    record_count=0
    for spec in receipts:
        name=spec["name"]
        file=Path(daily_root)/name
        if (not file.is_file() or file.stat().st_size!=spec["size"]
            or sha256(file)!=spec["zip_sha256"]):
            raise JPDBHistoryReaderError(f"invalid pinned SED ZIP: {name}")
        with zipfile.ZipFile(file) as z:
            if z.testzip() is not None:
                raise JPDBHistoryReaderError(f"CRC failure: {name}")
            member=name.replace(".zip",".txt")
            members=[m for m in z.namelist() if re.fullmatch(r"SED26[0-9]{4}\.txt",m)]
            if members!=[member] or z.getinfo(member).is_dir():
                raise JPDBHistoryReaderError(f"missing/nonunique SED member: {name}")
            payload=z.read(member)
            if hashlib.sha256(payload).hexdigest()!=spec["sed_member_sha256"]:
                raise JPDBHistoryReaderError(f"SED member hash changed: {name}")
            if len(payload) % (BODY_LENGTHS["SED"]+2):
                raise JPDBHistoryReaderError(f"SED record size mismatch: {name}")
            records=len(payload)//(BODY_LENGTHS["SED"]+2)
            if records!=spec["sed_rows"]:
                raise JPDBHistoryReaderError(f"SED record count mismatch: {name}")
            for index in range(records):
                i=index*(BODY_LENGTHS["SED"]+2)
                record=payload[i:i+BODY_LENGTHS["SED"]+2]
                if not record.endswith(b"\r\n"):
                    raise JPDBHistoryReaderError("unexpected SED row terminator")
                parsed=parser.sed(record[:-2])
                d=ymd(parsed["date_raw"])
                if d!=spec["race_date"]:
                    raise JPDBHistoryReaderError(f"SED result date disagrees with ZIP: {name}")
                code=validate_jockey(parsed["jockey_code"])
                key=(parsed["race_key_raw"],parsed["horse_no"])
                if (not key[0] or key[1] is None or key in seen):
                    raise JPDBHistoryReaderError(f"duplicate/invalid 2026 runner key in {name}")
                seen.add(key)
                record_count+=1
                yield (d,parsed["surface_code"],code,parsed["abnormal_code"],
                       parsed["finish"],parsed["field_size"],key[0],key[1])
    if record_count != sum(x["sed_rows"] for x in receipts):
        raise JPDBHistoryReaderError("2026 parsed source row count mismatch")


class JPDBPerformanceReader2026(JPDBPerformanceReader):
    """Pinned separate 2026 snapshot plus SHA-verified historic Warehouse Reader."""

    def __init__(self, *, input_root: Path, manifest: Path, daily_root: Path,
                 daily_manifest: Path, expected_manifest_sha256: str|None=None,
                 expected_daily_manifest_sha256: str|None=None):
        super().__init__(input_root=input_root,manifest=manifest,
                         expected_manifest_sha256=expected_manifest_sha256)
        try:
            self.daily_manifest_sha256=sha256(Path(daily_manifest))
            if (expected_daily_manifest_sha256 is not None and
                expected_daily_manifest_sha256!=self.daily_manifest_sha256):
                raise JPDBHistoryReaderError("2026 daily manifest SHA-256 mismatch")
            self.daily_manifest,self.daily_sources=verify_manifest(daily_root,daily_manifest)
            # Old cohort was SHA/annual-count verified in super().__init__.
            sources=[]
            for y in (2023,2024,2025):
                specs=json.loads(Path(manifest).read_text(encoding="utf-8"))["artifacts"]
                x=next(z for z in specs if z["artifact_id"]==f"sed_{y}")
                sources.append(str((Path(input_root)/f"sed_{y}"/x["expected_name"]).resolve()))
            quoted=",".join("'"+s.replace("'","''")+"'" for s in sources)
            self.db.execute("CREATE VIEW sed_historical AS SELECT race_date, surface_code, jockey_code, abnormal_code, finish, field_size, race_key_raw, horse_no FROM read_parquet(["+quoted+"], union_by_name=true)")
            self.db.execute("""CREATE TABLE sed_2026 (
                 race_date VARCHAR, surface_code VARCHAR, jockey_code VARCHAR,
                 abnormal_code VARCHAR, finish INTEGER, field_size INTEGER,
                 race_key_raw VARCHAR, horse_no INTEGER)""")
            # Materialize only the projection through an automatically deleted
            # local CSV. NULL sentinel differs from the legitimate blank code.
            with tempfile.TemporaryDirectory(prefix="jpdb-p12-") as td:
                csv_path=Path(td)/"sed_2026.csv"
                with csv_path.open("w",encoding="utf-8",newline="") as stream:
                    w=csv.writer(stream)
                    w.writerow(CSV_FIELDS)
                    for row in raw_sed_rows(daily_root,self.daily_sources):
                        w.writerow(["\\N" if x is None else x for x in row])
                quoted_csv="'"+str(csv_path).replace("'","''")+"'"
                self.db.execute("COPY sed_2026 FROM "+quoted_csv+
                                " (HEADER TRUE, DELIMITER ',', NULL '\\N')")
            expected=sum(x["sed_rows"] for x in self.daily_sources)
            actual=self.db.execute("SELECT COUNT(*) FROM sed_2026").fetchone()[0]
            if actual!=expected:
                raise JPDBHistoryReaderError("2026 inserted row count mismatch")
            if self.db.execute("""SELECT COUNT(*) FROM (
                  SELECT race_key_raw,horse_no,COUNT(*) AS n
                  FROM sed_2026 GROUP BY 1,2 HAVING COUNT(*)!=1
                )""").fetchone()[0]:
                raise JPDBHistoryReaderError("duplicate 2026 runner keys")
            if self.db.execute("SELECT COUNT(*) FROM sed_2026 WHERE race_date<'2026-01-01' OR race_date>'2026-12-31'").fetchone()[0]:
                raise JPDBHistoryReaderError("2026 data outside year")
            if self.db.execute("""SELECT COUNT(*) FROM sed_historical h
                INNER JOIN sed_2026 d USING (race_key_raw,horse_no)""").fetchone()[0]:
                raise JPDBHistoryReaderError("2025/2026 duplicate runner key")
            self.db.execute("DROP VIEW sed_all")
            self.db.execute("""CREATE VIEW sed_all AS
                SELECT * FROM sed_historical
                UNION ALL BY NAME SELECT * FROM sed_2026""")
            self.daily_rows=int(actual)
            self.daily_coverage_to=date.fromisoformat(self.daily_manifest["coverage_to_inclusive"])
        except Exception:
            self.close()
            raise

    def rider_histories(self, *, target_date: str, jockey_codes: list[str]) -> dict:
        result=_grouped(
            self.db,target_date,jockey_codes,
            target_validator=lambda d: validate_extended_target(d,fresh_through=self.daily_coverage_to)
        )
        result["schema_version"]=VERSION
        result["source_generation"]=SOURCE_GENERATION+"+daily2026:"+self.daily_manifest_sha256[:16]
        result["historical_source_manifest_sha256"]=self.manifest_sha256
        result["historical_source_assets"]=self.asset_receipts
        result["daily_source_manifest_sha256"]=self.daily_manifest_sha256
        result["daily_source_dates"]=len(self.daily_sources)
        result["daily_source_row_count"]=self.daily_rows
        result["daily_source_coverage_to_inclusive"]=self.daily_manifest["coverage_to_inclusive"]
        result["daily_source_coverage_status"]="PACI_DATE_SET_MATCHED_MANIFEST"
        for rider in result["jockey_histories"].values():
            rider["schema_version"]=VERSION
            rider["source_generation"]=result["source_generation"]
        return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--daily-root",type=Path,required=True)
    p.add_argument("--daily-manifest",type=Path,required=True)
    p.add_argument("--expected-daily-manifest-sha256")
    p.add_argument("--target-date",required=True)
    p.add_argument("--jockey-code",action="append",required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    with JPDBPerformanceReader2026(
        input_root=a.input_root,manifest=a.manifest,daily_root=a.daily_root,
        daily_manifest=a.daily_manifest,
        expected_daily_manifest_sha256=a.expected_daily_manifest_sha256
    ) as reader:
        result=reader.rider_histories(target_date=a.target_date,jockey_codes=a.jockey_code)
    if a.output.exists():
        raise FileExistsError("refusing to overwrite output")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
