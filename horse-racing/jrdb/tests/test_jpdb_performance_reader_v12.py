"""P1.2 synthetic 2025/2026 source extension with actual historical Parquet.

Run with accepted historical public-drive asset root and manifest. The 2026 ZIP
fixtures are *entirely synthetic*, never proprietary source bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SRC=Path(__file__).resolve().parents[1]/"src"
sys.path.insert(0,str(SRC))
from jpdb_performance_reader_v12 import (
    JPDBPerformanceReader2026, JPDBHistoryReaderError, DAILY_MANIFEST_VERSION,
    verify_manifest, validate_extended_target
)
from jpdb_performance_reader_v11 import JPDBPerformanceReader

HIST_ROOT=None
HIST_MANIFEST=None


def synthetic_record(day, code, *, race="01260101", horse=1,
                     abnormal="0", finish=1, surface="1"):
    # Test-only synthetic fixture generator using the offsets provided by the
    # canonical jrdb_raw.Parser. Production decoding never defines offsets.
    s=bytearray(b" "*374)
    def write(pos, value):
        b=str(value).encode("ascii")
        s[pos-1:pos-1+len(b)]=b
    write(1,race)
    write(9,f"{horse:02d}")
    write(19,day.replace("-",""))
    write(67,surface)
    write(131,"12")
    if finish is not None:
        write(141,f"{finish:02d}")
    write(143,abnormal)
    write(323,code)
    return bytes(s)+b"\r\n"


def fixture(root: Path):
    droot=root/"daily"
    droot.mkdir()
    specs=[]
    for day,rows in (
        ("2026-01-04",[
          synthetic_record("2026-01-04","99999",race="01260101"),
          synthetic_record("2026-01-04","88888",race="01260101",horse=2,finish=2),
        ]),
        ("2026-01-05",[
          synthetic_record("2026-01-05","99999",race="01260102",abnormal="3",finish=None),
        ]),
    ):
        stamp=day[2:].replace("-","")
        name=f"SED{stamp}.zip"
        zpath=droot/name
        payload=b"".join(rows)
        with zipfile.ZipFile(zpath,"w",compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"SED{stamp}.txt",payload)
        specs.append({
          "name":name,"race_date":day,"size":zpath.stat().st_size,
          "zip_sha256":hashlib.sha256(zpath.read_bytes()).hexdigest(),
          "sed_member_sha256":hashlib.sha256(payload).hexdigest(),
          "sed_rows":len(rows),
        })
    cfg={"schema_version":DAILY_MANIFEST_VERSION,
         "asof_policy":"JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1",
         "calendar_source":"PACI_DRIVE_DATE_INVENTORY",
         "coverage_to_inclusive":"2026-01-05",
         "expected_race_dates":["2026-01-04","2026-01-05"],
         "selected":specs}
    manifest=root/"daily_manifest.json"
    manifest.write_text(json.dumps(cfg),encoding="utf-8")
    return droot,manifest


class P12Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.daily_root,self.daily_manifest=fixture(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dual_source_reader_boundary_and_old_parity(self):
        with JPDBPerformanceReader2026(
            input_root=HIST_ROOT,manifest=HIST_MANIFEST,
            daily_root=self.daily_root,daily_manifest=self.daily_manifest
        ) as reader:
            self.assertEqual(reader.daily_rows,3)
            self.assertEqual(reader.daily_manifest["coverage_to_inclusive"],"2026-01-05")
            baseline=reader.db.execute("""SELECT COUNT(*) FROM sed_historical
               WHERE jockey_code='99999' AND race_date<'2026-01-05'
                 AND race_date>='2023-01-05' AND surface_code IN ('1','2')""").fetchone()[0]
            d5=reader.rider_histories(target_date="2026-01-05",jockey_codes=["99999","88888"])
            r=d5["jockey_histories"]["99999"]["windows"]["ROLLING_3Y"]["all_flat"]
            self.assertEqual(r["entries"],baseline+1)
            self.assertEqual(r["last_observed"],"2026-01-04")
            self.assertEqual(d5["daily_source_dates"],2)
            d6=reader.rider_histories(target_date="2026-01-06",jockey_codes=["99999"])
            x=d6["jockey_histories"]["99999"]["windows"]["ROLLING_3Y"]["all_flat"]
            self.assertEqual(x["entries"],baseline+2)
            self.assertEqual(x["dnf"],1)
            self.assertTrue(d6["assumption_based_backtest_eligible"])
            old_in_new=reader.rider_histories(target_date="2025-11-15",jockey_codes=["99999"])
        with JPDBPerformanceReader(input_root=HIST_ROOT,manifest=HIST_MANIFEST) as old:
            original=old.rider_histories(target_date="2025-11-15",jockey_codes=["99999"])
        self.assertEqual(
            old_in_new["jockey_histories"]["99999"]["windows"],
            original["jockey_histories"]["99999"]["windows"]
        )

    def test_manifest_missing_source_and_bad_hash(self):
        src=json.loads(self.daily_manifest.read_text())
        src["selected"]=src["selected"][:1]
        self.daily_manifest.write_text(json.dumps(src))
        with self.assertRaises(JPDBHistoryReaderError):
            verify_manifest(self.daily_root,self.daily_manifest)
        self.daily_root.joinpath("SED260105.zip").unlink()
        src["expected_race_dates"]=["2026-01-04"]
        src["coverage_to_inclusive"]="2026-01-04"
        self.daily_manifest.write_text(json.dumps(src))
        verify_manifest(self.daily_root,self.daily_manifest)
        with self.daily_root.joinpath("SED260104.zip").open("ab") as f:
            f.write(b"tamper")
        with self.assertRaises(JPDBHistoryReaderError):
            with JPDBPerformanceReader2026(
                input_root=HIST_ROOT,manifest=HIST_MANIFEST,
                daily_root=self.daily_root,daily_manifest=self.daily_manifest
            ):
                pass

    def test_wrong_record_date_or_duplicate_runner(self):
        p=self.daily_root/"SED260105.zip"
        bad=synthetic_record("2026-01-04","99999",race="01260102")
        with zipfile.ZipFile(p,"w") as z:
            z.writestr("SED260105.txt",bad)
        cfg=json.loads(self.daily_manifest.read_text())
        spec=cfg["selected"][1]
        spec.update(size=p.stat().st_size,
                    zip_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                    sed_member_sha256=hashlib.sha256(bad).hexdigest(),
                    sed_rows=1)
        self.daily_manifest.write_text(json.dumps(cfg))
        with self.assertRaises(JPDBHistoryReaderError):
            with JPDBPerformanceReader2026(
                input_root=HIST_ROOT,manifest=HIST_MANIFEST,
                daily_root=self.daily_root,daily_manifest=self.daily_manifest
            ):
                pass

    def test_future_or_unsupported_target_rejected(self):
        from datetime import date
        self.assertEqual(validate_extended_target("2026-01-06",fresh_through=date(2026,1,5)).year,2026)
        for x in ("2027-01-01","2026-02-10","2026-1-6"):
            with self.subTest(x=x),self.assertRaises(JPDBHistoryReaderError):
                validate_extended_target(x,fresh_through=date(2026,1,5))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input-root",required=True,type=Path)
    p.add_argument("--manifest",required=True,type=Path)
    args=p.parse_args()
    HIST_ROOT=args.input_root
    HIST_MANIFEST=args.manifest
    unittest.main(argv=[sys.argv[0]])
