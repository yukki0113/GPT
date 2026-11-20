#!/usr/bin/env python3
"""Join a private decrypted v0.6 horse-level result with private M7 relative detail locally."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from brdb_going_multilane_discovery import attach_relative_conditions,VERSION as V06
from brdb_going_private_acceptance import load_relatives_detail,aggregate_receipt,require

VERSION='brdb-going-private-existing-join-v0.1-candidate'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run(v06_path:Path,relative_path:Path,private_output:Path,aggregate_output:Path):
    base=json.loads(v06_path.read_text(encoding='utf-8'))
    require(base.get('contract_version')==V06,'v0.6 contract')
    require(base.get('release_status')=='RESEARCH_ONLY','v0.6 release')
    race=base['race'];horses=[{'horse_no':h['horse_no'],'horse_id':h['horse_id']} for h in base['horses']]
    require(len(horses)==race['field_size'],'v0.6 cohort size')
    relmap,relreceipt=load_relatives_detail(relative_path,race,horses)
    out=attach_relative_conditions(base,relmap)
    receipt=aggregate_receipt(out,relreceipt)
    receipt['join_contract']=VERSION
    receipt['v06_input_sha256']=sha(v06_path)
    private_output.parent.mkdir(parents=True,exist_ok=True);aggregate_output.parent.mkdir(parents=True,exist_ok=True)
    private_output.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    aggregate_output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return out,receipt

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--v06-input',required=True);ap.add_argument('--relative-detail',required=True)
    ap.add_argument('--private-output',required=True);ap.add_argument('--aggregate-output',required=True);a=ap.parse_args()
    _,r=run(Path(a.v06_input),Path(a.relative_detail),Path(a.private_output),Path(a.aggregate_output))
    print(json.dumps({'status':r['status'],'horse_count':r['horse_count'],'relative_condition_link_count':r['relative_condition_link_count']},ensure_ascii=False))
if __name__=='__main__':main()
