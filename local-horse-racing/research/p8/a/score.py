"""Score-only process. Reads SHA-pinned feature Parquet and frozen configuration, never label, history or canonical files."""
import sys,json,hashlib
from pathlib import Path
import duckdb
O=Path(__file__).parent; mode=sys.argv[1]; thread=int(sys.argv[2]); c=duckdb.connect();c.execute(f'set threads={thread}');c.execute("set memory_limit='1800MB'")
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
base=['a0','ac0','acj0','last3','last5','last8','mean90','mean365','hl30','hl60','hl90']; windows=set(base)-{'ac0','acj0'}
period=(2017,2021) if mode in ('dev','a2') else (2022,2023)
config=json.loads((O/'run_config.json').read_text()); fmanifest=json.loads((O/'feature_manifest.json').read_text()); assert fmanifest['status']=='PASS' and sha(O/'run_config.json')==fmanifest['config_sha256']
if mode=='dev':models=base; parent=None
else:
 sel=json.loads((O/('a1_selection.json' if mode=='a2' else 'shortlist.json')).read_text()); parent=sel['a1']; assert parent in windows
 models=['a0','ac0','acj0',parent,'median','top2'] if mode=='a2' else sel['models']
 models=list(dict.fromkeys(models))
expr={'ac0':'a0+coalesce(.25*cn/(cn+3.0)*(course-a0),0)','acj0':'a0+coalesce(.25*cn/(cn+3.0)*(course-a0),0)+coalesce(.15*jn/(jn+20.0)*(jp-.5),0)'}
for m in base:expr.setdefault(m,m)
if parent:
 window='mean365' if parent.startswith('hl') else parent
 expr.update(median='med_'+window,top2='top_'+window)
counts={m:'n_'+('a0' if m in ('ac0','acj0') else window if m in ('median','top2') else m) for m in models}
# exact rank boundary test; test ties and just to either side of 12 decimal boundary.
assert c.execute('select list(horse_no order by round(score,12) desc,horse_no asc) from (values (3,0.12345678901249::double),(1,0.12345678901249::double),(2,0.12345678901251::double)) t(horse_no,score)').fetchone()[0]==[2,1,3]
for year in range(period[0],period[1]+1):
 p=O/f'features_{year}_t{thread}.parquet'; assert sha(p)==fmanifest['files'][p.name]; c.execute(f"create or replace view f as select * from read_parquet('{p}')")
 # whitelist explicitly. No raw / label columns allowed.
 cols={x[0] for x in c.execute('describe f').fetchall()}; assert cols==set(fmanifest['columns']) and not(cols & {'finish_position','finish_time_seconds','popularity','status','payout_yen','track_condition','body_weight_kg'})
 scores=','.join(f'case when not ambiguous and {counts[m]}>=2 then {expr[m]} end as s_{m}' for m in models)
 ns=','.join(f'{counts[m]} as n_{m}' for m in models)
 c.execute(f'create or replace temp table s as select runner_id,race_id,race_date,venue,horse_no,field_size,ambiguous,{ns},{scores} from f')
 for m in models:assert c.execute(f'select count(*) from s where s_{m} is not null and not isfinite(s_{m})').fetchone()[0]==0
 ranks=','.join(f'case when s_{m} is not null then row_number() over(partition by race_id order by round(s_{m},12) desc nulls last,horse_no asc) end as r_{m}' for m in models)
 reasons=','.join(f"case when ambiguous then 'AMBIGUOUS_IDENTITY' when n_{m}<2 then 'INSUFFICIENT_HISTORY' when s_{m} is null then 'UNKNOWN' else 'SCORED' end as reason_{m}" for m in models)
 p=O/f'pred_{mode}_{year}_t{thread}.parquet';c.execute(f"copy (select *,{ranks},{reasons} from s order by runner_id) to '{p}' (format parquet,compression zstd)");print(mode,year,thread,sha(p),flush=True)
