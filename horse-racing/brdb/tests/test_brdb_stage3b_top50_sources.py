import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import audit_brdb_stage3b_top50_sources as audit

class SourceAuditTest(unittest.TestCase):
 def test_country_suffix_is_removed_without_transliteration(self):
  self.assertEqual(audit.normalize('Kingmambo(USA)'), 'Kingmambo')
  self.assertNotEqual(audit.normalize('Kingmambo(USA)'), 'キングマンボ')
 def test_wrong_ranking_fails_before_other_sources_are_read(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'wrong';p.write_bytes(b'wrong')
   original=audit.PINS.copy()
   try:
    audit.PINS['top50']=audit.sha(p)
    with self.assertRaisesRegex(ValueError,'ranking SHA mismatch'):
     audit.run(p,p,p,p,p,p,p,p,Path(t)/'out')
   finally:audit.PINS.clear();audit.PINS.update(original)

if __name__=='__main__':unittest.main()
