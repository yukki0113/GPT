#!/usr/bin/env python3
"""Conservative race-day provenance audit for one SHA-pinned PACI archive.

Attests only that the exact bytes currently observed in the user's canonical
Drive folder had no Drive content modification after a recorded pre-off time.
It does not attest JRDB provider release time and never promotes D3 or D4 to
prediction-safe.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys, zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'horse-racing/jrdb/src'))
from jrdb_raw import Parser, canonical_members, split_fixed_records  # noqa:E402

JST=ZoneInfo('Asia/Tokyo')

class ProvenanceError(ValueError): pass
def require(x,msg):
    if not x: raise ProvenanceError(msg)
def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def iso(s):
    try: d=datetime.fromisoformat(s.replace('Z','+00:00'))
    except Exception as e: raise ProvenanceError('invalid Drive timestamp') from e
    require(d.tzinfo is not None,'Drive timestamp must be timezone aware')
    return d

def audit(*,paci:Path,race_key:str,drive_metadata:dict,expected_sha256:str,
          expected_parent_id:str)->dict:
    require(re.fullmatch(r'[0-9a-f]{64}',expected_sha256) is not None,'invalid expected SHA')
    actual=sha256(paci); require(actual==expected_sha256,'PACI SHA mismatch')
    require(drive_metadata.get('title')==paci.name,'Drive filename mismatch')
    require(str(drive_metadata.get('size'))==str(paci.stat().st_size),'Drive size mismatch')
    require(expected_parent_id in (drive_metadata.get('parent_ids') or []),'wrong Drive parent')
    created=iso(drive_metadata.get('created_time'))
    modified=iso(drive_metadata.get('modified_time'))
    require(modified>=created,'Drive modified_time precedes created_time')

    parser=Parser()
    with zipfile.ZipFile(paci) as z:
        require(z.testzip() is None,'PACI ZIP CRC failure')
        members=canonical_members(z,'BAC'); require(members,'BAC missing')
        races=[]
        for member in members:
            for rec in split_fixed_records(z.read(member),'BAC'):
                row=parser.bac(rec)
                if row['race_key_raw']==race_key: races.append(row)
    require(len(races)==1,'missing or duplicate BAC race')
    race=races[0]
    require(re.fullmatch(r'20\d{6}',race['date_raw']) is not None,'invalid BAC date')
    require(re.fullmatch(r'\d{4}',race['post_time_raw']) is not None,'invalid BAC post time')
    ymd=race['date_raw']; hm=race['post_time_raw']
    off=datetime(int(ymd[:4]),int(ymd[4:6]),int(ymd[6:]),int(hm[:2]),int(hm[2:]),tzinfo=JST)
    created_jst=created.astimezone(JST); modified_jst=modified.astimezone(JST)

    preoff=created_jst < off and modified_jst < off
    status='PRE_OFF_DRIVE_BYTES_ATTESTED' if preoff else 'PRE_OFF_NOT_ATTESTED'
    return {
      'status':'PASS',
      'research_only':True,
      'prediction_safe':False,
      'race_key':race_key,
      'race_date':f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}',
      'scheduled_post_time_jst':off.isoformat(),
      'source_archive':paci.name,
      'source_archive_sha256':actual,
      'drive_file_id':drive_metadata.get('id'),
      'drive_parent_id':expected_parent_id,
      'drive_created_time':created.isoformat(),
      'drive_modified_time':modified.isoformat(),
      'drive_created_time_jst':created_jst.isoformat(),
      'drive_modified_time_jst':modified_jst.isoformat(),
      'paci_acquisition_status':status,
      'provider_release_status':'UNKNOWN_NOT_ATTESTED',
      'd3_historical_asof_status':'AS_OF_UNVERIFIED_UNCHANGED',
      'interpretation':'EXACT_PACI_BYTES_OBSERVED_IN_CANONICAL_DRIVE_PRE_OFF' if preoff else 'PRE_OFF_PACI_BYTES_NOT_PROVEN',
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--paci',type=Path,required=True); p.add_argument('--race-key',required=True)
    p.add_argument('--drive-metadata',type=Path,required=True); p.add_argument('--expected-sha256',required=True)
    p.add_argument('--expected-parent-id',required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); meta=json.loads(a.drive_metadata.read_text(encoding='utf-8'))
    out=audit(paci=a.paci,race_key=a.race_key,drive_metadata=meta,expected_sha256=a.expected_sha256,expected_parent_id=a.expected_parent_id)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=='__main__': main()
