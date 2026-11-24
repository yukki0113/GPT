"""Editorial research-only formatter regression with synthetic bloodlines."""
import copy
import sys
import unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'src'))
from brdb_condition_discovery import build
from brdb_condition_editorial import draft
from test_brdb_condition_discovery import mock

class EditorialTests(unittest.TestCase):
    def test_observed_sentence_not_prediction(self):
        a,b,c,g=mock();x=draft(build(a,b,c,g,'a'*64))
        self.assertEqual(len(x['horses']),2)
        self.assertTrue(x['horses'][0]['observation_sentences'])
        self.assertTrue(x['horses'][0]['evidence_refs'])
        self.assertIsNone(x['horses'][0]['review_paragraph'])
        self.assertFalse(x['horses'][0]['betting_tips'])
        self.assertFalse(x['horses'][0]['display_authorized'])
    def test_forecast_promotion_refused(self):
        a,b,c,g=mock();x=build(a,b,c,g,'a'*64)
        x['policy']['prediction_safe']=True
        with self.assertRaisesRegex(ValueError,'cannot format'):draft(x)
    def test_reproducible(self):
        a,b,c,g=mock();x=build(a,b,c,g,'a'*64)
        self.assertEqual(draft(x),draft(x))

if __name__=='__main__':unittest.main()
