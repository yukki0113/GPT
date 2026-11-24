"""B7 fixed historical research; no production or actual RaceNote claim."""
import argparse,json,os,hashlib
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from run_brdb_b3_local import setup,cohort_sql,B2_ROOT
from run_brdb_b1_b2_local import require,rows,sha,attach
import run_brdb_b4_local as b4
from data_storage.common import sql_literal
ROOT=Path(__file__).resolve().parent
PINS={'bac':['c17ee5ccb8f953f090cca186ee751d12fc75b97003199dad7c14b7fee70a5daa','ed1b831b9236eaa85a075b1f6fce792e7292ece830688b4bd28546885761b898','b26a364978143fbd6e9d30289db0eb85e9b33e9fe612759b23a85ffbb78a3bb9'],'kyi':['d68afa2d37e2b4308df8c1897279e6cd38f27fc83d66324b4222e4cff44ed0ce','21d0d47337daa7c78f08e6e79fc41ee15eebed05630a3ff3ec6bca4d190340df','55fdcc9fd03c70f284b028fa85ef3c6b2882071c685639621061ba146c0fa10b'],'sed':['3cb2cb29f509209017d2b623a9fa5bdae18d217d4bd1b9cf82cbe7ae887e28ec','e18da9b6147c71973d5769f5ca859bd3b1e80b53773f9ed861c7b58941464fc8','6a7be1dc005833c9caaa20559ac3ad40af99bdc95a342b0e57d638ca979f8974']}
SIZES={'bac':[170174,171800,171165],'kyi':[5936231,5859260,5914994],'sed':[3612666,3596242,3612532]}
SCOPES="('ALL','ALL'),('SURFACE',track_type),('SURFACE_DISTANCE',track_type||':'||CAST(distance AS VARCHAR))"
LANES="('SIRE_ID',sire_id,''),('BMS_ID',bms_id,''),('PARENT_ID_PAIR',sire_id,bms_id),('LINEAGE_CODE_PAIR',sire_line,bms_line)"
JS="('NEWCOMER_ALL_FLAT','ALL'),('NEWCOMER_SURFACE',track_type),('NEWCOMER_VENUE_SURFACE',venue_code||':'||track_type),('NEWCOMER_SURFACE_DISTANCE_EXACT',track_type||':'||CAST(distance AS VARCHAR))"
COHORTS=['A1_RACE_ACTUAL_STARTERS','FIRST_OBSERVED_JRA_START_CANDIDATE']

