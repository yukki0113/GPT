"""Synthetic fixed-width regression for canonical JRDB Reader based SED/PACI ingest.

Executed against the real jrdb_raw module in the repository CI.
No licensed horse records included.
"""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
import brdb_sed_going_ingest as ingest


def place(buf, start, value, width):
    b = str(value).encode('cp932')
    assert len(b) <= width
    buf[start-1:start-1+width] = b.ljust(width,b' ')


def sample_files(tmp, token, going='21', abnormal='0', sed_id='23100001', ukc_date=None, finish='01'):
    day='20'+token
    rkey='05264a12'
    sid='23100001'
    sed=bytearray(b' '*374)
    for args in [(1,rkey,8),(9,'01',2),(11,sed_id,8),(19,day,8),
                 (63,'2000',4),(67,'1',1),(70,going,2),(131,'12',2),
                 (141,finish,2),(143,abnormal,1)]:place(sed,*args)
    kyi=bytearray(b' '*1022)
    for args in [(1,rkey,8),(9,'01',2),(11,sid,8),(19,'サンプル',36)]:place(kyi,*args)
    ukc=bytearray(b' '*290)
    for args in [(1,sid,8),(9,'サンプル',36),(50,'テスト種牡馬',36),
                 (86,'母',36),(122,'母父',36),(269,ukc_date or day,8)]:place(ukc,*args)
    p=Path(tmp)/f'PACI{token}.zip';s=Path(tmp)/f'SED{token}.zip'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr(f'KYI{token}.txt',bytes(kyi)+b'\r\n')
        z.writestr(f'UKC{token}.txt',bytes(ukc)+b'\r\n')
    with zipfile.ZipFile(s,'w') as z:
        z.writestr(f'SED{token}.txt',bytes(sed)+b'\r\n')
    return str(p),str(s)


RACE={'target_date':'2026-11-15','surface_code':'1','race_key':'05265412',
      'venue_code':'05','distance_m':2000,'course_code':'4','field_size':18}


class TestRealSedGoingIngest(unittest.TestCase):
    def test_official_going_map(self):
        self.assertEqual(len(ingest.GOING_CODE),12)
        self.assertEqual(ingest.GOING_CODE['11'],'良')
        self.assertEqual(ingest.GOING_CODE['21'],'稍重')
        self.assertEqual(ingest.GOING_CODE['32'],'重')
        self.assertEqual(ingest.GOING_CODE['42'],'不良')

    def test_real_reader_join_good(self):
        with tempfile.TemporaryDirectory() as t:
            p=sample_files(t,'261108')
            a,r=ingest.normalize([p],RACE,RACE['target_date'])
            self.assertEqual(len(a['records']),1)
            row=a['records'][0]
            self.assertEqual((row['horse_id'],row['sire_name'],row['going_class']),
                             ('23100001','テスト種牡馬','稍重'))
            self.assertEqual(row['outcome'],'FINISHED')
            self.assertEqual(r['going_codes'],{'21':1})
            self.assertFalse(a['prediction_safe'])

    def test_abnormal_excluded_without_false_finish(self):
        with tempfile.TemporaryDirectory() as t:
            p=sample_files(t,'261108',abnormal='3',finish='00')
            a,_=ingest.normalize([p],RACE,RACE['target_date'])
            self.assertEqual(a['records'][0]['outcome'],'EXCLUDED')
            self.assertIsNone(a['records'][0]['finish_position'])

    def test_unknown_going_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=sample_files(t,'261108',going='99')
            with self.assertRaisesRegex(ValueError,'going code'):
                ingest.normalize([p],RACE,RACE['target_date'])

    def test_mismatched_blood_id_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=sample_files(t,'261108',sed_id='23100002')
            with self.assertRaisesRegex(ValueError,'missing KYI or UKC'):
                ingest.normalize([p],RACE,RACE['target_date'])

    def test_ukc_profile_after_day_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=sample_files(t,'261108',ukc_date='20261115')
            with self.assertRaisesRegex(ValueError,'UKC profile as-of'):
                ingest.normalize([p],RACE,RACE['target_date'])

    def test_future_race_day_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=sample_files(t,'261115')
            with self.assertRaisesRegex(ValueError,'post-target'):
                ingest.normalize([p],RACE,RACE['target_date'])

    def test_duplicate_day_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=sample_files(t,'261108')
            with self.assertRaisesRegex(ValueError,'duplicate historical date'):
                ingest.normalize([p,p],RACE,RACE['target_date'])

    def test_normal_without_finish_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=sample_files(t,'261108',finish='00')
            with self.assertRaisesRegex(ValueError,'normal finisher'):
                ingest.normalize([p],RACE,RACE['target_date'])

    def test_deterministic_manifest_sha(self):
        with tempfile.TemporaryDirectory() as t:
            p=sample_files(t,'261108')
            a,r=ingest.normalize([p],RACE,RACE['target_date'])
            aa,rr=ingest.normalize([p],RACE,RACE['target_date'])
            self.assertEqual(a,aa)
            self.assertEqual(r,rr)
            self.assertEqual(len(r['manifest_sha256']),64)


if __name__=='__main__':
    unittest.main()
