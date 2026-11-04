"""TEMPORARY source-only artifact export; unmerged branch, no licensed JRDB inputs."""
from pathlib import Path
import argparse
import hashlib
import json

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    base=Path(__file__).resolve().parents[3]
    out=Path(args.out)
    paths=[
        "horse-racing/brdb/src/build_brdb_historical_ukc_kyi_candidate.py",
        "horse-racing/brdb/tests/test_build_brdb_historical_ukc_kyi_candidate.py",
        "horse-racing/jrdb/src/jrdb_ukc.py",
        "horse-racing/jrdb/src/jrdb_raw.py",
    ]
    receipt=[]
    for rel in paths:
        data=(base/rel).read_bytes()
        p=out/"source_bundle"/rel
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(data)
        receipt.append({"path":rel,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
    (out/"receipt.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":"PASS","sources":len(receipt)}))
if __name__=="__main__":
    main()
