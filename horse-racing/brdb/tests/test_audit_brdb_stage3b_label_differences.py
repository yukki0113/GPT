from __future__ import annotations
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from audit_brdb_stage3b_label_differences import classify,AuditError

def row(aid="",status="NAME_OBSERVED"):
 return {"name_agreement":"DIFFERENT_UNREVIEWED","ancestor_id":aid,"status":status}

class T(unittest.TestCase):
 def test_jbis_id_is_identity_qualified_label_only(self):
  self.assertEqual(classify(row("JBIS:0000347989","JBIS_SOURCE_QUALIFIED")),"IDENTITY_ALREADY_JBIS_QUALIFIED_LABEL_ONLY")
 def test_jrdb_id_is_identity_qualified_label_only(self):
  self.assertEqual(classify(row("JRDB:02100844","JRDB_CANONICAL")),"IDENTITY_ALREADY_JRDB_CANONICAL_LABEL_ONLY")
 def test_no_id_requires_alias_review(self):
  self.assertEqual(classify(row()),"ALIAS_REVIEW_REQUIRED_NO_CANONICAL_ID")
 def test_does_not_infer_from_names(self):
  r=row();r.update({"jrdb_name":"キングマンボ","jbis_name":"Kingmambo(USA)"})
  self.assertEqual(classify(r),"ALIAS_REVIEW_REQUIRED_NO_CANONICAL_ID")
 def test_non_difference_rejected(self):
  r=row();r["name_agreement"]="EXACT"
  with self.assertRaises(AuditError): classify(r)
if __name__=="__main__":unittest.main()
