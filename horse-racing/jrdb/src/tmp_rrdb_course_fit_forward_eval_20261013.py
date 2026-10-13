#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import duckdb

def q(x): return "'" + str(x).replace("'","''") + "'"

ap=argparse.ArgumentParser()
ap.add_argument("--fit-root",type=Path,required=True)
ap.add_argument("--rrdb-root",type=Path,required=True)
ap.add_argument("--out",type=Path,required=True)
a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
c=duckdb.connect()
cand=a.fit_root/"fit/research/candidate_fit_view.parquet"
cm=a.fit_root/"course_master/course_master_seed_v0_1.jsonl"
hp=list(a.rrdb_root.glob("**/objects/fact_horse_performance/year=202[56]/*.parquet"))
c.execute(f"create view cand as select * from read_parquet({q(cand)})")
c.execute("create view hp as select * from read_parquet(["+",".join(q(x) for x in hp)+"],union_by_name=true)")
c.execute(f"create view cm0 as select * from read_json_auto({q(cm)})")
schemas={x:[r[0] for r in c.execute("describe "+x).fetchall()] for x in ["cand","hp","cm0"]}
(a.out/"schemas.json").write_text(json.dumps(schemas,indent=2,ensure_ascii=False)+"\n")
need=["race_date","race_key","horse_id","horse_no","surface_code","distance_m","finish","horse_adjusted_delta_per_1000m"]
miss=[x for x in need if x not in schemas["hp"]]
if miss: raise SystemExit("missing hp "+repr(miss))
track="track_condition_code" if "track_condition_code" in schemas["hp"] else None
pace="race_pace_code" if "race_pace_code" in schemas["hp"] else None
c.execute("""create view cmu as with x as(
 select venue_code,surface_code,distance_m,count(*) n,min(turn_direction) turn_direction,
 min(layout_variant) layout_variant,min(final_straight_m) final_straight_m,
 min(final_straight_slope_flag) slope,min(course_size_class) course_size
 from cm0 where current_jra_official and surface_code in ('1','2') and physical_valid_from is not null
 group by 1,2,3) select * from x where n=1""")
track_expr=f"h.{track}" if track else "NULL::VARCHAR"
pace_expr=f"h.{pace}" if pace else "NULL::VARCHAR"
c.execute(f"""create view r0 as select h.*,substr(race_key,1,2) venue_code,
 -horse_adjusted_delta_per_1000m perf,m.turn_direction,m.layout_variant,m.final_straight_m,
 case when m.slope then 'PRESENT' when m.slope=false then 'ABSENT' end final_slope,
 m.course_size,
 case when m.final_straight_m<350 then 'SHORT' when m.final_straight_m<450 then 'MEDIUM'
 when m.final_straight_m>=450 then 'LONG' end straight_bucket,
 cast({track_expr} as varchar) going,cast({pace_expr} as varchar) pace
 from hp h left join cmu m on substr(race_key,1,2)=m.venue_code
 and h.surface_code=m.surface_code and h.distance_m=m.distance_m
 where race_date>=date '2025-01-01' and race_date<date '2026-10-13'""")
c.execute("""create view r as select *,
 lag(race_date) over w prev_date,lag(surface_code) over w prev_surface,
 lag(distance_m) over w prev_distance,lag(turn_direction) over w prev_turn,
 lag(final_slope) over w prev_slope,lag(final_straight_m) over w prev_straight,
 lag(course_size) over w prev_size,lag(layout_variant) over w prev_layout,
 lag(going) over w prev_going
 from r0 window w as(partition by horse_id order by race_date,race_key,horse_no)""")
c.execute("""create view e as select *,
 distance_m-prev_distance dd,final_straight_m-prev_straight sd,
 surface_code is distinct from prev_surface schg,
 case when distance_m-prev_distance<=-400 then 'SHORTEN_LARGE'
 when distance_m-prev_distance<=-100 then 'SHORTEN_SMALL'
 when distance_m-prev_distance<100 then 'SAME'
 when distance_m-prev_distance<400 then 'EXTEND_SMALL'
 else 'EXTEND_LARGE' end dchg,
 case when going='1' then 'FIRM' when going in('2','3','4') then 'SOFT' end gc,
 case when prev_going='1' then 'FIRM' when prev_going in('2','3','4') then 'SOFT' end pgc
 from r where race_date>=date '2026-01-01'""")
