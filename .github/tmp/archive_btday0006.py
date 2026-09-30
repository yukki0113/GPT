#!/usr/bin/env python3
import json, hashlib, html, shutil, sys
from pathlib import Path

PREP=Path(sys.argv[1])
TARGET=Path(sys.argv[2])
TARGET.mkdir(parents=True,exist_ok=True)

LOGIC="RaceNote-Human-Context-Reader-0.3.3-candidate"
BASE="RaceNote-Human-Context-Reader-0.3.2"
MAIN_SHA="7e12eaca74d9779c15847075bdf2432a68bdb6d5"
FROZEN="2026-09-30T06:17:21+00:00"
EXPECTED_HASHES=[
"2911eba430b5a6bafb53df93aae43703ee46ed5ef3aad668fcb0f7aa204139af",
"83228634401ee7b4b83a5678325d619b08b0c5ebc8413f44edd52c40aa652469",
"8fa6b829dac9aed7d709090c5f120d689bc2dafb4cb383daca9381aa29a18ea2",
"2b550b67959a45de7841e3210cfec0e6a32f63b9646d7beef0403e3e0322c359",
"21665d83a24ed8af69559174ffc302c995c21c3b10b007faaa419d2a8b352969",
"d0104349b03dae67a3611e7f178e8643b10a26aaf4b6dbf8e42d3b27becdef39",
"bfba26caca72958c198b4745a620a0b6f387215de7c378c3b521fb3193ad27e6",
"a63c91b2b5436383c674868ef56fedbea1da235dba95cc988e6919ed04c29f3a",
"cce72781c7727e8a787ff4dcae1fdfff7861b9cc7141eeeeedda424dffcabbc8",
"2df753885bd4ba8cf8d1a3cd3f4801c15cfef06f96f01e568d160303c4aba74a",
"95f7664c26ac877af0730bbb7a31c9e4a079b6890fe5b3e6704f1c736b2d163d",
"08b00bcd9e34bcfe088a06f190c1616d5be4b0e0cdb6b2ffbdb230bb6ea1a205",
"76ace67c6e8e189b249473402e3aff257d34914baae96e8bb3edf66b4e5e61ef",
"19aa02ed256e8f29fb5db19e1d0a359cbb60e4852208fb412352da31655fddc7",
"ab910b87db00f37243708d8673493a8a863115160820750befec829e6901c6db",
"b6726188ce778a3ddd0e6c4d84f964f1519c6cd830e53a75471e6924f9394b01",
"fb8c68332235eb5cfba87d652df9f1ae8aaead18e2183ad76d0d80fd836aeb54",
"b9df86798ffeafa3a7fc50886b9becbd385a9433f277ba25343b82b42a743df0",
"f0193b45f99c5d489f5bf1e806b4ff7988a510f0298d1ff3131e4037f31cde17",
"367fc01835125422f7be04723a2c3e1cfc5add90cf47ddbed53092cc3206fa58",
"784922dccf357a575b1722c724766ca2610b9eab9732003821b7d1cad062d172",
"b1e119fdf4b962a81517292dc89737c50cf9af76755ee9b0207cbcdc2d9970c7",
"dd760d91d06a4b109e00ce32fdc32de93705bb403698b432cd767fafa47284e2",
"d41f26ea807a064ba9a2810626c17876d72365e3321d07c6a78ff72d3b15e60b"
]

