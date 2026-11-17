"""Resolve the five held Stage3B root identities using explicit, source-backed aliases.

No transliteration, fuzzy match, name-only fallback, or JRDB ID inference is allowed.
Existing 45 accepted root decisions are copied unchanged into a new v0.2 decision set.
"""
from __future__ import annotations
import argparse, copy, json, re
from pathlib import Path

COUNTRY_SUFFIX=re.compile(r"\([A-Z]{2,3}\)$")
HELD={"リアルスティール","シンボリクリスエス","ヘニーヒューズ","モズアスコット","タワーオブロンドン"}
JRDB_ROOTS=HELD-{"ヘニーヒューズ"}

class ResolutionError(ValueError): pass
def require(ok,msg):
    if not ok: raise ResolutionError(msg)
def clean(s):
    return COUNTRY_SUFFIX.sub("",(s or "").strip())
def alias_index(payload):
    require(payload.get("schema_version")=="brdb-stage3b-root-parent-aliases-research-v0.1","alias schema drift")
    out={}
    for a in payload.get("aliases",[]):
        key=(a["target"],a["role"])
        require(key not in out,"duplicate target/role alias")
        require(a["target"] in HELD and a["role"] in ("sire","dam"),"alias outside held-root scope")
        out[key]=(clean(a["jrdb"]),clean(a["external"]))
    return out
def equivalent(target,role,jrdb,external,aliases):
    a,b=clean(jrdb),clean(external)
    if a==b:return True,"EXACT_AFTER_COUNTRY_SUFFIX"
    pair=aliases.get((target,role))
    return (pair is not None and (a,b)==pair,
            "EXPLICIT_ALIAS" if pair is not None and (a,b)==pair else "MISMATCH")

def resolve(fixed_audit,old_decisions,evidence,aliases_payload,seed):
    require(fixed_audit.get("schema_version")=="brdb-stage3b-root-identity-debt-audit-v0.1","fixed audit schema drift")
    require(fixed_audit.get("source_generation")=="5279af0bd8226cde","source generation drift")
    require(fixed_audit.get("no_name_fallback") is True and fixed_audit.get("prediction_safe") is False,"fixed audit boundary drift")
    require(old_decisions.get("schema_version")=="brdb-stage4-root-decisions-v0.1","old decision schema drift")
    decisions=old_decisions.get("decisions",[])
    require(len(decisions)==50 and sum(1 for x in decisions if x.get("approved"))==45,"expected frozen 45/50 baseline")
    old_by_name={x["name"]:x for x in decisions}
    require(set(x["name"] for x in decisions if not x["approved"])==HELD,"held-root baseline changed")
    ext={p["name"]:p for p in evidence.get("profiles",[])}
    require(set(ext)==HELD and evidence.get("prediction_safe") is False,"external evidence set drift")
    aliases=alias_index(aliases_payload)
    audit={x["target_label"]:x for x in fixed_audit["targets"]}
    seed_by_name={x["jrdb_observed_label"]:x for x in seed.get("pedigrees",[])}
    resolved={}
    for name in sorted(JRDB_ROOTS):
        row=audit[name]; p=ext[name]
        require(row.get("lookup")=="EXACT_HORSE_ID" and re.fullmatch(r"\d{8}",row.get("horse_id","")),"JRDB root missing")
        require(row["horse_name"]==name and row["birth_date"]==p["birth_date"] and row["sex_code"]=="1" and p["sex"]=="牡","root name/date/sex mismatch")
        require(row["sire_birth_year"]==p["sire_birth_year"] and row["dam_birth_year"]==p["dam_birth_year"],"parent birth-year mismatch")
        sire_ok,sire_basis=equivalent(name,"sire",row["sire_name"],p["sire"],aliases)
        dam_ok,dam_basis=equivalent(name,"dam",row["dam_name"],p["dam"],aliases)
        require(sire_ok and dam_ok,"parent identity mismatch")
        resolved[name]={
          "rank":old_by_name[name]["rank"],"name":name,"jbis_id":p["jbis_id"],"jrdb_horse_id":row["horse_id"],
          "approved":True,"basis":"MULTI_FIELD_EXACT_WITH_EXPLICIT_PARENT_ALIAS",
          "guards":{"name":True,"birth_date":True,"sex":True,"sire_birth_year":True,"dam_birth_year":True,
                    "sire_name":sire_basis,"dam_name":dam_basis},
          "evidence_urls":[p["jbis_url"],p["jra_url"]],
          "research_only":True,"prediction_safe":False,"historical_asof_status":"AS_OF_UNVERIFIED"
        }

    name="ヘニーヒューズ"; row=audit[name]; p=ext[name]; seedrow=seed_by_name[name]
    require(row.get("lookup")=="MULTI_GUARD_CANDIDATES" and row.get("candidate_count")==0,"unexpected JRDB Henny profile")
    require(seedrow["jbis_horse_id"]==p["jbis_id"] and int(p["birth_date"][:4])==2003 and p["sex"]=="牡","Henny source root mismatch")
    sire_ok,sire_basis=equivalent(name,"sire",seedrow["source_name_paths"]["S"],p["sire"],aliases)
    dam_ok,dam_basis=equivalent(name,"dam",seedrow["source_name_paths"]["D"],p["dam"],aliases)
    require(sire_ok and dam_ok,"Henny seed/profile parent mismatch")
    resolved[name]={
      "rank":old_by_name[name]["rank"],"name":name,"jbis_id":p["jbis_id"],"jrdb_horse_id":None,
      "approved":True,"basis":"EXTERNAL_PROFILE_AND_SEED_MATCH_WITH_EXPLICIT_PARENT_ALIAS",
      "guards":{"birth_year":True,"sex":True,"same_jbis_id":True,"sire_name":sire_basis,"dam_name":dam_basis},
      "evidence_urls":[p["jbis_url"]],"research_only":True,"prediction_safe":False,
      "historical_asof_status":"AS_OF_UNVERIFIED"
    }

    v2=[]
    for old in decisions:
        if old["name"] in resolved: v2.append(resolved[old["name"]])
        else:
            item=copy.deepcopy(old)
            item["carried_from_v0_1"]=True
            v2.append(item)
    require(len(v2)==50 and all(x.get("approved") is True for x in v2),"v0.2 root set not fully reviewed")
    return {
      "schema_version":"brdb-stage3b-root-decisions-research-v0.2",
      "source_generation":"5279af0bd8226cde",
      "research_only":True,"prediction_safe":False,"historical_asof_status":"AS_OF_UNVERIFIED",
      "policy":"EXPLICIT_SOURCE_BACKED_ALIAS_ONLY_NO_FUZZY_NO_TRANSLITERATION",
      "baseline_approved":45,"newly_resolved":5,"approved_total":50,
      "resolved_names":sorted(resolved),
      "decisions":v2,
    }

def main():
    p=argparse.ArgumentParser()
    for n in ("fixed-audit","old-decisions","evidence","aliases","seed","output"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    out=resolve(
      json.loads(a.fixed_audit.read_text(encoding="utf-8")),
      json.loads(a.old_decisions.read_text(encoding="utf-8")),
      json.loads(a.evidence.read_text(encoding="utf-8")),
      json.loads(a.aliases.read_text(encoding="utf-8")),
      json.loads(a.seed.read_text(encoding="utf-8")),
    )
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","approved_total":out["approved_total"],"newly_resolved":out["newly_resolved"]},sort_keys=True))
if __name__=="__main__": main()