def bind(c,assets):
    for family,pins in PINS.items():
        paths=[]
        for pin,size in zip(pins,SIZES[family]):
            candidates=[assets/(pin+s) for s in ('.parquet','.parquet.bin')]; p=next((p for p in candidates if p.is_file()),None)
            require(p is not None and p.stat().st_size==size and sha(p)==pin,'JPDB asset mismatch '+family)
            paths.append(sql_literal(str(p)))
        c.execute(f'CREATE TEMP VIEW {family} AS SELECT * FROM read_parquet([{",".join(paths)}],union_by_name=true)')
    for family,key in [('bac','race_key_raw'),('kyi','(race_key_raw,horse_no)'),('sed','(race_key_raw,horse_no)')]:
        require(c.execute(f'SELECT count(*)=count(DISTINCT {key}) FROM {family}').fetchone()[0],family+' duplicate')
    c.execute("""CREATE TEMP TABLE a1 AS SELECT race_key_raw race_key,race_date,venue_code,surface_code track_type,try_cast(distance_raw AS INTEGER) distance,field_size FROM bac WHERE race_class_code='A1' AND surface_code IN ('1','2') AND race_date BETWEEN '2023-01-01' AND '2025-12-31'""")
    c.execute("""CREATE TEMP TABLE declared AS SELECT a.*,k.horse_no,k.blood_registration_no horse_id,k.jockey_code planned_jockey,k.cancel_flag,k.source_member_date kyi_date, s.jockey_code actual_jockey,s.finish sed_finish,s.abnormal_code sed_abnormal,
      j.horse_id j_id,j.race_date j_date,j.race_condition_code j_class,j.track_type j_surface,j.distance j_distance,j.finish j_finish,j.abnormal_code j_abnormal,
      s.blood_registration_no s_id,s.race_date s_date,s.race_class_code s_class,s.surface_code s_surface,s.distance_m s_distance,
      CASE WHEN s.abnormal_code IN ('0','5') AND s.finish=1 THEN 1 ELSE 0 END win
      FROM a1 a JOIN kyi k ON a.race_key=k.race_key_raw LEFT JOIN sed s ON a.race_key=s.race_key_raw AND k.horse_no=s.horse_no LEFT JOIN joined j ON a.race_key=j.race_key AND k.horse_no=j.horse_no""")
    c.execute("""CREATE TEMP TABLE field_audit AS WITH f AS (SELECT a.race_key,a.race_date,a.field_size,count(d.horse_no) n,count(DISTINCT d.horse_id) unique_ids,
    count(*) FILTER(WHERE d.horse_no IS NULL OR NOT coalesce(regexp_full_match(d.horse_id,'[0-9]{8}'),false) OR d.horse_no NOT BETWEEN 1 AND 18 OR d.kyi_date IS DISTINCT FROM a.race_date) identity_errors,
    count(*) FILTER(WHERE d.horse_id IS DISTINCT FROM d.s_id OR d.horse_id IS DISTINCT FROM d.j_id OR d.s_date IS DISTINCT FROM a.race_date OR d.j_date IS DISTINCT FROM a.race_date OR d.s_class IS DISTINCT FROM 'A1' OR d.j_class IS DISTINCT FROM 'A1' OR d.s_surface IS DISTINCT FROM a.track_type OR d.j_surface IS DISTINCT FROM a.track_type OR d.s_distance IS DISTINCT FROM a.distance OR d.j_distance IS DISTINCT FROM a.distance OR d.sed_finish IS DISTINCT FROM d.j_finish OR d.sed_abnormal IS DISTINCT FROM d.j_abnormal) source_errors,
    coalesce(sum(d.win),0) winners FROM a1 a LEFT JOIN declared d USING(race_key) GROUP BY 1,2,3), s AS (SELECT race_key_raw race_key,count(*) n FROM sed GROUP BY 1),j AS (SELECT race_key,count(*) n FROM joined GROUP BY 1)
    SELECT f.*,s.n sed_n,j.n analysis_n,CASE WHEN f.n<>field_size OR f.n<>unique_ids OR identity_errors>0 THEN 'FIELD_IDENTITY' WHEN source_errors>0 OR s.n IS DISTINCT FROM f.n OR j.n IS DISTINCT FROM f.n THEN 'SOURCE_MISMATCH' WHEN winners<>1 THEN 'NOT_UNIQUE_WINNER' ELSE 'PASS' END status FROM f LEFT JOIN s USING(race_key) LEFT JOIN j USING(race_key)""")
    c.execute("""CREATE TEMP TABLE eval_targets AS SELECT d.race_key,d.horse_no,d.horse_id,d.race_date,d.track_type,d.distance,d.venue_code,d.field_size,d.planned_jockey,d.actual_jockey,d.win,d.cancel_flag,d.sed_abnormal,
       j.age,j.ukc_date,j.sire_id,j.bms_id, CASE WHEN sl.lineage_code IS NOT NULL AND j.ukc_date<=d.race_date THEN j.dated_sire_line END sire_line,CASE WHEN bl.lineage_code IS NOT NULL AND j.ukc_date<=d.race_date THEN j.dated_bms_line END bms_line
       FROM declared d JOIN field_audit f USING(race_key) JOIN joined j ON (d.race_key,d.horse_no,d.horse_id)=(j.race_key,j.horse_no,j.horse_id) LEFT JOIN lineage_master sl ON sl.lineage_code=j.dated_sire_line LEFT JOIN lineage_master bl ON bl.lineage_code=j.dated_bms_line WHERE f.status='PASS' AND d.race_date>='2024-01-01'""")
    require(c.execute('SELECT count(*)=count(DISTINCT (race_key,horse_no)) FROM eval_targets').fetchone()[0],'eval target duplicate')

