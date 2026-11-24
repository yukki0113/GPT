"""Local research runner. Input views are verified before use; detailed rows private."""
from pathlib import Path
import argparse,hashlib,json,csv
from data_storage.query import connect_parquet
from data_storage.common import parquet_glob,sql_literal
from data_storage.dependencies import dependency_report

ROOT=Path(__file__).resolve().parent
EXPECTED_V02='279ee9c61e9db06b487e473e60a1021b68153c1373d4b0358c58c8f10b259eb2'
ANALYSIS_SHA='39b4e94d31e5dc9507bd3aa037aa227c7c8dcefe0ddf3f744ec1e687a6965f1d'
WAREHOUSE_SHA='174eaf459f56eb1afe55bc157a2dcf0226a212bf6c00ba062ce5a3e641b2a269'
PEDIGREE_SHAS={'manifest.json':'7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c','pedigree_fact.parquet':'1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536','parent_relation.parquet':'c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85'}
UKC_SHAS=dict(enumerate(['b965d958fad102ac2c61ddf3e0dc1ec5157d7920b36d14c55f62374c60f6cb09','97ee4928cc9c954528d015f9b25911e7f693ccf50c48f2889a8311a35bc8479f','32143795bb755e93a860f9da68fbf14d8b3fbb5522c0180c9071c8f9f9b88f3c','706ea01a73f91df10e9001f7db47b9a5d4b69a4d0a4cd0dbdcf99e41853aa87f','824ee947b305c59d8f37cacbc3733d54d8f1a0f960e62ecbed9eae1e5c3b3495','0fb1de4fa86b1b71c199181437244133981e2c61aa748559adeea7b30ad5092f','00da0dc8171a0ce472ff06ad839b822ffc625e7115c262a86bd9cbd9c51642fb','29fdbe9b2658c804f5c2826ca5e6190726a3032c3319bf43fa5ca4fd814a73e8','fafa0b24ecec70ecc3dafbc6897ffd6da21b167439bb22512d15c241b856563b','554f1bf8f72a48b9b6462e1b7d1c4448383ce078c3c9b420006bb21e8558dad5'],2016))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical_hash(j):return hashlib.sha256(json.dumps(j,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def require(test,msg):
    if not test:raise ValueError(msg)
def verify_input(INPUT):
    p=INPUT/'analysis_manifest.json';require(sha(p)==ANALYSIS_SHA,'Analysis manifest SHA mismatch');m=json.loads(p.read_text())
    parts=[x for x in m['fact_table']['partitions'] if 2016<=x['year']<=2025]
    require({x['year'] for x in parts}==set(range(2016,2026)) and len(parts)==10,'Analysis year coverage')
    for x in parts:
        f=INPUT/x['relative_path'];require(f.stat().st_size==x['size_bytes'] and sha(f)==x['sha256'],'Analysis partition mismatch')
    wm=json.loads((INPUT/'warehouse/manifest.json').read_text());ptr=json.loads((INPUT/'warehouse/current.json').read_text());audit=json.loads((INPUT/'warehouse/audit.json').read_text())
    require(ptr['status']=='accepted' and wm['status']=='PASS' and wm['generation_id']==ptr['generation_id'] and canonical_hash(wm)==ptr['manifest_sha256']==WAREHOUSE_SHA and canonical_hash(audit)==ptr['final_audit_sha256'],'Warehouse manifest/audit mismatch')
    wa=[x for x in wm['assets'] if x['family']=='ukc' and 2016<=x['year']<=2025];require(len(wa)==10 and {x['year'] for x in wa}==set(range(2016,2026)),'UKC year coverage')
    for x in wa:
        f=INPUT/'warehouse/ukc'/Path(x['relative_path']).name;require(f.stat().st_size==x['size_bytes'] and sha(f)==x['sha256'],'UKC partition mismatch')
    for n,h in PEDIGREE_SHAS.items():require(sha(INPUT/'pedigree'/n)==h,'Pedigree asset SHA mismatch')
    # No accidental extra files included by glob.
    require(set((INPUT/'objects/fact_entry_result_lite').rglob('*.parquet'))=={INPUT/x['relative_path'] for x in parts},'unexpected Analysis files')
    require(set((INPUT/'warehouse/ukc').glob('*.parquet'))=={INPUT/'warehouse/ukc'/Path(x['relative_path']).name for x in wa},'unexpected UKC files')
    return parts,wa

def attach(c, name, path):c.execute(f'CREATE VIEW "{name}" AS SELECT * FROM read_parquet({sql_literal(parquet_glob(path))}, hive_partitioning=true,union_by_name=true)')
def classifier_sql():
    p=ROOT/'brdb_b1_debut_eligibility_audit_v0_2.sql';require(sha(p)==EXPECTED_V02,'B1 classifier SHA mismatch')
    s=p.read_text();marker=', metrics AS (';require(s.count(marker)==1,'classifier boundary mismatch');return s.split(marker)[0]+' SELECT * FROM classified'
def rows(c,sql):
    cur=c.execute(sql);keys=[x[0] for x in cur.description];return [dict(zip(keys,r)) for r in cur.fetchall()]
def main(INPUT,output):
    INPUT=INPUT.resolve();output=output.resolve();require(not output.is_relative_to(INPUT),'output must be separate from input');output.mkdir(parents=True,exist_ok=True)
    dep=dependency_report();require(dep['status']=='success','dependency check');parts,wa=verify_input(INPUT)
    c=connect_parquet(INPUT/'objects/fact_entry_result_lite');attach(c,'dated_ukc',INPUT/'warehouse/ukc');attach(c,'pedigree_master',INPUT/'pedigree/pedigree_fact.parquet');attach(c,'parent_master',INPUT/'pedigree/parent_relation.parquet')
    require(c.execute('SELECT count(*)=count(DISTINCT (horse_id,data_date_iso)) AND count(*) FILTER(WHERE data_date_iso IS NULL OR data_date_iso IS DISTINCT FROM source_member_date)=0 FROM dated_ukc').fetchone()[0],'UKC duplicate/date error')
    require(c.execute('SELECT count(*)=count(DISTINCT horse_id) FROM pedigree_master').fetchone()[0],'pedigree duplicate')
    require(c.execute('SELECT count(*)=count(DISTINCT (child_horse_id,role)) FROM parent_master').fetchone()[0],'relation duplicate')
    archive_rows=c.execute('SELECT DISTINCT CAST(substr(data_date_iso,1,4) AS INTEGER),source_archive_sha256 FROM dated_ukc').fetchall();require(len(archive_rows)==10 and dict(archive_rows)==UKC_SHAS,'UKC raw archive SHA mismatch')
    c.execute('CREATE TEMP TABLE classified AS '+classifier_sql()); require(c.execute('SELECT count(*)=481627 AND count(*)=count(DISTINCT (race_key,horse_no)) FROM classified').fetchone()[0],'B1 cohort mismatch')
    c.execute('CREATE TEMP TABLE joined AS '+(ROOT/'brdb_b1_pedigree_join_v0_1.sql').read_text()); require(c.execute('SELECT count(*)=481627 AND count(*)=count(DISTINCT (race_key,horse_no)) AND count(*) FILTER(WHERE ukc_date>race_date)=0 FROM joined').fetchone()[0],'join cardinality/future violation')
    # Audit full population and candidate subsets independently. Never sum them.
    metrics=rows(c,"""WITH cohorts AS (SELECT 'ALL_ENTRIES' AS cohort,* FROM joined UNION ALL SELECT 'A1_ENTRIES',* FROM joined WHERE race_condition_code='A1' UNION ALL SELECT 'A1_ACTUAL_STARTERS',* FROM joined WHERE race_condition_code='A1' AND start_status IN ('STARTED_NORMAL','STARTED_ABNORMAL') UNION ALL SELECT 'FIRST_CANDIDATE',* FROM joined WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' UNION ALL SELECT 'FIRST_A1_CANDIDATE',* FROM joined WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' AND race_condition_code='A1') SELECT cohort,count(*) AS entries,count(*) FILTER(WHERE ukc_date=race_date) AS same_day,count(*) FILTER(WHERE ukc_date<race_date) AS prior_day,count(*) FILTER(WHERE ukc_date IS NULL) AS missing_ukc,count(*) FILTER(WHERE child_master_present) AS child_master,count(*) FILTER(WHERE sire_id IS NOT NULL) AS sire_id,count(*) FILTER(WHERE bms_id IS NOT NULL) AS bms_id,count(*) FILTER(WHERE sire_id IS NOT NULL AND bms_id IS NOT NULL) AS both_ids,count(*) FILTER(WHERE ukc_date IS NOT NULL AND (sire_name IS DISTINCT FROM dated_sire OR broodmare_sire_name IS DISTINCT FROM dated_bms OR sire_line_code IS DISTINCT FROM dated_sire_line OR broodmare_sire_line_code IS DISTINCT FROM dated_bms_line)) AS analysis_dated_fact_diff FROM cohorts GROUP BY 1 ORDER BY 1""")
    statuses=rows(c,"""WITH co AS (SELECT 'A1_ENTRIES' AS cohort,* FROM joined WHERE race_condition_code='A1' UNION ALL SELECT 'FIRST_CANDIDATE',* FROM joined WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE') SELECT cohort,lane,status,count(*) AS entries FROM co CROSS JOIN LATERAL(VALUES ('SIRE',sire_join_status),('BMS',bms_join_status)) t(lane,status) GROUP BY 1,2,3 ORDER BY 1,2,3""")
    annual=rows(c,"""SELECT year,count(*) AS first_candidates,count(*) FILTER(WHERE ukc_date IS NULL) AS missing_ukc,count(*) FILTER(WHERE sire_id IS NOT NULL) AS sire_id,count(*) FILTER(WHERE bms_id IS NOT NULL) AS bms_id FROM joined WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' GROUP BY 1 ORDER BY 1""")
    symbols=rows(c,"""SELECT coalesce(ukc_symbol,'MISSING') AS symbol,count(*) AS entries FROM joined WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' GROUP BY 1 ORDER BY 1""")
    c.execute('CREATE TEMP TABLE cutoff(as_of_date VARCHAR)');b2sql=(ROOT/'brdb_b2_sire_debut_statistics_v0_1.sql').read_text();b2=[]
    for date in ('2025-01-01','2026-01-01'):
        c.execute('DELETE FROM cutoff');c.execute('INSERT INTO cutoff VALUES (?)',[date]);c.execute('CREATE OR REPLACE TEMP TABLE stats AS '+b2sql)
        require(c.execute('SELECT count(*) FILTER(WHERE max_history_date>=(SELECT as_of_date FROM cutoff) OR wins>top3 OR top3>starts OR starts>resolved_starts OR resolved_starts>baseline_starts OR horses>starts OR prediction_safe OR production_authorized)=0 FROM stats').fetchone()[0],'B2 date/count guard')
        require(c.execute('SELECT count(*)=count(DISTINCT (cohort,scope,dimension,sire_id)) FROM stats').fetchone()[0],'B2 duplicate group')
        require(c.execute('SELECT count(*) FROM (SELECT cohort,scope,dimension FROM stats GROUP BY 1,2,3 HAVING sum(starts)<>max(resolved_starts) OR sum(wins)<>max(resolved_wins) OR sum(top3)<>max(resolved_top3))').fetchone()[0]==0,'B2 baseline reconciliation')
        f=output/('PRIVATE_b2_sire_stats_'+date+'.csv');ordered='SELECT * FROM stats ORDER BY cohort,scope,dimension,sire_id';cur=c.execute(ordered)
        with f.open('w',encoding='utf-8',newline='') as out:
            w=csv.writer(out,lineterminator='\n');w.writerow([x[0] for x in cur.description]);w.writerows(cur.fetchall())
        # Re-run exact SQL and compare all rows, not just aggregates.
        first=c.execute(ordered).fetchall();c.execute('CREATE OR REPLACE TEMP TABLE stats AS '+b2sql);require(first==c.execute(ordered).fetchall(),'B2 deterministic replay mismatch')
        summary=rows(c,"""SELECT cohort,scope,count(*) AS groups,count(*) FILTER(WHERE sample_status='LOW_SAMPLE') AS low_sample_groups,count(DISTINCT sire_id) AS sires,sum(starts) AS starts FROM stats GROUP BY 1,2 ORDER BY 1,2""")
        baselines=rows(c,"""SELECT DISTINCT cohort,baseline_starts,baseline_horses,baseline_wins,baseline_top3,resolved_starts,resolved_wins,resolved_top3 FROM stats WHERE scope='ALL' ORDER BY 1""")
        b2.append(dict(cutoff=date,private_csv_sha256=sha(f),groups=len(first),summary=summary,baselines=baselines,deterministic=True))
    result=dict(status='RESEARCH_ONLY',prediction_safe=False,production_authorized=False,dependency_report=dep,analysis_sha=ANALYSIS_SHA,warehouse_sha=WAREHOUSE_SHA,pedigree_shas=PEDIGREE_SHAS,classification_sha=EXPECTED_V02,join_sha=sha(ROOT/'brdb_b1_pedigree_join_v0_1.sql'),b2_sql_sha=sha(ROOT/'brdb_b2_sire_debut_statistics_v0_1.sql'),metrics=metrics,statuses=statuses,annual=annual,symbols=symbols,b2=b2)
    (output/'b1_b2_receipt.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input-root',required=True,type=Path);parser.add_argument('--output-dir',required=True,type=Path);args=parser.parse_args();main(args.input_root,args.output_dir)
