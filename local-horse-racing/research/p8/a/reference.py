"""History-only A3/A4 reference generation; no labels. All reference dates strictly earlier than each historical observation."""
import duckdb,numpy as np,pyarrow as pa,pyarrow.parquet as pq,hashlib,json,sys,re,unicodedata
from pathlib import Path
from collections import defaultdict
O=Path(__file__).parent;threads=int(sys.argv[1]); c=duckdb.connect();c.execute(f'set threads={threads}');c.execute("set memory_limit='2200MB'")
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((O/'input_manifest.json').read_text()); assert sha(O/'entry.parquet')==m['entry_sha256'] and sha(O/'history.parquet')==m['history_sha256']; config=json.loads((O/'a34_config.json').read_text());assert sha(O/'a1a2_decision.json')==config['a1a2_decision_sha256']
for n,f in [('entry','entry.parquet'),('hist','history.parquet')]:c.execute(f"create view {n} as select * from read_parquet('{O/f}')")
# 2016 warm-up pre-A0 available only from earlier 2016. Later pre-A0 derived from the audited P8A.1 feature Freeze.
fmanifest=json.loads((O/'feature_manifest.json').read_text());files=[]
for y in range(2017,2024):
 p=O/f'features_{y}_t{threads}.parquet';assert sha(p)==fmanifest['files'][p.name];files.append(str(p))
c.execute(f"""create table base as select runner_id,race_id,race_date,venue,case when n_a0>=2 and not ambiguous then a0 end a0 from read_parquet({files!r}) union all select t.runner_id,t.race_id,t.race_date,t.venue,case when count(h.runner_id)>=2 and not t.ambiguous then avg(h.perf order by h.race_date,h.runner_id) end a0 from entry t left join hist h on h.horse_key=t.horse_key and h.race_date<t.race_date and h.race_date>=t.race_date-interval '180 days' where year(t.race_date)=2016 group by t.runner_id,t.race_id,t.race_date,t.venue,t.ambiguous""")
# Opponents defined by ENTRY roster, including unknowns, never current race finishing order. Global past-only reference daily sufficient stats.
c.execute("""create table opp_raw as with t as (select *,count(*) over w nr,count(a0) over w nk,sum(cast(a0 as decimal(28,16))) over w sa from base window w as(partition by race_id)), o as (select runner_id,race_date,case when nk-(a0 is not null)::int>=3 and (nk-(a0 is not null)::int)::double/nullif(nr-1,0)>=.5 then (sa::double-coalesce(a0,0))/(nk-(a0 is not null)::int) end opp from t) select * from o""")
opp_query="""with d as (select race_date,sum(cast(opp as decimal(28,16))) s,sum(cast(opp*opp as decimal(28,16))) ss,count(opp) n from {tbl} group by race_date), ref as (select race_date,sum(s) over w::double/nullif(sum(n) over w,0)::double mu,sum(ss) over w::double/nullif(sum(n) over w,0)::double m2,sum(n) over w n,max(race_date) filter(where n>0) over w refmax from d window w as(order by race_date range between interval '365 days' preceding and interval '1 day' preceding)) select runner_id,o.race_date,case when n>=100 and m2-mu*mu>1e-12 then greatest(-3.,least(3.,(opp-mu)/sqrt(m2-mu*mu)))/6 end opp_delta,refmax opp_ref_max from {tbl} o join ref using(race_date) where opp is not null"""
c.execute("create table opp as "+opp_query.format(tbl="opp_raw"))
opp_checks=[]
for y in range(2017,2024):
 d=c.execute(f"select min(race_date) from opp_raw where year(race_date)={y}").fetchone()[0]
 c.execute(f"create or replace view op_prefix as select * from opp_raw where race_date<=date '{d}'")
 c.execute(f"create or replace view op_inject as select * from opp_raw union all select runner_id,race_date+1,99999.0 from opp_raw where race_date=date '{d}'")
 for tab,src in [("op_p","op_prefix"),("op_i","op_inject")]:
  c.execute(f"create or replace temp table {tab} as "+opp_query.format(tbl=src)+f" and o.race_date=date '{d}'")
  diff=c.execute(f"select count(*) from (select * from opp where race_date=date '{d}') a full join {tab} b using(runner_id) where a.runner_id is null or b.runner_id is null or a.opp_ref_max is distinct from b.opp_ref_max or (a.opp_delta is null)<>(b.opp_delta is null) or abs(a.opp_delta-b.opp_delta)>1e-12").fetchone()[0];assert diff==0,(y,tab,diff);opp_checks.append({"year":y,"test":tab,"difference":diff})

# one valid race winner observation, all timing references earlier than the historical race date
races=c.execute("""select race_id,race_date,venue,distance_m,surface,any_value(conditions order by runner_id) conditions,any_value(race_name order by runner_id) race_name,any_value(prize_yen_1 order by runner_id) prize,min(finish_time_seconds) filter(where finish_position=1) win_time from hist group by 1,2,3,4,5 order by race_date,race_id""").fetchall()
def ageclass(s):
 s=unicodedata.normalize('NFKC',s or ''); m=re.search(r'([234])歳(以上)?',s);return (m.group(1)+'+' if m.group(2) else m.group(1)) if m else ('general' if '一般' in s else 'unknown')
def classcode(s):
 s=unicodedata.normalize('NFKC',s or ''); codes=set(re.findall(r'[ABC][1-9]',s));return next(iter(codes)) if len(codes)==1 else 'UNKNOWN'
