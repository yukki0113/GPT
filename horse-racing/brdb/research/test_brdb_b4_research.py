"""Synthetic-only B4 guard and early-history regression."""
import unittest
import duckdb
from run_brdb_b4_local import ROOT

class B4Test(unittest.TestCase):
    def setUp(self):
        self.c=duckdb.connect(':memory:')
    def tearDown(self):self.c.close()
    def graph(self):
        c=self.c
        c.execute('''CREATE TABLE pedigree_master(horse_id VARCHAR,horse_name VARCHAR,birth_date VARCHAR,profile_data_date VARCHAR,sex_code VARCHAR,sire_name VARCHAR,sire_birth_year INTEGER,dam_name VARCHAR,dam_birth_year INTEGER,broodmare_sire_name VARCHAR,broodmare_sire_birth_year INTEGER,sire_line_code VARCHAR,broodmare_sire_line_code VARCHAR);
        CREATE TABLE dated_ukc AS SELECT * EXCLUDE(birth_date,profile_data_date),''::VARCHAR AS birth_date_iso,''::VARCHAR AS data_date_iso FROM pedigree_master;
        CREATE TABLE parent_master(child_horse_id VARCHAR,role VARCHAR,resolved_parent_horse_id VARCHAR,resolution_status VARCHAR,candidate_count INTEGER,guard_result VARCHAR);
        CREATE TABLE cohort(race_key VARCHAR,horse_no INTEGER,horse_id VARCHAR,race_date VARCHAR,track_type VARCHAR,distance INTEGER,age INTEGER,ukc_date VARCHAR,sire_id VARCHAR);''')
        # Fictional IDs/names, unrelated to licensed data. Mother and granddam identities guarded by BMS facts.
        def profile(i,n,b,obs,sex,s,sy,d,dy,bs,by,sl='1001',bl='1001'):
            c.execute('INSERT INTO pedigree_master VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',[i,n,b,obs,sex,s,sy,d,dy,bs,by,sl,bl])
        profile('00000001','target','20200101','20230101','1','sire',2000,'dam',2010,'ms',1999)
        profile('00000002','dam','20100101','20150101','2','ms',1999,'grand',2000,'gs',1990)
        profile('00000003','grand','20000101','20100101','2','gs',1990,'x',1980,'y',1970)
        profile('00000004','sire','20000101','20100101','1','x',1990,'y',1990,'z',1980)
        profile('00000005','full','20190101','20210101','1','sire',2000,'dam',2010,'ms',1999)
        profile('00000006','future','20180101','20240101','1','sire',2000,'dam',2010,'ms',1999)
        profile('00000007','younger','20210101','20220101','1','sire',2000,'dam',2010,'ms',1999)
        profile('00000008','wrong','20180101','20210101','1','sire',2000,'dam',2010,'wrongms',1999)
        profile('00000009','aunt','20110101','20150101','2','ms',1999,'grand',2000,'gs',1990)
        profile('00000010','unknownsire','20170101','20200101','1','sire',2000,'dam',2010,'ms',1999)
        profile('00000011','alias','20160101','20200101','1','sire',2000,'dam',2010,'ms',1999)
        profile('00000012','other','20010101','20100101','1','x',1990,'y',1990,'z',1980)
        profile('00000013','half','20180101','20210101','1','other',2001,'dam',2010,'ms',1999)
        for child,parent,role in [('01','02','dam'),('02','03','dam'),('01','04','sire'),('05','02','dam'),('05','04','sire'),('06','02','dam'),('07','02','dam'),('08','02','dam'),('09','03','dam'),('10','02','dam'),('13','02','dam'),('13','12','sire')]:
            c.execute('INSERT INTO parent_master VALUES (?,?,?,?,?,?)',['000000'+child,role,'000000'+parent,'RESOLVED_EXACT',1,'dam_bms_name_birth_year_lineage_match' if role=='dam' else 'lineage_code_match'])
        c.execute("INSERT INTO parent_master VALUES ('00000011','dam','00000002','RESOLVED_ALIAS',1,'dam_bms_name_birth_year_lineage_match')")
        c.execute("INSERT INTO dated_ukc SELECT * EXCLUDE(birth_date,profile_data_date),'2020-01-01','2022-06-01' FROM pedigree_master WHERE horse_id='00000001'")
        c.execute("INSERT INTO cohort VALUES ('R',1,'00000001','2022-06-01','1',1600,2,'2022-06-01','00000004')")
        c.execute((ROOT/'brdb_b4_relative_paths_v0_1.sql').read_text())
    def test_guarded_paths(self):
        self.graph();c=self.c
        self.assertEqual(c.execute('SELECT dam_status,granddam_status FROM family_targets').fetchone(),('RESOLVED','RESOLVED'))
        self.assertEqual(c.execute("SELECT relative_id,relationship FROM relative_paths WHERE path_status='RESOLVED' ORDER BY 1").fetchall(), [('00000005','FULL_SIBLING'),('00000009','MATERNAL_AUNT_UNCLE'),('00000010','SAME_DAM_SIRE_UNVERIFIED'),('00000013','MATERNAL_HALF_SIBLING')])
    def test_future_younger_conflict_alias(self):
        self.graph();c=self.c
        self.assertEqual(c.execute("SELECT relative_id,path_status FROM relative_paths WHERE path_status<>'RESOLVED' ORDER BY 1").fetchall(), [('00000006','NO_RELATIVE_PROFILE_BY_TARGET'),('00000007','NOT_OLDER'),('00000008','RELATIVE_DAM_GUARD_MISMATCH')])
        self.assertEqual(c.execute("SELECT count(*) FROM relative_paths WHERE relative_id='00000011'").fetchone()[0],0)
    def test_duplicate_paths_preserved_but_pair_deduplicated(self):
        self.graph();c=self.c
        c.execute("INSERT INTO relative_paths SELECT * REPLACE ('MATERNAL_AUNT_UNCLE' AS path,'MATERNAL_AUNT_UNCLE' AS relationship) FROM relative_paths WHERE relative_id='00000005'")
        c.execute('DROP TABLE relative_pairs')
        sql=(ROOT/'brdb_b4_relative_paths_v0_1.sql').read_text().split('CREATE TEMP TABLE relative_pairs AS',1)[1]
        c.execute('CREATE TEMP TABLE relative_pairs AS'+sql)
        self.assertEqual(c.execute("SELECT path_count,paths FROM relative_pairs WHERE relative_id='00000005'").fetchone(),(2,['MATERNAL_AUNT_UNCLE','SAME_DAM']))
        self.assertEqual(c.execute('SELECT count(*) FROM relative_pairs').fetchone()[0],4)
    def history(self):
        self.graph();c=self.c
        c.execute('''CREATE TABLE classified(horse_id VARCHAR,race_key VARCHAR,race_date VARCHAR,track_type VARCHAR,distance INTEGER,age INTEGER,race_condition_code VARCHAR,eligibility VARCHAR,abnormal_code VARCHAR,finish INTEGER,start_status VARCHAR)''')
        def run(h,k,d,s,dist,e,code,f,status):
            c.execute('INSERT INTO classified VALUES (?,?,?,?,?,?,?,?,?,?,?)',[h,k,d,s,dist,2,'A1',e,code,f,status])
        first='FIRST_OBSERVED_JRA_START_CANDIDATE';normal='STARTED_NORMAL';ab='STARTED_ABNORMAL'
        for k,d,s,dist,e,code,f,status in [('c','2021-01-01','1',1600,'NON_STARTER','1',0,'NON_STARTER'),('f','2021-01-02','2',1800,first,'0',2,normal),('s','2021-02-01','1',1600,'KNOWN_PRIOR_JRA_START','3',0,ab),('t','2022-06-01','1',1600,'KNOWN_PRIOR_JRA_START','0',1,normal),('u','2022-06-02','1',1600,'KNOWN_PRIOR_JRA_START','0',1,normal)]:run('00000005',k,d,s,dist,e,code,f,status)
        run('00000009','left','2016-01-01','1',1600,'LEFT_EDGE_2016','0',1,normal)
        run('00000010','same','2022-06-01','1',1600,first,'0',1,normal)
        # For half sibling, 4th matching-surface win must not replace earlier starts.
        for k,d,s,dist,e,code,f,status in [('a','2020-01-01','2',1800,first,'0',4,normal),('b','2020-02-01','2',1800,'KNOWN_PRIOR_JRA_START','0',5,normal),('c2','2020-03-01','2',1800,'KNOWN_PRIOR_JRA_START','0',6,normal),('d','2020-04-01','1',1600,'KNOWN_PRIOR_JRA_START','0',1,normal)]:run('00000013',k,d,s,dist,e,code,f,status)
        c.execute((ROOT/'brdb_b4_relative_early_results_v0_1.sql').read_text())
    def test_strict_date_cancel_abnormal(self):
        self.history();c=self.c
        self.assertEqual(c.execute("SELECT first_starts,first_top3,early_starts,early_wins,early_history_keys FROM relative_stats WHERE relative_id='00000005' AND scope='ALL'").fetchone(),(1,1,2,0,['f','s']))
    def test_unknown_and_no_prior_are_not_zero_rates(self):
        self.history();c=self.c
        self.assertEqual(c.execute("SELECT relative_id,history_status,early_starts,early_top3_rate FROM relative_stats WHERE relative_id IN ('00000009','00000010') AND scope='ALL' ORDER BY 1").fetchall(), [('00000009','FIRST_START_UNRESOLVED',0,None),('00000010','NO_PRIOR_OBSERVED_START',0,None)])
    def test_scope_does_not_renumber(self):
        self.history();c=self.c
        self.assertEqual(c.execute("SELECT early_starts,early_top3_rate,sample_status FROM relative_stats WHERE relative_id='00000013' AND scope='SURFACE_DISTANCE'").fetchone(),(0,None,'NO_SAMPLE'))
        self.assertEqual(c.execute('SELECT count(*) FROM relative_stats').fetchone()[0],20)

if __name__=='__main__':unittest.main()
