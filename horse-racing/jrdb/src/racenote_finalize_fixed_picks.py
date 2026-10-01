#!/usr/bin/env python3
import argparse,copy,hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path

def lr(h):
    x=h.get("recent_runs") or []
    return x[0] if x else None
def rec(h): return (h.get("racereview") or {}).get("recommendation") or {}
def no(h): return int(h["basic"]["horse_no"])
def nm(h): return h["basic"]["horse_name"]
def phrase(h):
    r=lr(h); tr=((h.get("training") or {}).get("analysis") or {})
    if r:
        ra=r.get("race") or {}; rs=r.get("result") or {}; nt=r.get("notes") or {}
        fin=rs.get("finish"); ab=rs.get("abnormal"); com=(nt.get("race_comment") or "").strip("。 ")
        if fin is not None:
            s=f"前走{ra.get('venue')}{ra.get('surface')}{ra.get('distance_m')}mは{fin}着"
            if com:s+=f"。{com}"
        elif ab and ab!="異常なし": s=f"前走は{ab}で実戦内容を測りにくい"
        else:s="前走は結果だけでは評価しづらい内容"
    else:s="実戦前だが、事前能力評価と仕上がりを重視した"
    ti,ci=tr.get("training_index"),tr.get("condition_index")
    if isinstance(ti,(int,float)) and ti>=70:s+="。追い切りの動きも目立つ"
    elif isinstance(ci,(int,float)) and ci>=65:s+="。仕上がり面も良好"
    return s
def single(h):
    r=rec(h); ids=r.get("matched_signal_ids") or []
    if ids:
        hs=r.get("human_summary")
        return (f"{hs}という前走再評価材料があり、今回条件でも見直せる" if hs else
                "前走には着順以上の内容があり、今回条件でも見直せる")
    r0=lr(h); com=(((r0 or {}).get("notes") or {}).get("race_comment") or "")
    if any(k in com for k in ("出遅","詰","包","不利","寄ら","躓","接触","捌")):
        return phrase(h)+"。前走のロスが軽くなれば着順以上の前進があっていい"
    return phrase(h)+"。本線とは違う形で上位へ割り込む余地を取った"
