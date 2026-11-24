"""Research-only B5 ↔ JPDB R1/R2/R3 reference bridge. No reaggregation or scoring.
Input manifest SHA must be pinned independently; source files remain private.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from collections import Counter
from pathlib import Path
from run_brdb_b5_local import read_field, validate as validate_b5

VERSION = 'brdb-jpdb-debut-evidence-link-v0.1-candidate'
GROUP = 'SHARED_JRDB_HISTORY_NOT_INDEPENDENT'
WINDOWS = {'ROLLING_3Y','RECENT_365D','RECENT_90D'}
NEWCOMER = {'NEWCOMER_ALL_FLAT','NEWCOMER_SURFACE','NEWCOMER_VENUE_SURFACE','NEWCOMER_SURFACE_DISTANCE_EXACT'}

def require(ok, message):
    if not ok: raise ValueError(message)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def unique(pairs):
    result = {}
    for k,v in pairs:
        require(k not in result, 'duplicate JSON key'); result[k]=v
    return result

def load(path, pin):
    require(re.fullmatch('[0-9a-f]{64}',pin or '') and sha(path)==pin,'source SHA mismatch')
    return json.loads(Path(path).read_text(),object_pairs_hook=unique,parse_constant=lambda s: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def keyed(items, key):
    d={}
    for item in items:
        k=key(item);require(k not in d,'duplicate identity/evidence');d[k]=item
    return d

def ident(h): return h['horse_no'],h['horse_id'],h['scheduled_jockey_code'],h['entry_cancel_flag_raw']

def jp_refs(h1,h2,h3, key, target):
    require(ident(h1)==ident(h2)==ident(h3),'JPDB R1/R2/R3 identity mismatch')
    require(set(h1['windows'])==WINDOWS,'JPDB windows mismatch')
    axes=keyed(h2['axes'],lambda x:x['dimension'])
    require(NEWCOMER<=set(axes) and len(axes)==17,'newcomer axes mismatch')
    projected=keyed((e for e in h3['evidence'] if e['family']=='JPDB'),lambda e:e['evidence_id'])
    out=[]
    for win in sorted(WINDOWS):
        w=h1['windows'][win]; start=w['period_from_inclusive']
        require(start<target==w['period_to_exclusive'],'R1 cutoff')
        cells=keyed(w['evidence'],lambda e:e['dimension']);require(set(cells)==set(axes),'R1/R2 axes mismatch')
        for dim,e in sorted(cells.items()):
            eid=f'{key}:{h1["horse_no"]:02d}:{win}:{dim}'; a=axes[dim];r=a['windows'][win];p=projected.get('JPDB:'+eid)
            require(set(a['windows'])==WINDOWS and e['evidence_id']==r['r1_evidence_id']==eid and a['condition']==e['condition'] and a['redundancy_group_id']==e['redundancy_group_id'] and r['period_from_inclusive']==start and r['period_to_exclusive']==target,'R1/R2 binding mismatch')
            require(p is not None and p['source_ref']=={'asset':'jpdb_r1+r2','id':eid} and p['condition']==e['condition'] and p['scope']==dim and p['period_from_inclusive']==start and p['period_to_exclusive']==target and p['redundancy_group_id']==GROUP and p['native_overlap_group']==e['redundancy_group_id'] and p['sample_status']==e['status'] and p['source_status']==e['source_status'],'R3 reference mismatch')
            m=e['metrics'];g=r['groups'];o=p['observation']
            if m is None:require(o is None and g is None,'missing JPDB metric became observation')
            else:
                for date_field in ('first_observed','last_observed'):
                    require(m[date_field] is None or start<=m[date_field]<target,'future JPDB metric')
                require(o is not None and (o['n'],o['wins'],o['top3'],o['top2'],o['denominator'])==(m['actual_starts_candidate'],m['wins'],m['top3'],m['top2'],'JPDB_CANDIDATE_STARTS'),'R3 count mismatch')
                if g is not None:
                    own=g['own_match'];require(own['resolved_starts']+own['unresolved']==o['n'] and own['wins']==o['wins'] and own['top3']==o['top3'],'R2 count mismatch')
            out.append(dict(evidence_id='JPDB:'+eid,source_id=eid,scope=dim,window=win,source_status=e['source_status'],sample_status=e['status'],native_overlap_group=e['redundancy_group_id']))
    require(len(out)==51 and set(projected)=={e['evidence_id'] for e in out},'R3 evidence field mismatch')
    return out

def b_refs(h):
    # All values stay in the original B5 private asset, including restricted pair/relative observations.
    return ([dict(evidence_id=e['evidence_id'],cohort=e['cohort'],lane=e['lane'],scope=e['scope'],sample_status=e['status'],usage='RESEARCH_REFERENCE_ONLY') for e in h['population_evidence']],
            [dict(evidence_id=e['evidence_id'],relative_id=e['relative_id'],scope=e['scope'],sample_status=e['sample_status'],usage='RESEARCH_REFERENCE_ONLY') for e in h['relative_evidence']])

def assemble(review,r1,r2,details,paci,paci_pin,assets):
    validate_b5(review)
    target=review['target_date']; keys={r['race_key'] for r in review['races']}
    require(set(details)==keys,'R3 race set mismatch')
    require(review['paci_sha256']==paci_pin and r1['target_date']==r2['target_date']==target and r1['prediction_safe'] is r2['prediction_safe'] is False,'target/source flag mismatch')
    require(r1['schema_version']=='jpdb-r1-jockey-profile-v0.1-candidate' and r2['schema_version']=='jpdb-r2-condition-context-v0.1-candidate','JPDB version mismatch')
    s=r1['source'];require(s==r2['source'] and s['target_paci_sha256']==paci_pin and s['strict_asof_certified'] is False and s['historical_jockey_role']=='SED_ACTUAL' and s['target_jockey_role']=='PACI_KYI_SCHEDULED_IN_STORED_VERSION','JPDB source contract mismatch')
    require(r2['policy']['no_additive_votes'] is True and r2['policy']['suggestive_allowed'] is False,'JPDB policy mismatch')
    bac,entries,_,_,d=read_field(paci,paci_pin,keys);require(d==target,'PACI target date mismatch')
    by_bac=keyed(bac,lambda r:r['race_key_raw']);paci_rows=keyed(entries,lambda e:(e['race_key_raw'],e['horse_no']))
    b=keyed(review['horses'],lambda h:(h['race_key'],h['horse_no']));require(set(b)==set(paci_rows),'B5 missing/extra target')
    j1=keyed(r1['races'],lambda r:r['race_key_raw']);j2=keyed(r2['races'],lambda r:r['race_key_raw']);br=keyed(review['races'],lambda r:r['race_key'])
    output=[];raceout=[]
    for key in sorted(keys):
        a,c=j1[key],j2[key];bc=by_bac[key];detail=details[key]
        require(detail['contract_version'] in ('racenote-independent-evidence-v0.1-candidate','racenote-independent-evidence-base-only-v0.1-candidate') and detail['prediction_safe'] is False and detail['production_authorized'] is False and detail['research_only'] is True and detail['target_date']==detail['as_of_exclusive']==target and detail['target_paci_sha256']==paci_pin,'R3 contract/time mismatch')
        for src in ('jpdb_r1','jpdb_r2','jpdb_r1_receipt','jpdb_r2_receipt','paci'):
            require(detail['source_assets'][src]['sha256']==assets[src],'R3 pinned source mismatch')
        dr=keyed(detail['races'],lambda r:r['race_key_raw'])[key]
        require(a['is_newcomer_race'] is c['is_newcomer_race'] is dr['is_newcomer_race'] is True and a['race_class_code']==dr['race_class_code']==bc['race_class_code']=='A1' and dr['coverage_status']=='DUAL_SOURCE_RESEARCH','R3 race class/acceptance mismatch')
        require(a['distance_m']==dr['distance_m']==br[key]['distance']==int(bc['distance_raw']) and a['surface_code']==dr['surface_code']==br[key]['surface']==bc['surface_code'] and a['venue_code']==dr['venue_code']==key[:2],'race condition mismatch')
        pfield={n:e for (rk,n),e in paci_rows.items() if rk==key};x,y,z=(keyed(q['horses'],lambda h:h['horse_no']) for q in (a,c,dr))
        require(set(pfield)==set(x)==set(y)==set(z) and len(x)==a['entry_count']==c['entry_count']==dr['entry_count']==br[key]['declared_count']==bc['field_size'],'whole field mismatch')
        raceout.append(dict(race_key=key,field_size=len(x),surface=br[key]['surface'],distance=br[key]['distance'],r3_contract_version=detail['contract_version'],r3_detail_sha256=assets['r3_details'][key]))
        for n,e in sorted(pfield.items()):
            bh=b[key,n];j=x[n];hid=e['blood_registration_no'];code=e['jockey_code'];cancel=e['cancel_flag']
            require(re.fullmatch('[0-9]{5}',code or '') and code!='00000' and ident(j)==(n,hid,code,cancel) and bh['horse_id']==hid and bh['paci_cancel_flag']==cancel,'PACI identity/jockey/cancel mismatch')
            jr=jp_refs(j,y[n],z[n],key,target);pop,rel=b_refs(bh)
            output.append(dict(race_key=key,horse_no=n,horse_id=hid,scheduled_jockey_code=code,entry_cancel_flag_raw=cancel,individual_eligibility=bh['individual_eligibility']['status'],jpdb=dict(status='RESEARCH_CONTEXT_ONLY',evidence_refs=jr),brdb=dict(status='RESEARCH_REFERENCE_ONLY',profile_status=bh['profile_status'],relative_status=bh['relative_coverage']['status'],population_refs=pop,relative_refs=rel),redundancy_group_id=GROUP))
    return dict(schema_version=VERSION,target_date=target,target_paci_sha256=paci_pin,research_only=True,prediction_safe=False,production_authorized=False,r4_authorized=False,policy='NO_ADDITIVE_VOTES_NO_SCORES_NO_TARGET_OUTCOMES',brdb_history_cutoff_exclusive=review['history_cutoff_exclusive'],brdb_history_gap_2026=review['history_gap_2026'],jpdb_history_cutoff_exclusive=target,brdb_temporal_status=review['temporal_status'],jpdb_temporal_status='PRIOR_DAY_ASSUMED_NOT_STRICTLY_ATTESTED',source_assets=assets,races=raceout,horses=output)

def summarize(out,review,r1):
    # Fixed broad and matching scope availability: all entries retained, no probability or rank.
    b=keyed(review['horses'],lambda h:(h['race_key'],h['horse_no']))
    j={(r['race_key_raw'],h['horse_no']):h for r in r1['races'] for h in r['horses']}
    counts=Counter();support={};pop=Counter();rel=Counter();jp=Counter()
    for h in out['horses']:
        k=(h['race_key'],h['horse_no']);bh=b[k];jh=j[k];p=bh['population_evidence'];r=bh['relative_evidence']
        pop.update(e['status'] for e in p);rel.update(e['sample_status'] for e in r);jp.update(e['sample_status'] for e in h['jpdb']['evidence_refs'])
        for bs,js in [('ALL','NEWCOMER_ALL_FLAT'),('SURFACE','NEWCOMER_SURFACE'),('SURFACE_DISTANCE','NEWCOMER_SURFACE_DISTANCE_EXACT')]:
            bp=[e for e in p if e['cohort']=='A1_RACE_ACTUAL_STARTERS' and e['scope']==bs];je=next(e for e in jh['windows']['ROLLING_3Y']['evidence'] if e['dimension']==js);m=je['metrics'];j_ok=m is not None and m['actual_starts_candidate']>0 and m['unresolved_count']==0
            j30=j_ok and m['actual_starts_candidate']>=30
            for lane in sorted({e['lane'] for e in bp}):
                be=next(e for e in bp if e['lane']==lane);b_ok=be['starts'] is not None and be['starts']>0;b30=b_ok and be['starts']>=30
                name=bs+':'+lane;ctr=support.setdefault(name,Counter());ctr['both_positive' if b_ok and j_ok else 'blood_only' if b_ok else 'jockey_only' if j_ok else 'neither']+=1;ctr['both_n_ge_30']+=int(b30 and j30)
        counts['relative_targets_first']+=int(h['brdb']['relative_status']=='DESCRIPTIVE_FIRST_HISTORY')
    # Dependency audit: repeated keys across target entries, not independent statistical support.
    riders=Counter(h['scheduled_jockey_code'] for h in out['horses']);pair_keys=Counter((e['lane'],e['key1'],e['key2']) for h in review['horses'] for e in h['population_evidence'] if e['cohort']=='A1_RACE_ACTUAL_STARTERS' and e['scope']=='ALL' and e['key1'] is not None and e['key2'] is not None)
    relatives=Counter(e['relative_id'] for h in review['horses'] for e in h['relative_evidence'] if e['scope']=='ALL')
    return dict(horses=len(out['horses']),races=len(out['races']),jpdb_refs=sum(len(h['jpdb']['evidence_refs']) for h in out['horses']),population_refs=sum(pop.values()),relative_refs=sum(rel.values()),population_status=dict(pop),relative_status=dict(rel),jpdb_status=dict(jp),relative_targets_first=counts['relative_targets_first'],joint_support={k:dict(v) for k,v in support.items()},dependence=dict(distinct_riders=len(riders),riders_reused=sum(v>1 for v in riders.values()),repeated_blood_keys=sum(v>1 for v in pair_keys.values()),repeated_relative_ids=sum(v>1 for v in relatives.values()),historical_row_overlap='NOT_MEASURED_FROM_AGGREGATE_PROFILES',policy=GROUP))

def run(manifest_path,manifest_pin,output_dir):
    manifest=load(manifest_path,manifest_pin);require(manifest['version']=='brdb-b6-private-input-v1','manifest version')
    a=manifest['assets'];base=manifest_path.parent
    def file(asset):return base/asset['path']
    def doc(name):return load(file(a[name]),a[name]['sha256'])
    review=doc('brdb_b5');receipt=doc('brdb_b5_receipt');r1=doc('jpdb_r1');r2=doc('jpdb_r2');jr1=doc('jpdb_r1_receipt');jr2=doc('jpdb_r2_receipt')
    require(receipt['private_output_sha256']==a['brdb_b5']['sha256'] and receipt['status']=='PASS_RESEARCH_ONLY' and receipt['paci_sha256']==a['paci']['sha256'],'B5 receipt mismatch')
    # Accepted source receipt is independently pinned by manifest; verify target-specific R1/R2 bindings via the accepted R3 detail too.
    require(jr1['prediction_safe'] is False and jr2['prediction_safe'] is False and jr1['status']=='PASS' and jr2['status']=='PASS_RESEARCH_CONTEXT_ONLY','JPDB receipt flags')
    day=review['target_date']; proofs1=keyed(jr1['proofs'],lambda x:x['target_date']);proofs2=keyed(jr2['profile_proofs'],lambda x:x['date'])
    p1,p2=proofs1[day],proofs2[day]
    require(p1['repeat_equal'] is p2['repeat_equal'] is True and p1['profile_sha256']==p2['r1_profile_sha256']==a['jpdb_r1']['sha256'] and p2['r2_context_sha256']==a['jpdb_r2']['sha256'] and p1['target_paci_sha256']==a['paci']['sha256'],'JPDB accepted profile receipt mismatch')
    details={k:load(file(v),v['sha256']) for k,v in a['r3_details'].items()}
    pins={k:v['sha256'] for k,v in a.items() if k!='r3_details'};pins['r3_details']={k:v['sha256'] for k,v in a['r3_details'].items()}
    out=assemble(review,r1,r2,details,file(a['paci']),a['paci']['sha256'],pins)
    require(not output_dir.exists() or not any(output_dir.iterdir()),'output directory must be new or empty')
    output_dir.mkdir(parents=True,exist_ok=True)
    def write(name,obj):
        p=output_dir/name;p.write_text(json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n');return sha(p)
    result_sha=write('PRIVATE_b6_link.json',out);audit=summarize(out,review,r1);audit.update(status='PASS_RESEARCH_ONLY',private_output_sha256=result_sha,input_manifest_sha256=manifest_pin,source_sha256=sha(__file__),prediction_safe=False,production_authorized=False);write('b6_receipt.json',audit);return audit

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.manifest,a.manifest_sha256,a.output_dir),indent=2))
