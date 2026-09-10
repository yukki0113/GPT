"""Pure deterministic ForwardTrial_Ver0.1 prediction generator.

Consumes only an official BOAT RACE racelist CSV and emits the three required
pre-result artifacts. No network access and no result access are performed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

RULE_VERSION = "ForwardTrial_Ver0.1"
CLASS_RANK = {"A1": 4, "A2": 3, "B1": 2, "B2": 1}
ZEN = str.maketrans("１２３４５６", "123456")

PREDICTION_COLUMNS = [
    "日付","会場","R","開催日目","レース種別","ルールVer","判定","1着軸","連軸",
    "2着本線","2着押さえ","逆転候補","3着候補","主推奨券種","主推奨買い目表記",
    "主推奨買い目展開後","主推奨点数","保険券種","保険買い目","保険点数",
    "参考券種","参考買い目","判定理由","予想確定日時",
]
RATIONALE_COLUMNS = [
    "日付","会場","R","開催日目","艇番","級別","全国勝率","当地勝率","平均ST",
    "モーター2連率","今節成績","今節平均着順","1着軸フラグ","2着本線フラグ",
    "2着押さえフラグ","逆転候補フラグ","3着候補フラグ","1号艇との全国勝率差",
    "1号艇との当地勝率差","1号艇とのST差","1号艇とのモーター2連率差",
    "1号艇との今節平均着順差","1号艇との級別比較","最強非1号艇フラグ",
    "軸警戒フラグ","予想確定日時",
]
SALES_COLUMNS = [
    "日付","会場","R","試行仕様Ver","正式判定","1着軸","2着本線","2着押さえ",
    "2連単1点対象","2連単1点","軸警戒","比較支持項目数","全国勝率差",
    "2着候補分離度","販売スコア","内部販売評価","掲載区分","選別理由",
    "予想確定日時","販売選別確定日時","結果参照状態",
]
REQUIRED = {
    "日付","会場","R","開催日目","レース種別","艇番","級別","全国勝率",
    "当地勝率","平均ST","モーター2連率","今節成績","欠場状態",
}
FORBIDDEN = ("展示タイム","展示航走","直前気象","オッズ","結果","払戻")


class ForwardTrialValidationError(ValueError):
    pass


def num(value):
    text = str(value if value is not None else "").strip()
    if text in {"", "-", "―", "ー", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def current_series_average(text):
    values = []
    for segment in str(text or "").split("|"):
        parts = [part.strip() for part in segment.split("/")]
        if len(parts) < 4:
            continue
        match = re.fullmatch(r"\s*([1-6])\s*", parts[-1].translate(ZEN))
        if match:
            values.append(int(match.group(1)))
    return sum(values) / len(values) if values else None


def better(a, b, higher=True):
    if a is None or b is None:
        return False
    return a > b if higher else a < b


def parse_boats(rows):
    boats = {}
    for row in rows:
        lane = int(row["艇番"])
        klass = row["級別"].strip()
        if klass not in CLASS_RANK:
            raise ForwardTrialValidationError(f"unsupported class: {klass}")
        boats[lane] = {
            "lane": lane, "row": row, "class": klass,
            "national": num(row["全国勝率"]), "local": num(row["当地勝率"]),
            "st": num(row["平均ST"]), "motor": num(row["モーター2連率"]),
            "form": current_series_average(row["今節成績"]),
        }
    if set(boats) != {1,2,3,4,5,6}:
        raise ForwardTrialValidationError(f"race must contain lanes 1-6: {sorted(boats)}")
    return boats


def strongest_non1(boats):
    def high(value):
        return (1, 0.0) if value is None else (0, -float(value))
    def low(value):
        return (1, 0.0) if value is None else (0, float(value))
    def key(boat):
        return (*high(boat["national"]), *high(boat["local"]), -CLASS_RANK[boat["class"]],
                *low(boat["st"]), *high(boat["motor"]), *low(boat["form"]), boat["lane"])
    return min((boat for lane, boat in boats.items() if lane != 1), key=key)


def support_flags(one, strongest):
    return {
        "当地勝率": better(one["local"], strongest["local"]),
        "平均ST": better(one["st"], strongest["st"], False),
        "モーター2連率": better(one["motor"], strongest["motor"]),
        "今節平均着順": better(one["form"], strongest["form"], False),
        "級別": CLASS_RANK[one["class"]] > CLASS_RANK[strongest["class"]],
    }


def non1_a_candidate(boats):
    one = boats[1]
    candidates = []
    for lane in (2,3):
        boat = boats[lane]
        if not better(boat["national"], one["national"]) or not better(boat["local"], one["local"]):
            continue
        advantages = [
            better(boat["st"], one["st"], False), better(boat["motor"], one["motor"]),
            better(boat["form"], one["form"], False), CLASS_RANK[boat["class"]] > CLASS_RANK[one["class"]],
        ]
        if sum(advantages) >= 3:
            advantage = (boat["national"] - one["national"]) + (boat["local"] - one["local"])
            candidates.append((advantage, lane, boat))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2] if candidates else None


def choose_axis_and_judgment(boats):
    one = boats[1]
    strongest = strongest_non1(boats)
    flags = support_flags(one, strongest)
    candidate = non1_a_candidate(boats)
    if candidate is not None:
        return candidate, strongest, "A", False, flags
    count = sum(flags.values())
    core = sum(flags[name] for name in ("当地勝率","平均ST","モーター2連率","今節平均着順"))
    warning = one["national"] is not None and strongest["national"] is not None and one["national"] < strongest["national"]
    if warning:
        judgment = "A" if count >= 3 and core >= 2 else ("B" if count >= 1 else "C")
    else:
        judgment = "A" if count >= 3 else ("B" if count >= 1 else "C")
    return one, strongest, judgment, warning, flags


def normalize(values, higher_good=True):
    valid = [value for value in values.values() if value is not None]
    if not valid:
        return {lane: 0.0 for lane in values}
    minimum, maximum = min(valid), max(valid)
    out = {}
    for lane, value in values.items():
        if value is None:
            out[lane] = 0.0
        elif maximum == minimum:
            out[lane] = 0.5
        else:
            base = (value - minimum) / (maximum - minimum)
            out[lane] = base if higher_good else 1.0 - base
    return out


def opponent_scores(boats):
    national = normalize({lane: boat["national"] for lane, boat in boats.items()})
    local = normalize({lane: boat["local"] for lane, boat in boats.items()})
    st = normalize({lane: boat["st"] for lane, boat in boats.items()}, False)
    motor = normalize({lane: boat["motor"] for lane, boat in boats.items()})
    form = normalize({lane: boat["form"] for lane, boat in boats.items()}, False)
    klass = normalize({lane: float(CLASS_RANK[boat["class"]]) for lane, boat in boats.items()})
    return {lane: .35*national[lane]+.20*local[lane]+.15*st[lane]+.10*motor[lane]+.15*form[lane]+.05*klass[lane] for lane in boats}


def relative(a, b, reverse=False):
    if a is None or b is None:
        return ""
    return round((b-a) if reverse else (a-b), 3)


def iso_date(raw):
    raw = raw.strip()
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    raise ForwardTrialValidationError(f"unsupported date: {raw}")


def validate_input(rows, columns):
    missing = REQUIRED - set(columns)
    if missing:
        raise ForwardTrialValidationError(f"missing columns: {sorted(missing)}")
    for marker in FORBIDDEN:
        if any(marker in column for column in columns):
            raise ForwardTrialValidationError(f"forbidden pre-result column: {marker}")
    if not rows:
        raise ForwardTrialValidationError("empty input")
    if any(str(row.get("欠場状態", "")).strip() for row in rows):
        raise ForwardTrialValidationError("withdrawn boat found")
    dates = {iso_date(str(row["日付"])) for row in rows}
    if len(dates) != 1:
        raise ForwardTrialValidationError(f"input dates mismatch: {sorted(dates)}")
    groups = defaultdict(list)
    venues = []
    seen = set()
    for row in rows:
        venue, race = row["会場"].strip(), int(row["R"])
        if venue not in seen:
            seen.add(venue); venues.append(venue)
        groups[(venue, race)].append(row)
    for venue in venues:
        races = sorted(race for v, race in groups if v == venue)
        if races != list(range(1,13)):
            raise ForwardTrialValidationError(f"{venue}: expected races 1-12")
        for race in races:
            if len(groups[(venue,race)]) != 6:
                raise ForwardTrialValidationError(f"{venue} {race}R: expected 6 boats")
    return dates.pop(), venues, groups


def generate(rows, columns, prediction_time, sales_time=None):
    sales_time = sales_time or prediction_time
    target_date, venues, groups = validate_input(rows, columns)
    predictions, rationales, sales = [], [], []

    for venue in venues:
        for race in range(1,13):
            race_rows = groups[(venue,race)]
            boats = parse_boats(race_rows)
            one = boats[1]
            axis, strongest, judgment, warning, flags = choose_axis_and_judgment(boats)
            scores = opponent_scores(boats)
            axis_lane = axis["lane"]
            support_count = sum(flags.values())
            core_count = sum(flags[name] for name in ("当地勝率","平均ST","モーター2連率","今節平均着順"))
            second_main = second_backup = third_candidates = notation = ""
            bets = []
            axis_set = main_set = backup_set = third_set = set()

            if judgment != "C":
                opponents = sorted((lane for lane in boats if lane != axis_lane), key=lambda lane: (-scores[lane], lane))
                first, second, third = opponents[:3]
                second_main, second_backup = str(first), str(second)
                third_candidates = f"{first},{second},{third}"
                notation = f"{axis_lane}→{first},{second}→{first},{second},{third}"
                bets = [f"{axis_lane}→{first}→{second}", f"{axis_lane}→{first}→{third}",
                        f"{axis_lane}→{second}→{first}", f"{axis_lane}→{second}→{third}"]
                axis_set, main_set, backup_set, third_set = {axis_lane}, {first}, {second}, {first,second,third}

            if judgment == "C":
                reason = f"1号艇基準。最強非1号艇は{strongest['lane']}号艇。比較支持項目数={support_count}、主要4項目優位数={core_count}、軸警戒={'あり' if warning else 'なし'}。{RULE_VERSION}固定規則によりC、正式購入対象なし。"
            elif axis_lane in (2,3):
                extras = [name for name, ok in (("平均ST",better(axis['st'],one['st'],False)),("モーター2連率",better(axis['motor'],one['motor'])),("今節平均着順",better(axis['form'],one['form'],False)),("級別",CLASS_RANK[axis['class']]>CLASS_RANK[one['class']])) if ok]
                reason = f"{axis_lane}号艇が非1号艇A条件を満たす。全国勝率・当地勝率とも1号艇を上回り、追加4項目中{len(extras)}項目（{'・'.join(extras)}）で優位。相手総合スコア上位は{second_main}号艇、{second_backup}号艇。"
            else:
                reason = f"1号艇軸。最強非1号艇は{strongest['lane']}号艇。比較支持項目数={support_count}、主要4項目優位数={core_count}、軸警戒={'あり' if warning else 'なし'}。{RULE_VERSION}固定規則により{judgment}。相手総合スコア上位は{second_main}号艇、{second_backup}号艇。"

            predictions.append([target_date,venue,race,race_rows[0]["開催日目"],race_rows[0]["レース種別"],RULE_VERSION,judgment,str(axis_lane) if judgment!="C" else "","",second_main,second_backup,"",third_candidates,"3連単" if judgment!="C" else "",notation,"／".join(bets),len(bets),"","",0,"","",reason,prediction_time])

            for lane in range(1,7):
                boat, row = boats[lane], boats[lane]["row"]
                class_delta = CLASS_RANK[boat["class"]] - CLASS_RANK[one["class"]]
                rationales.append([target_date,venue,race,row["開催日目"],lane,boat["class"],row["全国勝率"],row["当地勝率"],row["平均ST"],row["モーター2連率"],row["今節成績"],"" if boat["form"] is None else round(boat["form"],3),1 if lane in axis_set else 0,1 if lane in main_set else 0,1 if lane in backup_set else 0,0,1 if lane in third_set else 0,0 if lane==1 and boat["national"] is not None else relative(boat["national"],one["national"]),0 if lane==1 and boat["local"] is not None else relative(boat["local"],one["local"]),0 if lane==1 and boat["st"] is not None else relative(boat["st"],one["st"],True),0 if lane==1 and boat["motor"] is not None else relative(boat["motor"],one["motor"]),0 if lane==1 and boat["form"] is not None else relative(boat["form"],one["form"],True),"同等" if lane==1 else ("上位" if class_delta>0 else ("同等" if class_delta==0 else "下位")),1 if lane==strongest["lane"] else 0,1 if (lane==axis_lane and warning and judgment!="C") else 0,prediction_time])

            national_diff = "" if one["national"] is None or strongest["national"] is None else round(one["national"]-strongest["national"],3)
            target = judgment=="A" and axis_lane==1 and bool(second_main) and bool(second_backup)
            exacta = separation = sale_score = ""
            if target:
                main_lane, backup_lane = int(second_main), int(second_backup)
                opponent = min(main_lane, backup_lane)
                exacta = f"1→{opponent}"
                ranked = sorted((lane for lane in boats if lane != 1), key=lambda lane: (-scores[lane], lane))
                separation = round(scores[ranked[1]]-scores[ranked[2]],6)
                score = 0
                if not warning: score += 2
                if support_count == 5: score += 2
                elif support_count == 4: score += 1
                if national_diff != "" and national_diff >= .50: score += 1
                if separation >= .15: score += 2
                elif separation >= .08: score += 1
                if opponent in (2,3,4): score += 1
                if opponent == main_lane: score += 1
                sale_score = score
            sales.append({"日付":target_date,"会場":venue,"R":race,"試行仕様Ver":RULE_VERSION,"正式判定":judgment,"1着軸":str(axis_lane) if judgment!="C" else "","2着本線":second_main,"2着押さえ":second_backup,"2連単1点対象":"対象" if target else "対象外","2連単1点":exacta,"軸警戒":"あり" if warning else "なし","比較支持項目数":support_count,"全国勝率差":national_diff,"2着候補分離度":separation,"販売スコア":sale_score,"予想確定日時":prediction_time,"販売選別確定日時":sales_time,"結果参照状態":"未参照"})

    targets = [row for row in sales if row["2連単1点対象"] == "対象"]
    targets.sort(key=lambda row: (-int(row["販売スコア"]),-float(row["2着候補分離度"]),row["会場"],int(row["R"])))
    for rank, row in enumerate(targets,1):
        if rank <= 6: listing, internal = "有料", ("S" if int(row["販売スコア"]) >= 7 else "A")
        elif rank <= 9: listing, internal = "無料", "A-"
        else: listing, internal = "CSVのみ", "A-"
        row["掲載区分"], row["内部販売評価"] = listing, internal
        row["選別理由"] = f"2連単1点対象。販売順位{rank}位。販売スコア={row['販売スコア']}、2着候補分離度={float(row['2着候補分離度']):.6f}。固定順位規則により{listing}。"
    for row in sales:
        if row["2連単1点対象"] != "対象":
            row["掲載区分"], row["内部販売評価"] = "対象外", ""
            row["選別理由"] = "2連単1点対象条件を満たさないため販売選別対象外。"

    validate_generated(predictions, rationales, sales, venues)
    return {"date":target_date,"venues":venues,"predictions":predictions,"rationales":rationales,"sales":sales,"counts":Counter(row[6] for row in predictions),"target_count":len(targets)}


def validate_generated(predictions, rationales, sales, venues):
    expected = len(venues)*12
    if len(predictions)!=expected or any(len(row)!=24 for row in predictions): raise ForwardTrialValidationError("prediction shape mismatch")
    if len(rationales)!=expected*6 or any(len(row)!=26 for row in rationales): raise ForwardTrialValidationError("rationale shape mismatch")
    if len(sales)!=expected: raise ForwardTrialValidationError("sales shape mismatch")
    for row in predictions:
        bets=[bet for bet in str(row[15]).split("／") if bet]
        if int(row[16])!=len(bets): raise ForwardTrialValidationError("bet count mismatch")
        if row[6]=="C" and (row[7]!="" or row[15]!="" or int(row[16])!=0): raise ForwardTrialValidationError("C has purchase fields")
        if row[6]!="C" and len(bets)!=4: raise ForwardTrialValidationError("A/B must have four structures")
    ranked=sorted((row for row in sales if row["2連単1点対象"]=="対象"),key=lambda row:(-int(row["販売スコア"]),-float(row["2着候補分離度"]),row["会場"],int(row["R"])))
    for rank,row in enumerate(ranked,1):
        if row["正式判定"]!="A" or str(row["1着軸"])!="1": raise ForwardTrialValidationError("invalid exacta target")
        if int(str(row["2連単1点"]).split("→")[1]) != min(int(row["2着本線"]),int(row["2着押さえ"])): raise ForwardTrialValidationError("exacta is not inner opponent")
        expected_listing="有料" if rank<=6 else ("無料" if rank<=9 else "CSVのみ")
        if row["掲載区分"]!=expected_listing or row["結果参照状態"]!="未参照": raise ForwardTrialValidationError("sales rank/state mismatch")


def sha256_file(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""): digest.update(chunk)
    return digest.hexdigest()


def write_csv(path, columns, rows):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with Path(path).open("w",encoding="utf-8-sig",newline="") as handle:
        if rows and isinstance(rows[0],dict):
            writer=csv.DictWriter(handle,fieldnames=columns); writer.writeheader()
            for row in rows: writer.writerow({column:row.get(column,"") for column in columns})
        else:
            writer=csv.writer(handle); writer.writerow(columns); writer.writerows(rows)


def run(input_path, output_dir, prediction_time, sales_time=None, source_commit=""):
    input_path, output_dir = Path(input_path), Path(output_dir)
    with input_path.open("r",encoding="utf-8-sig",newline="") as handle:
        reader=csv.DictReader(handle); rows=list(reader); columns=reader.fieldnames or []
    result=generate(rows,columns,prediction_time,sales_time)
    compact=result["date"].replace("-",""); venue_part="_".join(result["venues"])
    pred=output_dir/f"{compact}_事前予想_{venue_part}_{RULE_VERSION}.csv"
    rat=output_dir/f"{compact}_予想根拠明細_{venue_part}_{RULE_VERSION}.csv"
    sale=output_dir/f"{compact}_2連単1点販売選別_{venue_part}_{RULE_VERSION}.csv"
    manifest=output_dir/f"{compact}_ForwardTrial実行manifest_{venue_part}_{RULE_VERSION}.json"
    write_csv(pred,PREDICTION_COLUMNS,result["predictions"]); write_csv(rat,RATIONALE_COLUMNS,result["rationales"]); write_csv(sale,SALES_COLUMNS,result["sales"])
    source=Path(__file__).resolve()
    data={"rule_version":RULE_VERSION,"source_commit":source_commit,"source_file":source.name,"source_file_sha256":sha256_file(source),"input_file":input_path.name,"input_sha256":sha256_file(input_path),"prediction_time":prediction_time,"sales_time":sales_time or prediction_time,"generated_at":datetime.now(timezone.utc).isoformat(),"stats":{"races":len(result["predictions"]),"boats":len(result["rationales"]),"A":result["counts"].get("A",0),"B":result["counts"].get("B",0),"C":result["counts"].get("C",0),"exacta_targets":result["target_count"]},"outputs":{pred.name:sha256_file(pred),rat.name:sha256_file(rat),sale.name:sha256_file(sale)}}
    manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True,type=Path); parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--prediction-time",required=True); parser.add_argument("--sales-time"); parser.add_argument("--source-commit",default="")
    args=parser.parse_args()
    print(json.dumps(run(args.input,args.output_dir,args.prediction_time,args.sales_time,args.source_commit),ensure_ascii=False,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
