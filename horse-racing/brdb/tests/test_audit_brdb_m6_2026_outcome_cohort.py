"""Synthetic-only regression for M6 P1-4d; no licensed JRDB rows."""
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from audit_brdb_m6_2026_outcome_cohort import DATES,audit

def h(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def ukc(day,hid=b"24100265"):
    b=bytearray(b" "*290);b[:8]=hid;b[268:276]=day.encode()
    return bytes(b)+bytes((13,10))

def kyi(hid=b"24100265"):
    b=bytearray(b" "*1022);b[:8]=b"06264501";b[8:10]=b"01";b[10:18]=hid
    return bytes(b)+bytes((13,10))

def sed(day,hid=b"24100265",abnormal=b"0",idm=None):
    b=bytearray(b" "*374);b[:8]=b"06264501";b[8:10]=b"01";b[10:18]=hid
    b[18:26]=day.encode();b[140:142]=b"01" if abnormal==b"0" else b"00"
    b[142:143]=abnormal
    if idm:b[182:185]=idm
    return bytes(b)+bytes((13,10))

def archive(root,day,alternative=False):
    part=day[2:];p=root/("SED"+part+("_later" if alternative else "")+".zip")
    with ZipFile(p,"w") as z:
        z.writestr("SED"+part+".txt",sed(day,idm=b"999" if alternative else None))
    return p

def fixtures(root):
    inputs=[]
    for idx,day in enumerate(DATES):
        suffix=day[2:];p=root/("PACI"+suffix+".zip")
        with ZipFile(p,"w") as z:
            z.writestr("UKC"+suffix+".txt",ukc(day))
            z.writestr("KYI"+suffix+".txt",kyi())
        s=archive(root,day)
        prior=datetime.strptime(day,"%Y%m%d").replace(tzinfo=timezone.utc)-timedelta(days=1)
        stamp=prior.strftime("%Y-%m-%dT00:00:00Z")
        item={"date":day,"paci_sha256":h(p),"paci_size":p.stat().st_size,
              "sed_sha256":h(s),"sed_size":s.stat().st_size,
              "paci_created_utc":stamp,"paci_modified_utc":stamp,
              "paci_revision_count":1,"alternate_sed":[]}
        if idx==0:
            a=archive(root,day,True)
            item["alternate_sed"]=[{"path":a.name,"sha256":h(a),"size":a.stat().st_size}]
        inputs.append(item)
    return {"schema_version":1,"prediction_safe":False,"archives":inputs}

class CohortTests(unittest.TestCase):
    def test_frozen_fixture_and_revised_nonoutcome(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);manifest=fixtures(root)
            report=audit(root,manifest,root/"output")
            self.assertEqual(report["race_declarations"],14)
            self.assertEqual(report["actual_starters"],14)
            self.assertEqual(report["unique_horses"],1)
            self.assertEqual(report["extra_declarations_of_repeated_horses"],13)
            self.assertEqual(report["duplicate_sed_versions"][0]["other_fields_revised_rows"],1)
            self.assertFalse(report["prediction_safe"])
            self.assertTrue((root/"output"/"private_outcome_cohort.csv").exists())

    def test_sha_tamper_denied(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);manifest=fixtures(root)
            (root/"SED"+DATES[0][2:]+".zip").write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError,"source SHA or size mismatch"):
                audit(root,manifest,root/"output")

    def test_alternate_changed_finish_denied(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);manifest=fixtures(root)
            day=DATES[0];p=root/("SED"+day[2:]+"_later.zip")
            with ZipFile(p,"w") as z:
                b=bytearray(sed(day));b[140:142]=b"02"
                z.writestr("SED"+day[2:]+".txt",bytes(b))
            alt=manifest["archives"][0]["alternate_sed"][0]
            alt.update({"sha256":h(p),"size":p.stat().st_size})
            with self.assertRaisesRegex(ValueError,"alternate results conflict"):
                audit(root,manifest,root/"output")

    def test_paci_kyi_sed_key_conflict_denied(self):
        with tempfile.TemporaryDirectory() as x:
            root=Path(x);manifest=fixtures(root)
            day=DATES[0];p=root/("SED"+day[2:]+".zip")
            with ZipFile(p,"w") as z:
                z.writestr("SED"+day[2:]+".txt",sed(day,hid=b"87654321"))
            entry=manifest["archives"][0]
            entry["sed_sha256"]=h(p);entry["sed_size"]=p.stat().st_size
            with self.assertRaisesRegex(ValueError,"canonical entry keys differ"):
                audit(root,manifest,root/"output")

if __name__=="__main__":unittest.main()
