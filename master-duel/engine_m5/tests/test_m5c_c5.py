"""M5-C C5 synthetic-only bundle and immutable ZIP verification."""
import copy
from hashlib import sha256
import unittest
from test_m5c_c0 import fixture
from engine_m5.private_bundle import (make_sidecar,open_sidecar as _open_sidecar,theme_knowledge_bundle,
                                     canonical,digest)


def sample():
    k=fixture()
    k['knowledge_version']=4
    k['c2_audit']={'current_master_sqlite_sha256':'b'*64}
    k['c4_audit']={'source_c3_sha256':'c'*64}
    k['recipe_refs']=[{'recipe_id':'r1','profile_id':'p1','source_id':'s1',
        'article_revision':'v1','main_count':40,'extra_count':0,
        'game_scope':'MD','banlist_on':None}]
    cards=[{'section':'MAIN','card_id':'konami:'+str(100+i),
            'quantity':3 if i<13 else 1,'rarity':'R'} for i in range(14)]
    k['recipe_cards']=[{'recipe_id':'r1','card_id':x['card_id'],
       'section':'MAIN','quantity':x['quantity'],'role':'CORE',
       'essentiality':'UNKNOWN','resolve_status':'RESOLVED'} for x in cards]
    variant={'variant_id':'variant1','source_recipe_id':'r1',
       'source_profile_id':'p1','candidate_cards':cards,
       'main_count':40,'extra_count':0,'verification':'REVIEW_REQUIRED'}
    k['c3_variants']=[variant]
    return k,[variant]


def packed(k=None,variants=None,overlay=None):
    if k is None:k,variants=sample()
    return make_sidecar(k,variants=variants,overlay=overlay,
            upstream_knowledge_sha256='c'*64,master_db_sha256='b'*64)


def open_sidecar(z,m,**kwargs):
    return _open_sidecar(z,m, expected_zip_sha256=kwargs.pop("expected_zip_sha256",digest(z)),
                         expected_manifest_sha256=kwargs.pop("expected_manifest_sha256",digest(m)),
                         expected_master_db_sha256=kwargs.pop("expected_master_db_sha256","b"*64),**kwargs)


class PrivateBundleTests(unittest.TestCase):
    def test_roundtrip_and_m6_unknown_gates(self):
        z,m=packed()
        data=open_sidecar(z,m,expected_zip_sha256=digest(z),
          expected_manifest_sha256=digest(m),expected_master_db_sha256='b'*64)
        b=theme_knowledge_bundle(data,'p1')
        self.assertEqual('md-m5c-theme-knowledge-bundle-v1',b['schema'])
        self.assertEqual(40,sum(x['quantity'] for x in b['recipe_cards']))
        self.assertFalse(b['recommendation_eligible'])
        self.assertFalse(b['ownership_verified'])
        self.assertFalse(b['regulation_verified'])
        self.assertEqual(1,len(b['low_cost_variants']))

    def test_deterministic_zip_and_manifest(self):
        z,m=packed()
        z2,m2=packed()
        self.assertEqual(z,z2)
        self.assertEqual(m,m2)

    def test_tampered_zip_rejected(self):
        z,m=packed()
        with self.assertRaises(ValueError):open_sidecar(z+b'X',m)

    def test_tampered_manifest_rejected(self):
        z,m=packed()
        with self.assertRaises(ValueError):open_sidecar(z,m[:-1]+b'x')

    def test_external_pins_rejected(self):
        z,m=packed()
        with self.assertRaises(ValueError):open_sidecar(z,m,expected_zip_sha256='0'*64)
        with self.assertRaises(ValueError):open_sidecar(z,m,expected_manifest_sha256='0'*64)
        with self.assertRaises(ValueError):open_sidecar(z,m,expected_master_db_sha256='0'*64)

    def test_variant_mismatch_rejected(self):
        k,v=sample()
        v=copy.deepcopy(v);v[0]['candidate_cards'][0]['quantity']=2
        with self.assertRaises(ValueError):packed(k,v)

    def test_missing_source_c4_pin_rejected(self):
        k,v=sample(); k['c4_audit']['source_c3_sha256']='d'*64
        with self.assertRaises(ValueError):packed(k,v)

    def test_variant_declared_sum_tamper_rejected(self):
        k,v=sample();v=copy.deepcopy(v);v[0]['main_count']=39
        k['c3_variants']=v
        with self.assertRaises(ValueError):packed(k,v)

    def test_overlay_blocks_only_dependent_claim(self):
        k,v=sample();overlay={'schema':'md-m5c-c4-staleness-overlay-v1',
          'source_knowledge_version':4,
          'source_knowledge_sha256':digest(canonical(k)),
          'unchanged_source_data':True,
          'statuses':[{'object_type':'CLAIM','object_id':'c1','status':'STALE','reasons':['RECHECK_EFFECT']}]}
        z,m=packed(k,v,overlay)
        b=theme_knowledge_bundle(open_sidecar(z,m),'p1')
        self.assertEqual(1,len(b['stale_dependencies']))
        self.assertIn({'kind':'STALE_OR_REVIEW_REQUIRED','count':1},b['issues'])

    def test_foreign_overlay_rejected(self):
        k,v=sample();overlay={'schema':'md-m5c-c4-staleness-overlay-v1',
          'source_knowledge_version':4,'source_knowledge_sha256':'0'*64,
          'unchanged_source_data':True,'statuses':[]}
        with self.assertRaises(ValueError):packed(k,v,overlay)

    def test_unknown_overlay_target_rejected(self):
        k,v=sample();overlay={'schema':'md-m5c-c4-staleness-overlay-v1',
          'source_knowledge_version':4,'source_knowledge_sha256':digest(canonical(k)),
          'unchanged_source_data':True,'statuses':[{'object_type':'CLAIM','object_id':'fake','status':'STALE'}]}
        with self.assertRaises(ValueError):packed(k,v,overlay)

    def test_source_inputs_immutable(self):
        k,v=sample();before=(copy.deepcopy(k),copy.deepcopy(v))
        packed(k,v)
        self.assertEqual(before,(k,v))

    def test_unknown_theme_rejected(self):
        z,m=packed()
        with self.assertRaises(ValueError):theme_knowledge_bundle(open_sidecar(z,m),'unknown')

    def test_missing_referenced_recipe_count_reported_not_corrected(self):
        k,v=sample();k['recipe_refs'][0]['main_count']=41
        z,m=packed(k,v)
        b=theme_knowledge_bundle(open_sidecar(z,m),'p1')
        self.assertTrue(any(x['kind']=='SOURCE_RECIPE_COUNT_MISMATCH' for x in b['issues']))

    def test_malformed_variant_with_duplicate_id_rejected(self):
        k,v=sample();v=v+[copy.deepcopy(v[0])]
        with self.assertRaises(ValueError):packed(k,v)

    def test_unpinned_open_is_rejected(self):
        z,m=packed()
        with self.assertRaises(TypeError):_open_sidecar(z,m)

    def test_noncanonical_manifest_rejected(self):
        z,m=packed()
        with self.assertRaises(ValueError):open_sidecar(z,b' '+m)


if __name__=='__main__':unittest.main()
