#!/usr/bin/env python3
"""Read-only Stage3B root-identity debt audit against fixed research generation.

Outputs only the minimum JRDB profile facts needed to review the five held roots.
No identity is approved here; no fuzzy/name-only crosswalk is created.
"""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path
import duckdb

ZIP_SHA="672c6c1f78f632db60a1f7c2e8304b63e0576e51efef79f0cf473351aa8fd0d4"
PEDIGREE_SHA="1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536"
MEMBER="generation/pedigree_fact.parquet"
KNOWN={
 "リアルスティール":"12104889",
 "シンボリクリスエス":"99110099",
 "モズアスコット":"14110031",
 "タワーオブロンドン":"15101621",
}

class AuditError(ValueError): pass
def require(ok,msg):
    if not ok: raise AuditError(msg)
def sha256_bytes(data:bytes)->str: return hashlib.sha256(data).hexdigest()
def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def execute(source_zip:Path, output:Path)->dict:
    require(sha256_file(source_zip)==ZIP_SHA,"fixed generation ZIP SHA mismatch")
    with zipfile.ZipFile(source_zip) as z:
        require(z.testzip() is None,"generation ZIP CRC failure")
        require(MEMBER in z.namelist(),"pedigree_fact member missing")
        raw=z.read(MEMBER)
    require(sha256_bytes(raw)==PEDIGREE_SHA,"pedigree_fact SHA mismatch")
    parquet=output.parent/"_pedigree_fact.tmp.parquet"
    parquet.parent.mkdir(parents=True,exist_ok=True); parquet.write_bytes(raw)
    con=duckdb.connect()
    try:
        rows=[]
        for name,hid in KNOWN.items():
            got=con.execute("""
              SELECT horse_id, horse_name, birth_date, sex_code, sire_name, dam_name,
                     sire_birth_year, dam_birth_year, sire_line_code
              FROM read_parquet(?) WHERE horse_id=?
            """,[str(parquet),hid]).fetchall()
            require(len(got)==1,f"known root missing/duplicate: {name}")
            r=got[0]
            rows.append(dict(zip(
              ["horse_id","horse_name","birth_date","sex_code","sire_name","dam_name",
               "sire_birth_year","dam_birth_year","sire_line_code"],r
            )) | {"target_label":name,"lookup":"EXACT_HORSE_ID"})

        # Henny Hughes had no bound root in the accepted Stage3B audit. Discover
        # narrowly by immutable profile guards instead of Japanese-name fallback.
        candidates=con.execute("""
          SELECT horse_id, horse_name, birth_date, sex_code, sire_name, dam_name,
                 sire_birth_year, dam_birth_year, sire_line_code
          FROM read_parquet(?)
          WHERE substr(birth_date,1,4)='2003'
            AND sex_code='1'
            AND sire_line_code='1108'
            AND sire_name='Hennessy'
            AND dam_name='Meadow Flyer'
          ORDER BY horse_id
        """,[str(parquet)]).fetchall()
        c=[dict(zip(
          ["horse_id","horse_name","birth_date","sex_code","sire_name","dam_name",
           "sire_birth_year","dam_birth_year","sire_line_code"],r
        )) for r in candidates]
        rows.append({
          "target_label":"ヘニーヒューズ","lookup":"MULTI_GUARD_CANDIDATES",
          "candidate_count":len(c),"candidates":c
        })
    finally:
        con.close()
        parquet.unlink(missing_ok=True)

    payload={
      "schema_version":"brdb-stage3b-root-identity-debt-audit-v0.1",
      "source_generation":"5279af0bd8226cde",
      "source_zip_sha256":ZIP_SHA,
      "pedigree_fact_sha256":PEDIGREE_SHA,
      "research_only":True,"prediction_safe":False,
      "historical_asof_status":"AS_OF_UNVERIFIED",
      "no_name_fallback":True,
      "targets":rows,
    }
    output.write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return payload

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-zip",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    out=execute(a.source_zip,a.output)
    print(json.dumps({"status":"PASS","targets":len(out["targets"])},sort_keys=True))
if __name__=="__main__": main()
