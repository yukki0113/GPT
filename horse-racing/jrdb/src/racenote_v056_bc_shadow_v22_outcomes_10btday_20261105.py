#!/usr/bin/env python3
"""Read-only 10-BTDAY frozen pre-result Shadow B/C analysis using canonical JRDB SED/HJC.
All betting tickets pre-specified. Original Prediction and Confidence remain immutable.
"""
from __future__ import annotations
import argparse,csv,hashlib,itertools,json
from collections import Counter
from pathlib import Path
from jrdb_result_query import query_results

DAYS={162:"20250503",163:"20250510",164:"20250928",165:"20250322",166:"20250209",167:"20250614",168:"20250330",169:"20251108",170:"20250915",171:"20250301"}
GENERATION="jrdb_normalized_warehouse_v1_2010_2025_g20260921"
EXPECTED={162:(36,None,15,12,None),163:(36,None,22,10,None),164:(24,None,14,3,None),165:(36,None,18,10,None),166:(36,None,19,5,None),167:(36,None,20,2,None),168:(36,None,19,4,None),169:(36,None,19,1,None),170:(24,None,12,2,None),171:(36,None,19,5,None)}
STRATEGIES=("win_honmei_1","place_honmei_1","quinella_honmei_4","quinella_box_10","trio_honmei_6","trio_honmei_second_3","trio_box_10")
BET_TYPES={"win_honmei_1":"win","place_honmei_1":"place","quinella_honmei_4":"quinella","quinella_box_10":"quinella","trio_honmei_6":"trio","trio_honmei_second_3":"trio","trio_box_10":"trio"}

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def tickets(marks):
    a,b,c,d,e=map(int,marks);o=(b,c,d,e)
    return {
        "win_honmei_1":{(a,)},
        "place_honmei_1":{(a,)},
        "quinella_honmei_4":{tuple(sorted((a,x))) for x in o},
        "quinella_box_10":{tuple(sorted(p)) for p in itertools.combinations(marks,2)},
        "trio_honmei_6":{tuple(sorted((a,x,y))) for x,y in itertools.combinations(o,2)},
        "trio_honmei_second_3":{tuple(sorted((a,b,x))) for x in (c,d,e)},
        "trio_box_10":{tuple(sorted(p)) for p in itertools.combinations(marks,3)}
    }
def score(result, strategy, planned):
    payouts=result["payouts"].get(BET_TYPES[strategy])
    if not isinstance(payouts,list):
        raise RuntimeError("Missing canonical payout "+str(result["race_key"]))
    win=sum(int(p["payout_yen"]) for p in payouts if tuple(sorted(map(int,p["numbers"]))) in planned)
    return {"hit":int(win>0),"stake":100*len(planned),"return":win}
def summary(rows):
    output={"races":len(rows),"honmei_win":sum(x["honmei_win"] for x in rows),"honmei_top3":sum(x["honmei_top3"] for x in rows),
            "honmei_win_pct":round(sum(x["honmei_win"] for x in rows)*100/len(rows),2) if rows else None,
            "honmei_top3_pct":round(sum(x["honmei_top3"] for x in rows)*100/len(rows),2) if rows else None,"strategies":{}}
    for s in STRATEGIES:
        stake=sum(x["strategies"][s]["stake"] for x in rows)
        ret=sum(x["strategies"][s]["return"] for x in rows)
        hits=sum(x["strategies"][s]["hit"] for x in rows)
        output["strategies"][s]={"hits":hits,"hit_pct":round(hits*100/len(rows),2) if rows else None,
            "stake_yen":stake,"return_yen":ret,"net_yen":ret-stake,"roi_pct":round(100*ret/stake,2) if stake else None}
    return output
def check_handoff(h,session,status):
    for name in ("session_id","selection_id","target_date","contract_revision"):
        if h.get(name)!=session.get(name): raise RuntimeError("handoff mismatch "+name)
    if h.get("status")!=status or h.get("result_opened") is not False or h.get("target_market_opened") is not False:
        raise RuntimeError("Invalid blind Freeze "+status)
