import copy
import unittest
from hashlib import sha256
from card_master_import.incremental.normalize import build_batch

STAMP = '2026-11-27T10:00:00+09:00'
S = {'url':'https://example.org/synthetic','observed_at':STAMP}
O = dict(S, role='OCG_CARD_JSON')
BASE = (12,'0'*64)

class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.obs = {'cid':999999,'card_id':'konami:999999','name_ja':'架空Ａ','name_en':'Wrong historical alias',
            'rarity':'R','effective_on':'2026-11-24','disposition':'U2_CANDIDATE','channels':['PACK_REPORTED'],
            'sources':[dict(S,role='MD_RARITY_DELTA'),dict(S,role='PACK_LIST')]}
        self.rec = {'konami_id':999999,'name':{'ja':'<ruby>架<rt>か</rt></ruby>空A','en':'Synthetic'},
            'text':{'ja':'①：架空の効果。'},'sets':{'ja':[{}]},'card_type':'Monster',
            'monster_type_line':'Dragon / Effect','attribute':'DARK','level':4,'atk':0,'def':'?','master_duel_rarity':'UR'}
        self.event = {'schema':'md-implementation-event-discovery-v1','batch_id':'synthetic','effective_on':'2026-11-24',
            'base_generation':12,'base_sqlite_sha256':BASE[1],'event_coverage':'PARTIAL','pack_coverage':'UNKNOWN','cards':[self.obs]}
    def run_batch(self, records=None, **kw):
        return build_batch(self.event,[self.rec] if records is None else records,O,
            expected_base=kw.pop('expected_base',BASE),input_sha='1'*64,observed_at=STAMP,**kw)
    def row(self):
        batch=self.run_batch(); self.assertEqual(batch['unresolved'],[]);return batch['cards'][0]
    def pending(self,reason):
        batch=self.run_batch(); self.assertEqual(batch['cards'],[]);self.assertEqual(batch['unresolved'][0]['reason'],reason)
    def test_main(self):
        row=self.row();self.assertEqual((row['name_ja'],row['name_en'],row['rarity'],row['def'],row['atk']),('架空A','Synthetic','R',None,0));self.assertEqual(row['craftable'],'UNKNOWN');self.assertEqual(row['sources']['ja_text']['verification'],'OCG_SHARED')
    def test_link(self):
        self.rec.update(monster_type_line='Dragon / Link / Effect',link_arrows=['⬅','➡']);self.rec.pop('level');self.rec.pop('def');r=self.row();self.assertEqual((r['link'],r['link_markers']),(2,['Middle-Left','Middle-Right']));self.assertIsNone(r['def'])
    def test_synchro(self):
        self.rec['monster_type_line']='Dragon / Synchro / Effect';self.rec['text']['ja']='チューナー＋チューナー以外のモンスター１体以上\n①：架空。';r=self.row();m=r['extra_material_requirement'];self.assertEqual(m['grammar'],'GENERIC_SYNCHRO_TUNER');self.assertEqual(m['source_text_sha256'],sha256(r['ja_text'].encode()).hexdigest())
    def test_fusion_pendulum(self):
        self.rec.update(monster_type_line='Dragon / Fusion / Pendulum / Effect',pendulum_scale=3,pendulum_effect={'ja':'架空のＰ効果。'});r=self.row();self.assertEqual(r['pendulum_scale'],3);self.assertEqual(r['extra_material_requirement']['summon_method'],'FUSION');self.assertIn('PENDULUM',r['monster_types'])
    def test_xyz(self):
        self.rec.update(monster_type_line='Dragon / Xyz / Effect',rank=4);self.rec.pop('level');r=self.row();self.assertEqual(r['rank'],4);self.assertIsNone(r['level'])
    def test_spell_trap(self):
        for k in ('monster_type_line','attribute','level','atk','def'):self.rec.pop(k)
        for kind,prop in [('Spell','Quick-Play'),('Trap','Counter')]:
            self.rec.update(card_type=kind,property=prop);r=self.row();self.assertEqual(r['spell_trap_property'],prop);self.assertEqual(r['monster_types'],[])
    def test_missing_text(self):
        self.rec['text']['ja']=None;self.pending('MISSING_JAPANESE_EFFECT')
    def test_missing_pendulum(self):
        self.rec.update(monster_type_line='Dragon / Pendulum / Effect',pendulum_scale=1);self.pending('MISSING_JAPANESE_PENDULUM_EFFECT')
    def test_missing_event(self):
        self.obs['disposition']='PENDING_EVENT_EVIDENCE';self.pending('PENDING_EVENT_EVIDENCE')
    def test_ocg_only_excluded(self):
        self.event['cards']=[];self.assertEqual(self.run_batch()['cards'],[])
    def test_ambiguous(self):
        b=self.run_batch([self.rec,copy.deepcopy(self.rec)]);self.assertEqual(b['unresolved'][0]['reason'],'MISSING_OR_AMBIGUOUS_CID')
    def test_name_conflict(self):
        self.obs['name_ja']='別カード';self.pending('JAPANESE_NAME_CONFLICT')
    def test_missing_id(self):
        self.obs['card_id']='temp:1';self.pending('MISSING_OR_INVALID_CID')
    def test_unknown_rarity(self):
        self.obs['rarity']=None;self.assertIsNone(self.row()['rarity'])
    def test_missing_rarity_source(self):
        self.obs['sources']=self.obs['sources'][1:];self.pending('INVALID_OR_UNSOURCED_MD_RARITY')
    def test_missing_basic(self):
        self.rec.pop('atk');self.pending('MISSING_ATK')
    def test_conflicting_base(self):
        with self.assertRaisesRegex(ValueError,'BASE_MISMATCH'):self.run_batch(expected_base=(13,'0'*64))
    def test_partial(self):
        bad=dict(self.obs,cid=123,card_id='konami:123');self.event['cards'].append(bad);b=self.run_batch();self.assertEqual((len(b['cards']),len(b['unresolved'])),(1,1))
    def test_duplicate_event(self):
        self.event['cards'].append(dict(self.obs));b=self.run_batch();self.assertEqual(len(b['cards']),0);self.assertEqual(len(b['unresolved']),2)
    def test_event_resolution(self):
        self.obs['disposition']='PENDING_EVENT_EVIDENCE';self.obs['channels']=[];b=self.run_batch(event_resolutions={999999:{'card_id':'konami:999999','channels':['OTHER_RELEASE_REPORTED'],'effective_on':'2026-11-24','sources':[dict(S,role='MD_EVENT') ]}});self.assertEqual(len(b['cards']),1);self.assertEqual(b['cards'][0]['channels'],['OTHER_RELEASE_REPORTED'])
    def test_repeat(self):
        self.assertEqual(self.run_batch(),self.run_batch())

if __name__=='__main__':unittest.main()