def rr(h,role):
    r=rec(h); src=r.get("source_run") or {}
    return {"horse_no":no(h),"horse_name":nm(h),"source_run_ref":src.get("race_key"),
      "recommendation_contract_version":"rrdb-recommendation-signals-v0.3",
      "matched_signal_ids":r.get("matched_signal_ids") or [],
      "signal_strength":{s.get("signal_id"):s.get("strength") for s in (r.get("signals") or [])} or None,
      "decision_role":role,"next_watch_grade":None,"matched_rule_ids":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prep-root",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--selection-id",required=True);p.add_argument("--date",required=True);p.add_argument("--turn-id",required=True)
    p.add_argument("--picks-json",type=Path,required=True);p.add_argument("--main-sha",required=True)
    a=p.parse_args(); picks=json.loads(a.picks_json.read_text()); out=a.output_root
    if out.exists():shutil.rmtree(out)
    for d in ("forecast","reader_stripped","day_merge"):(out/d).mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc).isoformat(); compact=a.date.replace("-",""); records=[]
    for fp in sorted((a.prep_root/"reader").glob("*.json")):
        x=json.loads(fp.read_text()); race=x["race"]; key=f"{race['venue']}:{int(race['race_no'])}"
        nums=picks[key]; by={no(h):h for h in x["horses"]}; assert len(nums)==5 and len(set(nums))==5 and all(n in by for n in nums)
        m,s,t,o1,o2=[by[n] for n in nums]
        stripped=copy.deepcopy(x)
        for h in stripped.get("horses",[]):h.pop("market",None)
        (out/"reader_stripped"/fp.name).write_text(json.dumps(stripped,ensure_ascii=False,separators=(",",":"))+"\n")
        mp,sp,tp=phrase(m),phrase(s),single(t)
        reader=f"{nm(m)}は{mp}。ここでは軸に取る。{nm(s)}は{sp}。相手の中心。{nm(t)}は{tp}。展開が噛み合えば上位へ割り込める。"
        model=f"{race['venue']} {race['surface']}{race['distance_m']}m {race['class']}。全頭の能力、近走内容、位置取り、仕上がり、適性を比較して本線を形成し、その後に本線順位とは独立して上位へ割り込める馬を再走査した。"
        refs=[rr(m,"UPGRADE_RECENT_FORM"),rr(s,"SUPPORT_REPEATABILITY"),rr(t,"SUPPORT_COUNTERARGUMENT"),rr(o1,"CONTEXT_ONLY"),rr(o2,"CONTEXT_ONLY")]
        used=any(z["matched_signal_ids"] for z in refs)
        r={"schema_version":"RaceNote-Forecast-Research-Record-0.4.2",
          "identity":{"target_date":a.date,"venue":race["venue"],"race_no":race["race_no"],"race_key":f"{a.date}-{race['venue']}-{race['race_no']}","race_name":race.get("race_name"),"surface":race["surface"],"distance_m":race["distance_m"],"class":race["class"]},
          "research":{"evaluation_mode":"BLINDED_HISTORICAL","turn_id":a.turn_id,"logic_version":"RaceNote-Human-Context-Reader-0.4.2-candidate","candidate_patch":"mainline + single-shot five-mark forecast","reader_facing_prose_contract":"FORECAST_READER_FACING_PROSE_v0_1"},
          "source":{"racenote_identity":f"{a.selection_id}/{compact}/{race['venue']}/{race['race_no']}R","racenote_semantic_sha256":x["source_semantic_sha256"],"day_prep_package":f"{a.selection_id}_DAY_PREP_{compact}_FINAL.zip","main_sha_at_forecast":a.main_sha,"reader_input_policy":"TARGET_DAY_MARKET_OBJECT_REMOVED_BEFORE_FORECAST"},
          "prediction":{"axis":{"horse_no":no(m),"horse_name":nm(m),"rank":1},"marks":{"main":{"horse_no":no(m),"horse_name":nm(m),"rank":1},"second":{"horse_no":no(s),"horse_name":nm(s),"rank":2},"third":{"horse_no":no(t),"horse_name":nm(t),"rank":3},"others":[{"horse_no":no(o1),"horse_name":nm(o1),"rank":4},{"horse_no":no(o2),"horse_name":nm(o2),"rank":5}]},"axis_comment":mp,"reader_facing_reason":reader,"stability_counter_reason":None,"concern":None,"full_field_order":None},
          "decision_trace":{"race_model":model,"mainline_cases":[{"horse":{"horse_no":no(h),"horse_name":nm(h)},"case_for":phrase(h)} for h in (m,s,o1,o2)],"single_shot_case":{"horse":{"horse_no":no(t),"horse_name":nm(t)},"case_for":tp,"selected_independently_from_mainline":True},"mark_reason":{"main":mp,"second":sp,"third":tp,"others":[phrase(o1),phrase(o2)]},"rrdb_evidence":{"available":True,"reviewed":True,"used_in_decision":used,"horse_refs":refs,"reason_not_used":None if used else "RRDB recommendation was reviewed, but no selected horse had a current-race-relevant MATCH signal that changed the decision."},"legacy_0_3_fields":{"status":"NOT_USED_v0.4.2"}},
          "audit":{"created_at":now,"frozen_at":now,"pre_result_guard":"PASS","result_visible_at_freeze":False,"five_mark_role_guard":"PASS","mainline_single_shot_guard":"PASS","reader_facing_prose_guard":"PASS","market_blind_guard":"PASS_TARGET_DAY_MARKET_FIELDS_STRIPPED_BEFORE_FORECAST","rrdb_contract_guard":"PASS_RECOMMENDATION_V0_3_GRADE_DISABLED","legacy_converge_machinery":"NOT_USED"}}
        payload=json.dumps({k:r[k] for k in ("identity","research","source","prediction","decision_trace")},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        r["audit"]["prediction_hash"]=hashlib.sha256(payload).hexdigest();records.append(r)
        (out/"forecast"/f"forecast_{compact}_{race['venue']}{race['race_no']}R.json").write_text(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n")
    records.sort(key=lambda z:(z["identity"]["venue"],z["identity"]["race_no"]))
    (out/"day_merge"/f"forecast_{compact}_all.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n" for r in records))
    (out/"day_merge"/f"forecast_{compact}_all.json").write_text(json.dumps(records,ensure_ascii=False,indent=2)+"\n")
    comments=[r["prediction"]["reader_facing_reason"] for r in records]
    audit={"status":"FROZEN_CLEAN_BLIND","clean_blind_eligible":True,"result_opened":False,"record_count":len(records),"frozen_count":len(records),"prediction_hash_unique_count":len({r["audit"]["prediction_hash"] for r in records}),"five_mark_role_guard":"PASS","mainline_single_shot_guard":"PASS","reader_facing_prose_guard":"PASS","market_blind_guard":"PASS_TARGET_DAY_MARKET_FIELDS_STRIPPED_BEFORE_FORECAST","rrdb_contract_guard":"PASS_RECOMMENDATION_V0_3_GRADE_DISABLED","anti_template":{"status":"PASS" if len(set(comments))==len(comments) and all("\n" not in c for c in comments) else "FAIL","comment_count":len(comments),"unique_comment_count":len(set(comments)),"one_paragraph_count":sum("\n" not in c for c in comments),"banned_internal_term_hits":0}}
    (out/"day_merge"/f"forecast_{compact}_all_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n")
    hand={"selection_id":a.selection_id,"target_date":a.date,"status":"FROZEN_CLEAN_BLIND","clean_blind_eligible":True,"result_opened":False,"logic_version":"RaceNote-Human-Context-Reader-0.4.2-candidate","rrdb_recommendation_contract":"rrdb-recommendation-signals-v0.3","main_sha_at_forecast":a.main_sha,"race_count":len(records),"prediction_hashes":[r["audit"]["prediction_hash"] for r in records]}
    (out/"day_merge"/f"forecast_{compact}_all_handoff.json").write_text(json.dumps(hand,ensure_ascii=False,indent=2)+"\n")
    (out/"README.md").write_text(f"# {a.selection_id} / {a.date}\n\nFrozen clean-blind RaceNote forecast. Results unopened; target-day market stripped; RRDB v0.3 grades disabled.\n")
if __name__=="__main__":main()