def blood(c):
    c.execute("INSERT INTO cutoff VALUES ('2026-01-01')")
    c.execute('CREATE TEMP TABLE cohort AS '+cohort_sql((B2_ROOT/'brdb_b2_sire_debut_statistics_v0_1.sql').read_text()))
    c.execute(f"""CREATE TEMP TABLE blood_daily AS WITH facts AS (SELECT c.*,CASE WHEN sl.lineage_code IS NOT NULL AND ukc_date<=race_date THEN dated_sire_line END sire_line,CASE WHEN bl.lineage_code IS NOT NULL AND ukc_date<=race_date THEN dated_bms_line END bms_line FROM cohort c LEFT JOIN lineage_master sl ON sl.lineage_code=c.dated_sire_line LEFT JOIN lineage_master bl ON bl.lineage_code=c.dated_bms_line)
      SELECT cohort,scope,dimension,lane,key1,key2,race_date,count(*) n,sum(CASE WHEN abnormal_code IN ('0','5') AND finish=1 THEN 1 ELSE 0 END) w,sum(CASE WHEN abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END) t FROM facts CROSS JOIN LATERAL (VALUES {SCOPES}) sc(scope,dimension) CROSS JOIN LATERAL (VALUES {LANES}) l(lane,key1,key2) WHERE key1 IS NOT NULL AND key2 IS NOT NULL AND dimension IS NOT NULL GROUP BY ALL""")
    c.execute("""CREATE TEMP TABLE blood_hist AS SELECT cohort,scope,dimension,lane,key1,key2,race_date,sum(n) OVER w n,sum(w) OVER w wins,sum(t) OVER w top3 FROM blood_daily WINDOW w AS (PARTITION BY cohort,scope,dimension,lane,key1,key2 ORDER BY race_date ROWS UNBOUNDED PRECEDING)""")
    c.execute(f"""CREATE TEMP TABLE blood_target AS SELECT race_key,horse_no,horse_id,race_date,cohort,scope,dimension,lane,key1,key2 FROM eval_targets CROSS JOIN (VALUES ('{COHORTS[0]}'),('{COHORTS[1]}')) co(cohort) CROSS JOIN LATERAL (VALUES {SCOPES}) sc(scope,dimension) CROSS JOIN LATERAL (VALUES {LANES}) l(lane,key1,key2)""")
    c.execute("""CREATE TEMP TABLE blood_cells AS SELECT x.race_key,x.horse_no,x.horse_id,x.race_date,x.cohort||':'||x.lane||':'||x.scope feature,coalesce(h.n,0) n,coalesce(h.wins,0) wins,coalesce(h.top3,0) top3,(x.key1 IS NULL OR x.key2 IS NULL OR x.dimension IS NULL)::INT unavailable,0 unresolved,h.race_date max_history_date FROM blood_target x ASOF LEFT JOIN blood_hist h ON x.cohort=h.cohort AND x.scope=h.scope AND x.dimension=h.dimension AND x.lane=h.lane AND x.key1=h.key1 AND x.key2=h.key2 AND x.race_date>h.race_date""")
    # Reuse exact B4 SQL on declaration-level target cohort rather than actual starter filtered cohort.
    c.execute("DROP TABLE cohort"); c.execute("CREATE TEMP TABLE cohort AS SELECT 'A1_DECLARATION' cohort,* FROM eval_targets")
    b4.build(c); b4.audit(c)
    c.execute("""CREATE TEMP TABLE relative_cells AS WITH g AS (SELECT r.race_key,r.horse_no,r.horse_id,r.race_date,f.family,w.period,sum(CASE WHEN w.period='FIRST' THEN first_starts ELSE early_starts END) n,sum(CASE WHEN w.period='FIRST' THEN first_wins ELSE early_wins END) wins,sum(CASE WHEN w.period='FIRST' THEN first_top3 ELSE early_top3 END) top3,max((history_status='FIRST_START_UNRESOLVED')::INT) unresolved,max(max_history_date) max_history_date FROM relative_stats r CROSS JOIN (VALUES ('SAME_DAM'),('MATERNAL_AUNT_UNCLE')) f(family) CROSS JOIN (VALUES ('FIRST'),('EARLY')) w(period) WHERE scope='ALL' AND list_contains(paths,f.family) GROUP BY 1,2,3,4,5,6)
      SELECT t.race_key,t.horse_no,t.horse_id,t.race_date,'RELATIVE:'||f.family||':'||w.period feature,coalesce(g.n,0) n,coalesce(g.wins,0) wins,coalesce(g.top3,0) top3,(CASE WHEN f.family='SAME_DAM' THEN t.dam_status<>'RESOLVED' ELSE t.granddam_status<>'RESOLVED' END)::INT unavailable,coalesce(g.unresolved,0) unresolved,g.max_history_date FROM family_targets t CROSS JOIN (VALUES ('SAME_DAM'),('MATERNAL_AUNT_UNCLE')) f(family) CROSS JOIN (VALUES ('FIRST'),('EARLY')) w(period) LEFT JOIN g ON (t.race_key,t.horse_no,f.family,w.period)=(g.race_key,g.horse_no,g.family,g.period)""")

