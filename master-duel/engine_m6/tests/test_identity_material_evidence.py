"""Synthetic-only identity claims: no real card text or private inventory."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine_m6.identity_material_evidence import (
    observe_identity_header, diagnose_identity_claims,
)
from engine_m6.structured_materials import screen_structured_extra_materials


def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()


class IdentityClaimTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'fiction.sqlite'
        c=sqlite3.connect(self.path)
        c.executescript("""
        CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT,level INTEGER,link INTEGER);
        CREATE TABLE card_texts(card_id TEXT,language TEXT,body TEXT);
        CREATE TABLE card_extra_material_requirements(card_id TEXT PRIMARY KEY,summon_method TEXT,
          material_header TEXT,material_header_sha256 TEXT,pre_effect_restrictions TEXT,
          source_text_sha256 TEXT,grammar TEXT,min_materials INTEGER,level_required INTEGER,
          qualifier TEXT,material_labels_json TEXT,material_verification TEXT,
          simultaneous_materials_verified INTEGER,summon_route_verified INTEGER,source TEXT);
        """)
        for cid,level,link in [('konami:11',4,None),('konami:12',3,None),('konami:13',4,2)]:
            c.execute('INSERT INTO card_attributes VALUES (?,?,?,?)',(cid,'MONSTER',level,link))
        for cid,method,header,link in [
            ('konami:901','XYZ','レベル4「架空テーマ」モンスター×2',None),
            ('konami:902','LINK','「架空テーマ」モンスター2体',2),
            ('konami:903','LINK','トークン以外のモンスター2体',2)]:
            body=header+'\n①：架空の効果。'
            c.execute('INSERT INTO card_attributes VALUES (?,?,?,?)',(cid,'MONSTER',None,link))
            c.execute('INSERT INTO card_texts VALUES (?,?,?)',(cid,'ja',body))
            c.execute('INSERT INTO card_extra_material_requirements VALUES ('+','.join('?'*15)+')',
              (cid,method,header,digest(header),'',digest(body),'UNPARSED',None,None,None,'[]',
               'SOURCE_TEXT_ONLY',0,0,'FICTION'))
        c.commit()
        c.close()
        self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def bundle(self,extra,header,ids,*,claim=True,review='REVIEWED',
               predicate='ARCHETYPE_MEMBERSHIP',label='架空テーマ'):
        return {'master_sqlite_sha256':self.sha,'extra_card_id':extra,
          'material_header_sha256':digest(header),'occurrences':[
          {'card_id':i,'predicate':predicate,'label':label,'claim':claim,
           'source_ref':'FICTION:ATTACHMENT','source_document_sha256':digest('synthetic-proof'),
           'review_status':review} for i in ids]}

    def check(self,target,method,header,ids,evidence,ratings=(),link=None):
        c=sqlite3.connect(self.path)
        c.row_factory=sqlite3.Row
        try:
            return diagnose_identity_claims(
                c,method=method,header=header,extra_card_id=target,
                material_card_ids=ids,expected_sqlite_sha256=self.sha,evidence=evidence,
                link_material_ratings=ratings,target_link=link)
        finally:
            c.close()

    def route(self,extra,method,ids,ratings=()):
        return {'extra_card_id':extra,'summon_method':method,'material_card_ids':ids,
          'evidence_ids':['FICTION:SOURCE'],'simultaneous_state_evidence_ids':['FICTION:STATE'],
          'summon_method_evidence_ids':['FICTION:METHOD'],'restriction_review':'REVIEWED',
          'material_labels':[],'link_material_ratings':list(ratings)}

    def integration(self,target,method,ids,bundle,ratings=()):
        return screen_structured_extra_materials(
            self.path,expected_sqlite_sha256=self.sha,extra_card_ids=[target],
            proposed_routes=[self.route(target,method,ids,ratings)],
            identity_evidence=[bundle])['results'][0]

    def test_theme_requires_per_occurrence_claims(self):
        h='レベル4「架空テーマ」モンスター×2'
        ids=['konami:11','konami:11']
        b=self.bundle('konami:901',h,ids)
        self.assertEqual(self.check('konami:901','XYZ',h,ids,b)[0],'CLAIM_ALIGNED')
        b['occurrences'][1]['claim']=False
        self.assertEqual(self.check('konami:901','XYZ',h,ids,b)[0],'MISMATCH')
        b['occurrences'][1]['claim']=True
        b['occurrences'][1]['review_status']='NOT_REVIEWED'
        self.assertEqual(self.check('konami:901','XYZ',h,ids,b)[0],'UNKNOWN')
        b['occurrences'][1]['review_status']='REVIEWED'
        b['material_header_sha256']='a'*64
        self.assertEqual(self.check('konami:901','XYZ',h,ids,b)[0],'UNKNOWN')

    def test_no_card_name_inference_and_bad_level(self):
        h='レベル4「架空テーマ」モンスター×2'
        ids=['konami:11','konami:12']
        b=self.bundle('konami:901',h,ids)
        self.assertEqual(self.check('konami:901','XYZ',h,ids,b)[0],'MISMATCH')
        self.assertEqual(self.check('konami:901','XYZ',h,ids,None)[0],'UNKNOWN')

    def test_non_token_is_occurrence_evidence_not_normal_type(self):
        h='トークン以外のモンスター2体'
        ids=['konami:11','konami:11']
        b=self.bundle('konami:903',h,ids,predicate='NOT_TOKEN',label=None,claim=False)
        out=self.integration('konami:903','LINK',ids,b,[1,1])
        self.assertEqual(out['screen'],'REQUIRES_REVIEW')
        self.assertIn('IDENTITY_CLAIM_ALIGNED',out['review_reason'])
        b['occurrences'][1]['claim']=True
        self.assertIn('IDENTITY_MISMATCH',self.integration('konami:903','LINK',ids,b,[1,1])['review_reason'])
        b['occurrences'][1]['claim']=None
        self.assertIn('IDENTITY_UNKNOWN',self.integration('konami:903','LINK',ids,b,[1,1])['review_reason'])

    def test_archetype_link_still_requires_review(self):
        h='「架空テーマ」モンスター2体'
        ids=['konami:11','konami:11']
        b=self.bundle('konami:902',h,ids)
        out=self.integration('konami:902','LINK',ids,b,[1,1])
        self.assertEqual(out['screen'],'REQUIRES_REVIEW')
        self.assertIn('IDENTITY_CLAIM_ALIGNED',out['review_reason'])
        for field in ('gameplay_compatibility_verified',
                      'materials_simultaneously_available_verified',
                      'official_md_legality_verified'):
            self.assertFalse(out[field])
        old=screen_structured_extra_materials(
            self.path,expected_sqlite_sha256=self.sha,
            extra_card_ids=['konami:902'],
            proposed_routes=[self.route('konami:902','LINK',ids,[1,1])])['results'][0]
        self.assertEqual(old['screen'],'REQUIRES_REVIEW')
        self.assertNotIn('IDENTITY_CLAIM_ALIGNED',old['review_reason'])

    def test_unrecognized_compounds_and_labels_never_pass(self):
        for text in ('トークン以外の闇属性モンスター2体',
                     '「架空」モンスターを含む2体',
                     '「架空」または「別」モンスター2体'):
            self.assertIsNone(observe_identity_header('LINK',text))
        h='「架空テーマ」モンスター2体'
        b=self.bundle('konami:902',h,['konami:11','konami:11'])
        b['occurrences'][1]['label']='別テーマ'
        self.assertEqual(self.check('konami:902','LINK',h,['konami:11']*2,b,[1,1],2)[0],
                         'UNKNOWN')

    def test_dangling_or_duplicate_evidence_rejected(self):
        h='「架空テーマ」モンスター2体'
        b=self.bundle('konami:902',h,['konami:11']*2)
        with self.assertRaisesRegex(ValueError,'IDENTITY_EVIDENCE_TARGET_INVALID'):
            screen_structured_extra_materials(
                self.path,expected_sqlite_sha256=self.sha,
                extra_card_ids=['konami:901'],
                proposed_routes=[self.route('konami:901','XYZ',['konami:11']*2)],
                identity_evidence=[b])
        with self.assertRaisesRegex(ValueError,'IDENTITY_EVIDENCE_TARGET_INVALID'):
            screen_structured_extra_materials(
                self.path,expected_sqlite_sha256=self.sha,
                extra_card_ids=['konami:902'],
                proposed_routes=[self.route('konami:902','LINK',['konami:11']*2,[1,1])],
                identity_evidence=[b,b])


if __name__=='__main__':
    unittest.main()
