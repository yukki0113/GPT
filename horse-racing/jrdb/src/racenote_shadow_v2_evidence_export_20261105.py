#!/usr/bin/env python3
"""Result-blind per-race evidence export for human/LLM Shadow v2 review.
Does not assign any Shadow label. Reads only frozen pre-result readers/decisions.
"""
import argparse,json,re
from pathlib import Path
DAYS={162:"20250503",163:"20250510",164:"20250928",165:"20250322",166:"20250209",167:"20250614",168:"20250330",169:"20251108",170:"20250915",171:"20250301"}
def read(path):return json.loads(path.read_text(encoding="utf-8"))
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo-root",required=True,type=Path);p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--days",required=True,nargs="+",type=int);a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    out=[];counts={}
    for n in a.days:
        d=DAYS[n];root=a.repo_root/f"horse-racing/jrdb/backtests/BTDAY-{n:04d}/{d}/v056"
        pr=read(root/"frozen/records.json");cf=read(root/"confidence_frozen/records.json")
        pred={(x["venue"],int(x["race_no"])):x for x in pr}
        count=0
        for c in cf:
            if c["confidence"] not in ("B","C"):continue
            venue,no=c["venue"],int(c["race_no"]);key=(venue,no)
            core=pred[key]["decision_core"];marks=list(map(int,core["marks"]))
            if int(c["honmei"])!=marks[0]:raise RuntimeError("unmatched marks")
            reader=read(root/"reader"/f"racenote_reader_{d}_{venue}{no}R.json")
            hi={int(h["identity"]["horse_no"]):h for h in reader["horses"]}
            horses=[]
            for mark,nohorse in zip(["◎","○","▲","△1","△2"],marks):
                h=hi[nohorse];o=h.get("other_context") or {};hist=o.get("historical_profile") or {}
                rev=((o.get("racereview") or {}).get("history_profile") or {})
                recent=[]
                for x in (o.get("recent_runs") or [])[:4]:
                    z=x.get("race") or {};res=x.get("result") or {};perf=x.get("performance") or {};notes=x.get("notes") or {}
                    recent.append({"date":z.get("date"),"venue":z.get("venue"),"surface":z.get("surface"),"distance":z.get("distance_m"),"class":z.get("class"),"finish":res.get("finish"),"field_size":z.get("field_size"),"idm":perf.get("idm"),"corners":perf.get("corners"),"comment":(notes.get("race_comment") or "")[:95],"special":(notes.get("special_notes") or [])[:5]})
                horses.append({"mark":mark,"no":nohorse,"name":h["identity"]["horse_name"],
                               "career":hist.get("career"),"same_distance":hist.get("same_distance"),"same_venue":hist.get("same_venue"),
                               "recent":recent,"positive":[{"code":x.get("code"),"facts":x.get("facts")} for x in rev.get("primary_positive",[])][:3],
                               "concerns":[{"code":x.get("code"),"facts":x.get("facts")} for x in rev.get("concerns",[])][:3],
                               "fragile":(rev.get("fragile_form") or {}).get("status"),
                               "pace":(((h.get("evidence") or {}).get("PACE_POSITION") or {}).get("S") or {}).get("running_style")})
            out.append({"btday":n,"date":d,"venue":venue,"race_no":no,"grade":c["confidence"],"marks":marks,
                        "race":{"surface":reader["race"].get("surface"),"distance":reader["race"].get("distance_m"),"class":reader["race"].get("class"),"field":reader["race"].get("field_size")},
                        "prediction_positive":core["honmei_win"]["evidence"],"prediction_risk":core["honmei_win"]["main_risk"],
                        "confidence_review":c.get("confidence_review"),"horses":horses})
            count+=1
        counts[n]=count
    (a.output_dir/"evidence.json").write_text(json.dumps({"rows":out,"counts":counts,"results_consulted":False},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"days":a.days,"counts":counts,"total":len(out),"results_consulted":False},ensure_ascii=False))
if __name__=="__main__":main()
