"""Fictional-only identity ledger contract and M6-5B fail-closed regression."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from engine_m6.identity_source_ledger import compile_identity_evidence,LedgerContractError
from engine_m6.structured_materials import screen_structured_extra_materials

def sha(v):return hashlib.sha256(v).hexdigest()

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.db=Path(self.t.name)/'fiction.sqlite'
        c=sqlite3.connect(self.db)
        c.executescript('''
          CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT,level INTEGER,link INTEGER);
          CREATE TABLE card_texts(card_id TEXT,language TEXT,body TEXT);
          CREATE TABLE card_extra_material_requirements(card_id TEXT PRIMARY KEY,summon_method TEXT,
            material_header TEXT,material_header_sha256 TEXT,pre_effect_restrictions TEXT,
            source_text_sha256 TEXT,grammar TEXT,min_materials INTEGER,level_required INTEGER,
            qualifier TEXT,material_labels_json TEXT,material_verification TEXT,
            simultaneous_materials_verified INTEGER,summon_route_verified INTEGER,source TEXT);
        ''')
        for cid in ('konami:11','konami:12'):
            c.execute('INSERT INTO card_attributes VALUES (?,?,?,?)',(cid,'MONSTER',4,None))
        for cid,method,head,link in (
            ('konami:901','XYZ','レベル4「架空」モンスター×2',None),
            ('konami:902','LINK','トークン以外のモンスター2体',2)):
            body=head+'\n①：架空の効果。'
            c.execute('INSERT INTO card_attributes VALUES (?,?,?,?)',(cid,'MONSTER',None,link))
            c.execute('INSERT INTO card_texts VALUES (?,?,?)',(cid,'ja',body))
            c.execute('INSERT INTO card_extra_material_requirements VALUES ('+','.join('?'*15)+')',
                (cid,method,head,sha(head.encode()),'',sha(body.encode()),'UNPARSED',
                 None,None,None,'[]','SOURCE_TEXT_ONLY',0,0,'FICTION'))
        c.commit();c.close()
        self.master=sha(self.db.read_bytes())
        self.raw=b'fictional source bytes'
        self.docs=[dict(document_id='FICTION:SOURCE',sha256=sha(self.raw),
                        media_type='text/plain',source_locator='fiction://source',
                        review_status='REVIEWED')]
        self.members=[dict(card_id=cid,archetype_label='架空',is_member=True,
                           document_id='FICTION:SOURCE',review_status='REVIEWED')
                      for cid in ('konami:11','konami:12')]
        self.board=[dict(instance_id=ins,card_id='konami:11',board_snapshot_id='s1',
                         is_token=False,document_id='FICTION:SOURCE',review_status='REVIEWED')
                    for ins in ('a','b')]

    def tearDown(self):self.t.cleanup()

    def compile(self,**changes):
        k=dict(method='XYZ',material_header='レベル4「架空」モンスター×2',
               extra_card_id='konami:901',material_card_ids=['konami:11','konami:12'],
               occurrence_instance_ids=None,master_sqlite_sha256=self.master,
               documents=self.docs,document_bytes={'FICTION:SOURCE':self.raw},
               membership_rows=self.members,board_rows=self.board,
               board_snapshot_id=None)
        k.update(changes)
        return compile_identity_evidence(**k)

    def route(self,eid,method,ids,ratings=()):
        return dict(extra_card_id=eid,summon_method=method,material_card_ids=ids,
          evidence_ids=['FICTION:source'],simultaneous_state_evidence_ids=['FICTION:board'],
          summon_method_evidence_ids=['FICTION:method'],restriction_review='REVIEWED',
          material_labels=[],link_material_ratings=list(ratings))

    def screen(self,eid,method,ids,bundle,ratings=()):
        return screen_structured_extra_materials(
            self.db,expected_sqlite_sha256=self.master,extra_card_ids=[eid],
            proposed_routes=[self.route(eid,method,ids,ratings)],
            identity_evidence=[bundle])['results'][0]

    def test_review_only_membership_and_no_db_mutation(self):
        before=self.db.read_bytes()
        claim=self.compile()
        out=self.screen('konami:901','XYZ',['konami:11','konami:12'],claim)
        self.assertEqual(out['screen'],'REQUIRES_REVIEW')
        self.assertIn('IDENTITY_CLAIM_ALIGNED',out['review_reason'])
        self.assertEqual(before,self.db.read_bytes())

    def test_board_instances_are_unique_and_time_scoped(self):
        k=dict(method='LINK',material_header='トークン以外のモンスター2体',
               extra_card_id='konami:902',material_card_ids=['konami:11']*2,
               occurrence_instance_ids=['a','b'],board_snapshot_id='s1')
        bundle=self.compile(**k)
        self.assertEqual(len(bundle['occurrences']),2)
        self.assertEqual([c['claim'] for c in bundle['occurrences']],[False,False])
        result=self.screen('konami:902','LINK',['konami:11']*2,bundle,[1,1])
        self.assertEqual(result['screen'],'REQUIRES_REVIEW')
        self.assertIn('IDENTITY_CLAIM_ALIGNED',result['review_reason'])
        for changed in (dict(occurrence_instance_ids=['a','a']),
                        dict(occurrence_instance_ids=['a']),dict(board_snapshot_id='s2')):
            with self.subTest(changed=changed),self.assertRaises(LedgerContractError):
                self.compile(**(k|changed))
        row=deepcopy(self.board)
        row[1]['card_id']='konami:12'
        with self.assertRaisesRegex(LedgerContractError,'CARD_MISMATCH'):
            self.compile(**(k|{'board_rows':row}))

    def test_token_claim_mismatch_is_not_summon_permission(self):
        k=dict(method='LINK',material_header='トークン以外のモンスター2体',
               extra_card_id='konami:902',material_card_ids=['konami:11']*2,
               occurrence_instance_ids=['a','b'],board_snapshot_id='s1')
        board=deepcopy(self.board)
        board[1]['is_token']=True
        claim=self.compile(**(k|{'board_rows':board}))
        out=self.screen('konami:902','LINK',['konami:11']*2,claim,[1,1])
        self.assertEqual(out['screen'],'REQUIRES_REVIEW')
        self.assertIn('IDENTITY_MISMATCH',out['review_reason'])

    def test_missing_or_wrong_document_bytes_rejected(self):
        with self.assertRaisesRegex(LedgerContractError,'BYTES_SHA_MISMATCH'):
            self.compile(document_bytes={'FICTION:SOURCE':b'changed'})
        with self.assertRaises(LedgerContractError):
            self.compile(document_bytes={})
        bad=deepcopy(self.docs)
        bad[0]['review_status']='NOT_REVIEWED'
        with self.assertRaisesRegex(LedgerContractError,'NOT_REVIEWED'):
            self.compile(documents=bad)

    def test_missing_conflicting_and_not_reviewed_membership(self):
        with self.assertRaisesRegex(LedgerContractError,'REQUIRED_CLAIM_MISSING'):
            self.compile(membership_rows=[])
        with self.assertRaisesRegex(LedgerContractError,'DUPLICATE_OR_CONFLICT'):
            self.compile(membership_rows=self.members+[self.members[0]])
        rows=deepcopy(self.members)
        rows[0]['review_status']='NOT_REVIEWED'
        with self.assertRaisesRegex(LedgerContractError,'NOT_REVIEWED'):
            self.compile(membership_rows=rows)

    def test_unknown_compound_header_does_not_generate_claims(self):
        with self.assertRaisesRegex(LedgerContractError,'SOURCE_GRAMMAR_UNSUPPORTED'):
            self.compile(method='LINK',material_header='トークン以外の闇属性モンスター2体')


if __name__=='__main__':unittest.main()