P={}
def A(v,r,m,a,s,c=False): P[(v,r)]=(m,a,s,c)
A("中山",1,["ギンケイ","キタノエピックアン","タイセイルビー",["サーロー","サクラボーベル"]],"前走の中山ダ1800m3着で上がり最速。今回は調教も大きく上昇しており、同条件でさらに前進する余地を一番買います。","キタノエピックアンは中山1800mで2着が2回あり、近3走すべて3着以内。再現性では最も安定しています。")
A("中山",2,["ラインジーク","ミスタートントン","キイチムーブメント",["ヘイスティハート","グランマズドリーム"]],"1400mで2着、1300mでも3着と短距離ダートで安定し、今回は調教も上昇。1200mへの短縮でスピードをより生かせる点を買います。","ミスタートントンは中山1200mで2着・3着。今回条件そのものの再現性ではこちらが上です。")
A("中山",3,["モロノカガヤキ","ミスターキャンベラ","カシノスパーク",["コスモラムバック","ラッキーストーン"]],"2100m3着のあと中山1800mでも3着と距離対応を広げ、今回は調教も上昇。使うごとに内容を上げている点を買います。","ミスターキャンベラは中山1800mで2着が2回あり、今回条件で最も崩れにくい存在です。")
A("中山",4,["シャンデルナゴル","デスティネ","ヴォンヌヴォー",["エクロジャイト","ドーバーホーク"]],"中山障害2880mで3着、2着、2着と完全に条件が合っており、今回は調教も上昇。買い材料と安定性が同じ馬に収束します。","シャンデルナゴル自身が中山2880mで最も安定しており、魅力と安定が収束。○には次位の比較馬としてデスティネを置きます。",True)
A("中山",5,["ショウナンサイオウ","エリュグレイス","ラインクインビー",["タッカーヴァンバン","ファーザーアウェイ"]],"1800mで3着があり、前走5着から今回は調教がデキ抜群。2000mへの延長で折り合って持続力を出せれば一段上があると見ます。","エリュグレイスは中山2000mで2着・3着、東京1800mでも2着。実績と再現性は最も安定しています。")
A("中山",6,["ウリズンベー","テンカムテキ","ガンダ",["リヒトミューレ","アレンスター"]],"前走の中山1800m勝ちは上がり最速で、まだキャリアも浅い馬。昇級でも同条件で伸びしろを見込める点を買います。","テンカムテキは中山1800mで2着・3着があり、現級での安定性では一枚上です。")
A("中山",7,["ファインサマーデイ","ニルマーネル","ガラベイヤ",["ハッピーラッキー","ラヴノー"]],"前走の中山1200m2着から調教がさらに上昇。キャリアの浅さを残したまま同条件で上積みを狙える点を買います。","ニルマーネルは1200mで3戦すべて3着以内、中山では1着・2着。安定性は明確に最上位です。")
A("中山",8,["パシーヴ","トモジャシーマ","キョウエイスレーヴ",["リッキースタイル","ガンバレベアー"]],"中山1200mで3着が2回あり、今回は調教が上昇。近走の着順以上に同条件で再び前進できる余地を買います。","トモジャシーマは中山1200mで前走2着、その前も4着で末脚が安定。信頼度はこちらが上です。")
A("中山",9,["オストラヴァ","カーミングライツ","イクリール",["タッチアンドムーブ","ダイシンアポロン"]],"中山2500m3着があり、前走2200m2着。今回は調教がデキ抜群で、この舞台へ戻るタイミングの上積みを買います。","カーミングライツは2600mで1着・2着・3着と長距離で崩れず、スタミナの再現性では最も安定しています。")
A("中山",10,["デルアヴァー","メリークリスマス","タイセイミッション",["ペイシャモノノフ","ラオラシオン"]],"前走京都1800m8着からの巻き返し狙い。ひとつ前は阪神1800mを勝っており、今回の調教も高水準で、見た目の着順以上に反発余地があります。","メリークリスマスは中山1800mで1着・3着・1着と抜群に安定し、今回条件の信頼度は最上位です。")
A("中山",11,["スパークリシャール","ヤマニンアドホック","クルミナーレ",["ジュタ","フレーヴァード"]],"近3走は8着、7着、10着でも、前走は最後に脚を伸ばしており内容は着順ほど悪くありません。中山2000mへ戻って差しが届く形なら反発を狙えます。","ヤマニンアドホックは中山2000m勝ちに加え1800mでも2着・3着、今回は調教も上昇。安定性は明確です。")
A("中山",12,["パワースナッチ","プリムツァール","リバーバレイト",["レーヴブリリアント","シャンパンマーク"]],"中山1600mで2着・3着があり、今回は調教がデキ抜群。現条件での実績に今の状態上昇が重なる点を一番買います。","プリムツァールは中山1600m勝ちがあり、前走1800mでも3着。地力と再現性では最も信頼できます。")
A("阪神",1,["プリンセスアツコ","マリブサーフ","タガノプディング",["エバイダンス","ココロザスノ"]],"阪神1400m3着、京都1400m2着と連続好走し、今回は調教も上昇。勝ち切りへもう一段前進できる余地を買います。","マリブサーフは前走阪神1400m2着で、1400mを2戦経験。今回条件への再現性を安定材料に取ります。")
A("阪神",2,["タイセイサーブル","テイエムスターラン","マイカラー",["キタノアンドレイ","キングジェネシス"]],"阪神1800mで前走3着、今回は調教指数も高水準。買い材料と安定性の両方がこの馬に収束します。","タイセイサーブル自身が阪神1800mで最も完成度の高い実績を持つため魅力と安定が収束。○は同条件3着・4着のテイエムスターランです。",True)
A("阪神",3,["シオミン","キャッチアシーフ","アクアマイスター",["アルムアポジェ","レジーナテンペスタ"]],"初ダート1200mで3着、しかも上がり最速。まだ1戦分の直接証拠しかないからこそ、同条件でもう一段上がる余地を買います。","キャッチアシーフは阪神1200m2着に加え1200〜1400mで安定しており、信頼度では最上位です。")
A("阪神",4,["パーヴォ","カモンメーン","デルマフジ",["レイワノキセキ","フクチャンブラック"]],"2400m5着、2000m2着の実績があり、今回は調教が上昇。距離経験を積んだ2走目の2400mで前進余地を買います。","カモンメーンは京都2400m2着で、2000mでも4着。長距離への再現性では最も安定しています。")
A("阪神",5,["アスクチャンスマン","シルバーレシオ","スカイストライプス",["セルジュバローズ","ヴォーカライズ"]],"1900mで1着・3着し、前走はクラス水準以上の内容で上がりも鋭い。1800mへの短縮でさらに運びやすくなる余地を買います。","シルバーレシオは1800mで2着・2着・4着、今回は調教も上昇。距離実績の安定性が高いです。")
A("阪神",6,["ドウアドバンテージ","ドルチェリターン","ハルフロンティア",["デルシエロ","ウインポセイドン"]],"函館2000mで1着・3着、勝ったレースでは上がり最速。今回は調教も上昇しており、芝へ戻って能力を出し切る余地を買います。","ドルチェリターンは2000m3着に加え2400mでも大崩れせず、芝中距離の再現性では最も安定しています。")
A("阪神",7,["マテンロウブレイブ","バトンインディ","アラナコア",["ショーダンサー","ワイドクリーガー"]],"1700mで4着・5着から今回は調教上昇、前走は上がり最速。1800mへ戻して差し脚を生かせる余地を買います。","バトンインディは前走阪神1800m2着で、同距離15戦の経験。現条件の安定性では最上位です。")
A("阪神",8,["フェアリーライク","ジーティーマン","ホウオウトランプ",["モアリジット","ツーエムクロノス"]],"前走阪神1600m3着はクラス水準以上で上がり最速。1800m延長でも末脚を持続できれば勝ち切りまで狙えると見ます。","ジーティーマンは1800mで1着・2着を含む4戦3回の3着以内。距離の再現性は最も安定しています。")
A("阪神",9,["エコロレーヴ","メイショウカクウチ","テーオーグレーザー",["ハグレジョー","マジッククッキー"]],"前走1200m勝ちはクラス水準以上で、以前の東京1400m3着もある。スピードを増した今なら1400mへ戻して上積みを狙えます。","メイショウカクウチは1400mで3戦すべて3着以内、阪神1400mも勝利。安定性は明確に最上位です。")
A("阪神",10,["エイムフォーエース","スカイハイ","スライビングロード",["ウナギノボリ","サクセスアイ"]],"近2走は1600mで9着・12着でも、前走は上がり最速。1400mでは京都で勝っており、距離短縮で末脚を生かす反発を買います。","スカイハイは1400mで8戦7回が3着以内、直近も3着・1着・2着。安定性は群を抜きます。")
A("阪神",11,["クロワデュノール","ダノンデサイル","レーベンスティール",["ショウヘイ","タガノデュード"]],"海外を含む強い相手と戦いながら2000mは2戦2回好走し、今回の調教指数も高水準。阪神2000mで能力を出し切れる買い材料と安定性が収束します。","クロワデュノール自身が能力・2000m実績・状態の3点で最も安定。○にはG1級実績と状態上昇のダノンデサイルを置きます。",True)
A("阪神",12,["ニューオーリンズ","タマモティーカップ","ルークススペイ",["ゲイルライダー","ダノンスウィッチ"]],"阪神1400mを2勝し、前走勝ちはクラス水準以上で上がりも鋭い。今回は調教も上昇しており、魅力と安定性がこの馬に収束します。","ニューオーリンズ自身が阪神1400mの実績と現在の状態で最も安定。○には同条件2着と連勝実績のあるタマモティーカップを置きます。",True)

