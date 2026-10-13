#!/usr/bin/env python3
"""Build JRA Course Profile Master Phase 3 seed from Phase 1 BAC audit + official config."""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path

SURFACE_NAMES={"1":"turf","2":"dirt","3":"obstacle"}
TOKENS={"1":"T","2":"D","3":"O"}

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_jsonl(path, rows):
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows),encoding="utf-8")

def layout_from_observation(venue,surface,distance,turn,layout):
    if surface=="1":
        if turn=="3":
            return "straight"
        if venue=="04":
            return "outer" if layout=="2" else "inner"
        if venue=="06":
            return "outer-inner" if distance==3200 else ("outer" if layout=="2" else "inner")
        if venue=="08":
            return "outer" if layout=="2" else "inner"
        if venue=="09":
            return "outer-inner" if distance==3200 else ("outer" if layout=="2" else "inner")
        return "main"
    if surface=="2":
        return "main"
    return "obstacle"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--phase1-audit",required=True)
    ap.add_argument("--official-config",required=True)
    ap.add_argument("--output-dir",required=True)
    args=ap.parse_args()
    audit=load_json(args.phase1_audit)
    official=load_json(args.official_config)
    venues=official["venues"]

    current_keys=set()
    for venue,cfg in venues.items():
        for surface,layouts in cfg["current_flat_course_layouts"].items():
            for layout_variant,distances in layouts.items():
                for distance in distances:
                    current_keys.add((venue,surface,int(distance),layout_variant))

    grouped={}
    observed_route_variants=defaultdict(set)
    for r in audit["distinct_course_combinations"]:
        key=(str(r["venue_code"]),str(r["surface_code"]),int(r["distance_m"]),str(r["turn_code"]),str(r["layout_code"]))
        g=grouped.setdefault(key,{"race_count":0,"first_race_date":r["first_race_date"],"last_race_date":r["last_race_date"]})
        g["race_count"]+=int(r["race_count"])
        g["first_race_date"]=min(g["first_race_date"],r["first_race_date"])
        g["last_race_date"]=max(g["last_race_date"],r["last_race_date"])
        observed_route_variants[(key[0],key[1],key[2])].add((key[3],key[4]))

    masters={}
    for (venue,surface,distance,turn,layout),g in grouped.items():
        lv=layout_from_observation(venue,surface,distance,turn,layout)
        ck=f"JRA:{venue}:{TOKENS[surface]}:{distance}:{lv}"
        current=(venue,surface,distance,lv) in current_keys
        cfg=venues[venue]
        if ck not in masters:
            masters[ck]={
                "course_key":ck,"venue_code":venue,"venue_name":cfg["venue_name"],
                "surface_code":surface,"surface":SURFACE_NAMES[surface],"distance_m":distance,
                "layout_variant":lv,"status":"ACTIVE" if current else ("PROVISIONAL" if surface=="3" else "HISTORICAL"),
                "turn_direction":"straight" if lv=="straight" else (cfg["turn_direction"] if surface!="3" else None),
                "physical_data_status":"PARTIAL" if current and surface!="3" else "UNKNOWN",
                "observed_2010_2025":True,"current_jra_official":current,
                "first_observed_race_date":g["first_race_date"],"last_observed_race_date":g["last_race_date"],
                "observed_race_count":g["race_count"],"source_locator":cfg["source_locator"] if current else None,
                "first_corner_distance_m":None,"start_straight_m":None,
                "final_straight_slope_flag":None,"start_slope_flag":None
            }
        else:
            rec=masters[ck]
            rec["observed_race_count"] += g["race_count"]
            rec["first_observed_race_date"]=min(rec["first_observed_race_date"],g["first_race_date"])
            rec["last_observed_race_date"]=max(rec["last_observed_race_date"],g["last_race_date"])

    for venue,surface,distance,lv in sorted(current_keys):
        ck=f"JRA:{venue}:{TOKENS[surface]}:{distance}:{lv}"
        if ck not in masters:
            cfg=venues[venue]
            masters[ck]={
                "course_key":ck,"venue_code":venue,"venue_name":cfg["venue_name"],
                "surface_code":surface,"surface":SURFACE_NAMES[surface],"distance_m":distance,
                "layout_variant":lv,"status":"ACTIVE","turn_direction":"straight" if lv=="straight" else cfg["turn_direction"],
                "physical_data_status":"PARTIAL","observed_2010_2025":False,"current_jra_official":True,
                "first_observed_race_date":None,"last_observed_race_date":None,"observed_race_count":0,
                "source_locator":cfg["source_locator"],"first_corner_distance_m":None,"start_straight_m":None,
                "final_straight_slope_flag":None,"start_slope_flag":None
            }

    geometry=[]
    geometry_by=(defaultdict(list))
    for venue,cfg in venues.items():
        for row0 in cfg["geometry_configurations"]:
            row=dict(row0); geometry.append(row)
            geometry_by[(venue,row["surface_code"],row["layout_variant"])].append(row)
    for rec in masters.values():
        rows=geometry_by.get((rec["venue_code"],rec["surface_code"],rec["layout_variant"]),[])
        if rec["current_jra_official"] and rows:
            elevations={r.get("elevation_difference_m") for r in rows if r.get("elevation_difference_m") is not None}
            straights={r.get("final_straight_m") for r in rows if r.get("final_straight_m") is not None}
            rec["elevation_difference_m"]=next(iter(elevations)) if len(elevations)==1 else None
            rec["final_straight_m"]=next(iter(straights)) if len(straights)==1 else None
            rec["final_straight_m_varies_by_rail"]=len(straights)>1
        else:
            rec["elevation_difference_m"]=None
            rec["final_straight_m"]=None
            rec["final_straight_m_varies_by_rail"]=False

    mappings=[]
    for r in audit["distinct_course_combinations"]:
        venue=str(r["venue_code"]); surface=str(r["surface_code"]); distance=int(r["distance_m"])
        turn=str(r["turn_code"]); layout=str(r["layout_code"]); cc=r.get("course_code")
        lv=layout_from_observation(venue,surface,distance,turn,layout)
        ck=f"JRA:{venue}:{TOKENS[surface]}:{distance}:{lv}"
        if surface in ("1","2"):
            status="CONFIRMED" if masters.get(ck,{}).get("current_jra_official") else "PROVISIONAL"
            reason="Flat-course tuple mapped by Phase 3 v0.1 identity rule"
        else:
            if len(observed_route_variants[(venue,surface,distance)])>1:
                ck=None; status="UNRESOLVED"; reason="Multiple obstacle route observations require route-level verification"
            else:
                status="PROVISIONAL"; reason="Obstacle route not yet verified against JRA route definition"
        mappings.append({
            "venue_code":venue,"surface_code":surface,"distance_m":distance,
            "turn_code":turn,"layout_code":layout,"course_code":None if cc in (None,"") else str(cc),
            "course_key":ck,"mapping_status":status,"mapping_reason":reason,
            "first_observed_race_date":r["first_race_date"],"last_observed_race_date":r["last_race_date"],
            "observed_race_count":int(r["race_count"])
        })

    master_rows=sorted(masters.values(),key=lambda x:(x["venue_code"],x["surface_code"],x["distance_m"],x["layout_variant"]))
    mappings=sorted(mappings,key=lambda x:(x["venue_code"],x["surface_code"],x["distance_m"],x["turn_code"],x["layout_code"],x["course_code"] or ""))
    geometry=sorted(geometry,key=lambda x:(x["venue_code"],x["surface_code"],x["layout_variant"],x["rail_label"]))
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    write_jsonl(out/"course_master_seed_v0_1.jsonl",master_rows)
    write_jsonl(out/"course_jrdb_mapping_seed_v0_1.jsonl",mappings)
    write_jsonl(out/"course_geometry_configuration_v0_1.jsonl",geometry)
    summary={
        "schema_version":"jra-course-profile-phase3-build-v0.1",
        "course_master_rows":len(master_rows),
        "flat_rows":sum(r["surface_code"]!="3" for r in master_rows),
        "obstacle_rows":sum(r["surface_code"]=="3" for r in master_rows),
        "current_official_only_rows":sum(r["current_jra_official"] and not r["observed_2010_2025"] for r in master_rows),
        "historical_observed_only_rows":sum(r["observed_2010_2025"] and not r["current_jra_official"] for r in master_rows),
        "geometry_rows":len(geometry),
        "mapping_rows":len(mappings),
        "unresolved_mapping_rows":sum(r["mapping_status"]=="UNRESOLVED" for r in mappings)
    }
    (out/"phase3_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS",**summary},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
