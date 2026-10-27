from __future__ import annotations
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from audit_race_year_pedigree import AuditSnapshot, aggregate, verified, parse_entries
from brdb_research_reader import ResearchPedigreeReader


def snapshot():
    s = object.__new__(AuditSnapshot)
    s.profiles = {h: {'profile_data_date':'20260101', 'sire_name':'S', 'dam_name':'D',
        'broodmare_sire_name':'B','sire_line_code':'1206','broodmare_sire_line_code':'1503'} for h in ('C','P')}
    s.available={'C':'20260104','P':'20260201'}
    s.mapped={'1206','1503'};s.graph_cache={};s.relations=defaultdict(list)
    s.relations['C']=[{'child_horse_id':'C','role':role,
        'resolution_status':'RESOLVED_EXACT' if role=='sire' else 'NO_CANDIDATE',
        'resolved_parent_horse_id':'P' if role=='sire' else None} for role in ('sire','dam','broodmare_sire')]
    return s


class AuditTest(unittest.TestCase):
    def test_future_profile_never_counts_names_or_codes(self):
        s=snapshot()
        self.assertEqual(s.flags('C','20260103')['three_names_present'],0)
        self.assertEqual(s.flags('C','20260104')['three_names_present'],1)
        self.assertEqual(s.flags('C','20260104')['sire_line_code_mapped'],1)
        s.profiles['C']['profile_data_date']='20270101'
        self.assertEqual(s.flags('C','20260104')['id_joined'],0)

    def test_future_parent_blocks_canonical_id_and_graph(self):
        s=snapshot()
        self.assertEqual(s.flags('C')['sire_id_resolved'],1)
        self.assertEqual(s.flags('C','20260104')['sire_id_resolved'],0)
        self.assertEqual(s.depths('C','20260104')['ancestor_depth'],0)
        self.assertEqual(s.depths('C','20260201')['ancestor_depth'],1)

    def test_entry_denominator_preserves_repeat_appearances(self):
        s=snapshot()
        a=aggregate(s,[('C','20260104'),('C','20260201'),('MISSING','20260201')],True)
        self.assertEqual(a['denominator'],3)
        self.assertEqual(a['metrics']['id_joined']['count'],2)
        self.assertEqual(a['metrics']['sire_id_resolved']['count'],1)

    def test_direct_broodmare_sire_is_generation_two(self):
        s=snapshot()
        s.relations['C'][2].update(resolution_status='RESOLVED_EXACT',resolved_parent_horse_id='P')
        self.assertEqual(s.depths('C')['broodmare_sire_ancestor_depth'],2)

    def test_unknown_name_never_falls_back_to_another_id(self):
        s=snapshot()
        self.assertEqual(s.flags('S')['id_joined'],0)
        self.assertEqual(s.depths('S')['ancestor_depth'],0)

    def test_reader_uses_selected_latest_observation(self):
        r=object.__new__(ResearchPedigreeReader)
        r.first_seen={'C':'20260104'};r.latest_profile_available_from={'C':'20260201'}
        self.assertFalse(r._available('C','20260131'))
        self.assertTrue(r._available('C','20260201'))

    def test_missing_or_changed_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'file.zip';p.write_bytes(b'wrong')
            with self.assertRaises(ValueError):verified(p,{'size_bytes':5,'sha256':'0'*64})
            with self.assertRaises(ValueError):parse_entries(Path(tmp),[])


if __name__=='__main__':unittest.main()