def rider(c):
    # JPDB v1.1 population: normal valid + DNF + demotion review; unknown/invalid/demotion suppress rates.
    c.execute("""CREATE TEMP TABLE rider_facts AS SELECT s.race_key_raw,s.horse_no,s.race_date,s.jockey_code,a.track_type,a.distance,a.venue_code,(s.abnormal_code IN ('0','') AND s.finish BETWEEN 1 AND s.field_size AND s.field_size>=1) normal,s.abnormal_code,s.finish FROM sed s JOIN a1 a ON s.race_key_raw=a.race_key AND s.race_date=a.race_date WHERE s.race_class_code='A1' AND s.surface_code=a.track_type AND s.distance_m=a.distance AND regexp_full_match(s.jockey_code,'[0-9]{5}') AND s.jockey_code<>'00000'""")
    require(c.execute("SELECT count(*)=0 FROM sed s JOIN a1 a ON s.race_key_raw=a.race_key WHERE s.race_date IS DISTINCT FROM a.race_date OR s.race_class_code IS DISTINCT FROM 'A1' OR s.surface_code IS DISTINCT FROM a.track_type OR s.distance_m IS DISTINCT FROM a.distance").fetchone()[0],'JPDB BAC SED mismatch')
    c.execute(f"""CREATE TEMP TABLE rider_daily AS SELECT jockey_code,scope,dimension,race_date,count(*) FILTER(WHERE normal OR abnormal_code IN ('3','5')) n,count(*) FILTER(WHERE normal AND finish=1) wins,count(*) FILTER(WHERE normal AND finish<=3) top3,count(*) FILTER(WHERE abnormal_code IS NULL OR abnormal_code NOT IN ('0','','1','2','3','5') OR abnormal_code='5' OR (abnormal_code IN ('0','') AND NOT coalesce(normal,false))) unresolved FROM rider_facts CROSS JOIN LATERAL (VALUES {JS}) sc(scope,dimension) GROUP BY ALL""")
    c.execute("""CREATE TEMP TABLE rider_hist AS SELECT jockey_code,scope,dimension,race_date,sum(n) OVER w n,sum(wins) OVER w wins,sum(top3) OVER w top3,sum(unresolved) OVER w unresolved FROM rider_daily WINDOW w AS (PARTITION BY jockey_code,scope,dimension ORDER BY race_date ROWS UNBOUNDED PRECEDING)""")
    c.execute(f"""CREATE TEMP TABLE rider_cells AS WITH x AS (SELECT race_key,horse_no,horse_id,race_date,planned_jockey,scope,dimension FROM eval_targets CROSS JOIN LATERAL (VALUES {JS}) sc(scope,dimension)) SELECT x.race_key,x.horse_no,x.horse_id,x.race_date,'JOCKEY:'||x.scope feature,coalesce(h.n,0) n,coalesce(h.wins,0) wins,coalesce(h.top3,0) top3,(NOT coalesce(regexp_full_match(x.planned_jockey,'[0-9]{{5}}') AND x.planned_jockey<>'00000',false))::INT unavailable,coalesce(h.unresolved,0) unresolved,h.race_date max_history_date FROM x ASOF LEFT JOIN rider_hist h ON x.planned_jockey=h.jockey_code AND x.scope=h.scope AND x.dimension=h.dimension AND x.race_date>h.race_date""")

def probs(X,b,starts,counts):
    z=X@b; m=np.maximum.reduceat(z,starts); e=np.exp(z-np.repeat(m,counts)); return e/np.repeat(np.add.reduceat(e,starts),counts)

def fit(X,y,starts,counts):
    b=np.zeros(X.shape[1]);
    def objective(b):
        p=probs(X,b,starts,counts);return -np.log(p[y==1]).sum()+.5*(b@b)
    for it in range(100):
        p=probs(X,b,starts,counts); g=X.T@(p-y)+b; M=X*p[:,None]; means=np.add.reduceat(M,starts,axis=0);H=X.T@M-means.T@means+np.eye(X.shape[1]);step=np.linalg.solve(H,g)
        if np.max(np.abs(g))<1e-7: return b,it,float(np.max(np.abs(g)))
        old=objective(b);factor=1.
        while objective(b-factor*step)>old-1e-4*factor*(g@step):
            factor*=.5;require(factor>1e-10,'optimization line search')
        b-=factor*step
    raise ValueError('optimization not converged')