def load(v,r):
    return json.loads((PREP/"reader"/f"racenote_reader_20260405_{v}{r}R.json").read_text(encoding="utf-8"))
def get_h(d,n): return next(h for h in d["horses"] if h["basic"]["horse_name"]==n)
def href(h,rank=None):
    x={"horse_no":int(h["basic"]["horse_no"]),"horse_name":h["basic"]["horse_name"]}
    if rank is not None: x["rank"]=rank
    return x
def rr_ref(h):
    rr=h.get("racereview") or {}; lp=rr.get("latest_prior_run") or {}
    if not lp:return None
    tags=lp.get("review_tags") or []; nw=(rr.get("next_watch") or {}).get("grade")
    state="NEUTRAL"
    if "TIME_ABOVE_DECLARED_CLASS" in tags or "FASTEST_LAST3F" in tags or nw in ("S","A"): state="UPGRADE"
    if "MOVE_THEN_FADE" in tags or "CLOSING_LOSS" in tags: state="DOWNGRADE"
    if "TIME_AT_DECLARED_CLASS" in tags and state=="NEUTRAL": state="CONFIRM"
    return {"horse_no":int(h["basic"]["horse_no"]),"horse_name":h["basic"]["horse_name"],"reinterpretation_state":state,"source_run_ref":lp.get("race_key"),"review_tags":tags,"next_watch_grade":nw}
