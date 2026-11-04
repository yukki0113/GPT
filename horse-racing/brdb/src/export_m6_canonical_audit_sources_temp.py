"""Temporary research-only source transport: copy GitHub checkout source bytes.

Transfers only GitHub-committed Python files for private local audit. Absolutely
NO JRDB licensed records, artifacts or authenticated tokens are handled here.
This temporary transport stays out of main.
"""
import argparse
from pathlib import Path
import hashlib
import json
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);args=p.parse_args()
    root=Path(__file__).resolve().parents[3]
    output=Path(args.out)
    files=[
      "horse-racing/jrdb/src/jrdb_raw.py",
      "horse-racing/jrdb/src/jrdb_ukc.py",
      "horse-racing/jrdb/src/jrdb_result_query.py",
      "horse-racing/jrdb/src/jrdb_result_query_runner.py",
      "horse-racing/brdb/src/audit_brdb_paci_pre_day_inventory.py",
    ]
    receipts=[]
    for rel in files:
        source=root/rel;dest=output/"github_sources"/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        binary=source.read_bytes();dest.write_bytes(binary)
        receipts.append({"path":rel,"sha256":hashlib.sha256(binary).hexdigest(),"size":len(binary)})
    (output/"source_receipts.json").write_text(json.dumps(receipts,indent=2)+"\n")
    print(json.dumps({"status":"PASS","sources":len(receipts)}))
if __name__=="__main__":main()
