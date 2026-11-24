"""B7 synthetic gates plus optional real receipt integrity tests."""
import csv,gzip,json,os,tempfile,unittest
from pathlib import Path
import numpy as np
import duckdb
from run_brdb_b7_local import probs,fit,compare,group,rider,encode_cells,bind,sha

class B7Tests(unittest.TestCase):
    def test_softmax_field_normalization(self):
        X=np.array([[0.],[1.],[2.],[3.],[4.]])
        a=np.array([0,2]);n=np.array([2,3]);p=probs(X,np.array([0.]),a,n)
        np.testing.assert_allclose(p,[.5,.5,1/3,1/3,1/3]);np.testing.assert_allclose(np.add.reduceat(p,a),1)
        q=probs(X,np.array([1000.]),a,n);self.assertTrue(np.all(np.isfinite(q)));np.testing.assert_allclose(np.add.reduceat(q,a),1)

    def test_fixed_ridge_fit(self):
        X=np.array([[1.],[-1.],[1.],[-1.]])
        b,it,g=fit(X,np.array([1,0,1,0]),np.array([0,2]),np.array([2,2]));self.assertGreater(b[0],0);self.assertLess(g,1e-7)
        p=probs(X,b,np.array([0,2]),np.array([2,2]));self.assertGreater(p[0],.5)

    def test_holdout_labels_cannot_change_fit(self):
        ids=[];X=[]
        for yr in (2024,2025):
            for i,(month,s) in enumerate(((1,'1'),(8,'2'))):
                for no in (1,2):
                    ids.append((f'{yr}{i}',no,f'0000000{no}',f'{yr}-{month:02d}-01',s,int(no==1)))
                    X.append([float(no==1)]*6+[float(no==2)]*6)
        X=np.array(X);keys=['A1:SIRE_ID:ALL','JOCKEY:NEWCOMER_ALL_FLAT'];other=[r if r[3]<'2025-01-01' else (*r[:-1],1-r[-1]) for r in ids]
        with tempfile.TemporaryDirectory() as d:
            a=compare(ids,X,keys,Path(d));b=compare(other,X,keys,Path(d));self.assertEqual(a['models'],b['models']);self.assertEqual(a['mean'],b['mean']);self.assertNotEqual(a['metrics']['ALL']['JPDB']['winner_logloss'],b['metrics']['ALL']['JPDB']['winner_logloss'])

    def test_rider_history_uses_planned_code_and_strict_day(self):
        c=duckdb.connect();c.execute('''CREATE TABLE a1(race_key VARCHAR,race_date VARCHAR,track_type VARCHAR,distance INTEGER,venue_code VARCHAR);
        INSERT INTO a1 VALUES ('old','2024-01-01','1',1600,'05'),('old2','2024-01-02','1',1600,'05'),('same','2024-01-03','1',1600,'05'),('next','2024-01-04','1',1600,'05');
        CREATE TABLE sed(race_key_raw VARCHAR,horse_no INT,race_date VARCHAR,jockey_code VARCHAR,abnormal_code VARCHAR,finish INT,field_size INT,race_class_code VARCHAR,surface_code VARCHAR,distance_m INT);
        INSERT INTO sed VALUES ('old',1,'2024-01-01','12345','0',1,8,'A1','1',1600),('old',2,'2024-01-01','22222','0',2,8,'A1','1',1600),('old2',1,'2024-01-02','12345','3',NULL,8,'A1','1',1600),('same',1,'2024-01-03','12345','0',1,8,'A1','1',1600),('next',1,'2024-01-04','12345','0',1,8,'A1','1',1600);
        CREATE TABLE eval_targets(race_key VARCHAR,horse_no INT,horse_id VARCHAR,race_date VARCHAR,planned_jockey VARCHAR,actual_jockey VARCHAR,track_type VARCHAR,distance INT,venue_code VARCHAR);
        INSERT INTO eval_targets VALUES ('same',1,'00000001','2024-01-03','12345','22222','1',1600,'05'),('same',2,'00000002','2024-01-03','00000','12345','1',1600,'05');''');rider(c)
        self.assertEqual(c.execute('SELECT DISTINCT n,wins,top3,unavailable,unresolved,max_history_date FROM rider_cells WHERE horse_no=1').fetchall(),[(2,1,1,0,0,'2024-01-02')]);self.assertEqual(c.execute('SELECT DISTINCT n,unavailable,max_history_date FROM rider_cells WHERE horse_no=2').fetchall(),[(0,1,None)]);c.close()

    def test_unresolved_rider_history_separate(self):
        c=duckdb.connect();c.execute('''CREATE TABLE a1(race_key VARCHAR,race_date VARCHAR,track_type VARCHAR,distance INTEGER,venue_code VARCHAR);
        INSERT INTO a1 VALUES ('old','2024-01-01','2',1800,'08');
        CREATE TABLE sed(race_key_raw VARCHAR,horse_no INT,race_date VARCHAR,jockey_code VARCHAR,abnormal_code VARCHAR,finish INT,field_size INT,race_class_code VARCHAR,surface_code VARCHAR,distance_m INT);
        INSERT INTO sed VALUES ('old',1,'2024-01-01','12345','5',2,8,'A1','2',1800);
        CREATE TABLE eval_targets(race_key VARCHAR,horse_no INT,horse_id VARCHAR,race_date VARCHAR,planned_jockey VARCHAR,track_type VARCHAR,distance INT,venue_code VARCHAR);
        INSERT INTO eval_targets VALUES ('target',1,'00000001','2024-01-02','12345','2',1800,'08');''');rider(c)
        self.assertEqual(c.execute('SELECT DISTINCT n,wins,top3,unresolved FROM rider_cells').fetchall(),[(1,0,0,1)]);c.close()

    def cell_fixture(self):
        c=duckdb.connect();c.execute("CREATE TABLE eval_targets AS SELECT 'a' race_key,1 horse_no,'00000001' horse_id,'2025-01-02' race_date,'1' track_type,1 win")
        c.execute("""CREATE TABLE blood_cells AS SELECT 'a' race_key,1 horse_no,'00000001' horse_id,'2025-01-02' race_date,'A1:'||i feature,0 n,0 wins,0 top3,(i=0)::INT unavailable,0 unresolved,NULL::VARCHAR max_history_date FROM range(24) r(i); CREATE TABLE relative_cells AS SELECT 'a' race_key,1 horse_no,'00000001' horse_id,'2025-01-02' race_date,'RELATIVE:'||i feature,0 n,0 wins,0 top3,0 unavailable,0 unresolved,NULL::VARCHAR max_history_date FROM range(4) r(i); CREATE TABLE rider_cells AS SELECT 'a' race_key,1 horse_no,'00000001' horse_id,'2025-01-02' race_date,'JOCKEY:'||i feature,2 n,1 wins,1 top3,0 unavailable,1 unresolved,'2025-01-01' max_history_date FROM range(4) r(i);""");return c

    def test_missing_and_no_sample_not_equal(self):
        c=self.cell_fixture()
        with tempfile.TemporaryDirectory() as d:
            _,X,keys=encode_cells(c,Path(d));self.assertEqual(X.shape,(1,192))
            k=keys.index('A1:0')*6;l=keys.index('A1:1')*6;j=keys.index('JOCKEY:0')*6
            np.testing.assert_allclose(X[0,k:k+6],[0,.08,.23,1,0,0]);np.testing.assert_allclose(X[0,l:l+6],[0,.08,.23,0,1,0]);np.testing.assert_allclose(X[0,j:j+6],[np.log(3),.08,.23,0,0,1])
        c.close()

    def test_same_day_cell_rejected(self):
        c=self.cell_fixture();c.execute("UPDATE rider_cells SET max_history_date='2025-01-02'")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises((ValueError,AssertionError),msg='same day accepted'):encode_cells(c,Path(d))
        c.close()

    def test_hash_gate(self):
        c=duckdb.connect()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises((ValueError,AssertionError)):bind(c,Path(d))
        c.close()

    @unittest.skipUnless(os.environ.get('BRDB_B7_OUTPUT'),'real fixture not requested')
    def test_real_output_integrity(self):
        p=Path(os.environ['BRDB_B7_OUTPUT']);r=json.loads((p/'b7_receipt.json').read_text());self.assertFalse(r['prediction_safe']);self.assertFalse(r['production_authorized']);self.assertEqual(r['train_entries'],3982);self.assertEqual(r['holdout_entries'],3910)
        for name,h in r['output_sha256'].items():self.assertEqual(sha(p/name),h)
        fields={};wins={}
        with gzip.open(p/'PRIVATE_b7_predictions.csv.gz','rt') as f:
            for row in csv.DictReader(f):
                k=(row['race_key'],row['race_date']);fields.setdefault(k,[]).append([float(row[m]) for m in ['UNIFORM','BRDB','JPDB','BOTH']]);wins[k]=wins.get(k,0)+int(row['winner']);self.assertTrue(row['race_date'].startswith('2025'))
        self.assertEqual(len(fields),294);self.assertEqual(sum(map(len,fields.values())),3910);self.assertTrue(all(v==1 for v in wins.values()))
        for x in fields.values():np.testing.assert_allclose(np.sum(x,axis=0),1,atol=1e-12)
        with gzip.open(p/'PRIVATE_b7_cells.csv.gz','rt') as f:
            rows=list(csv.DictReader(f));self.assertEqual(len(rows),7892*32);self.assertTrue(all(not x['max_history_date'] or x['max_history_date']<x['race_date'] for x in rows))
        self.assertEqual(sum(r['independent_audit']['direct_count_date_checks'].values()),2048)

if __name__=='__main__':unittest.main()
