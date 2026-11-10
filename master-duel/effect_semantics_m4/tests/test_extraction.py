"""Entirely synthetic unit tests; never publish private card text."""
from hashlib import sha256
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from effect_semantics_m4 import extract_effect_facets


def facets(text):
    return extract_effect_facets('konami:1001',text,text_version='fixture-v1',text_source='SYNTHETIC')

def pairs(text):
    return {(f['facet'],f['role']) for f in facets(text)}

class ExtractorTests(unittest.TestCase):
    def test_direct_draw_and_search_are_distinct(self):
        self.assertIn(('DRAW','ACTION'),pairs('自分は２枚ドローする。'))
        self.assertNotIn(('SEARCH_FROM_DECK','ACTION'),pairs('自分は２枚ドローする。'))
        self.assertIn(('SEARCH_FROM_DECK','ACTION'),pairs('デッキからカード１枚を手札に加える。'))
        self.assertNotIn(('DRAW','ACTION'),pairs('デッキからカード１枚を手札に加える。'))

    def test_grave_recovery_not_deck_search(self):
        r=pairs('自分の墓地からモンスター１体を手札に加える。')
        self.assertIn(('RECOVER_FROM_GRAVE','ACTION'),r)
        self.assertNotIn(('SEARCH_FROM_DECK','ACTION'),r)

    def test_opposing_summon_is_condition_for_own_draw(self):
        r=pairs('相手がモンスターを特殊召喚する度に、自分は１枚ドローする。')
        self.assertIn(('DRAW','ACTION'),r)
        self.assertIn(('SPECIAL_SUMMON','CONDITION'),r)
        self.assertNotIn(('SPECIAL_SUMMON','ACTION'),r)

    def test_negated_references_are_not_self_search_or_summon(self):
        text=('以下のいずれかの効果を含むモンスターの効果が発動した時、'
              'このカードを手札から捨てて発動できる。その効果を無効にする。\n'
              '●デッキからカードを手札に加える効果\n'
              '●デッキからモンスターを特殊召喚する効果')
        r=pairs(text)
        self.assertIn(('SEARCH_FROM_DECK','REFERENCED'),r)
        self.assertIn(('SPECIAL_SUMMON','REFERENCED'),r)
        self.assertNotIn(('SEARCH_FROM_DECK','ACTION'),r)
        self.assertNotIn(('SPECIAL_SUMMON','ACTION'),r)
        self.assertIn(('NEGATE','ACTION'),r)
        self.assertIn(('COST','METADATA'),r)
        self.assertIn(('DISCARD','METADATA'),r)
        self.assertNotIn(('DISCARD','ACTION'),r)

    def test_negation_and_once_per_turn_are_separate(self):
        r=pairs('このカード名の効果は１ターンに１度しか使用できない。相手の効果を無効にする。')
        self.assertIn(('ONCE_PER_TURN','RESTRICTION'),r)
        self.assertIn(('NEGATE','ACTION'),r)

    def test_no_positive_summon_for_summon_lock(self):
        r=pairs('このターン自分はモンスターを特殊召喚できない。')
        self.assertIn(('SUMMON_LOCK','RESTRICTION'),r)
        self.assertNotIn(('SPECIAL_SUMMON','ACTION'),r)

    def test_cost_is_not_self_mill(self):
        r=pairs('このカードを手札から墓地へ送って発動できる。')
        self.assertIn(('SEND_TO_GRAVE','METADATA'),r)
        self.assertNotIn(('SEND_TO_GRAVE','ACTION'),r)

    def test_target_references_are_metadata_not_verified_archetypes(self):
        r=pairs('デッキから「架空戦士」カード１枚を手札に加える。光属性・戦士族・レベル４のモンスター。')
        self.assertIn(('SEARCH_FROM_DECK','ACTION'),r)
        self.assertIn(('NAMED_TARGET','METADATA'),r)
        self.assertIn(('ATTRIBUTE_TARGET','METADATA'),r)
        self.assertIn(('RACE_TARGET','METADATA'),r)
        self.assertIn(('LEVEL_TARGET','METADATA'),r)

    def test_evidence_exact_offsets_and_provenance(self):
        text='①：自分は１枚ドローする。\n②：手札からカード１枚を捨てて発動できる。'
        for f in facets(text):
            self.assertEqual(text[f['start']:f['end']],f['evidence'])
            self.assertEqual(f['text_sha256'],sha256(text.encode()).hexdigest())
            self.assertEqual(f['text_version'],'fixture-v1')
            self.assertEqual(f['verification'],'UNVERIFIED_INTERPRETATION')

    def test_invalid_identity_text_source_rejected(self):
        with self.assertRaises(ValueError):extract_effect_facets('invalid','本文',text_version='v',text_source='s')
        with self.assertRaises(ValueError):extract_effect_facets('konami:1001','',text_version='v',text_source='s')
        with self.assertRaises(ValueError):extract_effect_facets('konami:1001','本文',text_version='',text_source='s')

    def test_unmatched_text_stays_unclassified_not_false(self):
        self.assertEqual(facets('これは詳細な裁定が必要な架空効果である。'),[])

if __name__=='__main__':unittest.main()
