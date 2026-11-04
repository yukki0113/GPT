"""Synthetic-only 2016-2025 UKC/KYI temporal candidate regression."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from build_brdb_historical_ukc_kyi_candidate import assemble

def ukc(day,horse):
    b=bytearray(b' '*290)
    b[:8]=horse.encode('ascii')
    b[49:56]=b'SIRE_A '
    b[268:276]=day.encode('ascii')
    b[276:280]=b'1311'
    return bytes(b)+bytes((13,10))

def kyi(race,horse,no):
    b=bytearray(b' '*1022)
    b[:8]=race.encode('ascii')
    b[8:10]=f'{no:02}'.encode()
    b[10:18]=horse.encode('ascii')
    return bytes(b)+bytes((13,10))

def fixture(root):
    u=root/'ukc';k=root/'kyi';u.mkdir();k.mkdir()
    with ZipFile(u/'UKC_2025.zip','w') as z:
        z.writestr('UKC251206.txt',ukc('20251206','20000001')+ukc('20251206','20000002'))
        z.writestr('UKC251213.txt',ukc('20251213','20000001')+ukc('20251213','20000001'))
    with ZipFile(k/'KYI_2025.zip','w') as z:
        z.writestr('KYI251206.txt',kyi('05250101','20000001',1))
        z.writestr('KYI251213.txt',
                   kyi('05250111','20000001',1)+kyi('05250111','20000002',2)+kyi('05250111','20000003',3))
    return u,k

class TemporalCandidate(unittest.TestCase):
    def test_missing_and_prior_day_fallback_never_promotes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);u,k=fixture(root)
            a=assemble(u,k,root/'out',years=(2025,))
            self.assertEqual(a['kyi_entries'],4)
            self.assertEqual(a['matched_entries'],3)
            self.assertEqual(a['same_day_ukc_entries'],2)
            self.assertEqual(a['prior_day_ukc_entries'],1)
            self.assertEqual(a['missing_ukc_entries'],1)
            self.assertEqual(a['duplicate_identical_ukc_rows'],1)
            self.assertEqual(a['independently_attested_asof_entries'],0)
            self.assertFalse(a['prediction_safe'])
            with gzip.open(root/'out'/'private_historical_ukc_kyi_candidate.csv.gz','rt',encoding='utf-8') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[-1]['ukc_data_date'],'20251206')
            self.assertEqual(rows[-1]['selection_method'],'PRIOR_DATE_LAST_OBSERVED')

    def test_source_zip_tamper_changes_audit_identity(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);u,k=fixture(root)
            a=assemble(u,k,root/'first',years=(2025,))
            with ZipFile(k/'KYI_2025.zip','a') as z:
                z.comment=b'changed after archiving'
            b=assemble(u,k,root/'second',years=(2025,))
            self.assertNotEqual(a['source_zip_sha256']['2025']['kyi_sha256'],
                                b['source_zip_sha256']['2025']['kyi_sha256'])
            self.assertNotEqual(a['private_csv_gzip_sha256'],b['private_csv_gzip_sha256'])

    def test_conflicting_duplicate_ukc_denied(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);u,k=fixture(root)
            with ZipFile(u/'UKC_2025.zip','w') as z:
                z.writestr('UKC251206.txt',ukc('20251206','20000001'))
                b=bytearray(ukc('20251213','20000001'));b[49:56]=b'SIRE_B '
                z.writestr('UKC251213.txt',ukc('20251213','20000001')+bytes(b))
            with self.assertRaisesRegex(ValueError,'conflicting UKC'):
                assemble(u,k,root/'out',years=(2025,))

    def test_missing_year_and_source_identity_denied(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);u,k=fixture(root)
            with self.assertRaisesRegex(ValueError,'original ZIP pair missing'):
                assemble(u,k,root/'out',years=(2024,2025))
            p=k/'KYI_2025.zip'
            with ZipFile(p,'w') as z:z.writestr('KYI251206.txt',kyi('05250101','20000001',1))
            with self.assertRaisesRegex(ValueError,'incompatible or unexpected'):
                assemble(u,k,root/'bad',years=(2025,))

if __name__=='__main__':
    unittest.main()