def main():
    p=argparse.ArgumentParser()
    for key in ("repo-root","warehouse-root","warehouse-manifest","output-dir"):p.add_argument("--"+key,required=True,type=Path)
    args=p.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    freeze={};audit=[];canoncounts=Counter();transitions=Counter()
    for n,date in DAYS.items():
        root=args.repo_root/f"horse-racing/jrdb/backtests/BTDAY-{n:04d}/{date}/v056"
        session=read(root/"session.json")
        pred=read(root/"frozen/records.json")
        conf=read(root/"confidence_frozen/records.json")
        ph=read(root/"frozen/day_handoff.json")
        ch=read(root/"confidence_frozen/day_handoff.json")
        t2=read(root/"turn2_summary.json")
        check_handoff(ph,session,"PREDICTION_FROZEN_CLEAN_BLIND")
        check_handoff(ch,session,"CONFIDENCE_FROZEN_CLEAN_BLIND")
        predsha=digest(root/"frozen/records.json");confsha=digest(root/"confidence_frozen/records.json")
        if ph.get("records_sha256")!=predsha or ch.get("confidence_records_sha256")!=confsha or ch.get("prediction_records_sha256")!=predsha:
            raise RuntimeError(f"Source SHA mismatch {n}")
        if t2.get("status")!="TURN2_COMPLETE" or t2.get("prediction_records_sha256")!=predsha or t2.get("confidence_records_sha256")!=confsha:
            raise RuntimeError(f"T2 invalid {n}")
        if session.get("contract_revision")!="v056-prediction-confidence-audit-newspaper-v1":
            raise RuntimeError(f"Wrong contract {n}")
        if len(pred)!=len(conf)!=EXPECTED[n][0]:
            raise RuntimeError(f"Prediction cardinality {n}")
        if len(pred)!=EXPECTED[n][0] or len(conf)!=EXPECTED[n][0]:
            raise RuntimeError(f"Wrong cohort cardinality {n}")
        ct=Counter(x["confidence"] for x in conf)
        if ct["B"]!=EXPECTED[n][2] or ct["C"]!=EXPECTED[n][3] or len(conf)!=EXPECTED[n][0]:
            raise RuntimeError(f"Unexpected confidence distribution {n}: {ct}")
        bypred={(x["venue"],int(x["race_no"])):x for x in pred}
        byconf={(x["venue"],int(x["race_no"])):x for x in conf}
        if len(bypred)!=len(pred) or len(byconf)!=len(conf) or set(bypred)!=set(byconf):
            raise RuntimeError(f"Duplicate/missing Freeze race {n}")
        sn="validated_pre_result_v22_20261105.json" if n==162 else "validated_pre_result_20261105.json"
        sp=args.repo_root/f"horse-racing/jrdb/research/bc_shadow_v2/BTDAY-{n:04d}/{sn}"
        shadow=read(sp)
        if shadow.get("status")!="SHADOW_BC_DRAFT_VALIDATED_NOT_CANONICAL_FREEZE" or shadow.get("session_id")!=session["session_id"] or shadow.get("selection_id")!=session["selection_id"] or shadow.get("target_date")!=session["target_date"] or shadow.get("prediction_records_sha256")!=predsha or shadow.get("confidence_records_sha256")!=confsha:
            raise RuntimeError(f"Unbound Shadow source {n}")
        shadow_by={(x["venue"],int(x["race_no"])):x for x in shadow["records"]}
        expected_bc={key for key,c in byconf.items() if c["confidence"] in ("B","C")}
        if len(shadow_by)!=len(shadow["records"]) or set(shadow_by)!=expected_bc:
            raise RuntimeError(f"Bad Shadow coverage {n}")
        localtrans=Counter()
        for key,c in byconf.items():
            pr=bypred[key];marks=pr["decision_core"]["marks"]
            if len(marks)!=5 or len(set(marks))!=5 or int(marks[0])!=int(c["honmei"]):
                raise RuntimeError(f"Invalid frozen marks {n} {key}")
            g=c["confidence"];canongrade=g
            if key in shadow_by:
                sh=shadow_by[key]
                if sh["canonical_confidence"]!=g or sh["honmei"]!=int(marks[0]) or sh["shadow_grade"] not in ("B","C") or sh["strongest_rival"] not in marks[1:]:
                    raise RuntimeError(f"Invalid Shadow binding {n} {key}")
                sg=sh["shadow_grade"];localtrans[g+"->"+sg]+=1;transitions[g+"->"+sg]+=1
            else:sg=None
            rowkey=(f"{date[:4]}-{date[4:6]}-{date[6:]}",key[0],key[1])
            if rowkey in freeze:raise RuntimeError("Duplicate across cohort "+str(rowkey))
            evidence_tag="PRE_RACE_PROXY_NO_HISTORY" if sg and "EVIDENCE_SOURCE=PRE_RACE_PROXY_NO_HISTORY" in sh.get("final_reason","") else ("RACE_HISTORY" if sg else None)
            freeze[rowkey]={"evidence_source":evidence_tag,"btday":f"BTDAY-{n:04d}","btday_n":n,"date":rowkey[0],
                           "venue":key[0],"race_no":key[1],"confidence":canongrade,"shadow_grade":sg,
                           "marks":list(map(int,marks)),"honmei":int(marks[0])}
            canoncounts[g]+=1
        if dict(localtrans)!=shadow.get("grade_transitions"):
            raise RuntimeError(f"Shadow transition counts changed {n}")
        audit.append({"btday":n,"date":date,"races":len(pred),"prediction_sha256":predsha,"confidence_sha256":confsha,"shadow_sha256":digest(sp),
                      "shadow_races":len(shadow_by),"transitions":dict(localtrans)})
    if len(freeze)!=336 or canoncounts["B"]!=177 or canoncounts["C"]!=54:
        raise RuntimeError(f"Unexpected total population {len(freeze)} {canoncounts}")
    if sum(transitions.values())!=231 or dict(transitions)!={"B->B":168,"B->C":9,"C->B":9,"C->C":45}:raise RuntimeError(f"Expected pre-frozen transitions: {transitions}")
    results={};query_audit=[]
    for date in sorted({x[0] for x in freeze}):
        response=query_results(date=date,source="warehouse",warehouse_root=args.warehouse_root,
                               warehouse_manifest=args.warehouse_manifest)
        prov=response.get("provenance",{})
        if response.get("status")!="success" or prov.get("web_used") is not False or prov.get("source_generation_id")!=GENERATION:
            raise RuntimeError(f"Canonical query not successful {date}: {response.get('status')}")
        query_audit.append({"date":date,"source_generation":prov.get("source_generation_id"),"race_count":response.get("race_count"),"status":response["status"]})
        for result in response["races"]:
            key=(date,result["venue_name"],int(result["race_no"]))
            if key in results: raise RuntimeError("Duplicate result "+str(key))
            if result.get("result_status")!="available" or result.get("payouts_status")!="available" or result["cross_validation"].get("review_required"):
                raise RuntimeError("Result not fully accepted "+str(key))
            results[key]=result
    if not set(freeze).issubset(results):
        raise RuntimeError("Missing required canonical races "+str(list(set(freeze)-set(results))[:8]))
    rows=[]
    for key,fr in sorted(freeze.items()):
        race=results[key];top3=race["top3"];top3nos={int(x["horse_no"]) for x in top3}
        winners={int(x["horse_no"]) for x in top3 if x["finish"]==1}
        planned=tickets(fr["marks"])
        rows.append({**fr,"honmei_win":int(fr["honmei"] in winners),"honmei_top3":int(fr["honmei"] in top3nos),
                     "strategies":{s:score(race,s,planned[s]) for s in STRATEGIES}})
    groups={
       "canonical":{g:summary([r for r in rows if r["confidence"]==g]) for g in ("A","B","C","Z")},
       "shadow":{g:summary([r for r in rows if r["shadow_grade"]==g]) for g in ("B","C")},
       "transitions":{t:summary([r for r in rows if r["confidence"]+"->"+str(r["shadow_grade"])==t]) for t in ("B->B","B->C","C->B","C->C")},
       "batch_3_3_4":{label:{g:summary([r for r in rows if r["btday_n"] in ns and r["shadow_grade"]==g]) for g in ("B","C")} for label,ns in [
          ("0162_0164",{162,163,164}),("0165_0167",{165,166,167}),("0168_0171",{168,169,170,171})]},
       "daily_shadow":{str(n):{g:summary([r for r in rows if r["btday_n"]==n and r["shadow_grade"]==g]) for g in ("B","C")} for n in DAYS},
       "debut_evidence_source":{tag:summary([r for r in rows if r["evidence_source"]==tag]) for tag in ("PRE_RACE_PROXY_NO_HISTORY","RACE_HISTORY")},
    }
    paired={}
    for grade in ("B","C"):
        grade_rows=[r for r in rows if r["shadow_grade"]==grade]
        a="trio_honmei_6";b="trio_box_10"
        extra_hits=sum(int(r["strategies"][b]["hit"] and not r["strategies"][a]["hit"]) for r in grade_rows)
        extra_stake=sum(r["strategies"][b]["stake"]-r["strategies"][a]["stake"] for r in grade_rows)
        extra_return=sum(r["strategies"][b]["return"]-r["strategies"][a]["return"] for r in grade_rows)
        paired[grade]={"additional_races_hit_box_over_axis":extra_hits,"incremental_stake_yen":extra_stake,
                       "incremental_return_yen":extra_return,"incremental_roi_pct":round(100*extra_return/extra_stake,2) if extra_stake else None}
    report={"status":"PASS","verification":"JRDB post-freeze outcome evaluation; all 10 frozen prior to result read","research_type":"retrospective fixed-frozen-classification evaluation, no postresult shadow adjustments",
            "population":len(rows),"shadow_population":231,"selection_counts":dict(canoncounts),"transitions":dict(transitions),
            "source_generation":GENERATION,"unit_stake_yen":100,"audit":audit,"result_queries":query_audit,
            "groups":groups,"box_incremental":paired,
            "cautions":["BTDAY-0162 debut ◎10 Kyoto R1 has only pre-race proxy evidence; analyze separately.",
                       "BTDAY-0164 and 0170 contain 24 frozen races; score only roster.",
                       "v2.1 U draft is superseded by v2.2 B/C-only pre-result commitment; original v2.1 audit preserved.",
                       "No high payout trimming. Compare to development 0152-0161 cautiously because the v2 rule was motivated by those results."]}
    (out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    fields=["btday","date","venue","race_no","confidence","shadow_grade","evidence_source","honmei","marks","honmei_win","honmei_top3"]
    for s in STRATEGIES:fields.extend([s+"_hit",s+"_stake",s+"_return"])
    with (out/"per_race.csv").open("w",encoding="utf-8-sig",newline="") as fh:
        wr=csv.DictWriter(fh,fieldnames=fields);wr.writeheader()
        for r in rows:
            f={k:r.get(k) for k in fields};f["marks"]="/".join(map(str,r["marks"]))
            for s in STRATEGIES:
                for k in ("hit","stake","return"):f[s+"_"+k]=r["strategies"][s][k]
            wr.writerow(f)
    (out/"checks.txt").write_text("PASS: 10 BTDay, 336R, 231 pre-result Shadow B/C, v2.2 only, all 10 canonical JRDB queries, A/Z untouched\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","counts":dict(canoncounts),"transitions":dict(transitions),
                      "canonical":groups["canonical"],"shadow":groups["shadow"],"paired":paired},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
