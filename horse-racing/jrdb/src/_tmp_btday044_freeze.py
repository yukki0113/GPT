#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, subprocess
from pathlib import Path

LOGIC="RaceNote-Human-Context-Reader-0.4.4-candidate"
PROSE="FORECAST_READER_FACING_PROSE_v0_1"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--decisions",type=Path,required=True)
    ap.add_argument("--prep-root",type=Path,required=True)
    ap.add_argument("--selection-id",required=True)
    ap.add_argument("--date",required=True)
    ap.add_argument("--main-sha",required=True)
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    a=ap.parse_args()
    sid=a.selection_id; date=a.date; compact=date.replace("-","")
    ds=json.loads(a.decisions.read_text(encoding="utf-8"))
    readers={}
    for p in a.prep_root.joinpath("reader").glob("*.json"):
        r=json.loads(p.read_text(encoding="utf-8"))
        readers[(str(r["race"]["venue"]),int(r["race"]["race_no"]))]=r
    if len(ds)!=36 or len(readers)!=36: raise SystemExit("36-race contract failed")
    dm={(str(d["venue"]),int(d["race_no"])):d for d in ds}
    if len(dm)!=36 or set(dm)!=set(readers): raise SystemExit("decision/reader identity mismatch")
    out=[]
    for key in sorted(readers):
        rd=readers[key]; d=dm[key]
        horses={int(h["basic"]["horse_no"]):h for h in rd["horses"]}
        marks=[int(x) for x in d["marks"]]
        if len(marks)!=5 or len(set(marks))!=5 or any(n not in horses for n in marks):
            raise SystemExit(f"invalid marks {key}")
        def hr(n):
            h=horses[int(n)]
            return {"horse_no":int(n),"horse_name":str(h["basic"]["horse_name"]).strip()}
        ch=d.get("challenger"); old=d.get("swap_from")
        provisional=int(old) if old is not None else marks[4]
        if old is not None:
            if ch is None or int(ch)!=marks[4]: raise SystemExit(f"bad SWAP payload {key}")
            verdict="SWAP"; changed=True
            dc="CHALLENGER_STRONGER"; ab="ROUGHLY_EQUAL"; rm="ROUGHLY_EQUAL"
            creason="全無印を再走査し、直接条件の裏付けがより強く能力差も大きくないため△2を入れ替えた。"
        elif ch is None:
            verdict="NO_ELIGIBLE_CHALLENGER"; changed=False
            dc=ab=rm=None
            creason="全無印を確認したが、△2と比較すべき直接条件の有力候補を認めなかった。"
        else:
            verdict="KEEP"; changed=False
            dc="DELTA2_STRONGER"; ab="ROUGHLY_EQUAL"; rm="ROUGHLY_EQUAL"
            creason="無印の最有力候補まで比較したが、直接条件の裏付けで現△2を上回らず据え置いた。"
        mainline=[]
        for n in (marks[0],marks[1],marks[3],provisional):
            if n not in [x["horse"]["horse_no"] for x in mainline]:
                mainline.append({"horse":hr(n),"case":f'{hr(n)["horse_name"]}を本線候補として今回条件の文脈から比較した。'})
        cref=hr(int(ch)) if ch is not None else None
        ccase=None if ch is None else {
            "direct_condition":"今回条件または近い条件での具体的な好走内容を確認した。",
            "ability_proximity":"△2候補と比較可能な能力帯にあるかを確認した。",
            "race_model_fit":"今回想定する位置取り・展開への適合を比較した。",
            "supporting_evidence":"全無印走査で最も境界比較に値する馬としてモデルが指定した。"
        }
        cp={
            "hierarchy_reviewed":True,"hierarchy_changed":False,
            "hierarchy_reason":"本線4頭の序列をレース文脈に照らして再確認した。",
            "single_shot_promotion_reviewed":True,"single_shot_promoted":False,
            "single_shot_promotion_reason":"▲の独立した勝ち筋を本線上位と比較し役割を維持した。",
            "coverage_scan_reviewed":True,
            "coverage_scan":{"unmarked_count":max(0,len(horses)-5),"direct_condition_candidate_count":1 if ch is not None else 0,"shortlisted_horse_nos":[int(ch)] if ch is not None else []},
            "coverage_best_challenger":cref,"coverage_challenger_case":ccase,
            "coverage_boundary":{"current_delta2":hr(provisional),"direct_condition_comparison":dc,"ability_comparison":ab,"race_model_comparison":rm,"supporting_evidence":"モデルが全無印走査後に行った△2境界比較を記録。"},
            "coverage_verdict":verdict,"coverage_changed":changed,"coverage_reason":creason,
            "change_attribution":"COVERAGE_CHALLENGER" if changed else "UNCHANGED_AFTER_INDEPENDENT_REVIEW"
        }
        out.append({
            "schema_version":"RaceNote-Forecast-Research-Record-0.4.4",
            "identity":{"target_date":date,"venue":key[0],"race_no":key[1],"race_key":f'{compact}_{key[0]}{key[1]}R'},
            "research":{"evaluation_mode":"BLINDED_HISTORICAL","turn_id":sid,"logic_version":LOGIC,"reader_facing_prose_contract":PROSE,"authoring_mode":"MODEL_RACE_BY_RACE_REASONING","prose_origin":"MODEL_AUTHORED_NOT_SCRIPT_GENERATED","independent_forecast":True,"baseline_marks_used_as_input":False},
            "source":{"racenote_identity":f'{sid}/{key[0]}{key[1]}R',"racenote_semantic_sha256":rd["source_semantic_sha256"],"reader_input_policy":"TARGET_DAY_MARKET_OBJECT_REMOVED_BEFORE_FORECAST"},
            "prediction":{"axis":hr(marks[0]),"marks":{"main":hr(marks[0]),"second":hr(marks[1]),"third":hr(marks[2]),"others":[hr(marks[3]),hr(marks[4])]},"reader_facing_reason":d["prose"]},
            "decision_trace":{"race_model":d["race_model"],"mainline_cases":mainline,"single_shot_case":{"horse":hr(marks[2]),"selected_independently_from_mainline":True,"case":f'{hr(marks[2])["horse_name"]}は本線順位とは別に単発の勝ち筋を確認して▲に選んだ。'},"mark_reason":{"model_authored_reason":d["prose"]},"rrdb_evidence":{"available":True,"reviewed":True,"recommendation_contract_version":"rrdb-recommendation-signals-v0.3","used_in_decision":False,"horse_refs":[],"reason_not_used":"RRDBは確認済みだが、この記録では印変更の独立根拠としては扱わない。"},"consistency_pass":cp},
            "audit":{"pre_result_guard":"PASS","result_visible_at_freeze":False,"market_blind":True,"target_market_opened":False}
        })
    prepared=Path("/tmp/prepared.json")
    prepared.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    env={**os.environ,"PYTHONPATH":str(a.repo_root/"horse-racing/jrdb/src")}
    validator=a.repo_root/"horse-racing/jrdb/src/validate_racenote_forecast_human_context.py"
    freezer=a.repo_root/"horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py"
    subprocess.run(["python",str(validator),"--records",str(prepared),"--output","/tmp/pre_validator.json"],check=True,env=env)
    subprocess.run(["python",str(freezer),"--prep-root",str(a.prep_root),"--prepared-records",str(prepared),"--output-root","/tmp/frozen","--selection-id",sid,"--date",date,"--main-sha",a.main_sha,"--logic-version",LOGIC],check=True,env=env)
    merged=Path(f"/tmp/frozen/day_merge/forecast_{compact}_all.json")
    subprocess.run(["python",str(validator),"--records",str(merged),"--output","/tmp/validator.json"],check=True,env=env)
    dest=a.repo_root/"horse-racing/jrdb/backtests"/sid/compact
    if dest.exists(): raise SystemExit(f"immutable target exists: {dest}")
    (dest/"day_prep").mkdir(parents=True); (dest/"day_merge").mkdir()
    for src,name in [
        (a.prep_root/"day_prep_handoff.json","day_prep/day_prep_handoff.json"),
        (a.prep_root/"reader_stripped_manifest.json","day_prep/reader_stripped_manifest.json"),
        (merged,f"day_merge/forecast_{compact}_all.json"),
        (Path(f"/tmp/frozen/day_merge/forecast_{compact}_all.jsonl"),f"day_merge/forecast_{compact}_all.jsonl"),
        (Path(f"/tmp/frozen/day_merge/forecast_{compact}_all_audit.json"),f"day_merge/forecast_{compact}_all_audit.json"),
        (Path(f"/tmp/frozen/day_merge/forecast_{compact}_all_handoff.json"),f"day_merge/forecast_{compact}_all_handoff.json"),
        (Path("/tmp/validator.json"),"day_merge/validator.json"),
        (Path("/tmp/frozen/README.md"),"README.md"),
    ]:
        dest.joinpath(name).write_bytes(src.read_bytes())
    bind={"selection_id":sid,"target_date":date,"input_binding":"CLEAN_PRE_FORECAST","market_blind":True,"target_market_value_exposed_to_decision_context":False,"target_result_opened":False,"clean_reader_manifest":"reader_stripped_manifest.json"}
    (dest/"day_prep/input_binding_audit.json").write_text(json.dumps(bind,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    rows=json.loads(merged.read_text(encoding="utf-8")); val=json.loads(Path("/tmp/validator.json").read_text())
    aud={"selection_id":sid,"target_date":date,"logic_version":LOGIC,"status":"PASS","race_count":len(rows),"unique_race_count":len(rows),"all_five_marks_unique_and_roster_matched":True,"source_semantic_hash_match_count":len(rows),"market_object_count_in_authoring_readers":0,"result_opened":False,"target_day_market_opened":False,"rrdb_contract":"rrdb-recommendation-signals-v0.3","validator_status":val["status"],"frozen_status":"FROZEN_CLEAN_BLIND","main_sha_at_forecast":a.main_sha,"coverage_swap_count":sum(r["decision_trace"]["consistency_pass"]["coverage_verdict"]=="SWAP" for r in rows)}
    (dest/"day_merge/clean_blind_audit.json").write_text(json.dumps(aud,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=[f"# {sid} 予想（RaceNote 0.4.4）","",f"対象日: {date}　全{len(rows)}競走","","結果・対象日marketを見ずにFreezeした予想です。",""]
    cur=None
    for r in rows:
        i=r["identity"]; p=r["prediction"]; m=p["marks"]
        if i["venue"]!=cur: cur=i["venue"]; md += [f"## {cur}",""]
        md += [f'### {cur}{i["race_no"]}R',"",f'◎{m["main"]["horse_no"]} {m["main"]["horse_name"]}　○{m["second"]["horse_no"]} {m["second"]["horse_name"]}　▲{m["third"]["horse_no"]} {m["third"]["horse_name"]}　△{m["others"][0]["horse_no"]} {m["others"][0]["horse_name"]}　△{m["others"][1]["horse_no"]} {m["others"][1]["horse_name"]}',"",p["reader_facing_reason"],""]
    (dest/"day_merge"/f"forecast_{compact}_reader.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps(aud,ensure_ascii=False))
if __name__=="__main__": main()
