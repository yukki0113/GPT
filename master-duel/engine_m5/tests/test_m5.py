"""All names and effect clauses in these tests are fictional fixtures."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from effect_semantics_m4 import build_private_index
from engine_m5 import (validate_seed,load_seed,build_private_m5_index,
                       search_theme,search_generic_roles,list_engine_variants,
                       get_engine,preview_engine,assess_engine_variant,
                       inspect_engine_combination,file_sha256)

NOW='2026-11-10'
URL='https://example.org/source'


def part(cid,section='MAIN',min=1,max=3,role='STARTER'):
    return dict(card_id=f'konami:{cid}',section=section,min_copies=min,
                max_copies=max,role=role)


def synthetic_seed(dbsha,m4sha):
    return dict(schema_version=1,as_of=NOW,source_db_sha256=dbsha,
                m4_index_sha256=m4sha,
                themes=[
                    dict(theme_id='FANTASY',name='架空戦士',
                         name_patterns=[dict(text='架空戦士',mode='PREFIX')],
                         quoted_targets=['架空戦士']),
                    dict(theme_id='WIND',name='架空風',
                         name_patterns=[dict(text='架空風',mode='PREFIX')],
                         quoted_targets=['架空風'])],
                generic_cards=[dict(card_id='konami:1001',role='HAND_TRAP',
                                    source_url=URL,verification='SECONDARY_SOURCE_CANDIDATE')],
                engines=[
                    dict(engine_id='FANTASY_PACKAGE',name='架空戦士セット',
                         theme_id='FANTASY',model_kind='PACKAGE',
                         verification='SECONDARY_SOURCE_CANDIDATE',source_url=URL,
                         notes='これは架空データの検証専用である。',
                         cards=[part(1001,min=2,max=3),part(1002,max=1),
                                part(1003,section='EXTRA',role='PAYOFF')],
                         choice_groups=[],constraints=[dict(code='WIND_LOCK_OPTIONAL',
                         scope='OPTIONAL_LINE',source_url=URL,
                         verification='SECONDARY_SOURCE_CANDIDATE',
                         note='任意ルートの制約を検証する。')]),
                    dict(engine_id='WIND_CHOICE',name='架空風の選択セット',
                         theme_id='WIND',model_kind='PACKAGE',
                         verification='SECONDARY_SOURCE_CANDIDATE',source_url=URL,
                         notes='代替パーツを持つパッケージの合成テスト。',
                         cards=[part(1002,min=1)],
                         choice_groups=[dict(group_id='ONE_TECH',min_choices=1,
                                             options=[part(1004),part(1005)])],
                         constraints=[]),
                    dict(engine_id='SOLO_CHOICE',name='架空の単体札',
                         theme_id='FANTASY',model_kind='SINGLETON',
                         verification='SECONDARY_SOURCE_CANDIDATE',source_url=URL,
                         notes='一枚だけ選べばよい単体札モデル。',cards=[],
                         choice_groups=[dict(group_id='ONE_FLEX',min_choices=1,
                                             options=[part(1004),part(1005)])],constraints=[])] )


class M5Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.source=root/'fixture.sqlite'
        self.m4=root/'m4.sqlite'
        self.seedpath=root/'m5-seed.json'
        self.index=root/'m5.sqlite'
        con=sqlite3.connect(self.source)
        con.executescript('''
            CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY);
            INSERT INTO schema_migrations VALUES(1);
            CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);
            CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT,attribute TEXT,
                                         race TEXT,level INTEGER,rank INTEGER,link INTEGER);
            CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT);
            CREATE TABLE card_texts(card_id TEXT,language TEXT,version TEXT,body TEXT,
                                    source TEXT,acquired_at TEXT,PRIMARY KEY(card_id,language,version));''')
        texts=[
            ('架空戦士ア','MONSTER','LIGHT','Fiend','UR','相手の効果を無効にする。'),
            ('架空戦士イ','MONSTER','LIGHT','Fiend','R','デッキから「架空戦士」カード１枚を手札に加える。'),
            ('架空EX','MONSTER','LIGHT','Fiend','SR','モンスターを特殊召喚する。'),
            ('架空風A','MONSTER','WIND','Machine','N','自分は１枚ドローする。'),
            ('架空風B','MONSTER','WIND','Machine','N','このカードを破壊する。'),
            ('架空外部サポート','SPELL',None,None,'N','デッキから「架空戦士」カード１枚を手札に加える。'),
        ]
        for id,(name,kind,attr,race,rarity,text) in enumerate(texts,start=1001):
            key=f'konami:{id}'
            con.execute('INSERT INTO cards VALUES(?,?)',(key,name))
            con.execute('INSERT INTO card_attributes VALUES(?,?,?,?,?,?,?)',
                        (key,kind,attr,race,3 if kind=='MONSTER' else None,None,None))
            con.execute('INSERT INTO md_catalog VALUES(?,?)',(key,rarity))
            con.execute('INSERT INTO card_texts VALUES(?,?,?,?,?,?)',
                        (key,'ja','v1',text,'SYNTHETIC',NOW))
        con.commit();con.close()
        self.source_sha=file_sha256(self.source)
        build_private_index(self.source,self.m4,expected_source_sha256=self.source_sha)
        self.m4_sha=file_sha256(self.m4)
        self.seed=synthetic_seed(self.source_sha,self.m4_sha)
        self.save_seed()

    def tearDown(self):self.temp.cleanup()

    def save_seed(self):
        self.seedpath.write_text(json.dumps(self.seed,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
        self.seedsha=file_sha256(self.seedpath)

    def build(self,**kwargs):
        return build_private_m5_index(
            self.source,self.m4,self.seedpath,self.index,
            expected_source_sha256=self.source_sha,
            expected_m4_sha256=self.m4_sha,
            expected_seed_sha256=self.seedsha,**kwargs)

    def test_valid_seed_and_defensive_copy(self):
        out=validate_seed(self.seed)
        out['themes'][0]['name']='changed'
        self.assertEqual(self.seed['themes'][0]['name'],'架空戦士')

    def test_different_input_hash_rejected(self):
        with self.assertRaisesRegex(ValueError,'seed SHA-256 mismatch'):
            load_seed(self.seedpath,expected_sha256='f'*64)
        with self.assertRaisesRegex(ValueError,'seed source hash mismatch'):
            build_private_m5_index(self.source,self.m4,self.seedpath,self.index,
                 expected_source_sha256='f'*64,
                 expected_m4_sha256=self.m4_sha,expected_seed_sha256=self.seedsha)
        with self.assertRaisesRegex(ValueError,'seed source hash mismatch'):
            build_private_m5_index(self.source,self.m4,self.seedpath,self.index,
                 expected_source_sha256=self.source_sha,
                 expected_m4_sha256='f'*64,expected_seed_sha256=self.seedsha)

    def test_theme_not_inferred_from_quoted_target(self):
        result=self.build()
        self.assertEqual(result['counts']['cards'],6)
        hits=search_theme(self.index,'FANTASY',limit=100)['results']
        external=[h for h in hits if h['card_id']=='konami:1006']
        self.assertEqual(len(external),1)
        self.assertEqual(external[0]['relation'],'QUOTED_TARGET_CANDIDATE')
        self.assertEqual(external[0]['verification'],'UNVERIFIED_INTERPRETATION')
        self.assertFalse(any(h['relation']=='NAME_MATCH_CANDIDATE' for h in external))

    def test_theme_name_match_independent_of_effect(self):
        self.build()
        hits=search_theme(self.index,'FANTASY',relations=['NAME_MATCH_CANDIDATE'])['results']
        self.assertEqual({h['card_id'] for h in hits},{'konami:1001','konami:1002'})
        self.assertEqual(len(search_theme(self.index,'WIND')['results']),2)

    def test_evidence_spans_from_m4(self):
        self.build()
        hits=search_theme(self.index,'FANTASY',relations=['QUOTED_TARGET_CANDIDATE'])['results']
        with sqlite3.connect(self.source) as db:
            for hit in hits:
                body=db.execute('SELECT body FROM card_texts WHERE card_id=?',(hit['card_id'],)).fetchone()[0]
                self.assertEqual(hit['evidence'],body[hit['start']:hit['end']])
                self.assertEqual(hit['source_sha256'],sha256(body.encode()).hexdigest())

    def test_generic_independent_of_theme_membership(self):
        self.build()
        roles=search_generic_roles(self.index,role='HAND_TRAP')
        self.assertEqual([x['card_id'] for x in roles],['konami:1001'])
        self.assertEqual(roles[0]['verification'],'SECONDARY_SOURCE_CANDIDATE')
        self.assertEqual(roles[0]['rarity'],'UR')

    def test_variants_have_separate_typed_parts(self):
        self.build()
        v=list_engine_variants(self.index)
        self.assertEqual(len(v['results']),3)
        e=get_engine(self.index,'WIND_CHOICE')
        self.assertEqual(len(e['choice_groups']),1)
        self.assertEqual(len(e['parts']),3)
        self.assertEqual(e['engine']['verification'],'SECONDARY_SOURCE_CANDIDATE')

    def test_fixed_minimum_main_extra_ur(self):
        self.build()
        p=preview_engine(self.index,'FANTASY_PACKAGE')
        self.assertEqual(p['minimum'],{'MAIN':3,'EXTRA':1,'ur_min_spec_copies':2})
        self.assertEqual(p['constraints'][0]['scope'],'OPTIONAL_LINE')

    def test_singleton_choice_is_one_main_and_no_ur(self):
        self.build()
        p=preview_engine(self.index,'SOLO_CHOICE')
        self.assertEqual(p['minimum'],{'MAIN':1,'EXTRA':0,'ur_min_spec_copies':0})

    def test_package_incomplete_then_spec_complete(self):
        self.build()
        one=[dict(card_id='konami:1001',section='MAIN',quantity=2)]
        self.assertEqual(assess_engine_variant(self.index,'FANTASY_PACKAGE',one)['status'],'INCOMPLETE_SPEC')
        complete=one+[dict(card_id='konami:1002',section='MAIN',quantity=1),
                      dict(card_id='konami:1003',section='EXTRA',quantity=1)]
        a=assess_engine_variant(self.index,'FANTASY_PACKAGE',complete)
        self.assertEqual(a['status'],'COMPLETE_SPEC_VARIANT')
        self.assertFalse(a['playable_or_legal_certified'])
        self.assertTrue(a['requires_m3_regulation_check'])

    def test_choice_option_and_duplicate_max_guard(self):
        self.build()
        a=assess_engine_variant(self.index,'SOLO_CHOICE',[dict(card_id='konami:1004',section='MAIN',quantity=1)])
        self.assertEqual(a['status'],'COMPLETE_SPEC_VARIANT')
        with self.assertRaisesRegex(ValueError,'duplicate exceeds'):
            assess_engine_variant(self.index,'SOLO_CHOICE',[dict(card_id='konami:1004',section='MAIN',quantity=3)]*2)

    def test_unfilled_choice_is_incomplete(self):
        self.build()
        a=assess_engine_variant(self.index,'SOLO_CHOICE',[])
        self.assertEqual(a['status'],'INCOMPLETE_SPEC')
        self.assertEqual(a['missing'][0]['group_id'],'ONE_FLEX')

    def test_over_max_is_flagged_not_legal(self):
        self.build()
        a=assess_engine_variant(self.index,'FANTASY_PACKAGE',[
          dict(card_id='konami:1001',section='MAIN',quantity=2),
          dict(card_id='konami:1002',section='MAIN',quantity=2),
          dict(card_id='konami:1003',section='EXTRA',quantity=1)])
        self.assertEqual(a['status'],'OVER_SPEC_MAX')
        self.assertEqual(a['over_max'][0]['card_id'],'konami:1002')
        self.assertFalse(a['playable_or_legal_certified'])

    def test_extra_slot_budget_conflict(self):
        self.build()
        r=inspect_engine_combination(self.index,['FANTASY_PACKAGE','WIND_CHOICE'],ex_budget=0)
        self.assertEqual(r['compatibility'],'EX_SLOT_CONFLICT')
        self.assertTrue(r['known_slot_conflict'])
        self.assertIn('EX_SLOTS_EXCEEDED_BY_CANDIDATE_MINIMA',r['warnings'])

    def test_same_card_shared_not_double_counted(self):
        self.build()
        r=inspect_engine_combination(self.index,['FANTASY_PACKAGE','WIND_CHOICE'])
        self.assertEqual(r['candidate_min_main_slots'],4)
        self.assertEqual(r['candidate_min_extra_slots'],1)
        self.assertIn('SHARED_CARDS_SIMULTANEOUS_USAGE_UNVERIFIED',r['warnings'])
        self.assertEqual(len(r['shared_parts']),1)
        self.assertFalse(r['source_verified_synergy'])

    def test_choice_group_overlap_does_not_raise_false_ex_conflict(self):
        # Both variants can choose one already-required EX card. The minimum
        # EX slots is one, not one per engine choice group.
        self.seed['engines'][1]['choice_groups'][0]['options']=[part(1003,section='EXTRA',role='PAYOFF')]
        self.seed['engines'][2]['choice_groups'][0]['options']=[part(1003,section='EXTRA',role='PAYOFF')]
        self.save_seed();self.build()
        result=inspect_engine_combination(self.index,
             ['FANTASY_PACKAGE','WIND_CHOICE','SOLO_CHOICE'],ex_budget=1)
        self.assertEqual(result['candidate_min_extra_slots'],1)
        self.assertFalse(result['known_slot_conflict'])
        self.assertEqual(result['compatibility'],'REVIEW_REQUIRED')

    def test_constraints_never_silently_marked_compatible(self):
        self.build()
        r=inspect_engine_combination(self.index,['FANTASY_PACKAGE','SOLO_CHOICE'])
        self.assertEqual(r['compatibility'],'REVIEW_REQUIRED')
        self.assertEqual(r['constraints'][0]['scope'],'OPTIONAL_LINE')

    def test_source_files_unchanged(self):
        source,m4=self.source_sha,self.m4_sha
        self.build()
        self.assertEqual(file_sha256(self.source),source)
        self.assertEqual(file_sha256(self.m4),m4)
        self.assertEqual(file_sha256(self.index),file_sha256(self.index))
        with sqlite3.connect(self.index) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_no_overwrite_without_replace(self):
        self.build()
        with self.assertRaisesRegex(ValueError,'explicit replace'):self.build()
        self.assertEqual(self.build(replace=True)['counts']['engines'],3)

    def test_missing_generic_card_rejected_fail_closed(self):
        self.seed['generic_cards'][0]['card_id']='konami:9999'
        self.save_seed()
        with self.assertRaisesRegex(ValueError,'missing generic'):
            self.build()
        self.assertFalse(self.index.exists())

    def test_wrong_extra_card_type_rejected(self):
        self.seed['engines'][0]['cards'][2]['card_id']='konami:1006'  # SPELL
        self.save_seed()
        with self.assertRaisesRegex(ValueError,'non-monster'):
            self.build()

    def test_invalid_recipe_rejected(self):
        self.build()
        for recipe in ('not a list',[dict(card_id='konami:1001',section='MAIN',quantity=0)],
                       [dict(card_id='konami:1001',section='BENCH',quantity=1)]):
            with self.subTest(recipe=recipe),self.assertRaises(ValueError):
                assess_engine_variant(self.index,'SOLO_CHOICE',recipe)

    def test_stale_index_metadata_rejected(self):
        self.build()
        with self.assertRaisesRegex(ValueError,'M5 stale'):
            search_theme(self.index,'FANTASY',expected_m4_sha256='f'*64)
        with self.assertRaisesRegex(ValueError,'M5 stale'):
            list_engine_variants(self.index,expected_seed_sha256='f'*64)

    def test_invalid_structured_filters_rejected(self):
        self.build()
        for args in [{'relations':['DROP TABLE']},{'limit':0}]:
            with self.assertRaises(ValueError):search_theme(self.index,'FANTASY',**args)
        with self.assertRaises(ValueError):search_generic_roles(self.index,role='negative')


class SeedValidationTests(unittest.TestCase):
    def setUp(self):
        self.seed=synthetic_seed('a'*64,'b'*64)
    def test_duplicate_theme_refused(self):
        self.seed['themes'].append(deepcopy(self.seed['themes'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate theme'):validate_seed(self.seed)
    def test_unknown_engine_theme_refused(self):
        self.seed['engines'][0]['theme_id']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'unknown engine theme'):validate_seed(self.seed)
    def test_no_false_person_verification(self):
        self.seed['engines'][0]['verification']='GAME_VERIFIED'
        with self.assertRaisesRegex(ValueError,'unsupported engine verification'):validate_seed(self.seed)
    def test_no_http_evidence(self):
        self.seed['engines'][0]['source_url']='http://example.com'
        with self.assertRaisesRegex(ValueError,'HTTPS'):validate_seed(self.seed)
    def test_duplicate_engine_card_refused(self):
        e=self.seed['engines'][0];e['cards'].append(deepcopy(e['cards'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate engine card'):validate_seed(self.seed)
    def test_bad_choice_min_refused(self):
        self.seed['engines'][2]['choice_groups'][0]['min_choices']=3
        with self.assertRaisesRegex(ValueError,'invalid min_choices'):validate_seed(self.seed)
    def test_one_card_not_claimed_legal(self):
        self.seed['engines'][2]['model_kind']='PACKAGE'  # arbitrary legal schema but no magic certification
        self.assertEqual(validate_seed(self.seed)['engines'][2]['verification'],
                         'SECONDARY_SOURCE_CANDIDATE')

if __name__=='__main__':unittest.main()
