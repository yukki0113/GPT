#!/usr/bin/env python3
"""Fixed R5 historical pilot audit; no forecast generation or production writes.
Run only after both research freezes; raw/result/horse-level data remain private.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

VERSION='racenote-r5-paired-pilot-audit-v0.1'
PROTOCOL='9968b6723facbb790212e0b7f555493afd1b7218'
R4_MANIFEST='718b7b0b2d0d284a040eba987b36c51c02dc087a25b032770896ee4f438ecae2'
A_PRED='9992e2dcbd885f9ca588c5b713f48e79a218521eb18c25e038e7225d4924e28c'
A_CONF='bae76036af02e9cb8e57f28f1f5553f8a93a62a183afd4bd3075d41093187a35'
B_PRED='ba44c7bedec39eaae18c263fb0c760d953c5638eaaa73ab8b2102cc7dce8c810'
B_CONF='394ce65f3499929dc83246a36e7e27992e0c9932f0c32338c2ad9c27d623e4ae'
TARGET={'05265404':('A1',12),'05265405':('A1',10),'05265412':('OTHER',18)}
LOGIC='RaceNote-Human-Context-Reader-0.5.6-candidate'
METRICS=('honmei_win','honmei_top3','winner_in_five','top3_in_five','all_top3_in_five')

def require(ok,msg):
    if not ok: raise ValueError(msg)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,pin=None):
    b=Path(p).read_bytes();require(pin is None or hashlib.sha256(b).hexdigest()==pin,'input SHA mismatch');return json.loads(b)
def keyed(rows,key):
    d={}
    for r in rows:
        k=key(r);require(k not in d,'duplicate key');d[k]=r
    return d

def checked_ref(a):return load(a['path'],a['sha256'])
def valid_five(m,roster):return len(m)==5 and len(set(m))==5 and set(m)<=roster

def metrics(m,top):
    require(len(top)==3 and len(set(top))==3,'pilot requires unambiguous top3')
    return dict(zip(METRICS,[int(m[0]==top[0]),int(m[0] in top),int(top[0] in m),len(set(m)&set(top)),int(set(top)<=set(m))]))

def paired(a,b,top):
    x,y=metrics(a,top),metrics(b,top)
    return {'A':x,'B':y,'paired':{k:'B_BETTER' if y[k]>x[k] else 'A_BETTER' if y[k]<x[k] else 'TIE' for k in METRICS},'honmei_changed':a[0]!=b[0],'five_changed':set(a)!=set(b),'promoted':len(set(b)-set(a)),'dropped':len(set(a)-set(b))}

def result_top(data,k,roster):
    require(data['status']=='success' and data['provenance']['web_used'] is False and data['provenance']['result_source']=='SED' and data['provenance']['payout_source']=='HJC' and len(data['races'])==1,'unaccepted result source')
    r=data['races'][0];require(r['race_key']==k and r['race_date']=='2026-11-15' and r['cross_validation']['status']=='pass','result binding or cross validation failed')
    allr=keyed(r['all_runners'],lambda x:x['horse_no']);require(set(allr)==roster and all(x['abnormal_code']=='0' and x['completed_normally'] for x in allr.values()),'pilot abnormal or incomplete roster: manual review required')
    top=r['top3'];require([x['finish'] for x in top]==[1,2,3] and all(x==allr[x['horse_no']] for x in top),'ambiguous result: manual review required')
    return [x['horse_no'] for x in top]

def run(manifest,a_pred,a_conf,b_pred,b_conf,b_pred_readback,b_conf_readback,result_dir):
    m=load(manifest,R4_MANIFEST);a=load(a_pred,A_PRED);ac=load(a_conf,A_CONF);b=load(b_pred,B_PRED);bc=load(b_conf,B_CONF)
    require(sha(b_pred_readback)==B_PRED and sha(b_conf_readback)==B_CONF,'private freeze readback mismatch')
    require(b['protocol_commit']==bc['protocol_commit']==PROTOCOL and b['logic_version']==LOGIC and bc['prediction_sha256']==B_PRED,'research freeze binding')
    require(all(x['research_only'] is True and x['prediction_safe'] is False and x['production_authorized'] is False and x['target_result_opened'] is False and x['a_marks_opened'] is False for x in (b,bc)),'unsafe research freeze')
    aa=keyed(a,lambda x:(x['venue'],x['race_no']));acc=keyed(ac,lambda x:(x['venue'],x['race_no']));bb=keyed(b['races'],lambda x:x['race_key']);bcc=keyed(bc['races'],lambda x:x['race_key']);jobs=keyed(m['jobs'],lambda x:x['race_key']);require(set(bb)==set(bcc)==set(TARGET),'pilot target set drift')
    require({k for k,j in jobs.items() if j['baseline'] is not None}==set(TARGET),'R4 eligible set drift')
    rows=[]
    for k,(cohort,n) in sorted(TARGET.items()):
        j=jobs[k];reader=checked_ref(j['baseline']['reader']);detail=checked_ref(j['detail']);preview=checked_ref(j['preview']);rb=bb[k];cf=bcc[k];num=int(k[-2:]);ra=aa[('東京',num)];ca=acc[('東京',num)]
        require(rb['cohort']==cohort and rb['reader_sha256']==ra['reader_sha256']==j['baseline']['reader']['sha256'] and rb['preview_sha256']==j['preview']['sha256'] and rb['detail_sha256']==j['detail']['sha256']==preview['detail_sha256'] and rb['paci_sha256']==j['paci']['sha256'],'reader/sidecar binding drift')
        require(ra['logic_version']==LOGIC and ra['target_date']=='2026-11-15','baseline version/date drift')
        race=next(x for x in detail['races'] if x['race_key_raw']==k);require(race['is_newcomer_race']==(cohort=='A1') and race['coverage_status']=='DUAL_SOURCE_RESEARCH','cohort/source mismatch')
        hs=keyed(race['horses'],lambda x:x['horse_no']);rh=keyed(reader['horses'],lambda x:x['identity']['horse_no']);bh=keyed(rb['all_horse_assessments'],lambda x:x['horse_no']);ph=keyed(preview['horses'],lambda x:x['horse_no']);roster=set(hs)
        require(len(roster)==n and roster==set(rh)==set(bh)==set(ph)==set(ra['horse_nos']),'whole-field roster mismatch')
        counts=Counter();families=Counter()
        for i,h in hs.items():
            x=bh[i];require(h['horse_id']==x['horse_id']==rh[i]['identity']['horse_id']==ph[i]['horse_id'],'horse identity mismatch')
            ev=keyed(h['evidence'],lambda e:e['evidence_id']);restricted={e['evidence_id'] for e in h['restricted_refs']};ids=x['evidence_ids'];require(ids and len(ids)==len(set(ids)) and set(ids)<=set(ev) and not set(ids)&restricted and x['restricted_numeric_used'] is False and x['reason'].strip(),'trace or restriction failure')
            counts[x['assessment']]+=1;counts['evidence_refs']+=len(ids);counts['horses_with_jpdb_refs']+=any(ev[z]['family']=='JPDB' for z in ids);counts['horses_with_brdb_refs']+=any(ev[z]['family'].startswith('BRDB:') for z in ids)
            for z in ids: families[ev[z]['family']]+=1
        ma=ra['decision_core']['marks'];marks=rb['marks'];mb=[marks['◎'],marks['○'],marks['▲'],*marks['△']];require(valid_five(ma,roster) and valid_five(mb,roster) and ca['honmei']==ma[0] and cf['honmei']==mb[0],'marks or confidence anchor mismatch')
        require((ca['confidence']=='Z')==(cf['confidence']=='Z')==(cohort=='A1') and rb['b5_numeric_used'] is False and rb['shared_history_not_independent'] is True,'confidence or research restriction mismatch')
        require(rb['challenger_decision']=='KEEP' and set(rb['ordinary_five'])==set(mb) and rb['challenger'] not in mb and rb['challenger'] in roster,'pilot challenger mismatch')
        path=Path(result_dir)/f'result_{num}_all.json';out=load(path);top=result_top(out,k,roster);x=paired(ma,mb,top)
        rows.append({'race_key':k,'cohort':cohort,'horses':n,'result_sha256':sha(path),'result_cross_validation':'PASS','all_horse_assessments':n,'trace_counts':dict(counts),'trace_family_counts':dict(families),'confidence_A':ca['confidence'],'confidence_B':cf['confidence'],'metrics':x})
    cohorts={}
    for c in ('A1','OTHER'):
        z=[r for r in rows if r['cohort']==c];counts=Counter();
        for r in z:counts.update(r['trace_counts'])
        cohorts[c]={'races':len(z),'horses':sum(r['horses'] for r in z),'trace_counts':dict(counts),'changed_honmei':sum(r['metrics']['honmei_changed'] for r in z),'changed_five':sum(r['metrics']['five_changed'] for r in z),'promoted':sum(r['metrics']['promoted'] for r in z),'dropped':sum(r['metrics']['dropped'] for r in z),'A':{k:sum(r['metrics']['A'][k] for r in z) for k in METRICS},'B':{k:sum(r['metrics']['B'][k] for r in z) for k in METRICS},'paired':{k:dict(Counter(r['metrics']['paired'][k] for r in z)) for k in METRICS}}
    return {'schema_version':VERSION,'status':'PASS_INITIAL_HISTORICAL_PAIRED_PILOT_ONLY','protocol_commit':PROTOCOL,'r4_manifest_sha256':R4_MANIFEST,'A_prediction_sha256':A_PRED,'A_confidence_sha256':A_CONF,'B_prediction_sha256':B_PRED,'B_confidence_sha256':B_CONF,'research_only':True,'prediction_safe':False,'production_authorized':False,'r6_authorized':False,'true_forward':False,'semantic_audit':'AUTHOR_SELF_REVIEW_NOT_INDEPENDENT','result_source':'CANONICAL_JRDB_RESULT_QUERY_SED_HJC','result_roster_coverage':40,'private_freeze_readback_sha_match':True,'races':rows,'cohorts':cohorts,'remaining':['PROSPECTIVE_50R_READING_AUDIT','TRUE_FORWARD','INDEPENDENT_SEMANTIC_AUDIT','B5_NUMERIC_AND_JPDB_BRDB_ABLATION','PERFORMANCE_CERTIFICATION','R6_APPROVAL']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','a-pred','a-conf','b-pred','b-conf','b-pred-readback','b-conf-readback','result-dir','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();d=vars(a);out=d.pop('output');r=run(**d);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
