import sys, sqlite3, tempfile, zipfile, unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"jrdb"/"src"))
import build_brdb_pedigree_generation as builder
import jrdb_ukc


def record(horse_id, data_date):
    row=bytearray(b" "*jrdb_ukc.RECORD_LENGTH)
    row[0:8]=horse_id.encode("ascii")
    row[268:276]=data_date.encode("ascii")
    return bytes(row)


class DateSentinelTest(unittest.TestCase):
    def test_sentinel_quarantine_and_latest_valid_date(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/"UKC_1999.zip"
            with zipfile.ZipFile(source,"w") as z:
                z.writestr("UKC999999.txt",record("04102987","99999999")+b"\r\n")
                z.writestr("UKC990101.txt",record("04102987","19990101")+b"\r\n")
                z.writestr("UKC990102.txt",record("04102987","19990102")+b"\r\n")
            con=sqlite3.connect(":memory:")
            source_audit,ids=builder.ingest(con,[source])
            self.assertEqual(len(source_audit["quarantined_date_records"]),1)
            self.assertEqual(source_audit["max_data_date"],"19990102")
            result=builder.reduce_profiles(con,"test-generation")
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]["profile_data_date"],"19990102")

    def test_impossible_calendar_date_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/"UKC_2000.zip"
            with zipfile.ZipFile(source,"w") as z:
                z.writestr("UKC000101.txt",record("04102987","20000231")+b"\r\n")
            with self.assertRaisesRegex(ValueError,"invalid UKC calendar date"):
                builder.ingest(sqlite3.connect(":memory:"),[source])

if __name__=="__main__":
    unittest.main()
