import copy, unittest
from discovery import validate

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.s = [{'url':'https://example.org/synthetic','observed_at':'2026-11-25T10:00:00+09:00'}]
        self.b = {'pack':{'name_ja':'架空パック','pack_type':'SELECTION','available_from':'2026-11-24','coverage':'PARTIAL','reported_slots':3,'sources':self.s}, 'cards':[{'name_ja':'架空カードＡ','rarity':None,'sources':self.s}]}
    def test_partial(self):
        self.assertEqual(validate(self.b)['observations'],1)
    def test_unknown_rarity(self):
        self.assertEqual(validate(self.b)['rarities'],{'UNKNOWN':1})
    def test_duplicate(self):
        self.b['cards'].append(dict(self.b['cards'][0],name_ja='架空カードA'))
        with self.assertRaises(ValueError): validate(self.b)
    def test_unsupported_full(self):
        self.b['pack']['coverage']='FULL'
        with self.assertRaises(ValueError): validate(self.b)
    def test_rarity_evidence(self):
        self.b['cards'][0].update(rarity='UR',rarity_sources=[])
        with self.assertRaises(ValueError): validate(self.b)
    def test_variant_distinct(self):
        self.b['cards'].append(dict(self.b['cards'][0],variant='ALT'))
        self.assertEqual(validate(self.b)['observations'],2)
    def test_full(self):
        self.b['pack'].update(coverage='FULL',reported_slots=1,full_list_evidence=self.s)
        self.assertEqual(validate(self.b)['coverage'],'FULL')

if __name__=='__main__': unittest.main()
