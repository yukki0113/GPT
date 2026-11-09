import hashlib, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from zip_store.archive import pack, unpack, NAME
from voice_staging import preview
from card_master_import.importer import dry_run, convert, read_inputs, display_name

META={'md_filename':'md.json','cards_filename':'cards.json','md_sha256':'a'*64,'cards_sha256':'b'*64}
def pair(i=1):
    return ({'en_name':f'Fiction {i}','card_type':'Monster','types':['Normal'],'rarity':'SR'}, {'name':{'en':f'Fiction {i}','ja':f'<ruby>架空<rt>かくう</rt></ruby>{i}'},'konami_id':i,'card_type':'Monster','types':['Normal'],'master_duel_rarity':'SR'})
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.path=self.root/'db'; s=Store.create(self.path); s.close(); self.base,_=pack(self.path)
    def tearDown(self): self.tmp.cleanup()
    def test_roundtrip_and_p3(self):
        md,card=pair(); report,rows=dry_run([md],[card],META); self.assertTrue(report['ok']); self.assertEqual(report['craftable_unknown'],1)
        out,meta=convert(self.base,rows,report,acquired_at='2026-11-10'); self.assertEqual(meta['schema_version'],1)
        path=self.root/'restored'; unpack(out,path); s=Store(path)
        try: self.assertEqual(s.get_card('konami:1')['name'],'架空1'); self.assertEqual(s.get_md_catalog('konami:1')['rarity'],'SR'); self.assertEqual(s.get_md_catalog('konami:1')['craftable'],'UNKNOWN'); self.assertTrue(s.integrity_check()['ok'])
        finally: s.close()
        from zip_store.archive import digest
        target={'head_name':'P2B_TEST_CURRENT_HEAD.json','scope':'SYNTHETIC_TEST','snapshot_id':'s','zip_sha256':digest(out)}
        b={'batch_id':'one','scope':'SYNTHETIC_TEST','entries':[{'raw_name':'架空1','owned_count':2}]}
        self.assertTrue(preview(b,out,target)['can_apply'])
        again,_=convert(out,rows,report,acquired_at='2026-11-10'); p2=self.root/'restored2'; unpack(again,p2); s=Store(p2); self.assertEqual(s.db.execute('select count(*) from cards').fetchone()[0],1); s.close()
    def test_13948_synthetic(self):
        pairs=[pair(i) for i in range(1,13949)]; audit,rows=dry_run([p[0] for p in pairs],[p[1] for p in pairs],META)
        self.assertTrue(audit['ok']); self.assertEqual(len(rows),13948)
        out,_=convert(self.base,rows,audit,acquired_at='2026-11-10'); path=self.root/'large'; unpack(out,path); s=Store(path); self.assertEqual(s.db.execute('select count(*) from cards').fetchone()[0],13948); s.close()
    def test_missing_and_duplicate(self):
        m,c=pair(); missing={**c,'name':{'en':'Fiction 1'}}; a,_=dry_run([m],[missing],META); self.assertEqual(a['missing_ja'],1); self.assertFalse(a['ok'])
        m2,c2=pair(2); c2['konami_id']=1; a,_=dry_run([m,m2],[c,c2],META); self.assertEqual(a['duplicate_konami_id'],1)
        with self.assertRaises(ValueError): convert(self.base,[],a,acquired_at='2026-11-10')
    def test_exception_names_and_normalization(self):
        m,c=pair(); m['en_name']='Fiction ＜1＞'; c['name']['en']='Fiction <1>'; a,_=dry_run([m],[c],META); self.assertEqual(a['normalized'],1)
        for name in ('Dark Magician','Polymerization'):
            m,c=pair(); m['en_name']=name; c['name']['en']=name; duplicate={**c,'password':'another'}
            a,r=dry_run([m],[c,duplicate],META); self.assertTrue(a['ok']); self.assertEqual(a['exceptions'],1); self.assertEqual(len(r),1)
        m,c=pair(); m['en_name']='Black Luster Soldier'; c['name']['en']=m['en_name']; m['types']=['Normal']; c['types']=['Normal']; ritual={**c,'konami_id':2,'types':['Ritual']}; a,r=dry_run([m],[c,ritual],META); self.assertTrue(a['ok']); self.assertEqual(r[0]['konami_id'],1)
    def test_inconsistent_and_no(self):
        m,c=pair(); m['craftable']='No'; a,r=dry_run([m],[c],META); self.assertEqual(r[0]['craftable'],'NO')
        c['master_duel_rarity']='UR'; a,_=dry_run([m],[c],META); self.assertFalse(a['ok'])
        self.assertEqual(display_name('<ruby>空<rp>(</rp><rt>そら</rt><rp>)</rp></ruby>竜'),'空竜')
    def test_real_json_field_shapes(self):
        # Actual MD JSON: monsters have types but no card_type, and
        # numeric fields are strings. cards.json stores integer stats.
        md={'en_name':'Fiction Dragon','types':'Dragon / Effect',
            'rarity':'SR','attribute':'LIGHT','level':'8','atk':'1000','def':'2000'}
        card={'name':{'en':'Fiction Dragon','ja':'架空竜'},
              'konami_id':123,'card_type':'Monster','monster_type_line':'Dragon / Effect',
              'attribute':'LIGHT','level':8,'atk':1000,'def':2000,'master_duel_rarity':'SR'}
        audit, rows=dry_run([md],[card],META)
        self.assertTrue(audit['ok'],audit)
        self.assertEqual(rows[0]['kind'],'MONSTER')
        self.assertEqual(rows[0]['race'],'Dragon')
        self.assertEqual((rows[0]['level'],rows[0]['atk']), (8,1000))
        out,_=convert(self.base,rows,audit,acquired_at='2026-11-10')
        path=self.root/'actual-shape'; unpack(out,path)
        store=Store(path)
        try:
            attrs=store.get_attributes('konami:123')
            self.assertEqual(attrs['race'],'Dragon')
            self.assertEqual(attrs['atk'],1000)
        finally: store.close()

    def test_unknown_atk_def_does_not_become_zero(self):
        md={'en_name':'Fiction Unknown','types':'Spellcaster / Effect',
            'rarity':'UR','level':'3','atk':'?','def':'?'}
        card={'name':{'en':'Fiction Unknown','ja':'架空の不明値'},
              'konami_id':789,'card_type':'Monster','monster_type_line':'Spellcaster / Effect',
              'level':3,'atk':'?','def':'?','master_duel_rarity':'UR'}
        audit, rows=dry_run([md],[card],META)
        self.assertTrue(audit['ok'],audit)
        self.assertEqual(rows[0]['kind'],'MONSTER')
        self.assertIsNone(rows[0]['atk'])
        self.assertIsNone(rows[0]['def'])
        md['atk']='not-a-number'
        bad,_=dry_run([md],[card],META)
        self.assertFalse(bad['ok'])

    def test_input_hash_and_bad_json(self):
        p=self.root/'m'; q=self.root/'c'; p.write_text('{}'); q.write_text('[]'); h=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
        with self.assertRaises(ValueError): read_inputs(p,q,expected_md='0'*64,expected_cards=h(q))
        with self.assertRaises(ValueError): read_inputs(p,q,expected_md=h(p),expected_cards=h(q))
        p.write_text('{');
        with self.assertRaises(ValueError): read_inputs(p,q,expected_md=h(p),expected_cards=h(q))
    def test_conflict_keeps_base(self):
        m,c=pair(); audit,rows=dry_run([m],[c],META); rows.append(dict(rows[0],card_id='other')); altered={**audit,'md_count':2}
        with self.assertRaises(Exception): convert(self.base,rows,altered,acquired_at='2026-11-10')
        path=self.root/'check'; unpack(self.base,path); s=Store(path); self.assertEqual(s.db.execute('select count(*) from cards').fetchone()[0],0); s.close()

if __name__=='__main__': unittest.main()
