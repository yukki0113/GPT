"""Synthetic B3 regression tests; no licensed rows."""
import unittest
from pathlib import Path
import duckdb
from run_brdb_b3_local import cohort_sql,validate,B2_ROOT
SQL=Path(__file__).with_name('brdb_b3_debut_statistics_v0_1.sql').read_text()
B2=(B2_ROOT/'brdb_b2_sire_debut_statistics_v0_1.sql').read_text()
class B3Test(unittest.TestCase):
    def setUp(self):
        self.c=duckdb.connect(':memory:')
        self.c.execute('''CREATE TABLE joined(year INTEGER,race_date VARCHAR,race_key VARCHAR,horse_no INTEGER,horse_id VARCHAR,track_type VARCHAR,distance INTEGER,age INTEGER,abnormal_code VARCHAR,finish INTEGER,start_status VARCHAR,eligibility VARCHAR,race_condition_code VARCHAR,sire_id VARCHAR,bms_id VARCHAR,ukc_date VARCHAR,dated_sire_line VARCHAR,dated_bms_line VARCHAR)''')
        self.c.execute("CREATE TABLE cutoff AS SELECT '2026-01-01' AS as_of_date")
        self.c.execute("CREATE TABLE lineage_master(lineage_code VARCHAR); INSERT INTO lineage_master VALUES ('1101'),('2202')")
    def tearDown(self): self.c.close()
    def insert(self,i,*,date='2025-01-01',year=2025,sire='00000001',bms='00000002',sline='1101',bline='2202',ukc='2025-01-01',code='0',finish=1,status='STARTED_NORMAL',eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE',raceclass='A1',surface='1'):
        self.c.execute('INSERT INTO joined VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',[year,date,'r'+str(i),1,str(i).zfill(8),surface,1600,2,code,finish,status,eligibility,raceclass,sire,bms,ukc,sline,bline])
    def build(self):
        self.c.execute('CREATE OR REPLACE TEMP TABLE cohort AS '+cohort_sql(B2))
        self.c.execute('CREATE OR REPLACE TEMP TABLE stats AS '+SQL)
        validate(self.c,'2026-01-01')
    def all(self,lane):
        return self.c.execute("SELECT key1,key2,starts,wins,top3,resolved_starts,baseline_starts,left_marginal_starts,right_marginal_starts,top3_rate,sample_status FROM stats WHERE cohort='A1_RACE_ACTUAL_STARTERS' AND scope='ALL' AND lane=? ORDER BY key1,key2",[lane]).fetchall()
    def test_ordered_pairs_and_same_eligible_marginals(self):
        self.insert(1);self.insert(2,sire='00000002',bms='00000001',sline='2202',bline='1101',finish=4)
        self.insert(3,sire='00000001',bms='00000003',finish=2);self.insert(4,bms=None)
        self.build();p=self.all('PARENT_ID_PAIR');self.assertEqual(len(p),3)
        self.assertEqual(p[0][:9],('00000001','00000002',1,1,1,3,4,2,1))
        self.assertEqual(p[2][:9],('00000002','00000001',1,0,0,3,4,1,1))
        self.assertEqual(len(self.all('LINEAGE_CODE_PAIR')),2)
        self.assertEqual(sum(r[2] for r in self.all('SIRE_ID')),4)
    def test_missing_invalid_and_future_lineage_never_fallback(self):
        self.insert(1,sire=None,bms=None,ukc=None);self.insert(2,sire=None,bms=None,bline='9999');self.insert(3,sire=None,bms=None,ukc='2025-01-02');self.insert(4,sire=None,bms=None)
        self.build();self.assertEqual(self.all('LINEAGE_CODE_PAIR')[0][2:7],(1,1,1,1,4))
        b=self.all('BMS_ID')[0];self.assertEqual(b[0:3],(None,None,0));self.assertIsNone(b[9]);self.assertEqual(b[10],'NO_RESOLVED_GROUP')
    def test_cutoff_denominator_and_cohort_difference(self):
        self.insert(1);self.insert(2,code='3',status='STARTED_ABNORMAL',finish=0);self.insert(3,code='5',status='STARTED_ABNORMAL',finish=2)
        self.insert(4,code='1',status='NOT_STARTED',eligibility='NOT_STARTED');self.insert(5,date='2026-01-01',year=2025);self.insert(6,date='2016-12-31',year=2016,ukc='2016-12-31')
        self.insert(7,raceclass='A3');self.build()
        self.assertEqual(self.all('BMS_ID')[0][2:7],(3,1,2,3,3));self.assertEqual(self.c.execute("SELECT starts FROM stats WHERE cohort='FIRST_OBSERVED_JRA_START_CANDIDATE' AND scope='ALL' AND lane='BMS_ID'").fetchone()[0],4)
    def test_low_n_boundary_and_scope_overlap(self):
        for i in range(1,31):self.insert(i,bms='00000002' if i<=29 else '00000003')
        self.insert(31,bms='00000002');self.build()
        self.assertEqual([r[10] for r in self.all('BMS_ID')],['DESCRIPTIVE','LOW_SAMPLE'])
        self.assertEqual(self.c.execute("SELECT sum(starts) FROM stats WHERE cohort='A1_RACE_ACTUAL_STARTERS' AND lane='BMS_ID'").fetchone()[0],31*5)
    def test_deterministic(self):
        self.insert(1);self.insert(2,bms=None);self.build();a=self.c.execute('SELECT * FROM stats ORDER BY cohort,scope,dimension,lane,key1,key2').fetchall();self.build();self.assertEqual(a,self.c.execute('SELECT * FROM stats ORDER BY cohort,scope,dimension,lane,key1,key2').fetchall())
if __name__=='__main__':unittest.main()
