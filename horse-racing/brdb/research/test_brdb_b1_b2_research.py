"""Synthetic fixtures only: actual-start, dated-profile guard, historical cutoff."""
import unittest
from pathlib import Path
import duckdb
from run_brdb_b1_b2_local import classifier_sql
ROOT=Path(__file__).resolve().parent

class B1B2Test(unittest.TestCase):
    def setUp(self):
        self.c=duckdb.connect(':memory:')
        self.c.execute('''CREATE TABLE data(race_date VARCHAR,year INTEGER,race_key VARCHAR,horse_no INTEGER,horse_id VARCHAR,age INTEGER,abnormal_code VARCHAR,finish INTEGER,prev_result_key_1 VARCHAR,prev_race_key_1 VARCHAR,race_condition_code VARCHAR,track_type VARCHAR,distance INTEGER)''')
    def tearDown(self):self.c.close()
    def add(self,horse,date,key,code='0',finish=1,age=2,prev=None,prev_key=None,cls='A1'):
        self.c.execute('INSERT INTO data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',[date,int(date[:4]),key,1,horse,age,code,finish,prev,prev_key,cls,'1',1600])
    def classify(self):self.c.execute('CREATE OR REPLACE TEMP TABLE classified AS '+classifier_sql())
    def eligibility(self,horse,key):return self.c.execute('SELECT eligibility FROM classified WHERE horse_id=? AND race_key=?',[horse,key]).fetchone()[0]
    def test_nonstarter_and_abnormal_prior(self):
        h='00000001';self.add(h,'2018-01-01','00000001','1',0);self.add(h,'2018-01-02','00000002',prev=h+'20180101',prev_key='00000001')
        h2='00000002';self.add(h2,'2018-01-01','00000003','3',0);self.add(h2,'2018-01-02','00000004',prev=h2+'20180101',prev_key='00000003',cls='A3')
        self.classify();self.assertEqual(self.eligibility(h,'00000001'),'NON_STARTER');self.assertEqual(self.eligibility(h,'00000002'),'FIRST_OBSERVED_JRA_START_CANDIDATE');self.assertEqual(self.eligibility(h2,'00000004'),'KNOWN_PRIOR_JRA_START')
    def test_unresolved_unknown_left_edge(self):
        self.add('00000003','2018-01-01','00000005',prev='0000000320170101',prev_key='99999999')
        self.add('00000004','2018-01-01','00000006','9',0)
        self.add('00000005','2016-01-01','00000007');self.add('00000006','2018-01-01','00000008',age=None)
        self.add('00000007','2018-01-01','00000009',prev='0000000720180101',prev_key='00000009')
        self.add('00000008','2018-01-01','00000010',prev='0000009920170101',prev_key='00000011')
        self.classify()
        self.assertEqual([self.eligibility(f'{i:08d}',k) for i,k in zip(range(3,9),['00000005','00000006','00000007','00000008','00000009','00000010'])],['PRIOR_HISTORY_UNRESOLVED','UNKNOWN_START_STATUS','LEFT_EDGE_2016','AGE_OR_HISTORY_UNCERTAIN','PRIOR_HISTORY_UNRESOLVED','PRIOR_HISTORY_UNRESOLVED'])
    def test_dated_parent_guard(self):
        for i in range(1,5):self.add(f'{i:08d}','2018-01-02',f'{i:08d}')
        self.classify();self.c.execute('''CREATE TABLE dated_ukc(horse_id VARCHAR,data_date_iso VARCHAR,horse_symbol_code VARCHAR,source_archive_sha256 VARCHAR,source_member_sha256 VARCHAR,sire_name VARCHAR,sire_birth_year INTEGER,sire_line_code VARCHAR,broodmare_sire_name VARCHAR,broodmare_sire_birth_year INTEGER,broodmare_sire_line_code VARCHAR)''')
        for i,date,y in [(1,'2018-01-01',2000),(1,'2018-01-03',2001),(2,'2018-01-03',2000),(3,'2018-01-02',2001),(4,'2018-01-02',2000)]:self.c.execute('INSERT INTO dated_ukc VALUES (?,?,?,?,?,?,?,?,?,?,?)',[f'{i:08d}',date,'00','a','b','SyntheticSire',y,'1206','SyntheticBMS',1998,'1503'])
        self.c.execute('CREATE TABLE pedigree_master(horse_id VARCHAR,profile_data_date VARCHAR)');self.c.executemany('INSERT INTO pedigree_master VALUES (?,?)',[(f'{i:08d}','2025-01-01') for i in range(1,7)])
        self.c.execute('''CREATE TABLE parent_master(child_horse_id VARCHAR,role VARCHAR,resolution_status VARCHAR,guard_result VARCHAR,candidate_count INTEGER,resolved_parent_horse_id VARCHAR,parent_name VARCHAR,parent_birth_year INTEGER,parent_lineage_code VARCHAR)''')
        for i in range(1,5):
            for role,parent,name,y,line in [('sire','00000005','SyntheticSire',2000,'1206'),('broodmare_sire','00000006','SyntheticBMS',1998,'1503')]:
                self.c.execute('INSERT INTO parent_master VALUES (?,?,?,?,?,?,?,?,?)',[f'{i:08d}',role,'RESOLVED_EXACT','lineage_code_match' if i!=4 else 'bad',1,parent,name,y,line])
        self.c.execute('CREATE TEMP TABLE joined AS '+(ROOT/'brdb_b1_pedigree_join_v0_1.sql').read_text())
        self.assertEqual(self.c.execute('SELECT sire_join_status,sire_id,ukc_date FROM joined ORDER BY horse_id').fetchall(),[('MATCHED_GUARDED_STATIC_ID','00000005','2018-01-01'),('NO_DATED_PROFILE',None,None),('DATED_FACT_MISMATCH',None,'2018-01-02'),('INVALID_STATIC_GUARD',None,'2018-01-02')])
        self.assertEqual(self.c.execute('SELECT count(*) FROM joined WHERE prediction_safe OR production_authorized').fetchone()[0],0)
    def test_b2_cutoff_denominator(self):
        self.c.execute('''CREATE TABLE joined(year INTEGER,race_date VARCHAR,race_condition_code VARCHAR,start_status VARCHAR,eligibility VARCHAR,horse_id VARCHAR,race_key VARCHAR,sire_id VARCHAR,track_type VARCHAR,distance INTEGER,age INTEGER,abnormal_code VARCHAR,finish INTEGER)''')
        rows=[('2018-01-01','STARTED_NORMAL','0',1,'00000001','00000010'),('2018-01-01','STARTED_ABNORMAL','3',0,'00000002','00000010'),('2018-01-01','STARTED_ABNORMAL','5',3,'00000003','00000010'),('2018-01-01','NON_STARTER','1',0,'00000004','00000010'),('2018-01-01','STARTED_NORMAL','0',2,'00000005',None),('2018-01-02','STARTED_NORMAL','0',1,'00000006','00000010')]
        for d,st,code,finish,h,sire in rows:self.c.execute('INSERT INTO joined VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',[2018,d,'A1',st,'NON_STARTER' if st=='NON_STARTER' else 'FIRST_OBSERVED_JRA_START_CANDIDATE',h,h,sire,'1',1600,2,code,finish])
        self.c.execute("CREATE TABLE cutoff AS SELECT '2018-01-02' AS as_of_date")
        self.c.execute('CREATE TEMP TABLE stats AS '+(ROOT/'brdb_b2_sire_debut_statistics_v0_1.sql').read_text())
        self.assertEqual(self.c.execute("SELECT starts,wins,top3,normal_finishers,baseline_starts,baseline_top3,resolved_starts,sample_status,max_history_date FROM stats WHERE scope='ALL' ORDER BY cohort").fetchall(),[(3,1,2,1,4,3,3,'LOW_SAMPLE','2018-01-01')]*2)
        self.assertEqual(self.c.execute('SELECT count(*) FROM stats').fetchone()[0],10)

if __name__=='__main__':unittest.main()
