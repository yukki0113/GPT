"""Non-lossy ④ research sidecar and consumer-boundary regressions (synthetic)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from brdb_m7_relatives_detail_candidate import build, digest, RelativesDetailError, SCOPES
from brdb_m7_research_consumer_preview import build_preview
from brdb_m7_evidence_adapter import build_v02
from brdb_integrated_review_v03_candidate import merge
from brdb_newspaper_handoff import project_review, BRDBHandoffError
from test_brdb_m7_evidence_adapter import inputs
from test_brdb_m7_identity_field_scaffold import fake_d4


def fixtures():
    context, receipt, source, pair, relatives = inputs()
    for row in relatives['horses']:
        row['horse_name'] = source['horses'][row['horse_no']-1]['horse_name']
        row['maternal_granddam_horse_id'] = None
        row['relative_counts'] = {
            k:sum(x.get('relationship')==k for x in row['relatives'])
            for k in ('FULL_SIBLING','SAME_DAM_SAME_SIRE_NAME_UNVERIFIED',
                      'MATERNAL_HALF_SIBLING','MATERNAL_AUNT_UNCLE')}
        for rel in row['relatives']:
            rel['horse_name'] = '架空親族'
            rel['birth_date'] = '20100102'
            rel['scope_stats'] = {key:{'starts':0, 'wins':0, 'top3':0,
                                       'top3_rate':None} for key in SCOPES}
            rel['has_target_surface_band_history'] = False
        row['with_relevant_starts'] = 0
    relatives['timing_ms'] = {'total': 1.0}
    v02 = build_v02(context, receipt, source, pairing=pair, relatives=relatives)
    v03 = merge(v02, fake_d4(v02))
    return v03, relatives


class TestRelativesDetail(unittest.TestCase):
    def build(self):
        v03, source = fixtures()
        return v03, source, build(v03, source)

    def test_schema_and_source_roundtrip(self):
        v03, src, out = self.build()
        schema = json.loads((ROOT/'schema/brdb_m7_relatives_detail_v0_1_candidate.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(out)
        self.assertEqual({**out['source_metadata'], 'horses':out['horses']}, src)
        self.assertEqual(out['source_canonical_sha256'], digest(src))
        self.assertEqual(out['integrated_v03_canonical_sha256'], digest(v03))
        self.assertFalse(out['prediction_safe'])

    def test_replay_deterministic_non_mutating(self):
        v03, src = fixtures()
        before = copy.deepcopy((v03,src))
        self.assertEqual(build(v03,src),build(v03,src))
        self.assertEqual((v03,src), before)

    def test_zero_starts_null_preserved(self):
        _, _, out = self.build()
        self.assertEqual(out['aggregate_coverage']['zero_start_cells'], 5)
        self.assertIsNone(out['horses'][0]['relatives'][0]['scope_stats']['VENUE_BAND']['top3_rate'])

    def test_genuine_start_valid_zero_top3(self):
        v03,src=fixtures()
        stat=src['horses'][0]['relatives'][0]['scope_stats']['ALL_VENUES_BAND']
        stat.update(starts=3,wins=0,top3=0,top3_rate=0.0)
        src['horses'][0]['relatives'][0]['has_target_surface_band_history']=True
        src['horses'][0]['with_relevant_starts']=1
        out=build(v03,src)
        self.assertEqual(out['aggregate_coverage']['zero_start_cells'],4)
        self.assertEqual(out['horses'][0]['relatives'][0]['scope_stats']['ALL_VENUES_BAND']['top3_rate'],0.0)

    def test_future_profile_rejected(self):
        v03,src=fixtures()
        src['horses'][0]['relatives'][0]['profile_data_date']='20261116'
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_broken_denominator_rejected(self):
        v03,src=fixtures()
        src['horses'][0]['relatives'][0]['scope_stats']['VENUE_BAND']['top3']=1
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_wrong_rate_rejected(self):
        v03,src=fixtures()
        s=src['horses'][0]['relatives'][0]['scope_stats']['VENUE_BAND']
        s.update(starts=10, wins=0, top3=3, top3_rate=0.4)
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_missing_scope_rejected(self):
        v03,src=fixtures()
        del src['horses'][0]['relatives'][0]['scope_stats']['VENUE_BAND']
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_relative_identity_drift_rejected(self):
        v03,src=fixtures()
        src['horses'][0]['relatives'][0]['horse_id']='11119999'
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_field_identity_drift_rejected(self):
        v03,src=fixtures()
        src['horses'][0]['horse_id']='99999999'
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_mother_unresolved_with_relatives_rejected(self):
        v03,src=fixtures()
        src['horses'][0]['mother_horse_id']=None
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_generation_drift_rejected(self):
        v03,src=fixtures()
        src['pedigree_generation']='wrong-generation'
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_asof_promotion_rejected(self):
        v03,src=fixtures()
        src['prediction_safe']=True
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_scoring_in_v03_rejected(self):
        v03,src=fixtures()
        v03['horses'][0]['confidence']='SUPPORTED'
        with self.assertRaises(RelativesDetailError): build(v03,src)

    def test_preview_carries_only_qualified_status(self):
        v03, src, sidecar = self.build()
        p=build_preview(v03,sidecar)
        schema = json.loads((ROOT/'schema/brdb_m7_research_consumer_preview_v0_1.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(p)
        self.assertFalse(p['production_authorized'])
        self.assertFalse(p['prediction_safe'])
        self.assertTrue(all(h['score'] is None and h['rank'] is None and
                            h['probability'] is None for h in p['horses']))
        self.assertEqual(p['horses'][0]['lanes']['pairing']['display_reason'],
                         'HISTORICAL_AS_OF_UNVERIFIED')
        self.assertEqual(p['horses'][1]['lanes']['relatives']['display_reason'],
                         'SOURCE_UNAVAILABLE')

    def test_preview_tampered_sidecar_sha_rejected(self):
        v03, _, sidecar = self.build()
        sidecar['integrated_v03_canonical_sha256']='0'*64
        with self.assertRaises(RelativesDetailError): build_preview(v03,sidecar)

    def test_preview_modified_relative_stat_rejected(self):
        v03, _, sidecar = self.build()
        sidecar['horses'][0]['relatives'][0]['scope_stats']['VENUE_BAND']['wins'] = 1
        with self.assertRaises(RelativesDetailError): build_preview(v03, sidecar)

    def test_frozen_newspaper_handoff_rejects_new_contracts(self):
        v03, _, sidecar = self.build()
        preview=build_preview(v03,sidecar)
        with self.assertRaises(BRDBHandoffError): project_review(v03['horses'][0])
        with self.assertRaises(BRDBHandoffError): project_review(preview)


if __name__=='__main__': unittest.main()