def candidate_case(h):
    a=h.get("ability") or {}; tr=(h.get("training") or {}).get("summary") or {}
    hp=h.get("historical_profile") or {}; runs=h.get("recent_runs") or []
    recent="初出走" if not runs else f"{runs[0]['race']['venue']}{runs[0]['race']['surface']}{runs[0]['race']['distance_m']}m {runs[0]['result']['finish']}着"
    sd=hp.get("same_distance") or {}
    return {"horse":href(h),"case_for":f"{recent}。同距離{sd.get('starts',0)}走・3着以内{sd.get('top3',0)}回。調教は{tr.get('training_arrow')}。","case_against":"実戦経験がなく不確実性が大きい。" if not runs else f"脚質{a.get('running_style')}で展開・相手強化・条件替わりによる不確実性がある。","context_hook":"今回一番買いたい理由と、地力・実績・再現性の安定材料を分けて比較する。"}

records=[]
for venue in ["中山","阪神"]:
  for rn in range(1,13):
    d=load(venue,rn); race=d["race"]; marks,ar,sr,conv=P[(venue,rn)]
    main,second,third,others=marks; hs=[get_h(d,n) for n in [main,second,third]+others]
    rrrefs=[x for x in (rr_ref(h) for h in d["horses"]) if x]
    if conv:
      counter=f"○{second}が今回の条件で持つ実績・再現性を最大限発揮する場合が、◎{main}に対する最も明確な反証です。"
      reversal=f"○{second}が想定以上に安定して走り、◎{main}の今回の強みが十分に表面化しない場合。"
      stability_h=hs[0]
    else:
      counter=f"○{second}は{sr}"
      reversal=f"○{second}の再現性が想定どおり出て、◎{main}の今回の上積み・条件変化が表面化しない場合。"
      stability_h=hs[1]
    rec={"schema_version":"RaceNote-Forecast-Research-Record-0.3.1","identity":{"target_date":race["date"],"venue":venue,"race_no":rn,"race_key":f"{race['date']}-{venue}-{rn}","race_name":race.get("race_name"),"surface":race["surface"],"distance_m":race["distance_m"],"class":race["class"]},"research":{"evaluation_mode":"BLINDED_HISTORICAL","turn_id":"BTDAY-0006-TURN2-FULLDAY","logic_version":LOGIC,"base_logic_version":BASE},"source":{"racenote_identity":f"BTDAY-0006/20260405/{venue}/{rn}R","racenote_semantic_sha256":d["source_semantic_sha256"],"day_prep_package":"BTDAY-0006_DAY_PREP_20260405_FINAL.zip","main_sha_at_forecast":MAIN_SHA},"prediction":{"axis":href(hs[0],1),"marks":{"main":href(hs[0],1),"second":href(hs[1],2),"third":href(hs[2],3),"others":[href(hs[3],4),href(hs[4],5)]},"axis_comment":ar,"reader_facing_reason":ar,"stability_counter_reason":sr,"concern":counter,"full_field_order":None},"decision_trace":{"human_principles_used":["RACE_CONTEXT_FIRST","ATTRACTION_STABILITY_ROLE_SEPARATION","NO_MECHANICAL_SCORE"],"race_model":f"{race['surface']}{race['distance_m']}m {race['class']}。今回一番買いたい馬と、地力・実績・再現性で最も信頼できる馬を別の問いとして比較する。","primary_question":"魅力のある買い材料が、安定性の高い比較馬を上回って◎に値するか。","candidate_cases":[candidate_case(h) for h in hs],"attraction_choice":{"horse":href(hs[0]),"reason":ar},"stability_choice":{"horse":href(stability_h),"reason":sr},"attraction_stability_convergence":bool(conv),"main_vs_second":{"preferred":href(hs[0]),"other":href(hs[1]),"reason":f"◎{main}: {ar} ○{second}: {sr}"},"main_vs_third":{"preferred":href(hs[0]),"other":href(hs[2]),"reason":f"▲{third}にも勝ち筋はあるが、今回一番買いたい理由は◎{main}の方が明確。"},"why_not_numeric_leader":"IDM・調教・Trend・RRDBなどを固定配点や合算順位にせず、レース文脈で魅力と安定性を分けて比較した。","strongest_counter":counter,"reversal_condition":reversal,"missing_evidence":(["Obstacle-specific evidence remains limited"] if venue=="中山" and rn==4 else [])+["P3 sibling evidence unavailable"],"rrdb_evidence":{"available":True,"reviewed":True,"used_in_decision":any(x["reinterpretation_state"]!="NEUTRAL" for x in rrrefs),"horse_refs":rrrefs,"all_horses_reviewed":True,"reviewed_horse_count":len(d["horses"])}},"audit":{"created_at":FROZEN,"frozen_at":FROZEN,"prediction_hash":None,"pre_result_guard":"PASS","result_visible_at_freeze":False,"candidate_role_separation":"APPLIED","converge_counter_self_reference_guard":"PASS"}}
    tmp=json.loads(json.dumps(rec,ensure_ascii=False)); tmp["audit"]["prediction_hash"]=None
    rec["audit"]["prediction_hash"]=hashlib.sha256(json.dumps(tmp,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    records.append(rec)

actual=[r["audit"]["prediction_hash"] for r in records]
assert actual==EXPECTED_HASHES,(actual,EXPECTED_HASHES)

for venue,dirname in [("中山","nakayama"),("阪神","hanshin")]:
  vd=TARGET/"venues"/dirname; vd.mkdir(parents=True,exist_ok=True)
  vr=[r for r in records if r["identity"]["venue"]==venue]
  (vd/f"forecast_20260405_{venue}.json").write_text(json.dumps(vr,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  (vd/f"forecast_20260405_{venue}.jsonl").write_text("\n".join(json.dumps(r,ensure_ascii=False,separators=(",",":")) for r in vr)+"\n",encoding="utf-8")
  audit={"validator_version":"racenote-human-context-0.3.3-candidate-equivalent","candidate_patch":"CONVERGE counter/reversal self-reference guard","status":"PASS","venue":venue,"target_date":"2026-04-05","record_count":12,"frozen_count":12,"error_count":0,"prediction_hash_unique_count":12,"converge_races":[r["identity"]["race_no"] for r in vr if r["decision_trace"]["attraction_stability_convergence"]],"converge_semantic_guard":"PASS","result_opened":False}
  (vd/f"forecast_20260405_{venue}_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  handoff={"schema_version":"RaceNote-Venue-Forecast-Handoff-0.1-draft","selection_id":"BTDAY-0006","target_date":"2026-04-05","venue":venue,"logic_version":LOGIC,"main_sha":MAIN_SHA,"race_count":12,"frozen_count":12,"technical_skips":0,"result_opened":False,"prediction_hashes":[r["audit"]["prediction_hash"] for r in vr]}
  (vd/f"forecast_20260405_{venue}_handoff.json").write_text(json.dumps(handoff,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

merged=records
dm=TARGET/"day_merge"; dm.mkdir(parents=True,exist_ok=True)
(dm/"forecast_20260405_all.json").write_text(json.dumps(merged,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(dm/"forecast_20260405_all.jsonl").write_text("\n".join(json.dumps(r,ensure_ascii=False,separators=(",",":")) for r in merged)+"\n",encoding="utf-8")
audit={"schema_version":"RaceNote-Daily-Merge-Audit-0.1-draft","selection_id":"BTDAY-0006","target_date":"2026-04-05","status":"PASS","logic_version":LOGIC,"candidate_patch":"CONVERGE counter/reversal self-reference guard","venues":["中山","阪神"],"venue_count":2,"expected_races":24,"merged_races":24,"frozen_count":24,"technical_skips":0,"duplicate_race_keys":0,"prediction_hash_unique_count":24,"prediction_hash_preserved":True,"marks_recomputed":False,"reader_reasons_rewritten":False,"converge_semantic_guard":"PASS","result_opened":False,"turn_shape":"TWO_TURN_DAILY_DEFAULT"}
(dm/"forecast_20260405_all_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
handoff={"schema_version":"RaceNote-Day-Forecast-Handoff-0.1-draft","selection_id":"BTDAY-0006","target_date":"2026-04-05","logic_version":LOGIC,"venues":["中山","阪神"],"venue_count":2,"race_count":24,"frozen_count":24,"technical_skips":0,"result_opened":False,"prediction_hashes":actual,"merge_policy":"deterministic packaging only; no forecast judgment changed","simple_html_generated":True,"next_stage":"STOP before results; post-race work belongs to separate research flow"}
(dm/"forecast_20260405_all_handoff.json").write_text(json.dumps(handoff,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

sections=[]
for venue in ["中山","阪神"]:
  rows=[]
  for r in [x for x in merged if x["identity"]["venue"]==venue]:
    i=r["identity"]; m=r["prediction"]["marks"]; conv=" / 堅軸型" if r["decision_trace"]["attraction_stability_convergence"] else ""
    rows.append(f"<tr><td>{i['race_no']}R<br>{html.escape(i.get('race_name') or '')}</td><td>◎{m['main']['horse_no']} {html.escape(m['main']['horse_name'])}{conv}</td><td>○{m['second']['horse_no']} {html.escape(m['second']['horse_name'])}</td><td>▲{m['third']['horse_no']} {html.escape(m['third']['horse_name'])}</td><td>{' / '.join('△'+str(x['horse_no'])+' '+html.escape(x['horse_name']) for x in m['others'])}</td><td>{html.escape(r['prediction']['reader_facing_reason'])}</td><td>{html.escape(r['prediction']['stability_counter_reason'])}</td></tr>")
  sections.append(f"<h2>{venue}</h2><table><tr><th>R</th><th>◎</th><th>○</th><th>▲</th><th>△</th><th>◎を買う理由</th><th>安定比較</th></tr>{''.join(rows)}</table>")
doc="<!doctype html><html lang='ja'><meta charset='utf-8'><title>BTDAY-0006 2026-04-05</title><style>body{font-family:system-ui;max-width:1400px;margin:24px auto;padding:0 16px;line-height:1.5}table{border-collapse:collapse;width:100%;margin-bottom:30px}td,th{border:1px solid #bbb;padding:7px;vertical-align:top}th{background:#f3f3f3}</style><h1>BTDAY-0006 — 2026-04-05 Daily Forecast</h1><p>24R Frozen / RaceNote-Human-Context-Reader-0.3.3-candidate / result_opened=false</p>"+''.join(sections)+"</html>"
(dm/"forecast_20260405_all.html").write_text(doc,encoding="utf-8")

dp=TARGET/"day_prep"; dp.mkdir(exist_ok=True)
for name in ["day_prep_handoff.json","manifest.json","validation_report.json","selected_pool_state.json"]:
    shutil.copy2(PREP/name,dp/name)

readme="""# BTDAY-0006 — 2026-04-05

Status: FROZEN PRE-RESULT DAILY BACKTEST

- selection_id: BTDAY-0006
- target_date: 2026-04-05
- venues: 中山 / 阪神
- race_count: 24
- logic: RaceNote-Human-Context-Reader-0.3.3-candidate
- candidate patch: CONVERGE counter/reversal self-reference guard
- DAY PREP: PASS
- venue Freeze: 12/12 x 2
- DAY MERGE: PASS
- result_opened: false

## Analysis entry point

Start with day_merge/forecast_20260405_all.json.
Use the Frozen prediction hashes as the immutable pre-result source of truth.
Results are intentionally not stored in this pre-result tree.
"""
(TARGET/"README.md").write_text(readme,encoding="utf-8")

files=[]
for p in sorted(TARGET.rglob("*")):
    if p.is_file() and p.name!="ARTIFACT_INDEX.json":
        b=p.read_bytes()
        files.append({"path":str(p.relative_to(TARGET)),"size_bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()})
idx={"schema_version":"RaceNote-Backtest-Artifact-Index-0.1","selection_id":"BTDAY-0006","target_date":"2026-04-05","canonical_entry":"day_merge/forecast_20260405_all.json","files":files}
(TARGET/"ARTIFACT_INDEX.json").write_text(json.dumps(idx,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"status":"PASS","records":24,"hashes_match":True,"target":str(TARGET)},ensure_ascii=False))
