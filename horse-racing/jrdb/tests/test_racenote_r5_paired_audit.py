import unittest
import json
import tempfile
from pathlib import Path
import racenote_r5_paired_audit as r

class PilotAuditTests(unittest.TestCase):
    def test_metrics(self):
        self.assertEqual(r.metrics([2,1,4,5,6],[1,2,3]),dict(honmei_win=0,honmei_top3=1,winner_in_five=1,top3_in_five=2,all_top3_in_five=0))
    def test_paired(self):
        p=r.paired([1,2,4,5,6],[2,1,3,5,6],[1,2,3]);self.assertEqual(p['paired']['honmei_win'],'A_BETTER');self.assertEqual(p['paired']['top3_in_five'],'B_BETTER');self.assertEqual(p['promoted'],1);self.assertTrue(p['five_changed'])
    def test_duplicate(self):
        with self.assertRaises(ValueError):r.keyed([{'id':1},{'id':1}],lambda x:x['id'])
    def test_duplicate_five(self):self.assertFalse(r.valid_five([1,2,3,4,4],set(range(1,7))))
    def test_bad_pin(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.json';p.write_text('{}')
            with self.assertRaises(ValueError):r.load(p,'0'*64)
    def test_ambiguous_top(self):
        with self.assertRaises(ValueError):r.metrics([1,2,3,4,5],[1,2,2])
    def test_result_source(self):
        with self.assertRaises(ValueError):r.result_top({'status':'partial'},'05265404',{1,2,3})
    def test_abnormal(self):
        a=[{'horse_no':i,'finish':i,'abnormal_code':'0','completed_normally':True} for i in (1,2,3)]
        d={'status':'success','provenance':{'web_used':False,'result_source':'SED','payout_source':'HJC'},'races':[{'race_key':'05265404','race_date':'2026-11-15','cross_validation':{'status':'pass'},'all_runners':a,'top3':a}]}
        self.assertEqual(r.result_top(d,'05265404',{1,2,3}),[1,2,3]);a[2]['abnormal_code']='2'
        with self.assertRaises(ValueError):r.result_top(d,'05265404',{1,2,3})
if __name__=='__main__':unittest.main()
