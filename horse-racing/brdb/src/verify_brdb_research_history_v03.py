import argparse, json
from collections import Counter
from brdb_research_history_reader_v03 import ResearchHistoryReader
parser=argparse.ArgumentParser()
parser.add_argument('--generation',required=True)
p=parser.parse_args().generation
r=ResearchHistoryReader(p,expected_generation_id='5279af0bd8226cde',expected_manifest_sha256='7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c')
c=Counter()
for h in r.latest.added_ids:
 date=r.latest.latest_profile_available_from[h]; a=r.horse_profile(h,as_of=date); f=r.facts[h]
 c['checked']+=1
 if a['profile'] is None or a['profile_data_date']!=f['profile_data_date'] or a['source']['semantic_hash']!=f['semantic_hash']: c['mismatch']+=1
 if a['profile'] and (a['profile_data_date']>date or a['observed_date']>date): c['leak']+=1
 if any(x['resolved_parent_horse_id'] is not None for x in r.parent_relations(h,as_of=date)): c['parent_leak']+=1
 if r.horse_profile(h,as_of='20251231')['profile'] is not None: c['pre2026_leak']+=1
 if any(x['in_preserved_cohort'] for x in r.history[h]): c['old104_checked']+=1
assert c['checked']==3898 and c['old104_checked']==104 and not c['mismatch'] and not c['leak'] and not c['pre2026_leak'] and not c['parent_leak']
print(json.dumps(dict(c),sort_keys=True))