course=defaultdict(list);prize=defaultdict(list);audit=defaultdict(lambda:[0,0,0]);
for r in races:
 rid,d,v,dist,surf,cond,name,amt,wt=r; course[(v,dist,surf)].append(r); ag=ageclass(cond);code=classcode(name)
 if ag!='unknown':prize[(v,ag)].append(r)
 if d.year<=2021:
  a=audit[(v,d.year,ag,code)];a[0]+=1;a[1]+=amt is not None and amt>0;a[2]+=wt is not None
# reference function uses sorted arrays, all dates strictly prior; equality handling via searchsorted left
import datetime as dt
ref={};pr={};guard=[]
def rolling(groups,kind):
 out={};tests=0
 for key,rs in groups.items():
  days=np.array([r[1].toordinal() for r in rs]); vals=np.array([float(r[8] if kind=='speed' else r[7]) if (r[8] if kind=='speed' else r[7]) is not None else np.nan for r in rs]);
  for day in np.unique(days):
   lo=np.searchsorted(days,day-365,'left');hi=np.searchsorted(days,day,'left');end=np.searchsorted(days,day,'right'); prior=vals[lo:hi];prior=prior[np.isfinite(prior)&(prior>0)];n=len(prior); md=scale=None;last=dt.date.fromordinal(int(days[hi-1])) if hi>lo else None
   if n>=100 and kind=='speed':
    md=float(np.median(prior));scale=float(1.4826*np.median(np.abs(prior-md)));scale=scale if scale>1e-12 else None
   for i in range(hi,end):
    r=rs[i]
    if kind=='speed':out[r[0]]=(md,scale,n,last)
    else:
     val=vals[i];p=float((np.count_nonzero(prior<val)+.5*np.count_nonzero(prior==val))/n-.5) if n>=100 and np.isfinite(val) and val>0 else None;out[r[0]]=(p,n,last)
   # explicit prefix/future mutation at every January boundary and a deterministic monthly sample per key
   if (dt.date.fromordinal(int(day)).day==1 or (hi==0 and n==0)) and len(rs)>0:
    prefix=vals[:hi];pre=prefix[lo:];pre=pre[np.isfinite(pre)&(pre>0)]; assert np.array_equal(prior,pre);assert hi==0 or days[hi-1]<day
    # same-day/future extreme values cannot alter prior slice, including equal-date races
    injected=vals.copy();injected[hi:]=999999999.;sub=injected[lo:hi];sub=sub[np.isfinite(sub)&(sub>0)];assert np.array_equal(prior,sub);tests+=1
 return out,tests
ref,t1=rolling(course,'speed');pr,t2=rolling(prize,'prize');
rows=[]
for r in races:
 rid,d,*_=r; med,scale,n,last=ref[rid];p,pn,pl=pr.get(rid,(None,0,None));rows.append((rid,med,scale,n,last,p,pn,pl,r[8]));assert last is None or last<d;assert pl is None or pl<d
schema=pa.schema([('race_id',pa.string()),('ref_median',pa.float64()),('ref_scale',pa.float64()),('speed_ref_n',pa.int64()),('speed_ref_max',pa.date32()),('prize_delta',pa.float64()),('prize_ref_n',pa.int64()),('prize_ref_max',pa.date32()),('winner_time',pa.float64())]); table=pa.Table.from_pylist([dict(zip(schema.names,r)) for r in rows],schema=schema);c.register('ref',table)
c.execute("""create table enriched as select h.runner_id,h.race_id,h.race_date,h.horse_key,h.perf,o.opp_delta,o.opp_ref_max,r.prize_delta,r.prize_ref_n,r.prize_ref_max,case when r.ref_scale>0 then .5+greatest(-3.,least(3.,(r.ref_median-h.finish_time_seconds)/r.ref_scale))/6 end speed_score,r.speed_ref_n,r.speed_ref_max,case when r.winner_time>0 then 1.0/(1.0+greatest(0.,h.finish_time_seconds-r.winner_time)/(h.distance_m/1000.0)) end gap_score from hist h left join opp o using(runner_id) left join ref r using(race_id)""")
assert c.execute('select count(*) from enriched where opp_ref_max>=race_date or prize_ref_max>=race_date or speed_ref_max>=race_date').fetchone()[0]==0
p=O/f'enriched_t{threads}.parquet';c.execute(f"copy (select * from enriched order by runner_id) to '{p}' (format parquet,compression zstd)");
import csv
with open(O/f'class_audit_t{threads}.csv','w') as f:
 w=csv.writer(f);w.writerow(['venue','year','age_group','explicit_class','races','prize_present','winner_time_present']);w.writerows([(*k,*v) for k,v in sorted(audit.items())])
coverage=c.execute('select year(race_date) yr,count(*) n,count(opp_delta),count(prize_delta),count(speed_score),count(gap_score) from enriched group by 1 order by 1').fetchall();print('reference',threads,coverage,sha(p),flush=True)
(O/f'reference_audit_t{threads}.json').write_text(json.dumps({'threads':threads,'coverage_by_year':coverage,'reference_prefix_injection_checks':{'speed':t1,'prize':t2,'opponent':opp_checks},'strict_reference_dates':'PASS','enriched_sha256':sha(p),'class_policy':'explicit class feasibility only, not promoted or nationally mapped'},indent=2)+'\n')
