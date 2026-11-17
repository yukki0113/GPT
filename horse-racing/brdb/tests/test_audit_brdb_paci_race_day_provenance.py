from __future__ import annotations
import hashlib, json, pathlib, sys, tempfile, unittest, zipfile
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
import audit_brdb_paci_race_day_provenance as m

class T(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup); self.p=pathlib.Path(self.t.name)/'PACI261115.zip'; self.p.write_bytes(b'x')
  self.meta={'id':'f','title':self.p.name,'size':'1','parent_ids':['folder'],'created_time':'2026-11-14T12:16:37.800Z','modified_time':'2026-11-14T12:16:37.800Z'}
  self.race={'race_key_raw':'05265412','date_raw':'20261115','post_time_raw':'1610'}
 def call(self):
  with patch.object(m,'sha256',return_value='a'*64), patch.object(m.zipfile,'ZipFile') as z, patch.object(m,'canonical_members',return_value=['BAC261115.txt']), patch.object(m,'split_fixed_records',return_value=[b'r']), patch.object(m.Parser,'bac',return_value=self.race):
   z.return_value.__enter__.return_value.testzip.return_value=None; z.return_value.__enter__.return_value.read.return_value=b'r'
   return m.audit(paci=self.p,race_key='05265412',drive_metadata=self.meta,expected_sha256='a'*64,expected_parent_id='folder')
 def test_previous_day_is_preoff(self): self.assertEqual(self.call()['paci_acquisition_status'],'PRE_OFF_DRIVE_BYTES_ATTESTED')
 def test_same_day_before_off_is_preoff(self):
  self.meta['created_time']=self.meta['modified_time']='2026-11-15T06:00:00Z'
  self.assertEqual(self.call()['paci_acquisition_status'],'PRE_OFF_DRIVE_BYTES_ATTESTED')
 def test_modified_after_off_not_attested(self):
  self.meta['modified_time']='2026-11-15T08:00:00Z'
  self.assertEqual(self.call()['paci_acquisition_status'],'PRE_OFF_NOT_ATTESTED')
 def test_wrong_parent_fails(self):
  self.meta['parent_ids']=['other']
  with self.assertRaises(m.ProvenanceError): self.call()
 def test_provider_release_never_promoted(self):
  self.assertEqual(self.call()['provider_release_status'],'UNKNOWN_NOT_ATTESTED')
 def test_d3_never_promoted(self):
  self.assertEqual(self.call()['d3_historical_asof_status'],'AS_OF_UNVERIFIED_UNCHANGED')
if __name__=='__main__': unittest.main()
