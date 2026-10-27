#!/usr/bin/env python3
"""Fail-closed tests for raw PACI UKC-to-provisional research overlay."""
from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/"src"/"build_brdb_recent_ukc_recovery_overlay.py"
SPEC=importlib.util.spec_from_file_location("recent_ukc",SOURCE)
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

def make_row(horse,date,horse_name="TEST",father="SIRE",mother="DAM",bms="BMS"):
    row=bytearray(b" "*290)
    for a,b,x in [(0,8,horse),(8,44,horse_name),(49,85,father),(85,121,mother),(121,157,bms),
                  (157,165,"20230401"),(165,169,"2010"),(169,173,"2012"),(173,177,"2005"),
                  (268,276,date),(276,280,"1206"),(280,284,"1503")]:
        v=x.encode("cp932");row[a:a+len(v)]=v
    return bytes(row)

class Recovery(unittest.TestCase):
    def _setup(self,root):
        root=Path(root)
        (root/"input.json").write_text(json.dumps({
          "kyi_year":2025,"missing_in_all_ukc_years_count":2,
          "missing_horses":[{"horse_id":"23100001","horse_name_sample":"TEST"},
                           {"horse_id":"23100002","horse_name_sample":"MISSING"}]}),encoding="utf-8")
        return root

    def test_source_confirmed_and_provisional_separate(self):
        with tempfile.TemporaryDirectory() as t:
            root=self._setup(t)
            with zipfile.ZipFile(root/"PACI261025.zip","w") as z:
                z.writestr("UKC261025.txt",make_row("23100001","20261025")+b"\r\n")
            result=MOD.recover(root,root/"input.json",root/"out.json")
            self.assertEqual(result["source_verified_count"],1)
            self.assertEqual(result["provisional_id_only_count"],1)
            self.assertEqual(result["horses"][1]["sire_name"],None)
            self.assertFalse(result["historical_asof_verified"])
            self.assertTrue((root/"out.json").is_file())

    def test_conflicting_same_date_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=self._setup(t)
            with zipfile.ZipFile(root/"PACI261025.zip","w") as z:
                z.writestr("UKC261025.txt",make_row("23100001","20261025")+b"\r\n"+
                           make_row("23100001","20261025",father="DIFFERENT")+b"\r\n")
            with self.assertRaisesRegex(ValueError,"same-date profile conflict"):
                MOD.recover(root,root/"input.json",root/"out.json")

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=self._setup(t)
            with zipfile.ZipFile(root/"PACI261025.zip","w") as z:
                z.writestr("UKC261025.txt",make_row("23100001","20261025")+b"\r\n")
            MOD.recover(root,root/"input.json",root/"out.json")
            with self.assertRaises(FileExistsError):
                MOD.recover(root,root/"input.json",root/"out.json")

if __name__=="__main__":
    unittest.main(verbosity=2)
