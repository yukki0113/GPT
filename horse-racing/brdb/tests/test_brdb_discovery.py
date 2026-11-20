import copy
import json
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent / "src"))
from brdb_discovery import discover

class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=json.loads((Path(__file__).parent/'fixtures'/'brdb_discovery_synthetic.json').read_text())

    def test_all_horses_and_no_prediction(self):
        output=discover(self.src)
        self.assertEqual(len(output['horses']),2)
        self.assertTrue(all(not f['prediction_eligible'] and not f['display_eligible'] for h in output['horses'] for f in h['findings']))

    def test_deterministic(self):
        self.assertEqual(discover(self.src),discover(self.src))

    def test_invalid_counts_rejected(self):
        src=copy.deepcopy(self.src)
        src['horses'][0]['components']['sire']['scopes'][0]['counts']['wins']=999
        with self.assertRaises(ValueError):discover(src)

    def test_asof_rejected(self):
        src=copy.deepcopy(self.src)
        src['horses'][0]['components']['sire']['scopes'][0]['as_of_exclusive']='2027-01-01'
        with self.assertRaises(ValueError):discover(src)

    def test_duplicate_rejected(self):
        src=copy.deepcopy(self.src);src['horses'][1]['horse_id']=src['horses'][0]['horse_id'];src['horses'][1]['horse_no']=src['horses'][0]['horse_no']
        with self.assertRaises(ValueError):discover(src)

    def test_production_authorization_rejected(self):
        src=copy.deepcopy(self.src);src['policy']['production_authorized']=True
        with self.assertRaises(ValueError):discover(src)

    def test_no_sample_no_phantom(self):
        src=copy.deepcopy(self.src);sc=src['horses'][0]['components']['sire']['scopes'][0];sc['counts'].update(starts=0,wins=0,top3=0);sc['rates']['top3_rate']=None
        out=discover(src)
        self.assertFalse(any(f['scope_key']==sc['scope_key'] for f in out['horses'][0]['findings'] if f['kind']=='SIRE_BASELINE_COMPARISON'))

    def test_unverified_pairing_not_promoted(self):
        out=discover(self.src)
        self.assertFalse(any('PAIRING' in f['kind'] for h in out['horses'] for f in h['findings']))

if __name__=='__main__':unittest.main()
