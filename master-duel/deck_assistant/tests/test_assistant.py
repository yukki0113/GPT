import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from deck_assistant import search_cards, search_effects, resolve_names, assess_deck

class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.sqlite'
        s=Store.create(self.path)
        self.ids=['fiction:'+str(i) for i in range(50)]
        for i,cid in enumerate(self.ids):
            s.add_card(cid,990000+i,['架空のドロー','同名の架空カード','同名の架空カード'][i] if i<3 else f'架空{i}号')
            s.set_attributes(cid,kind='MONSTER' if i%2==0 else 'SPELL',attribute='LIGHT')
            s.set_md_catalog(cid,rarity='UR' if i==0 else ('SR' if i==1 else 'N'),rarity_source='MD:fiction')
            s.db.execute('INSERT INTO card_texts(card_id,language,version,body) VALUES (?,?,?,?)',
                         (cid,'ja','v1','デッキから１枚ドローする。' if i==0 else 'デッキからカードを手札に加える。'))
        s.close()
    def tearDown(self):self.tmp.cleanup()
    def test_effects_are_literal_with_source(self):
        rows=search_effects(self.path,phrases=['ドロー'],kind='MONSTER')
        self.assertEqual([x['card_id'] for x in rows],['fiction:0'])
        self.assertIn('デッキから',rows[0]['effect_text'])
        self.assertEqual(rows[0]['text_version'],'v1')
        self.assertEqual(search_effects(self.path,phrases=['ドロー','サーチ']),[])
        self.assertEqual(len(search_effects(self.path,phrases=['デッキから'],rarity='SR')),1)
    def test_card_filters_and_normalized_search(self):
        self.assertEqual(search_cards(self.path,name='架空の ドロー')[0]['card_id'],'fiction:0')
        self.assertEqual(len(search_cards(self.path,rarity='UR')),1)
        self.assertEqual(resolve_names(self.path,['同名の架空カード','ない']) [0]['status'],'AMBIGUOUS')
        self.assertEqual(resolve_names(self.path,['同名の架空カード','ない'])[1]['status'],'UNRESOLVED')
    def test_invalid_input_and_readonly(self):
        with self.assertRaises(ValueError):search_effects(self.path,phrases=[])
        with self.assertRaises(ValueError):search_cards(self.path,rarity='X')
        with self.assertRaises(ValueError):search_cards(self.path,limit=0)
        self.assertEqual(sqlite3.connect(self.path).execute('SELECT count(*) FROM inventory').fetchone()[0],0)
    def _recipe(self,*,n=40,core_ur=False):
        return [
                 {'card_id':self.ids[i],'quantity':1,'section':'MAIN','core':core_ur if i==0 else True}
                 for i in range(n)]
    def test_ur_known_and_unknown(self):
        recipe=self._recipe()
        result=assess_deck(self.path,recipe)
        self.assertEqual(result['status'],'INDETERMINATE')
        self.assertIn('UNKNOWN_OWNERSHIP:fiction:0',result['unknowns'])
        self.assertEqual(result['potentially_missing_if_unowned']['UR'],1)
        self.assertEqual(assess_deck(self.path,recipe,mode='STRICT_NO_UR')['status'],'FAIL')
        self.assertEqual(assess_deck(self.path,self._recipe(core_ur=True))['status'],'FAIL')
    def test_owned_ur_and_banlist(self):
        s=Store(self.path)
        for cid in self.ids[:40]:
            s.set_inventory('own-'+cid,[{'card_id':cid,'owned_count':1}])
        s.close()
        rules={cid:3 for cid in self.ids[:40]}
        result=assess_deck(self.path,self._recipe(),allowed_copies=rules)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['new_needed_by_rarity']['UR'],0)
        self.assertEqual(assess_deck(self.path,self._recipe(),allowed_copies={**rules,self.ids[0]:0})['status'],'FAIL')
    def test_unknown_is_not_zero(self):
        rules={cid:3 for cid in self.ids[:40]}
        result=assess_deck(self.path,self._recipe(),allowed_copies=rules, mode='OWNED_UR_ONLY')
        self.assertEqual(result['status'],'INDETERMINATE')
        self.assertEqual(result['new_needed_by_rarity']['UR'],0)
        self.assertEqual(result['potentially_missing_if_unowned']['UR'],1)
    def test_size_invalid_and_cp_budget(self):
        self.assertEqual(assess_deck(self.path,self._recipe(n=39))['status'],'FAIL')
        with self.assertRaises(ValueError):assess_deck(self.path,[{'card_id':'fiction:0','quantity':True,'section':'MAIN','core':True}])
        s=Store(self.path)
        s.set_inventory('zero',[{'card_id':cid,'owned_count':0} for cid in self.ids[:40]])
        s.close()
        rules={cid:3 for cid in self.ids[:40]}
        result=assess_deck(self.path,self._recipe(),mode='CP_BUDGET',allowed_copies=rules,cp_budget=0,cp_per_card={'N':30,'SR':30,'UR':30})
        self.assertEqual(result['status'],'FAIL')
        self.assertIn('CP_BUDGET_EXCEEDED',result['errors'])
        self.assertEqual(result['cp_estimate']['UR'],30)
        self.assertEqual(assess_deck(self.path,self._recipe(),mode='UR_BUDGET',allowed_copies=rules,max_new_ur=1)['status'],'INDETERMINATE')

if __name__=='__main__': unittest.main()
