#!/usr/bin/env python3
"""Read-only audit of candidate BRDB generation, sentinel and lineage completeness."""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--generation-root",type=Path,required=True)
    p.add_argument("--output-json",type=Path,required=True)
    a=p.parse_args()
    roots=list(a.generation_root.rglob("pedigree_fact.parquet"))
    if len(roots)!=1: raise ValueError(f"expected one generation: {len(roots)}")
    root=roots[0].parent
    import duckdb
    con=duckdb.connect(":memory:")
    try:
        profiles=con.execute("SELECT horse_id, profile_data_date, sire_line_code, broodmare_sire_line_code FROM read_parquet(?)",[str(root/"pedigree_fact.parquet")]).fetchall()
        relations=con.execute("SELECT role, parent_birth_year, resolution_status, child_horse_id FROM read_parquet(?)",[str(root/"parent_relation.parquet")]).fetchall()
        lines=con.execute("SELECT lineage_code FROM read_parquet(?)",[str(root/"lineage_code_master.parquet")]).fetchall()
    finally:con.close()
    ids={r[0] for r in profiles};codes={r[0] for r in lines}
    sentinel=[r[0] for r in profiles if r[1]=="99999999"]
    suspicious_dates=[(r[0],r[1]) for r in profiles if not str(r[1]).isdigit() or len(str(r[1]))!=8 or str(r[1])[:4] not in [str(y) for y in range(1900,2101)]]
    by_year=Counter()
    statuses=Counter()
    for role,birth,status,child in relations:
        if status not in ("RESOLVED_EXACT","RESOLVED_ALIAS"):
            by_year[(str(birth) if birth is not None else "UNKNOWN",str(role),str(status))]+=1
            statuses[(str(role),str(status))]+=1
    def dimension(index):
        present=sum(bool(str(row[index] or "").strip()) for row in profiles)
        mapped=sum(str(row[index] or "").strip() in codes for row in profiles)
        return {"present":present,"mapped":mapped,"unknown":len(profiles)-mapped,"population":len(profiles)}
    results={
        "generation_id":root.name.replace("brdb-pedigree-generation-",""),
        "profile_count":len(profiles),
        "sentinel_profile_count":len(sentinel),
        "sentinel_profile_horse_ids":sorted(sentinel),
        "suspicious_profile_data_dates":suspicious_dates[:100],
        "official_lineage_master_codes":len(codes),
        "sire_lineage":dimension(2),
        "broodmare_sire_lineage":dimension(3),
        "unresolved_relation_status":{f"{role}|{status}":n for (role,status),n in sorted(statuses.items())},
        "unresolved_parent_birth_year": [
            {"year":year,"role":role,"status":status,"relations":n}
            for (year,role,status),n in sorted(by_year.items())
        ],
        "production_cutover":False,
        "regional_ancestry_tag_supported":False
    }
    a.output_json.parent.mkdir(parents=True,exist_ok=True)
    if a.output_json.exists(): raise FileExistsError(a.output_json)
    a.output_json.write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in results.items() if k not in ("unresolved_parent_birth_year","suspicious_profile_data_dates")},ensure_ascii=False))


if __name__=="__main__":main()
