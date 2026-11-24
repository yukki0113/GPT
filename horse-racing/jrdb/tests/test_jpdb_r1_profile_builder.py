"""Synthetic, license-free R1 regressions. Run under approved DuckDB runtime."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import duckdb
from jrdb_raw import BODY_LENGTHS
from jpdb_history_reader import JPDBHistoryReaderError
from jpdb_r1_profile_builder import (read_target_paci,select_cell,empty_metrics,scoped_metrics,
                                    make_evidence,resolve_course)

D='2026-11-15'
K='05265405'


def record(kind,fields):
    b=bytearray(b' '*BODY_LENGTHS[kind])
    for start,text in fields.items():
        v=text.encode('ascii');b[start-1:start-1+len(v)]=v
    return bytes(b)+b'\r\n'


def fixture(path, *, duplicate=False, wrong_date=False, field_size='01', malformed=False):
    bac=record('BAC',{1:K,9:'20261114' if wrong_date else '20261115',21:'1600',25:'1',26:'2',27:'1',30:'A1',95:field_size,97:'4'})
    kyi=record('KYI',{1:K,9:'01',11:'20240001',55:'98765',96:'99999',336:'00123',403:'0',530:'00999'})
    if duplicate:kyi+=kyi
    if malformed:kyi=kyi[:-1]
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('BAC261115.txt',bac);z.writestr('KYI261115.txt',kyi)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProfileTest(unittest.TestCase):
    def test_scheduled_kyi_not_reference_or_market(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'PACI261115.zip';h=fixture(p)
            races,entries=read_target_paci(p,target_date=D,expected_sha256=h)
            self.assertEqual(races[K]['race_class_code'],'A1')
            self.assertEqual(entries[K][1],{'horse_no':1,'horse_id':'20240001','scheduled_jockey_code':'00123','entry_cancel_flag_raw':'0'})

    def test_target_paci_invalid_cases(self):
        for settings in ({'duplicate':True},{'wrong_date':True},{'field_size':'02'},{'malformed':True}):
            with self.subTest(settings=settings), tempfile.TemporaryDirectory() as t:
                p=Path(t)/'PACI261115.zip';h=fixture(p,**settings)
                with self.assertRaises(JPDBHistoryReaderError):read_target_paci(p,target_date=D,expected_sha256=h)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'PACI261115.zip';fixture(p)
            with self.assertRaises(JPDBHistoryReaderError):read_target_paci(p,target_date=D,expected_sha256='0'*64)

    def test_missing_cell_not_negative(self):
        e=make_evidence(K,1,'ROLLING_3Y','COURSE_SIZE',{'course_size_class':None},None,'JOCKEY_CONDITION','P2_PHYSICAL_ALL_FLAT')
        self.assertIsNone(e['metrics']);self.assertIsNone(e['sample_n']);self.assertEqual(e['direction'],'UNCLASSIFIED')
        m=select_cell([],{'venue_code':'05'},D)
        self.assertEqual(m['entries'],0);self.assertIsNone(m['start_basis_win_rate_candidate'])
        self.assertEqual(m['sample_support_status'],'NO_HISTORY')

    def test_duplicate_condition_rejected(self):
        c={'dimension_value':{'venue_code':'05'},'metrics':empty_metrics(D)}
        with self.assertRaises(JPDBHistoryReaderError):select_cell([c,c],c['dimension_value'],D)

    def test_newcomer_date_surface_and_abnormal_guard(self):
        with duckdb.connect(':memory:') as db:
            db.execute('CREATE TABLE jpdb_course_facts(race_date VARCHAR,jockey_code VARCHAR,surface_code VARCHAR,race_class_code VARCHAR,venue_code VARCHAR,distance_m BIGINT,abnormal_code VARCHAR,finish INTEGER,field_size INTEGER)')
            rows=[('2026-11-14','00123','1','A1','05',1600,'0',1,10),
                  ('2026-11-14','00123','1','A1','05',1600,'1',None,10),
                  ('2026-11-14','00123','1','A1','05',1600,'3',None,10),
                  ('2026-11-14','00123','2','A1','05',1600,'0',1,10),
                  ('2026-11-14','00123','1','A2','05',1600,'0',1,10),
                  ('2026-11-14','00123','1','A3','05',1600,'0',1,10),
                  ('2026-11-15','00123','1','A1','05',1600,'0',1,10),
                  ('2026-11-16','00123','1','A1','05',1600,'0',1,10),
                  ('2023-01-01','00123','1','A1','05',1600,'0',1,10)]
            db.executemany('INSERT INTO jpdb_course_facts VALUES (?,?,?,?,?,?,?,?,?)',rows)
            m=scoped_metrics(db,'NEWCOMER_SURFACE_DISTANCE_EXACT',{'race_class_code':'A1','surface_code':'1','distance_m':1600},['00123','00999'],'2023-11-15',D)
            self.assertEqual((m['00123']['entries'],m['00123']['wins'],m['00123']['top3'],m['00123']['actual_starts_candidate']),(3,1,1,2))
            self.assertEqual(m['00123']['start_basis_win_rate_candidate'],.5)
            self.assertEqual(m['00999']['sample_support_status'],'NO_HISTORY')
            db.execute("INSERT INTO jpdb_course_facts VALUES ('2026-11-14','00123','1','A1','05',1600,'5',1,10)")
            n=scoped_metrics(db,'NEWCOMER_SURFACE',{'race_class_code':'A1','surface_code':'1'},['00123'],'2023-11-15',D)['00123']
            self.assertEqual(n['sample_support_status'],'REVIEW_REQUIRED');self.assertIsNone(n['start_basis_win_rate_candidate'])


if __name__=='__main__':unittest.main()
