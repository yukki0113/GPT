"""Independent fixed-sample source reconciliation and prior-history audit for B7.
Does not alter feature construction, training, predictions or protocol.
"""
from run_brdb_b7_local import COHORTS
from run_brdb_b1_b2_local import require,rows

def audit(c):
    # First and last field (calendar order) of each year: predetermined, not performance-selected.
    picked=c.execute("""WITH r AS (SELECT DISTINCT substr(race_date,1,4) yr,race_date,race_key FROM eval_targets), o AS (SELECT *,row_number() OVER(PARTITION BY yr ORDER BY race_date,race_key) a,row_number() OVER(PARTITION BY yr ORDER BY race_date DESC,race_key DESC) b FROM r) SELECT t.race_key,t.horse_no,t.horse_id,t.race_date,t.track_type,t.distance,t.venue_code,t.sire_id,t.bms_id,t.sire_line,t.bms_line,t.planned_jockey FROM eval_targets t JOIN o USING(race_key,race_date) WHERE o.a=1 OR o.b=1 ORDER BY t.race_date,t.race_key,t.horse_no""").fetchall()
    counts={'blood':0,'rider':0,'relative':0}
    for rk,no,hid,d,s,dist,venue,sire,bms,sl,bl,jockey in picked:
        def check(key,expected,group):
            actual=c.execute('SELECT n,wins,top3,unresolved,max_history_date FROM cells WHERE race_key=? AND horse_no=? AND feature=?',[rk,no,key]).fetchone()
            require(actual==expected,'independent direct source mismatch '+group+' '+key);counts[group]+=1
        for co in COHORTS:
            pred="race_condition_code='A1' AND start_status IN ('STARTED_NORMAL','STARTED_ABNORMAL')" if co==COHORTS[0] else "eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE'"
            for lane,keys,where in [('SIRE_ID',(sire,), 'sire_id=?'),('BMS_ID',(bms,),'bms_id=?'),('PARENT_ID_PAIR',(sire,bms),'sire_id=? AND bms_id=?'),('LINEAGE_CODE_PAIR',(sl,bl),'dated_sire_line=? AND dated_bms_line=? AND ukc_date<=race_date')]:
                for scope,cond,args in [('ALL','TRUE',[]),('SURFACE','track_type=?',[s]),('SURFACE_DISTANCE','track_type=? AND distance=?',[s,dist])]:
                    expected=(0,0,0,0,None) if None in keys else c.execute(f"SELECT count(*),coalesce(sum(CASE WHEN abnormal_code IN ('0','5') AND finish=1 THEN 1 ELSE 0 END),0),coalesce(sum(CASE WHEN abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END),0),0,max(race_date) FROM joined WHERE year BETWEEN 2017 AND 2025 AND race_date<? AND {pred} AND {where} AND {cond}",[d,*keys,*args]).fetchone()
                    check(co+':'+lane+':'+scope,expected,'blood')
        normal="abnormal_code IN ('0','') AND finish BETWEEN 1 AND field_size AND field_size>=1"
        invalid="abnormal_code IN ('0','') AND (finish IS NULL OR field_size IS NULL OR field_size<1 OR finish NOT BETWEEN 1 AND field_size)"
        for scope,cond,args in [('NEWCOMER_ALL_FLAT','TRUE',[]),('NEWCOMER_SURFACE','surface_code=?',[s]),('NEWCOMER_VENUE_SURFACE','substr(race_key_raw,1,2)=? AND surface_code=?',[venue,s]),('NEWCOMER_SURFACE_DISTANCE_EXACT','surface_code=? AND distance_m=?',[s,dist])]:
            expected=c.execute(f"SELECT coalesce(sum(CASE WHEN ({normal}) OR abnormal_code IN ('3','5') THEN 1 ELSE 0 END),0),coalesce(sum(CASE WHEN ({normal}) AND finish=1 THEN 1 ELSE 0 END),0),coalesce(sum(CASE WHEN ({normal}) AND finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END),0),coalesce(sum(CASE WHEN abnormal_code IS NULL OR abnormal_code NOT IN ('0','','1','2','3','5') OR abnormal_code='5' OR ({invalid}) THEN 1 ELSE 0 END),0),max(race_date) FROM sed WHERE race_date>='2023-01-01' AND race_date<? AND race_class_code='A1' AND surface_code IN ('1','2') AND jockey_code=? AND regexp_full_match(jockey_code,'[0-9]{{5}}') AND jockey_code<>'00000' AND {cond}",[d,jockey,*args]).fetchone()
            check('JOCKEY:'+scope,expected,'rider')
        for family in ['SAME_DAM','MATERNAL_AUNT_UNCLE']:
            rels=c.execute('SELECT relative_id FROM relative_pairs WHERE race_key=? AND horse_no=? AND list_contains(paths,?) ORDER BY relative_id',[rk,no,family]).fetchall();first=[];early=[];unresolved=0
            for (rid,) in rels:
                h=c.execute("SELECT race_date,eligibility,abnormal_code,finish FROM classified WHERE horse_id=? AND race_date<? AND start_status IN ('STARTED_NORMAL','STARTED_ABNORMAL') ORDER BY race_date,race_key LIMIT 3",[rid,d]).fetchall()
                if not h: continue
                if h[0][1]!='FIRST_OBSERVED_JRA_START_CANDIDATE':unresolved=1;continue
                first.append(h[0]);early.extend(h)
            # B4 first-cell provenance intentionally retains latest date of early window too.
            mx=max((r[0] for r in early),default=None)
            for period,h in [('FIRST',first),('EARLY',early)]:
                expected=(len(h),sum(r[2] in ('0','5') and r[3]==1 for r in h),sum(r[2] in ('0','5') and r[3] is not None and 1<=r[3]<=3 for r in h),unresolved,mx)
                check('RELATIVE:'+family+':'+period,expected,'relative')
    # Do not use target outcome or lifetime-first eligibility to select predictors.
    prior=rows(c,"""WITH p AS (SELECT t.race_key,t.horse_no,count(h.race_key)>0 observed_prior FROM eval_targets t LEFT JOIN classified h ON t.horse_id=h.horse_id AND h.race_date<t.race_date AND h.start_status IN ('STARTED_NORMAL','STARTED_ABNORMAL') GROUP BY 1,2), k AS (SELECT t.race_key,t.horse_no,t.race_date,regexp_full_match(coalesce(k.prev_result_key_1,''),'[0-9]{16}') AND k.prev_result_key_1<>'0000000000000000' kyiref FROM eval_targets t JOIN kyi k ON (t.race_key,t.horse_no,t.horse_id)=(k.race_key_raw,k.horse_no,k.blood_registration_no)) SELECT substr(k.race_date,1,4) cohort_year,p.observed_prior,k.kyiref,count(*) entries FROM p JOIN k USING(race_key,horse_no) GROUP BY ALL ORDER BY ALL""")
    excluded=rows(c,"""SELECT f.race_date,f.status,count(DISTINCT f.race_key) races,count(d.horse_no) entries,count(*) FILTER(WHERE d.j_class IS DISTINCT FROM 'A1') analysis_class_mismatch,count(*) FILTER(WHERE d.j_id IS NULL OR d.s_id IS NULL OR d.j_id<>d.horse_id OR d.s_id<>d.horse_id) identity_mismatch,count(*) FILTER(WHERE d.j_finish IS DISTINCT FROM d.sed_finish OR d.j_abnormal IS DISTINCT FROM d.sed_abnormal) outcome_mismatch FROM field_audit f LEFT JOIN declared d USING(race_key) WHERE f.status<>'PASS' GROUP BY ALL ORDER BY ALL""")
    return {'sample_policy':'FIRST_AND_LAST_FIELD_PER_YEAR_FIXED','sample_entries':len(picked),'direct_count_date_checks':counts,'individual_prior_history_audit':prior,'excluded_field_audit':excluded}
