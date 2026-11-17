"""D4 PACI field adapter contracts; synthetic data only, no licensed inputs."""
from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from brdb_d4_paci_field import assemble, PACIFieldError


class PACIFieldTests(unittest.TestCase):
    def setUp(self):
        self.kw = {
            'archive_name':'PACI261115.zip','race_key':'05260301',
            'bac':[{'race_key_raw':'05260301','date_raw':'20261115',
                    'surface_code':'1','distance_raw':'2000','field_size':2}],
            'kyi':[{'race_key_raw':'05260301','blood_registration_no':'12345678','horse_no':1},
                   {'race_key_raw':'05260301','blood_registration_no':'23456789','horse_no':3}],
            'ukc':[{'horse_id':'12345678','data_date':'20261114',
                    'sire_name':'父A','broodmare_sire_name':'母父A'},
                   {'horse_id':'23456789','data_date':'20261115',
                    'sire_name':'父B','broodmare_sire_name':'母父B'}],
        }

    def run_field(self):
        return assemble(**self.kw)

    def test_complete_field_and_non_scoring_contract(self):
        x=self.run_field()
        self.assertEqual(len(x['entrants']),2)
        self.assertEqual(x['race']['field_size'],2)
        self.assertEqual(x['entrants'][1]['horse_no'],3)
        self.assertNotIn('track_condition_code',x['race'])
        self.assertNotIn('score',x['entrants'][0])
        self.assertEqual(x['race']['research_only'],True)

    def test_reordering_is_deterministic(self):
        first=self.run_field()
        self.kw['ukc'].reverse()
        self.kw['kyi'].reverse()
        self.assertEqual(first,self.run_field())

    def test_duplicate_kyi_number_fails(self):
        self.kw['kyi'][1]['horse_no']=1
        with self.assertRaisesRegex(PACIFieldError,'duplicate KYI'):
            self.run_field()

    def test_missing_ukc_fails_closed(self):
        self.kw['ukc'].pop()
        with self.assertRaisesRegex(PACIFieldError,'not complete'):
            self.run_field()

    def test_duplicate_ukc_fails_closed(self):
        self.kw['ukc'].append(dict(self.kw['ukc'][0]))
        with self.assertRaisesRegex(PACIFieldError,'duplicate UKC'):
            self.run_field()

    def test_future_profile_fails(self):
        self.kw['ukc'][0]['data_date']='20261116'
        with self.assertRaisesRegex(PACIFieldError,'future UKC'):
            self.run_field()

    def test_sentinel_profile_fails(self):
        self.kw['ukc'][0]['data_date']='99999999'
        with self.assertRaisesRegex(PACIFieldError,'sentinel'):
            self.run_field()

    def test_wrong_archive_date_fails(self):
        self.kw['bac'][0]['date_raw']='20261114'
        with self.assertRaisesRegex(PACIFieldError,'date mismatch'):
            self.run_field()

    def test_pre_d3_cutoff_fails(self):
        self.kw['archive_name']='PACI261101.zip'
        self.kw['bac'][0]['date_raw']='20261101'
        with self.assertRaisesRegex(PACIFieldError,'cutoff'):
            self.run_field()

    def test_bac_field_mismatch_fails(self):
        self.kw['bac'][0]['field_size']=3
        with self.assertRaisesRegex(PACIFieldError,'field size'):
            self.run_field()

    def test_wrong_race_key_fails(self):
        self.kw['race_key']='06260301'
        with self.assertRaisesRegex(PACIFieldError,'missing or duplicate BAC'):
            self.run_field()

    def test_unsupported_surface_fails(self):
        self.kw['bac'][0]['surface_code']='3'
        with self.assertRaisesRegex(PACIFieldError,'unsupported surface'):
            self.run_field()


if __name__=='__main__':
    unittest.main()
