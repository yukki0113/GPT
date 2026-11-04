"""Temporary GitHub source-only transfer for local private M6 result audit.

No private JRDB ZIP, licensed data, credentials or per-horse observations.
Temporary branch only; DO NOT merge this exporter into main.
"""
import argparse
import hashlib
import json
from pathlib import Path
def main():
    a=argparse.ArgumentParser();a.add_argument("--out",required=True);args=a.parse_args()
    root=Path(__file__).resolve().parents[3]
    files=[
      "horse-racing/jrdb/src/jrdb_raw.py",
      "horse-racing/jrdb/src/jrdb_ukc.py",
      "horse-racing/brdb/src/audit_brdb_paci_pre_day_inventory.py",
      "horse-racing/brdb/src/audit_brdb_m6_2026_outcome_cohort.py",
      "horse-racing/brdb/tests/test_audit_brdb_m6_2026_outcome_cohort.py",
    ]
    out=Path(args.out)
    receipt=[]
    for rel in files:
        source=root/rel
        blob=source.read_bytes()
        dest=out/"source_bundle"/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(blob)
        receipt.append({"path":rel,"size":len(blob),"sha256":hashlib.sha256(blob).hexdigest()})
    (out/"bundle_receipt.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":"PASS","files":len(receipt)}))
if __name__=="__main__":main()
