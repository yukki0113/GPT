import unittest
import duckdb
from jpdb_r2_condition_context import *


def counts(n,top,win=0,unresolved=0,dnf=0,cancel=0):
    return (n+unresolved+cancel,n-dnf,cancel,0,dnf,unresolved,0,0,win,win,top)

class R2Tests(unittest.TestCase):
    def test_disjoint_groups_and_direction(self):
        cube=Cube('VENUE_SURFACE',[
            ('00001',('1','05'),counts(100,60,20)),('00001',('1','09'),counts(100,30,10)),
            ('00002',('1','05'),counts(100,35,10)),('00002',('1','09'),counts(100,30,10)),
            ('00001',('2','05'),counts(100,90)),('00002',('1',None),counts(100,90)),
        ])
        r=compare(cube,'00001',('1',),('05',));self.assertEqual([g['resolved_starts'] for g in r['groups'].values()],[100]*4)
        self.assertEqual(cube.unknown,100);self.assertEqual(r['comparisons']['relative_condition_contrast']['top3_delta_pp'],25)
        self.assertEqual(r['comparisons']['relative_condition_contrast']['direction'],'POSITIVE')
    def test_opposite_negative_and_conflict(self):
        p=contrast([stats(counts(100,60)),stats(counts(100,30)),stats(counts(100,30)),stats(counts(100,30))],COMPARISONS['relative_condition_contrast'])
        n=contrast([stats(counts(100,10)),stats(counts(100,30)),stats(counts(100,30)),stats(counts(100,30))],COMPARISONS['relative_condition_contrast'])
        self.assertEqual(n['direction'],'NEGATIVE');x=summarize_windows([{'comparisons':{'relative_condition_contrast':y}} for y in (p,n,p)])
        self.assertEqual(x['relative_condition_contrast']['status'],'CONFLICTED');self.assertEqual(x['relative_condition_contrast']['direction'],'UNCLASSIFIED')
    def test_small_missing_unresolved(self):
        w=COMPARISONS['within_rider']
        for n,u,status in [(0,0,'UNAVAILABLE'),(29,0,'INSUFFICIENT'),(100,1,'REVIEW_REQUIRED')]:
            g=[stats(counts(n,0,unresolved=u)),stats(counts(100,90)),stats(ZERO),stats(ZERO)]
            self.assertEqual(contrast(g,w)['status'],status);self.assertEqual(contrast(g,w)['direction'],'UNCLASSIFIED')
    def test_peer_unresolved_bounds(self):
        g=[stats(counts(100,40)),stats(counts(100,30)),stats(counts(100,30,unresolved=100)),stats(counts(100,30))]
        v=contrast(g,COMPARISONS['same_condition_peers']);self.assertEqual(v['direction'],'UNCLASSIFIED');self.assertEqual(v['top3_unresolved_bounds_pp'],[-25,25])
    def test_no_history_base(self):
        cube=Cube('ALL_FLAT',[('00002',(),counts(100,30))]);r=compare(cube,'00001',(),());self.assertEqual(set(r['comparisons']),{'same_condition_peers'});self.assertEqual(r['comparisons']['same_condition_peers']['status'],'UNAVAILABLE')
    def test_cutoff_and_newcomer_scope(self):
        db=duckdb.connect();db.execute('CREATE TABLE jpdb_course_facts(race_date VARCHAR,jockey_code VARCHAR,surface_code VARCHAR,race_class_code VARCHAR,venue_code VARCHAR,abnormal_code VARCHAR,finish INTEGER,field_size INTEGER)')
        rows=[('2025-01-01','00001','1','A1','05','0',1,10),('2025-01-02','00001','1','A1','09','3',None,10),('2025-01-02','00001','1','A3','05','0',1,10),('2025-01-02','00001','2','A1','05','0',1,10),('2025-02-01','00001','1','A1','05','0',1,10),('2025-02-02','00001','1','A1','05','0',1,10)]
        db.executemany('INSERT INTO jpdb_course_facts VALUES (?,?,?,?,?,?,?,?)',rows)
        c=query_cube(db,'NEWCOMER_VENUE_SURFACE',[('2025-01-01','2025-02-01')]);a,b,_,_=c.groups('00001',('A1','1'),('05',));self.assertEqual((a[0],b[0]),(1,1));self.assertEqual(stats(b)['resolved_starts'],1);self.assertEqual(stats(b)['top3'],0)
    def test_market_same_cohort(self):
        self.assertEqual(market_delta([(100,20,20.),(100,10,10.),(100,10,10.),(100,10,10.)]),(.1,0.))
    def test_invalid_partition(self):
        with self.assertRaises(JPDBHistoryReaderError):stats((2,1,0,0,0,0,0,0,0,0,0))

if __name__=='__main__':unittest.main()
