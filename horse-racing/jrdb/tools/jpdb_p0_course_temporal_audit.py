#!/usr/bin/env python3
"""Read-only JPDB P0 Course Master temporal join against accepted BAC 2023-25.

Course inputs are the accepted RRDB Horse Course Fit 2026-01-01 Phase3 seed,
not rebuilt guesses. Physical verification epoch != historical course_version.
"""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
import duckdb

def jsonl(p):
    return [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]

def path_sql(p):
    return str(p.resolve()).replace("'","''")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input-root",required=True,type=Path)
    ap.add_argument("--course-root",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    paths={k:a.course_root/"course_master"/f"{k}_v0_1.jsonl" for k in
           ("course_master_seed","course_jrdb_mapping_seed","course_geometry_configuration")}
    master,mapping,geometry=(jsonl(paths[k]) for k in paths)
    if tuple(map(len,(master,mapping,geometry)))!=(177,433,57):
        raise ValueError("Phase3 input cardinality changed")
    db=duckdb.connect(":memory:")
    db.execute("""CREATE TABLE cm (course_key VARCHAR, physical_data_status VARCHAR,
      physical_version_id VARCHAR, physical_valid_from VARCHAR,
      physical_valid_to_exclusive VARCHAR, final_straight_m DOUBLE,
      final_straight_slope_flag BOOLEAN, course_size_class VARCHAR)""")
    db.executemany("INSERT INTO cm VALUES (?,?,?,?,?,?,?,?)",[
        (x["course_key"],x.get("physical_data_status"),x.get("physical_version_id"),
         x.get("physical_valid_from"),x.get("physical_valid_to_exclusive"),
         x.get("final_straight_m"),x.get("final_straight_slope_flag"),
         x.get("course_size_class")) for x in master])
    db.execute("""CREATE TABLE map (venue_code VARCHAR, surface_code VARCHAR,
      distance_m BIGINT, turn_code VARCHAR, layout_code VARCHAR, course_code VARCHAR,
      course_key VARCHAR, mapping_status VARCHAR)""")
    db.executemany("INSERT INTO map VALUES (?,?,?,?,?,?,?,?)",[
        (x["venue_code"],x["surface_code"],x["distance_m"],x["turn_code"],
         x["layout_code"],x.get("course_code"),x.get("course_key"),x["mapping_status"])
        for x in mapping])
    db.execute("""CREATE TABLE geo (venue_code VARCHAR, surface_code VARCHAR,
      layout_variant VARCHAR, jrdb_course_code VARCHAR, geometry_key VARCHAR,
      physical_version_id VARCHAR, physical_valid_from VARCHAR,
      physical_valid_to_exclusive VARCHAR)""")
    db.executemany("INSERT INTO geo VALUES (?,?,?,?,?,?,?,?)",[
        (x["venue_code"],x["surface_code"],x["layout_variant"],
         x.get("jrdb_course_code"),x["geometry_key"],
         x.get("physical_version_id"),x.get("physical_valid_from"),
         x.get("physical_valid_to_exclusive")) for x in geometry])
    years=[]
    for year in (2023,2024,2025):
        for family in ("bac","kyi","sed"):
            matches=list((a.input_root/f"{family}_{year}").glob("*.parquet"))
            if len(matches)!=1:
                raise ValueError(f"Expected one immutable {family} {year}: {len(matches)}")
            db.execute(f"CREATE OR REPLACE VIEW {family} AS SELECT * FROM read_parquet('{path_sql(matches[0])}')")
        db.execute("""CREATE OR REPLACE VIEW joined AS SELECT b.race_key_raw,b.race_date,
          b.surface_code,b.course_code,m.course_key,m.mapping_status,
          c.physical_data_status,c.physical_version_id,c.physical_valid_from,
          c.physical_valid_to_exclusive,c.final_straight_m,c.final_straight_slope_flag,
          c.course_size_class,g.geometry_key,g.physical_version_id AS geo_version_id,
          g.physical_valid_from AS geo_valid_from,
          g.physical_valid_to_exclusive AS geo_valid_to
          FROM bac b LEFT JOIN map m
          ON b.venue_code=m.venue_code AND b.surface_code=m.surface_code
           AND TRY_CAST(b.distance_raw AS BIGINT)=m.distance_m
           AND b.turn_code=m.turn_code AND b.layout_code=m.layout_code
           AND b.course_code IS NOT DISTINCT FROM m.course_code
          LEFT JOIN cm c ON m.course_key=c.course_key
          LEFT JOIN geo g ON b.venue_code=g.venue_code AND b.surface_code=g.surface_code
           AND split_part(c.course_key,':',5)=g.layout_variant
           AND (b.course_code=g.jrdb_course_code OR
                (b.surface_code='2' AND g.jrdb_course_code IS NULL))
        """)
        q=lambda s:db.execute(s).fetchone()[0]
        def dist(s):
            return {(str(k) if k is not None else "<NULL>"):int(n)
              for k,n in db.execute(s).fetchall()}
        r={
          "year":year,"bac_count":q("SELECT COUNT(*) FROM bac"),
          "join_count":q("SELECT COUNT(*) FROM joined"),
          "surface_counts":dist("SELECT surface_code,COUNT(*) FROM joined GROUP BY 1"),
          "mapping_status_all":dist("SELECT COALESCE(mapping_status,'MISSING'),COUNT(*) FROM joined GROUP BY 1"),
          "mapping_status_flat":dist("""SELECT COALESCE(mapping_status,'MISSING'),COUNT(*)
                      FROM joined WHERE surface_code IN ('1','2') GROUP BY 1"""),
          "mapping_status_obstacle":dist("""SELECT COALESCE(mapping_status,'MISSING'),COUNT(*)
                      FROM joined WHERE surface_code='3' GROUP BY 1"""),
          "flat_missing_course_key":q("""SELECT COUNT(*) FROM joined
                  WHERE surface_code IN ('1','2') AND course_key IS NULL"""),
          "flat_missing_geometry_key":q("""SELECT COUNT(*) FROM joined
                  WHERE surface_code IN ('1','2') AND geometry_key IS NULL"""),
          "flat_geometry_version_conflict":q("""SELECT COUNT(*) FROM joined
                  WHERE surface_code IN ('1','2') AND geometry_key IS NOT NULL
                  AND physical_version_id IS DISTINCT FROM geo_version_id"""),
          "flat_master_physical_epoch_ok":q("""SELECT COUNT(*) FROM joined
                  WHERE surface_code IN ('1','2') AND physical_version_id IS NOT NULL
                  AND race_date>=physical_valid_from
                  AND (physical_valid_to_exclusive IS NULL OR race_date<physical_valid_to_exclusive)"""),
          "flat_geometry_physical_epoch_ok":q("""SELECT COUNT(*) FROM joined
                  WHERE surface_code IN ('1','2') AND geometry_key IS NOT NULL
                  AND race_date>=geo_valid_from
                  AND (geo_valid_to IS NULL OR race_date<geo_valid_to)"""),
          "flat_physical_data_status":dist("""SELECT COALESCE(physical_data_status,'MISSING'),
               COUNT(*) FROM joined WHERE surface_code IN ('1','2') GROUP BY 1"""),
          "flat_master_slope_known":q("""SELECT COUNT(*) FROM joined
               WHERE surface_code IN ('1','2') AND final_straight_slope_flag IS NOT NULL"""),
          "flat_master_final_straight_known":q("""SELECT COUNT(*) FROM joined
               WHERE surface_code IN ('1','2') AND final_straight_m IS NOT NULL"""),
          "flat_master_course_size_known":q("""SELECT COUNT(*) FROM joined
               WHERE surface_code IN ('1','2') AND course_size_class IS NOT NULL"""),
          "flat_distinct_course_keys":q("SELECT COUNT(DISTINCT course_key) FROM joined WHERE surface_code IN ('1','2')"),
          "flat_distinct_geometry_keys":q("SELECT COUNT(DISTINCT geometry_key) FROM joined WHERE surface_code IN ('1','2')"),
          "rider_difference_count":q("""SELECT COUNT(*) FROM kyi k JOIN sed s
               ON k.race_key_raw=s.race_key_raw AND k.horse_no=s.horse_no
               WHERE k.jockey_code IS DISTINCT FROM s.jockey_code"""),
          "rider_difference_abnormal_codes":dist("""SELECT COALESCE(s.abnormal_code,'<NULL>'),COUNT(*)
               FROM kyi k JOIN sed s ON k.race_key_raw=s.race_key_raw
               AND k.horse_no=s.horse_no WHERE k.jockey_code IS DISTINCT FROM s.jockey_code
               GROUP BY 1"""),
          "flat_outlier_samples":[dict(zip(("race_key_raw","race_date","surface_code","mapping_status","course_key","geometry_key"),row))
               for row in db.execute("""SELECT race_key_raw,race_date,surface_code,
                   mapping_status,course_key,geometry_key FROM joined
                   WHERE surface_code IN ('1','2') AND
                     (mapping_status IS DISTINCT FROM 'CONFIRMED' OR geometry_key IS NULL)
                   ORDER BY race_key_raw LIMIT 25""").fetchall()]
        }
        if r["join_count"]!=r["bac_count"]:
            raise RuntimeError(f"Fanout in course join {year}: {r['join_count']} != {r['bac_count']}")
        r["flat_total"]=r["surface_counts"].get("1",0)+r["surface_counts"].get("2",0)
        r["identity_gate_pass"]=r["flat_missing_course_key"]==0 and r["flat_geometry_version_conflict"]==0
        years.append(r)
    obj={
      "status":"PASS" if all(x["identity_gate_pass"] for x in years) else "REVIEW_REQUIRED",
      "warehouse_generation":"jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix",
      "course_seed_source":{"run_id":38370479179,
        "artifact_name":"rrdb-course-fit-v0-1-38370479179",
        "master_rows":len(master),"mapping_rows":len(mapping),"geometry_rows":len(geometry),
        "source_sha256":{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()}},
      "historical_course_version_id_available":False,
      "physical_epoch_is_not_full_historical_proof":True,
      "last_pre_race_jockey_snapshot_verified":False,
      "as_of_pre_race_availability_verified":False,
      "years":years
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":obj["status"],"years":[
      {k:v for k,v in r.items() if k!="flat_outlier_samples"} for r in years]},ensure_ascii=False))
    return 0 if obj["status"]=="PASS" else 2
if __name__=="__main__":
    raise SystemExit(main())
