#!/usr/bin/env python3
"""Independent JSON projection audit; no domain reaggregation or target results.

Run only in a private environment. Public receipt is aggregates and hashes only.
Requires jsonschema; use the approved runtime for the upstream producer separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter
from jsonschema import Draft202012Validator, FormatChecker


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def require(x,msg):
    if not x:raise ValueError(msg)

def audit(manifest_path,expected_manifest_sha,detail_path,preview_dir,schema_dir):
    require(sha(manifest_path)==expected_manifest_sha,'audit manifest mismatch')
    manifest=load(manifest_path);files=manifest['assets']
    for k,v in files.items():require(sha(v['path'])==v['sha256'],'audit input SHA mismatch')
    r1=load(files['jpdb_r1']['path']);r2=load(files['jpdb_r2']['path']);d=load(detail_path);target=d['target_date']
    a1={r['race_key_raw']:r for r in r1['races']};a2={r['race_key_raw']:r for r in r2['races']}
    require(set(a1)==set(a2)=={r['race_key_raw'] for r in d['races']},'race coverage mismatch')
    require(d['research_only'] and not d['prediction_safe'] and not d['production_authorized'] and d['as_of_exclusive']==target,'unsafe contract')
    b=load(files['brdb_v03']['path']) if 'brdb_v03' in files else None;rel=load(files['brdb_relatives_detail']['path']) if b else None
    root=Path(schema_dir)
    validators=[]
    for name in ('racenote_independent_evidence_v0_1_candidate.schema.json','racenote_independent_evidence_preview_v0_1_candidate.schema.json'):
        s=load(root/name);Draft202012Validator.check_schema(s);validators.append(Draft202012Validator(s,format_checker=FormatChecker()))
    validators[0].validate(d);results=[]
    for r in d['races']:
        key=r['race_key_raw'];is_b=b is not None and b['race']['race_key']==key
        h1={h['horse_no']:h for h in a1[key]['horses']};h2={h['horse_no']:h for h in a2[key]['horses']};hb={h['horse_no']:h for h in b['horses']} if is_b else {};hr={h['horse_no']:h for h in rel['horses']} if is_b else {}
        require(set(h1)==set(h2)=={h['horse_no'] for h in r['horses']},'horse coverage mismatch')
        ppath=Path(preview_dir)/(key+'.json');p=load(ppath);validators[1].validate(p);require(p['detail_sha256']==sha(detail_path) and p['race']['race_key_raw']==key,'preview SHA or key mismatch');hp={h['horse_no']:h for h in p['horses']}
        require(set(hp)==set(h1),'preview all-horse coverage mismatch')
        c=Counter();detail_bytes=len(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
        for h in r['horses']:
            n=h['horse_no'];s=h1[n];q=h2[n];pv=hp[n]
            require(all(h[k]==s[k]==q[k]==pv[k] for k in ('horse_id','horse_no','scheduled_jockey_code','entry_cancel_flag_raw')),'identity mismatch')
            e={x['evidence_id']:x for x in h['evidence']};rr={x['evidence_id']:x for x in h['restricted_refs']};require(len(e)==len(h['evidence']) and len(rr)==len(h['restricted_refs']) and not set(e)&set(rr),'duplicate evidence IDs')
            jids=set();bids=set();rids=set();axis={a['dimension']:a for a in q['axes']}
            for window,w in s['windows'].items():
                for item in w['evidence']:
                    eid='JPDB:'+item['evidence_id'];jids.add(eid);x=e[eid];m=item['metrics'];comp=axis[item['dimension']]['windows'][window];require(x['period_to_exclusive']==target and x['period_from_inclusive']==w['period_from_inclusive'] and x['condition']==item['condition'] and x['source_status']==item['source_status'] and x['sample_status']==item['status'],'JPDB metadata drift')
                    if m is None:require(x['observation'] is None,'unavailable became numeric')
                    else:
                        o=x['observation'];require([o[k] for k in ('n','wins','top2','top3','win_rate','top3_rate','unresolved')]==[m[k] for k in ('actual_starts_candidate','wins','top2','top3','start_basis_win_rate_candidate','start_basis_top3_rate_candidate','unresolved_count')],'JPDB observation drift');c['jpdb_numeric_cells']+=1
                    for kind,v in comp['comparisons'].items():
                        z=x['comparison'][kind];require(all(z[k]==v[k] for k in ('status','top3_delta_pp','wins_delta_pp','top3_unresolved_bounds_pp','wins_unresolved_bounds_pp')),'comparison numeric/status drift');c['jpdb_comparison_cells']+=1
                    c['jpdb_evidence']+=1
            if is_b:
                hbr=hb[n];require(hbr['horse_id']==hr[n]['horse_id']==h['horse_id'],'BRDB identity mismatch');require(h['brdb_components']=={k:v['availability'] for k,v in hbr['components'].items()},'BRDB coverage drift')
                for x in hbr['evidence']:
                    eid=f'BRDB:{key}:{n:02d}:'+x['evidence_id']
                    if x['component'] in ('sire','broodmare_sire'):
                        bids.add(eid);z=e[eid];o=z['observation'];m=x['observations'];require([o[k] for k in ('n','unique_horses','wins','top3','win_rate','top3_rate')]==[m[k] for k in ('starts','unique_horses','wins','top3','win_rate','top3_rate')],'blood numeric drift');require(z['condition']==x['condition'] and z['sample_status']==x['sample_status'] and z['uncertainty']['top3_wilson95']==m['top3_wilson95'],'blood condition/sample drift');c['brdb_observations']+=1
                    else:rids.add(eid);c['restricted_integrated_refs']+=1
                for z in hr[n]['relatives']:
                    eid=f'REL_{h["horse_id"]}_{z["horse_id"]}_{z["relationship"]}'
                    for scope,st in z['scope_stats'].items():
                        rid=f'BRDB_DETAIL:{key}:{n:02d}:{eid}:{scope}';rids.add(rid);require(rr[rid]['sample_status']==('NO_SAMPLE' if st['starts']==0 else 'DESCRIPTIVE'),'relative scope status drift');c['restricted_relative_cells']+=1;c['restricted_relative_zero_cells']+=int(st['starts']==0)
                for i in range(len(hbr['supplemental_insights'])):rids.add(f'BRDB_D4:{key}:{n:02d}:{i}');c['restricted_supplemental_refs']+=1
            else:require(h['brdb_status']=='SOURCE_UNAVAILABLE' and all(v=='SOURCE_UNAVAILABLE' for v in h['brdb_components'].values()),'missing blood promoted')
            require(set(e)==jids|bids and set(rr)==rids,'evidence completeness mismatch')
            require(all('observation' not in x and 'comparison' not in x and x['as_of_status']=='AS_OF_UNVERIFIED' for x in rr.values()),'restricted numeric leak')
            # Decode position-specific preview and verify source observation counts, exact ID, and status.
            visible=[]
            for lane in ('jockey','blood'):
                for row in pv[lane]:
                    x=dict(zip(p['columns'][lane],row));z=e[x['evidence_id']];o=z['observation'] or {};visible.append(x['evidence_id']);require(x['scope']==z['scope'] and x['condition']==z['condition'] and x['sample_status']==z['sample_status'] and all(x[k]==o.get(k) for k in ('n','wins','top3','top3_rate')),'preview observation drift')
                    if lane=='jockey' and x['comparison_kind']:
                        v=z['comparison'][x['comparison_kind']];require(x['across_windows_status']==v['across_windows_status'] and x['comparison_top3_delta_pp']==v['top3_delta_pp'],'preview comparison drift')
                        if v['across_windows_status']!='CONTEXTUAL':require(x['across_windows_direction']=='UNCLASSIFIED','preview conflict promoted')
            require(len(visible)==len(set(visible)) and pv['detail_evidence_count']==len(e) and pv['omitted_detail_count']==len(e)-len(visible) and pv['restricted_ref_count']==len(rr),'preview coverage drift')
            c['preview_rows']+=len(visible)
        results.append({'cohort':'NEWCOMER' if r['is_newcomer_race'] else 'OTHER','field_size':len(r['horses']),'coverage_status':r['coverage_status'],'counts':dict(c),'detail_race_bytes':detail_bytes,'preview_bytes':ppath.stat().st_size,'preview_sha256':sha(ppath)})
    return {'target_date':target,'input_manifest_sha256':expected_manifest_sha,'source_asset_sha256':{k:v['sha256'] for k,v in files.items()},'detail_sha256':sha(detail_path),'detail_bytes':Path(detail_path).stat().st_size,'races':results,'detail_schema_pass':True,'preview_schema_pass_count':len(results),'status':'PASS_FIXED_SOURCE_PROJECTION_ONLY'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--detail',type=Path,required=True);p.add_argument('--preview-dir',type=Path,required=True);p.add_argument('--schema-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();o=audit(a.manifest,a.manifest_sha256,a.detail,a.preview_dir,a.schema_dir);a.output.write_text(json.dumps(o,sort_keys=True,indent=2)+'\n')
if __name__=='__main__':main()
