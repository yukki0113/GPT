from __future__ import annotations
import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from audit_missing_daily_ukc_causes import (profile_guards,primary_reason,selected_profile,
    trustworthy_birth,dated_evidence,latest_eligible,scan_ukc)
import jrdb_ukc


def obs(date='20260104',observed='20260104',digest='a'*64,birth='20240102'):
    record={'horse_id':'12345678','horse_name':'SameName','data_date':date,'birth_date':birth,
            'sire_name':'S','dam_name':'D','broodmare_sire_name':'B','sire_line_code':'1206','broodmare_sire_line_code':'1503'}
    return {'horse_id':'12345678','record':record,'semantic_hash':digest,'observation_date':observed,
            'source_zip':'PACI'+observed[2:]+'.zip','source_zip_sha256':'b'*64,'member':'UKC'+observed[2:]+'.txt',
            'line_number':1,'guards':profile_guards(record,observed)}


class MissingCauseTest(unittest.TestCase):
    def test_daily_presence_is_overlay_exclusion_not_missing_source(self):
        self.assertEqual(primary_reason([],[obs()],False),'DAILY_UKC_PRESENT_OUTSIDE_104_OVERLAY')

    def test_absence_is_scoped_and_requires_complete_scan(self):
        self.assertEqual(primary_reason([],[],False),'NOT_FOUND_IN_SCANNED_ANNUAL_OR_DAILY_UKC')
        self.assertEqual(primary_reason([],[],False,False),'UNKNOWN_INPUT_GAP')

    def test_sentinel_and_future_dates_are_quarantined(self):
        for o in (obs('99999999'),obs('20260105'),obs('20260230')):
            self.assertIsNone(selected_profile([o])[0])
            self.assertEqual(primary_reason([],[o],False),'PROFILE_DATE_OR_SELECTION_GUARD')

    def test_latest_date_conflict_requires_review(self):
        a=obs();b=obs(observed='20260105',digest='c'*64)
        self.assertEqual(selected_profile([a,b]),(None,True))
        self.assertEqual(primary_reason([],[a,b],False),'PROFILE_DATE_OR_SELECTION_GUARD')

    def test_dated_evidence_does_not_make_latest_profile_historical(self):
        old=obs();latest=obs('20261025','20261025',digest='d'*64)
        selected,conflict=selected_profile([old,latest])
        self.assertFalse(conflict)
        self.assertEqual(dated_evidence([old,latest],'20260105'),old)
        self.assertFalse(latest_eligible(selected,'20260105'))
        self.assertTrue(latest_eligible(selected,'20261025'))

    def test_birth_year_requires_consistent_valid_source_dates(self):
        self.assertEqual(trustworthy_birth([obs()]),('2024','EXACT_ID_UKC_BIRTH_DATE'))
        self.assertEqual(trustworthy_birth([obs(birth='')])[0],'')
        self.assertEqual(trustworthy_birth([obs(),obs(birth='20230102')])[0],'')

    def test_present_annual_profile_is_not_asserted_to_be_overlay_root_cause(self):
        self.assertEqual(primary_reason([obs()],[],False),'ANNUAL_VALID_PROFILE_NOT_IN_BASE_REVIEW_REQUIRED')

    def test_existing_overlay_member_requires_build_review(self):
        self.assertEqual(primary_reason([],[obs()],True),'UNKNOWN_BUILD_DISCREPANCY')

    def test_parser_error_stays_unknown(self):
        o=obs();o['record']=None;o['guards']=['PARSER_ERROR']
        self.assertEqual(primary_reason([],[o],False),'UNKNOWN_PARSE_FAILURE')

    def test_exact_id_scan_never_uses_name_rescue_and_checks_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'UKC_2025.zip'
            body=bytearray(b' '*jrdb_ukc.RECORD_LENGTH)
            values={'horse_id':'87654321','horse_name':'SameName','data_date':'20250104'}
            for key,offset,width in jrdb_ukc.FIELD_SPECS:
                value=values.get(key,'').encode('cp932');body[offset:offset+len(value)]=value
            with zipfile.ZipFile(path,'w') as z:z.writestr('UKC250104.txt',bytes(body)+b'\r\n')
            item={'name':path.name,'size_bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                  'members':[{'member':'UKC250104.txt','records':1}]}
            found,inventory,errors,_=scan_ukc(root,[item],{'12345678'},'ANNUAL')
            self.assertFalse(found);self.assertFalse(errors);self.assertEqual(inventory[0]['records_identity_scanned'],1)
            body[:8]=b'ABCDEFGH';target=bytearray(body);target[:8]=b'12345678'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('UKC250104.txt',bytes(body)+b'\r\n'+bytes(target)+b'\r\n')
            item.update(size_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        members=[{'member':'UKC250104.txt','records':2}])
            found,inventory,errors,_=scan_ukc(root,[item],{'12345678'},'ANNUAL')
            self.assertFalse(errors);self.assertEqual(found['12345678'][0]['line_number'],2)
            self.assertEqual(inventory[0]['non_numeric_source_id_count'],1)
            self.assertEqual(inventory[0]['records_identity_scanned'],2)
            item['sha256']='0'*64
            found,inventory,errors,_=scan_ukc(root,[item],{'12345678'},'ANNUAL')
            self.assertTrue(errors);self.assertEqual(inventory[0]['status'],'INPUT_GAP')


if __name__=='__main__':unittest.main()