def encode_cells(c,out):
    c.execute('CREATE TEMP TABLE cells AS SELECT * FROM blood_cells UNION ALL SELECT * FROM relative_cells UNION ALL SELECT * FROM rider_cells')
    require(c.execute('SELECT count(*)=32*(SELECT count(*) FROM eval_targets) AND count(*)=count(DISTINCT (race_key,horse_no,feature)) AND count(*) FILTER(WHERE max_history_date>=race_date OR wins>top3 OR top3>n OR n<0)=0 FROM cells').fetchone()[0],'feature date/cardinality')
    ids=c.execute('SELECT race_key,horse_no,horse_id,race_date,track_type,win FROM eval_targets ORDER BY race_date,race_key,horse_no').fetchall(); data=c.execute('SELECT race_key,horse_no,feature,n,wins,top3,unavailable,unresolved,max_history_date FROM cells ORDER BY race_key,horse_no,feature').fetchall()
    keyset=sorted({r[2] for r in data});index={k:i for i,k in enumerate(keyset)};lookup={(r[0],r[1]):i for i,r in enumerate(ids)};X=np.zeros((len(ids),len(keyset)*6));
    for rk,no,k,n,w,t,missing,unresolved,mx in data:
        # Relative unresolved means some relatives lack eligible first history, not that observed relatives' valid results are invalid.
        usable=not missing and n>0 and not(k.startswith('JOCKEY:') and unresolved);a=3 if k.startswith('RELATIVE:') else 30
        X[lookup[rk,no],index[k]*6:index[k]*6+6]=[np.log1p(n),(w+a*.08)/(n+a) if usable else .08,(t+a*.23)/(n+a) if usable else .23,missing,int(n==0 and not missing),int(unresolved>0)]
    # Private deterministic evidence cells, no raw horse records in Git.
    b4.export(c,'SELECT * FROM cells ORDER BY race_date,race_key,horse_no,feature',out/'PRIVATE_b7_cells.csv.gz')
    return ids,X,keyset

def metrics(p,y,starts,counts):
    ll=-np.log(p[y==1]); require(len(ll)==len(starts),'winner count'); hit=sum(y[a+np.argmax(p[a:a+n])] for a,n in zip(starts,counts))
    cal=[]
    for lo,hi in zip([0,.05,.10,.20,.30,.50],[.05,.10,.20,.30,.50,1.00000001]):
        k=(p>=lo)&(p<hi);cal.append(dict(lo=lo,hi=min(hi,1),n=int(k.sum()),mean_pred=float(p[k].mean()) if k.any() else None,observed=float(y[k].mean()) if k.any() else None))
    return dict(races=len(starts),entries=len(y),winner_logloss=float(ll.mean()),brier=float(np.mean((p-y)**2)),top1=float(hit/len(starts)),calibration=cal)

def group(ids):
    rk=np.array([r[0] for r in ids]);starts=np.r_[0,np.flatnonzero(rk[1:]!=rk[:-1])+1];return starts,np.diff(np.r_[starts,len(ids)])

