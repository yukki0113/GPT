"""Unmerged temporary source-only export for verification in private runtime."""
from pathlib import Path
import argparse,hashlib,json
def main():
 p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
 root=Path(__file__).resolve().parents[3]
 dest=Path(a.out);items=[]
 for rel in ["horse-racing/brdb/src/run_brdb_m6_conditional_retrospective.py",
             "horse-racing/brdb/tests/test_run_brdb_m6_conditional_retrospective.py"]:
  b=(root/rel).read_bytes()
  path=dest/"source_bundle"/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b)
  items.append({"path":rel,"sha256":hashlib.sha256(b).hexdigest(),"bytes":len(b)})
 (dest/"source_receipt.json").write_text(json.dumps(items,sort_keys=True))
 print("SOURCE_ONLY",len(items))
if __name__=="__main__": main()
