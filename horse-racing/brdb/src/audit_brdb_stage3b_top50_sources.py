#!/usr/bin/env python3
"""Compare 50 JBIS pedigree observations with pinned JRDB research subjects.

External labels are kept separately; verified JRDB IDs and source-qualified
external IDs are distinct. No unknown ancestor is inferred from a name.
"""
import argparse, csv, hashlib, itertools, json, re
from collections import Counter
from pathlib import Path
import duckdb
from brdb_stage3b_reachability_contract import validate_reachability

PINS={'top50':'89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0',
      'ranking':'e982e7b5a1467af5bb18e74f583acd9315263a74516472ca439c88b0f2eaf362',
      'pedigree':'1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536',
      'source':'afb3ca403c200210e0bf4490c4c8400db1016a76fc489c0bb28075135b6fb78b',
      'seed':'28793703a85b3fcb4c41490dec70b49770457e7139e0443688d35a7688bc2602',
      'registry':'d9680857e1f8dcb6669b3ff57c57a4ba95de763b5fda9ff19221ab8b4e4e645e',
      'baseline':'bd501ef5586db3829606f28784f54bbca1bde0a0123fcdb07745cb18d1e19e43',
      'batch':'da7d6d6a830e69ef82a2d4fbde4bcce81746be2324536d3a9d77e0eaf7c1afcb'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def normalize(s):return re.sub(r'\([A-Z]{2,3}\)$','',(s or '').strip())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n')

def run(top50,ranking,pedigree,source,seed,registry,baseline,batch,out):
 for k,p in [('top50',top50),('ranking',ranking),('pedigree',pedigree),('source',source),('seed',seed),('registry',registry),('baseline',baseline),('batch',batch)]:
  if sha(p)!=PINS[k]:raise ValueError(k+' SHA mismatch')
 original=json.loads(top50.read_text());evidence=json.loads(source.read_text());seed=json.loads(seed.read_text());reg=json.loads(registry.read_text());hybrid=json.loads(baseline.read_text());batch2=json.loads(batch.read_text())
 if evidence.get('version')!='brdb-stage3b-jbis-observations-v0.1' or not evidence.get('research_only') or evidence.get('prediction_safe') is not False:raise ValueError('invalid external observation contract')
 with ranking.open(encoding='utf-8-sig',newline='') as f:ranked=list(csv.DictReader(f))[:50]
 subjects=original['subjects'];obs={x['rank']:x for x in evidence['pedigrees']};profiles={x['rank']:x for x in evidence['profiles']};seeds={x['jrdb_observed_label']:x for x in seed['pedigrees']};approved={x['jrdb_horse_id']:x for x in reg['approved_research_crosswalks']}
 if len(subjects)!=50 or len(ranked)!=50 or len(obs)!=len(evidence['pedigrees']) or len(profiles)!=len(evidence['profiles']) or len({x['jbis_id'] for x in evidence['profiles']})!=50 or set(obs)!=set(range(1,51)) or set(profiles)!=set(obs):raise ValueError('wrong top50 source set')
 con=duckdb.connect();rows=[];subjects_out=[];nodes={};paths=[];counts=Counter();root_status=Counter()
 hybrid_index={(x['stallion_name'],x['path']):x['ancestor_external_subject_key'] for x in hybrid['paths']}
 # Batch-2 adds three independently audited source-qualified endpoints.
 breg=json.loads(Path('horse-racing/brdb/taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_2.json').read_text())
 for row in batch2['new_paths']:
  subject=next(x for x in breg['approved_research_crosswalks'] if x['name']==row['stallion_name'])
  link=next(x for x in subject['parent_links'] if x['path']==row['path'])
  hybrid_index[(row['stallion_name'],row['path'])]=link['external_ancestor_key']
 if len(hybrid_index)!=29:raise ValueError('unexpected validated hybrid endpoints')
 for s,r in zip(subjects,ranked):
  rank=s['rank'];e=obs[rank];p=profiles[rank]
  if (s['name']!=r['name'] or int(r['birth_year'])!=s['birth_year'] or r['jrdb_lineage_code']!=s['jrdb_lineage_code_observed'] or int(r['sire_count'])!=s['sire_count_2022_2024'] or int(r['bms_count'])!=s['bms_count_2022_2024'] or s['name']!=e['name'] or s['name']!=p['name'] or e['jbis_subject_id']!=p['jbis_id'] or not re.fullmatch('[0-9]{10}',p['jbis_id'])):raise ValueError('rank/person source mismatch')
  if e['source_url']!=f"https://www.jbis.or.jp/horse/{p['jbis_id']}/pedigree/" or p['profile_url']!=f"https://www.jbis.or.jp/horse/{p['jbis_id']}/":raise ValueError('invalid source URL')
  expected_paths={''.join(bits) for depth in (1,2,3) for bits in itertools.product('SD', repeat=depth)}
  if set(e['paths'])!=expected_paths or any(not isinstance(v.get('label'),str) or not v['label'] or type(v.get('year')) is not int for v in e['paths'].values()):raise ValueError('invalid pedigree slots')
  root=s['jrdb_horse_id'];trust=False;root_reason='CROSSWALK_UNRESOLVED';jrdb=None
  if root:
   vals=con.execute('select horse_name,birth_date,sex_code,sire_name,dam_name from read_parquet(?) where horse_id=?',[str(pedigree),root]).fetchall()
   if len(vals)!=1:raise ValueError('JRDB root invalid')
   jrdb=vals[0];trust=(e['root_label_match'] and p['jbis_date']==jrdb[1] and p['jbis_sex']=='牡' and jrdb[2]=='1' and normalize(p['source_ancestor_sire'])==jrdb[3] and normalize(p['source_ancestor_dam'])==jrdb[4])
   if trust:root_reason='MULTI_FIELD_EXACT';
   elif root in approved and approved[root]['jbis_horse_id']==p['jbis_id']:
    trust=True;root_reason='EXISTING_AUDITED_CROSSWALK'
  else:
   old=seeds.get(s['name']);trust=bool(old and old['jbis_horse_id']==p['jbis_id'] and p['jbis_date'] and int(p['jbis_date'][:4])==s['birth_year'] and p['jbis_sex']=='牡' and normalize(p['source_ancestor_sire'])==old['source_name_paths']['S'] and normalize(p['source_ancestor_dam'])==old['source_name_paths']['D'])
   if trust:root_reason='EXTERNAL_PROFILE_AND_SEED_MATCH'
  root_status[root_reason]+=1
  original_paths={x['path']:x for x in s['paths']}
  root_key='JRDB:'+root if root else 'JBIS:'+p['jbis_id'] if trust else None
  if root_key:nodes.setdefault(root_key,{'id':root_key,'kind':'ENTRY','names':[]})['names'].append(s['name'])
  subjects_out.append({'rank':rank,'name':s['name'],'root_id':root_key,'jbis_id':p['jbis_id'],'source_identity_status':root_reason,'issue':('JRDB_OR_SOURCE_PARENT_OR_PROFILE_MISMATCH' if not trust else None),'profile_url':p['profile_url'],'pedigree_url':e['source_url'],'sire_count':int(r['sire_count']),'bms_count':int(r['bms_count'])})
  for depth in (1,2,3):
   for parts in itertools.product('SD',repeat=depth):
    path=''.join(parts);a=original_paths.get(path,{});src=e['paths'].get(path);jrdb_id=a.get('id');ext=hybrid_index.get((s['name'],path))
    if ext and not root:raise ValueError('hybrid path requires a JRDB root')
    if jrdb_id and ext:raise ValueError('source path double-counted')
    observed=bool(src and trust);observed_name=src['label'] if observed else None
    canonical='JRDB:'+jrdb_id if jrdb_id else ext
    status='JRDB_CANONICAL' if jrdb_id else 'JBIS_SOURCE_QUALIFIED' if ext else 'NAME_OBSERVED' if observed_name or a.get('name') else 'UNRESOLVED'
    counts[f'depth{depth}_{status}']+=1;counts[f'depth{depth}_named']+=bool(observed_name or a.get('name'));counts[f'depth{depth}_source_name']+=observed
    prior_name=a.get('name');name_agreement=('EXACT' if normalize(prior_name)==normalize(observed_name) else 'DIFFERENT_UNREVIEWED') if prior_name and observed_name else 'SINGLE_SOURCE_OR_UNKNOWN'
    if name_agreement=='DIFFERENT_UNREVIEWED':counts[f'depth{depth}_name_difference_unreviewed']+=1
    row={'rank':rank,'subject':s['name'],'path':path,'depth':depth,'jrdb_name':prior_name,'jbis_name':observed_name,'name_agreement':name_agreement,'jbis_year':src['year'] if observed else None,'ancestor_id':canonical,'status':status,'root_identity':root_reason,'source_url':e['source_url'] if observed else None}
    rows.append(row)
    if canonical:
     nodes.setdefault(canonical,{'id':canonical,'kind':'ANCESTOR','names':[]})['names'].append(a.get('name') or observed_name)
     paths.append({'root_id':root_key,'ancestor_id':canonical,'path':path,'status':status,'source_url':e['source_url'] if ext else 'JRDB_PARENT_RELATION'})
 for n in nodes.values():n['names']=sorted({x for x in n['names'] if x})
 out.mkdir(parents=True,exist_ok=True);dump(out/'subjects.json',subjects_out);dump(out/'slots.json',rows);dump(out/'shared_graph.json',{'schema_version':'brdb-stage3b-reachability-v0.1','graph_kind':'ROOT_TO_ANCESTOR_REACHABILITY','direct_parent_edge_count':0,'supports_cross_detection':False,'research_only':True,'prediction_safe':False,'historical_asof_status':'AS_OF_UNVERIFIED','path_semantics':'Each record joins a root stallion to an ancestor by an S/D traversal path; it does not assert a direct parent edge unless path length is one and its evidence is separately verified. Never interpret paths as direct parent edges.','nodes':list(nodes.values()),'paths':paths});graph_audit=validate_reachability({'schema_version':'brdb-stage3b-reachability-v0.1','graph_kind':'ROOT_TO_ANCESTOR_REACHABILITY','direct_parent_edge_count':0,'supports_cross_detection':False,'research_only':True,'prediction_safe':False,'historical_asof_status':'AS_OF_UNVERIFIED','nodes':list(nodes.values()),'paths':paths});dump(out/'summary.json',{'graph_contract_validation':graph_audit,'subject_count':50,'root_identity_status':dict(root_status),'slot_counts':dict(counts),'crosswalk_model':'exact name, full birth date, sex, sire and dam; prior independently verified identities preserved','historical_asof_status':'AS_OF_UNVERIFIED','prediction_safe':False,'source_sha256':{k:sha(p) for k,p in [('top50',top50),('ranking',ranking),('pedigree',pedigree),('external_observations',source)]}})
 with (out/'slots.csv').open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 print(json.dumps({'root_status':dict(root_status),'slot_counts':dict(counts)},ensure_ascii=False))

def main():
 p=argparse.ArgumentParser()
 for name in ('top50','ranking','pedigree','source','seed','registry','baseline','batch','out'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();run(**vars(a))
if __name__=='__main__':main()