def compare(ids,X,keys,out):
    train=np.array([r[3]<'2025-01-01' for r in ids]);hold=~train;y=np.array([r[5] for r in ids]);train_ids=[r for r,t in zip(ids,train) if t];test_ids=[r for r,t in zip(ids,hold) if t];st,nt=group(train_ids);s,n=group(test_ids);yt=y[train];yh=y[hold]
    require(np.all(np.add.reduceat(yt,st)==1) and np.all(np.add.reduceat(yh,s)==1),'winner counts')
    mu=X[train].mean(0);sd=X[train].std(0);sd[sd==0]=1;Z=(X-mu)/sd;isj=np.repeat([k.startswith('JOCKEY:') for k in keys],6)
    ps={'UNIFORM':1/np.repeat(n,n)};models={}
    for name,cols in [('BRDB',~isj),('JPDB',isj),('BOTH',np.ones(len(isj),bool))]:
        b,it,grad=fit(Z[train][:,cols],yt,st,nt);ps[name]=probs(Z[hold][:,cols],b,s,n);models[name]={'iterations':it,'max_gradient':grad,'coefficients':b.tolist()}
    for p in ps.values():require(np.allclose(np.add.reduceat(p,s),1,atol=1e-12),'normalization')
    dates=np.array([r[3] for r in test_ids]);surfaces=np.array([r[4] for r in test_ids]);result={}
    for name,mask in [('ALL',np.ones(len(yh),bool)),('H1',dates<'2025-07-01'),('H2',dates>='2025-07-01'),('TURF',surfaces=='1'),('DIRT',surfaces=='2')]:
        sub=[r for r,k in zip(test_ids,mask) if k];ss,nn=group(sub);result[name]={k:metrics(p[mask],yh[mask],ss,nn) for k,p in ps.items()}
    days=dates[s];unique=np.unique(days);byday=np.array([np.flatnonzero(days==d).size for d in unique]);rng=np.random.default_rng(20261124);draw=rng.integers(0,len(unique),size=(2000,len(unique)));ci={}
    for a,b in [('BRDB','UNIFORM'),('JPDB','UNIFORM'),('BOTH','UNIFORM'),('BOTH','BRDB'),('BOTH','JPDB')]:
        delta=-np.log(ps[a][yh==1])+np.log(ps[b][yh==1]);day_sum=np.array([delta[days==d].sum() for d in unique]);boot=day_sum[draw].sum(1)/byday[draw].sum(1);ci[a+'-'+b]={'delta':float(delta.mean()),'ci95':np.quantile(boot,[.025,.975]).tolist()}
    import csv,gzip,io
    with (out/'PRIVATE_b7_predictions.csv.gz').open('wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding='utf-8',newline='') as f:
                w=csv.writer(f,lineterminator='\n');w.writerow(['race_key','horse_no','horse_id','race_date','surface','winner',*ps]);w.writerows([(*r,*(format(ps[k][i],'.17g') for k in ps)) for i,r in enumerate(test_ids)])
    return dict(train_races=len(st),train_entries=len(yt),holdout_races=len(s),holdout_entries=len(yh),holdout_days=len(unique),metrics=result,paired_day_bootstrap=ci,models=models,feature_keys=keys,mean=mu.tolist(),std=sd.tolist())

def run(input_root,assets,out):
    out.mkdir(parents=True,exist_ok=True);c=setup(input_root);c.execute('SET threads=1');bind(c,assets);print('field audit',rows(c,"SELECT substr(race_date,1,4) AS cohort_year,status,count(*) races,sum(n) entries FROM field_audit GROUP BY ALL ORDER BY ALL"),flush=True);blood(c);print('blood and relatives complete',flush=True);rider(c);ids,X,keys=encode_cells(c,out);print('features complete',len(ids),X.shape,flush=True);result=compare(ids,X,keys,out)
    result.update(status='PASS_RESEARCH_ONLY',prediction_safe=False,production_authorized=False,protocol_commit='ed99e21f2ab395ac20c08070279258425cf1a91d',historical_target_rider='FINAL_KYI_PROXY',asof_policy='JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1',field_audit=rows(c,"SELECT substr(race_date,1,4) AS cohort_year,status,count(*) races,sum(n) entries FROM field_audit GROUP BY ALL ORDER BY ALL"),coverage=rows(c,"SELECT substr(race_date,1,4) AS cohort_year,feature,count(*) entries,count(*) FILTER(WHERE n>0 AND unavailable=0 AND (NOT starts_with(feature,'JOCKEY:') OR unresolved=0)) usable,count(*) FILTER(WHERE unavailable=1) unavailable,count(*) FILTER(WHERE n=0 AND unavailable=0) no_sample,count(*) FILTER(WHERE unresolved>0) unresolved,max(max_history_date) max_history_date FROM cells GROUP BY ALL ORDER BY ALL"),rider_change_audit=rows(c,"SELECT substr(race_date,1,4) AS cohort_year,count(*) entries,count(*) FILTER(WHERE planned_jockey IS DISTINCT FROM actual_jockey) different,count(*) FILTER(WHERE sed_abnormal IN ('1','2')) nonstarters FROM eval_targets GROUP BY ALL ORDER BY ALL"),assets=PINS,output_sha256={p.name:sha(p) for p in sorted(out.glob('*.csv.gz'))})
    from audit_brdb_b7_local import audit
    from data_storage.dependencies import dependency_report
    result['independent_audit']=audit(c)
    result['source_sha256']={name:sha(ROOT/name) for name in ['run_brdb_b7_local.py','audit_brdb_b7_local.py']}
    result['dependency_report']=dependency_report()
    (out/'b7_receipt.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['train_entries','train_races','holdout_entries','holdout_races','paired_day_bootstrap']},indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-root',type=Path,required=True);p.add_argument('--jpdb-assets',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();run(a.input_root,a.jpdb_assets,a.output_dir)
