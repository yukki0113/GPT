"""Synthetic-only regression tests for P1-4b UKC ZIP provenance inventory."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile, ZipInfo

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from audit_ukc_historical_zip_timestamps import audit,nominal_day

class AuditTests(unittest.TestCase):
    def fixtures(self,root):
        rows=[]
        for y in range(2016,2026):
            f=root/f"UKC_{y}.zip"
            with ZipFile(f,"w") as z:
                for day,stamp in [("0105",(y,1,4,12,0,0)),
                                  ("0109",(y,1,9,17,0,0)),
                                  ("0110",(y,1,11,17,0,0))]:
                    z.writestr(ZipInfo(f"UKC{str(y)[-2:]}{day}.txt",date_time=stamp),b"synthetic")
            rows.append({"year":y,"size_bytes":f.stat().st_size,
              "sha256":hashlib.sha256(f.read_bytes()).hexdigest(),
              "drive_created_time":"2026-09-16T03:25:00Z"})
        return {"archives":rows}

    def test_classification_never_attests_release(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            data=audit(root,self.fixtures(root))
            self.assertEqual(data["totals"]["members"],30)
            self.assertEqual(data["totals"]["member_mtime_previous_day"],10)
            self.assertEqual(data["totals"]["member_mtime_same_day"],10)
            self.assertEqual(data["totals"]["member_mtime_after_day"],10)
            self.assertFalse(data["prediction_safe"])
            self.assertEqual(data["asof_attested_entries"],0)

    def test_tampered_zip_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);manifest=self.fixtures(root)
            (root/"UKC_2019.zip").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"ZIP SHA/size mismatch"):audit(root,manifest)

    def test_wrong_year_and_invalid_dates(self):
        with self.assertRaises(ValueError):nominal_day("UKC250105.txt",2016)
        with self.assertRaises(ValueError):nominal_day("UKC161399.txt",2016)

    def test_incomplete_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);manifest=self.fixtures(root)
            manifest["archives"].pop()
            with self.assertRaisesRegex(ValueError,"exactly 2016-2025"):audit(root,manifest)

if __name__=="__main__":unittest.main()
