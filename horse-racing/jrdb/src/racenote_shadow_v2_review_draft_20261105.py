#!/usr/bin/env python3
"""Pre-result Shadow v2 authored-review assembler, never reads result/payouts.
Explicit overrides are analyst review decisions; unchanged labels require
per-race Reader evidence and independently saved quality audit.
No outcome fitting or group-count targets.
"""
from __future__ import annotations
import argparse,json,re,hashlib
from pathlib import Path
DAYS={162:"20250503",163:"20250510",164:"20250928",165:"20250322",166:"20250209",167:"20250614",168:"20250330",169:"20251108",170:"20250915",171:"20250301"}
# Human-reviewed exceptions based only on pre-result Reader histories.
# grade, rationale
DECISIONS={
162:{"京都1":("REVIEW","◎は初出走で既走の着内再現性を検証できない。調教指数だけで軸B/Cを捏造しない。"),
     "京都7":("C","◎は芝2600mで直近5着、前々走は2000m16着、その前も2600m10着。距離適性・持久力の不確実性が継続し、今回も後半に失速して4着以下となる具体的な経路がある。"),
     "京都6":("B","◎には阪神芝1200mで直近2着と3着の反復実績がある。○の逆転で◎の1着は揺らぐが、同距離で2〜3着に残る根拠は明瞭。"),
     "京都9":("B","◎は小倉芝1800m勝利と中京芝1600m3着があり、直近東京2000m5着だけで着内軸を否定しない。"),
     "新潟11":("B","◎はダート1700mで2・3・3着を連続記録しており、○の前走勝利による勝ち切り不安と着内軸の再現性を分離できる。"),
     "東京6":("B","◎には東京芝2400m3着、中山芝2200m勝利、東京芝1800m3着と長めの芝で反復上位実績があり、軸としての安定を積極評価。"),
     "東京8":("B","◎は中山2500m2着と札幌2600m2着を持ち、東京2400m7着という弱点もあるが、長距離で2着に残る実走証拠が複数ある。")},
163:{"京都4":("C","◎の近3走はダート1700m5着、芝1800m12着、芝1600m6着で着内実績がない。今回のダート1800mも4着以下となる追走・持続不足の再発経路がある。"),
     "新潟6":("B","◎には福島芝1800m3着と京都芝2000m2着があり、異なる芝中距離条件で着内に残る持続性が事前に確認できる。")},
164:{},
165:{"阪神6":("B","◎は小倉ダート1700mの直近2着・3着と同条件での反復上位がある。勝ち切りCの不安が残っても、馬券内軸の直接証拠は明瞭。")},
166:{"京都6":("C","◎の京都芝2000mは直近2走とも4着で、同条件で着内へ一歩足りない現象が反復。直線で差を詰め切れず4着以下となる経路が具体的。"),
     "小倉1":("C","◎の近3走は福島1700m4着、新潟1400m芝5着、中京1400mダ5着で着内なし。条件替わりの改善は未知で、追走・末脚不足による着外継続のリスクがある。"),
     "小倉6":("C","◎の実戦履歴は小倉芝1200m4着のみ。今回も同距離で追走・終いの差を埋められず4着以下となる再発リスクがあり、正の着内証拠も存在しない。"),
     "東京9":("B","◎は札幌芝1800mで3着と勝利があり、直近東京1800m4着の一戦をもって着内再現性が失われたとは判断しない。")},
167:{"函館7":("C","◎の近3走は芝1400m5・5着、芝1200m4着で3着内なし。今回も追走から直線で前を捕らえられず4着以下となる反復的リスクが高い。")},
168:{"中山8":("C","◎は同じ中山ダート1200mで4・3・4着と着内を継続できず、今回も最後の一押しを欠いて4着以下となる再発リスクがある。")},
169:{},
170:{"中山11":("C","◎は直近芝2400m6着で、比較対象となる○は芝2400m2着。2000m勝利の実績を2400mへ延長して再現できず4着以下に留まる経路が具体的。"),
     "阪神2":("C","◎は阪神芝1600mの唯一の実戦で5着で、○は中京芝1600m2着。◎が同距離で前を捕らえ切れず4着以下になる再発シナリオが現実的。"),
     "阪神6":("B","◎には芝2000mで阪神・中京をまたぐ3戦連続2着があり、勝ち切りのCと着内軸の高い再現性を明確に区別できる。")},
171:{}}
def read(p):return json.loads(p.read_text(encoding="utf-8"))
def fmt_run(r):
    date=r.get("race",{}).get("date")
    x=r.get("race",{});s=r.get("result",{});p=r.get("performance",{})
    f=s.get("finish");f="着順未確定" if not isinstance(f,int) else f"{f}着"
    return f"{x.get('venue','?')}{x.get('surface','?')}{x.get('distance_m','?')}m{f}(IDM{p.get('idm','不明')})"
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo-root",required=True,type=Path);p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--days",required=True,nargs="+",type=int);a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    summary={}
    for n in a.days:
        d=DAYS[n];root=a.repo_root/f"horse-racing/jrdb/backtests/BTDAY-{n:04d}/{d}/v056"
        preds=read(root/"frozen/records.json");conf=read(root/"confidence_frozen/records.json")
        pidx={(r["venue"],int(r["race_no"])):r for r in preds};records=[];reviews=[]
        for c in conf:
            if c["confidence"] not in ("B","C"):continue
            v=c["venue"];no=int(c["race_no"]);key=f"{v}{no}"
            pr=pidx[(v,no)];core=pr["decision_core"];marks=core["marks"];honmei=int(marks[0]);rival=int(marks[1])
            reader=read(root/"reader"/f"racenote_reader_{d}_{v}{no}R.json")
            hs={int(h["identity"]["horse_no"]):h for h in reader["horses"]}
            h=hs[honmei];rh=hs[rival]
            runs=(h.get("other_context") or {}).get("recent_runs") or []
            rruns=(rh.get("other_context") or {}).get("recent_runs") or []
            hist=(h.get("other_context") or {}).get("historical_profile") or {}
            same=hist.get("same_distance") or {}
            positive=core["honmei_win"]["evidence"];risk=core["honmei_win"]["main_risk"]
            posrun="、".join(map(fmt_run,runs[:3])) or "既走なし"
            rivrun="、".join(map(fmt_run,rruns[:2])) or "既走なし"
            recent_top=sum(isinstance((x.get("result") or {}).get("finish"),int) and x["result"]["finish"]<=3 for x in runs[:4])
            recent_out=sum(isinstance((x.get("result") or {}).get("finish"),int) and x["result"]["finish"]>=4 for x in runs[:4])
            proposed,note=DECISIONS.get(n,{}).get(key,(c["confidence"],""))
            if proposed=="REVIEW":
                reviews.append({"venue":v,"race_no":no,"honmei":honmei,"canonical_confidence":c["confidence"],
                                "status":"REVIEW_REQUIRED","reason":note,"recent":posrun})
                continue
            if proposed not in ("B","C"):raise RuntimeError("Unsupported proposed grade")
            # All fields cite genuine reader facts. No outcome, payout, or final odds.
            positive_case=f"◎{honmei}（{h['identity']['horse_name']}）の既走：{posrun}。同距離履歴{same.get('starts',0)}戦で3着内{same.get('top3',0)}回。凍結Prediction：{positive}"
            relative=f"○{rival}（{rh['identity']['horse_name']}）の既走：{rivrun}。◎の実走履歴との比較で、○の1着逆転と◎の4着以下は別問題として評価。"
            actual_struggle=[x for x in runs[:4] if isinstance((x.get("result") or {}).get("finish"),int) and x["result"]["finish"]>=4]
            if actual_struggle:
                vulnerable=fmt_run(actual_struggle[0])
                details=((actual_struggle[0].get("notes") or {}).get("race_comment") or "")[:100]
                fail=f"◎が4着以下となる経路：過去に{vulnerable}。当時の事前時点で利用可能なレース短評「{details}」。今回も同種の位置取り・消耗・末脚不足が再現する場合は着外になる。"
            elif runs:
                fail=f"◎が4着以下となる経路：先行・差しの想定位置を確保できず他の上位候補に先着を許す場合。ただし近走に同種の着外再発を裏付ける実証は薄い。"
            else:
                fail="◎が4着以下となる経路は既走から実証不能。結果非参照の追加検証が必要。"
            if proposed=="C":
                if note:conclusion=note
                elif recent_out>0:
                    conclusion=f"◎の近4走に着外{recent_out}回（{posrun}）。{fail} 今回の固定軸には再発の不確実性が残りShadow C。"
                else:
                    # No demonstrated out-of-top3 path => v2 cannot certify C on general risks alone.
                    reviews.append({"venue":v,"race_no":no,"honmei":honmei,"canonical_confidence":c["confidence"],"status":"REVIEW_REQUIRED",
                                    "reason":"元CだがReaderの過去走から◎の4着以下リスクを具体的に説明できず、機械的C維持をしない。","recent":posrun})
                    continue
            else:
                if not note and recent_top==0:
                    reviews.append({"venue":v,"race_no":no,"honmei":honmei,"canonical_confidence":c["confidence"],"status":"REVIEW_REQUIRED",
                                    "reason":"元BだがReader近4走に着内実走根拠がなく、数値・調教だけで機械的Bにしない。","recent":posrun})
                    continue
                conclusion=note or f"◎は近4走に3着内{recent_top}回（{posrun}）。○の先着はあり得るが◎自身の馬券外を示す十分な追加証拠はなく、着内の再現性を評価してShadow B。"
            records.append({"venue":v,"race_no":no,"honmei":honmei,"shadow_grade":proposed,"strongest_rival":rival,
                            "axis_positive_case":positive_case,"relative_axis_case":relative,
                            "unverified_assumptions":f"今回の{reader['race'].get('surface')}{reader['race'].get('distance_m')}m・隊列への適応および相手の動きは未確定。凍結時の主要リスク：{risk}",
                            "axis_failure_scenario":fail,"final_reason":conclusion})
        expected=sum(c["confidence"] in ("B","C") for c in conf)
        if expected!=len(records)+len(reviews):raise RuntimeError("Missing B/C")
        decisionset={f"{x['venue']}{x['race_no']}" for x in records+reviews}
        for k in DECISIONS.get(n,{}):
            if k not in decisionset:raise RuntimeError("Unmatched review decision "+str((n,k)))
        out=a.output_dir/f"BTDAY-{n:04d}";out.mkdir(exist_ok=True)
        draft=json.dumps(records,ensure_ascii=False,indent=2)+"\n"
        (out/"shadow_draft.json").write_text(draft,encoding="utf-8")
        (out/"review_required.json").write_text(json.dumps(reviews,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        summary[n]={"expected":expected,"draft":len(records),"review_required":len(reviews),"B":sum(r["shadow_grade"]=="B" for r in records),"C":sum(r["shadow_grade"]=="C" for r in records),
                    "blocked":bool(reviews),"review_keys":[f"{x['venue']}{x['race_no']}" for x in reviews]}
        # Explicitly marked research draft. The file may be committed only after analyst quality approval.
        print("SHADOW_DRAFT_START_"+str(n))
        print(json.dumps(records,ensure_ascii=False,separators=(",",":")))
        print("SHADOW_DRAFT_END_"+str(n))
        print("SHADOW_REVIEW_START_"+str(n))
        print(json.dumps(reviews,ensure_ascii=False,separators=(",",":")))
        print("SHADOW_REVIEW_END_"+str(n))
    (a.output_dir/"audit.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SHADOW_SUMMARY="+json.dumps(summary,ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