parts=[
"select *,'ABSOLUTE' fam,'TURN_DIRECTION' ft,turn_direction fv,false sc from e where turn_direction is not null",
"select *,'ABSOLUTE' fam,'FINAL_SLOPE' ft,final_slope fv,false sc from e where final_slope is not null",
"select *,'ABSOLUTE' fam,'FINAL_STRAIGHT_BUCKET' ft,straight_bucket fv,false sc from e where straight_bucket is not null",
"select *,'ABSOLUTE' fam,'COURSE_SIZE' ft,course_size fv,false sc from e where course_size is not null",
"select *,'ABSOLUTE' fam,'LAYOUT' ft,layout_variant fv,false sc from e where layout_variant is not null",
"select *,'TRANSITION' fam,'DISTANCE_CHANGE' ft,dchg fv,schg sc from e where prev_date is not null",
"select *,'TRANSITION' fam,'TURN_DIRECTION_CHANGE' ft,prev_turn||'_TO_'||turn_direction fv,schg sc from e where prev_turn is not null and turn_direction is not null",
"select *,'TRANSITION' fam,'FINAL_SLOPE_CHANGE' ft,case when prev_slope=final_slope then 'SAME' when prev_slope='ABSENT' then 'NO_SLOPE_TO_SLOPE' else 'SLOPE_TO_NO_SLOPE' end fv,schg sc from e where prev_slope is not null and final_slope is not null",
"select *,'TRANSITION' fam,'FINAL_STRAIGHT_CHANGE' ft,case when sd < -5 then 'SHORTER' when sd>5 then 'LONGER' else 'SIMILAR' end fv,schg sc from e where sd is not null",
"select *,'TRANSITION' fam,'COURSE_SIZE_CHANGE' ft,prev_size||'_TO_'||course_size fv,schg sc from e where prev_size is not null and course_size is not null",
"select *,'TRANSITION' fam,'LAYOUT_CHANGE' ft,prev_layout||'_TO_'||layout_variant fv,schg sc from e where prev_layout is not null and layout_variant is not null"]
if pace: parts.append("select *,'ABSOLUTE' fam,'PACE_PROFILE' ft,pace fv,false sc from e where pace in('H','M','S')")
if track:
 parts.append("select *,'TRANSITION' fam,'GOING_CHANGE' ft,pgc||'_TO_'||gc fv,schg sc from e where pgc is not null and gc is not null and not schg")
c.execute("create view ev as "+" union all ".join(parts))
c.execute("""create view m as select e.race_date,e.race_key,e.horse_id,e.finish,e.perf,e.fam,e.ft,e.fv,
 x.sample_count,x.shrunk_delta,x.confidence from ev e join cand x
 on e.horse_id=x.horse_id and e.surface_code=x.surface_code and e.fam=x.fit_family
 and e.ft=x.feature_type and e.fv=x.feature_value and e.sc=x.surface_changed""")
c.execute("""create view b as select fam,ft,count(*) bn,avg((finish=1)::int)::double bw,
 avg((finish<=3)::int)::double bp,avg(perf) bf from m where sample_count>=4 group by 1,2""")
thresholds=[("POS",0,0,4),("D05C03",.05,.3,4),("D10C05",.10,.5,4),("D15C05",.15,.5,4),("D10C07H",.10,.7,6)]
qs=[]
for n,d,cf,nn in thresholds:
 qs.append(f"""select m.fam,m.ft,'{n}' rule,count(*) n,count(distinct horse_id) horses,
 avg((finish=1)::int)::double win,avg((finish<=3)::int)::double top3,avg(perf) perf,
 avg((finish=1)::int)::double-b.bw win_lift,avg((finish<=3)::int)::double-b.bp top3_lift,
 avg(perf)-b.bf perf_lift from m join b using(fam,ft)
 where sample_count>={nn} and shrunk_delta>={d} and confidence>={cf}
 group by 1,2,3,b.bw,b.bp,b.bf""")
c.execute("create view ts as "+" union all ".join(qs))
c.execute(f"copy(select * from ts order by fam,ft,rule) to {q(a.out/'thresholds.csv')} (header,delimiter ',')")
c.execute(f"""copy(select m.fam,m.ft,m.fv,count(*) n,avg((finish=1)::int)::double win,
 avg((finish<=3)::int)::double top3,avg(perf) perf,avg((finish=1)::int)::double-b.bw win_lift,
 avg((finish<=3)::int)::double-b.bp top3_lift,avg(perf)-b.bf perf_lift
 from m join b using(fam,ft) where sample_count>=4 and shrunk_delta>=.10 and confidence>=.5
 group by 1,2,3,b.bw,b.bp,b.bf order by n desc)
 to {q(a.out/'values.csv')} (header,delimiter ',')""")
c.execute(f"""copy(select fam,ft,case when race_date<date '2026-07-01' then 'H1' else 'H2' end period,
 count(*) n,avg((finish=1)::int)::double win,avg((finish<=3)::int)::double top3,avg(perf) perf
 from m where sample_count>=4 and shrunk_delta>=.10 and confidence>=.5
 group by 1,2,3 order by 1,2,3) to {q(a.out/'stability.csv')} (header,delimiter ',')""")
meta={"rrdb_runs":c.execute("select count(*) from e").fetchone()[0],
"races":c.execute("select count(distinct race_key) from e").fetchone()[0],
"matched":c.execute("select count(*) from m").fetchone()[0],
"track":bool(track),"pace":bool(pace),
"course_mapping":"unique venue+surface+distance only","roi":"not in first-pass"}
(a.out/"summary.json").write_text(json.dumps(meta,indent=2)+"\n")
print(json.dumps(meta))
