"""Synthetic-only tests for P1-4c; no JRDB raw rows are committed."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_brdb_paci_pre_day_inventory import DATES, audit

def synthetic(root):
    archives = []
    for day in DATES:
        name = "PACI" + day[2:] + ".zip"
        p = root / name
        hid = b"12345678"
        uk = bytearray(b" " * 290)
        uk[:8] = hid
        uk[268:276] = day.encode("ascii")
        ky = bytearray(b" " * 1022)
        ky[10:18] = hid
        uk_data, ky_data = bytes(uk) + b"\r\n", bytes(ky) + b"\r\n"
        with ZipFile(p, "w") as z:
            z.writestr("UKC" + day[2:] + ".txt", uk_data)
            z.writestr("KYI" + day[2:] + ".txt", ky_data)
            for k in range(12):
                z.writestr("AUX%02d%s.txt" % (k, day[2:]), b"fixture")
        archives.append({
            "date": day,
            "created_time": "%s-%s-%sT10:00:00Z" % (day[:4], day[4:6], str(int(day[6:8])-1).zfill(2)),
            "modified_time": "%s-%s-%sT10:00:00Z" % (day[:4], day[4:6], str(int(day[6:8])-1).zfill(2)),
            "revision_count": 1,
            "zip_size": p.stat().st_size,
            "zip_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "ukc_sha256": hashlib.sha256(uk_data).hexdigest(),
            "kyi_sha256": hashlib.sha256(ky_data).hexdigest(),
        })
    return {"archives": archives}

class TestPaciAudit(unittest.TestCase):
    def test_positive_but_not_predictive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); report = audit(root, synthetic(root))
            self.assertEqual(report["paci_declarations"], 14)
            self.assertEqual(report["ukc_kyi_id_matches"], 14)
            self.assertFalse(report["prediction_safe"])
            self.assertFalse(report["pre_race_release_time_proven"])

    def test_late_modified_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); m=synthetic(root)
            m["archives"][0]["modified_time"]="2026-09-19T02:00:00Z"
            with self.assertRaisesRegex(ValueError, "on or after"):audit(root,m)

    def test_zip_content_tamper_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); m=synthetic(root)
            (root/"PACI260919.zip").write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError,"ZIP size mismatch|ZIP SHA mismatch"):audit(root,m)

    def test_unmatched_canonical_id_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); m=synthetic(root)
            p=root/"PACI260919.zip"
            with ZipFile(p) as z: data={n:z.read(n) for n in z.namelist()}
            name="KYI260919.txt"; blob=bytearray(data[name]);blob[10:18]=b"87654321";data[name]=bytes(blob)
            with ZipFile(p,"w") as z:
                for n,b in data.items():z.writestr(n,b)
            item=m["archives"][0]
            item["zip_sha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
            item["zip_size"]=p.stat().st_size
            item["kyi_sha256"]=hashlib.sha256(data[name]).hexdigest()
            with self.assertRaisesRegex(ValueError,"horse_id"):audit(root,m)

if __name__=="__main__":
    unittest.main()
