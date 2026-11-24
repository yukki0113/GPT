"""Private deterministic B3 research; reuse B1/B2 exact inputs and cohort SQL."""
from pathlib import Path
import argparse,csv,json,hashlib
from run_brdb_b1_b2_local import (verify_input, attach, classifier_sql, require, rows, sha, ROOT as B2_ROOT, UKC_SHAS, ANALYSIS_SHA, WAREHOUSE_SHA, PEDIGREE_SHAS)
from data_storage.query import connect_parquet
from data_storage.dependencies import dependency_report
ROOT=Path(__file__).resolve().parent
BASE_SHA={'run_brdb_b1_b2_local.py':'310aadcec58596383ee93d676776884699c1ae6a6e8fad96e375a250e37789ed','brdb_b1_pedigree_join_v0_1.sql':'624226d5d330eed4026cc88a955fe59d30bdaba883c9844c569437ffe51ff21a','brdb_b2_sire_debut_statistics_v0_1.sql':'a98f85b2d1beba81bc7a78a2e73015da0b3cb0b67c9f99c954554efcc7cffac8'}
LINEAGE_SHA='6263f4b239e9018e03fe6ce8333ba843b05c2eac32470369368e7be0fe7bd54b'
BASELINE_CSV={'2025-01-01':'59fa2cafd01e9d5af9dc2c7faca36095b5165d1e82c558e0c4170c76ad9920df','2026-01-01':'9c996773da635c30e82d81435319bcaa6bd20a28e32c0919aec33769c6e39c39'}

def setup(input_root):
    for name,h in BASE_SHA.items(): require(sha(B2_ROOT/name)==h,'B2 source mismatch '+name)
    require(dependency_report()['status']=='success','dependency check')
    verify_input(input_root)
    require(sha(input_root/'pedigree/lineage_code_master.parquet')==LINEAGE_SHA,'lineage master SHA mismatch')
    c=connect_parquet(input_root/'objects/fact_entry_result_lite')
    for name,path in [('dated_ukc','warehouse/ukc'),('pedigree_master','pedigree/pedigree_fact.parquet'),('parent_master','pedigree/parent_relation.parquet'),('lineage_master','pedigree/lineage_code_master.parquet')]:attach(c,name,input_root/path)
    for table,key in [('dated_ukc','(horse_id,data_date_iso)'),('pedigree_master','horse_id'),('parent_master','(child_horse_id,role)'),('lineage_master','lineage_code')]:
        require(c.execute(f'SELECT count(*)=count(DISTINCT {key}) FROM {table}').fetchone()[0],table+' duplicate')
    require(c.execute('SELECT count(*) FILTER(WHERE data_date_iso IS NULL OR data_date_iso IS DISTINCT FROM source_member_date)=0 FROM dated_ukc').fetchone()[0],'UKC date')
    archive_rows=c.execute('SELECT DISTINCT CAST(substr(data_date_iso,1,4) AS INTEGER),source_archive_sha256 FROM dated_ukc').fetchall(); require(len(archive_rows)==10 and dict(archive_rows)==UKC_SHAS,'UKC raw archive SHA')
    c.execute('CREATE TEMP TABLE classified AS '+classifier_sql())
    c.execute('CREATE TEMP TABLE joined AS '+(B2_ROOT/'brdb_b1_pedigree_join_v0_1.sql').read_text())
    require(c.execute('SELECT count(*)=481627 AND count(*)=count(DISTINCT (race_key,horse_no)) AND count(*) FILTER(WHERE ukc_date>race_date)=0 FROM joined').fetchone()[0],'B1 join integrity')
    c.execute('CREATE TEMP TABLE cutoff(as_of_date VARCHAR)')
    return c

def cohort_sql(b2):
    marker=', facts AS (';require(b2.count(marker)==1,'B2 cohort boundary');return b2.split(marker)[0]+' SELECT * FROM cohort'

def csv_write(c,query,path):
    cur=c.execute(query)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow([x[0] for x in cur.description]);w.writerows(cur.fetchall())
    return sha(path)

def validate(c,cutoff):
    require(c.execute('SELECT count(*)=count(DISTINCT (cohort,scope,dimension,lane,key1,key2)) FROM stats').fetchone()[0],'duplicate group')
    require(c.execute('''SELECT count(*)=0 FROM stats WHERE max_history_date>=? OR wins>top3 OR top3>starts OR starts>resolved_starts OR resolved_starts>baseline_starts OR horses>starts OR prediction_safe OR production_authorized OR (starts=0 AND (top3_rate IS NOT NULL OR sample_status<>'NO_RESOLVED_GROUP')) OR (starts>0 AND (key1 IS NULL OR key2 IS NULL)) OR (lane IN ('PARENT_ID_PAIR','LINEAGE_CODE_PAIR') AND starts>0 AND (left_marginal_starts IS NULL OR right_marginal_starts IS NULL OR left_marginal_starts<starts OR right_marginal_starts<starts OR left_marginal_top3<top3 OR right_marginal_top3<top3))''',[cutoff]).fetchone()[0],'date/count/marginal guard')
    require(c.execute('''SELECT count(*)=0 FROM (SELECT cohort,scope,dimension,lane FROM stats GROUP BY 1,2,3,4 HAVING sum(starts)<>max(resolved_starts) OR sum(wins)<>max(resolved_wins) OR sum(top3)<>max(resolved_top3))''').fetchone()[0],'baseline reconciliation')

def run(input_root,output):
    input_root=input_root.resolve();output=output.resolve();require(not output.is_relative_to(input_root),'output inside input');output.mkdir(parents=True,exist_ok=True)
    c=setup(input_root);b2=(B2_ROOT/'brdb_b2_sire_debut_statistics_v0_1.sql').read_text();sql=(ROOT/'brdb_b3_debut_statistics_v0_1.sql').read_text();summaries=[]
    for cutoff in BASELINE_CSV:
        c.execute('DELETE FROM cutoff');c.execute('INSERT INTO cutoff VALUES (?)',[cutoff]);c.execute('CREATE OR REPLACE TEMP TABLE cohort AS '+cohort_sql(b2));c.execute('CREATE OR REPLACE TEMP TABLE stats AS '+sql);validate(c,cutoff)
        # Exact B2 snapshot hash verifies the existing sire contract has not drifted.
        p=output/'_b2_regression.csv';actual=csv_write(c,b2,p);p.unlink();require(actual==BASELINE_CSV[cutoff],'B2 byte regression')
        c.execute('CREATE OR REPLACE TEMP TABLE b2_stats AS '+b2)
        cols='cohort,scope,dimension,starts,horses,races,wins,top3,normal_finishers,max_history_date,baseline_starts,baseline_horses,baseline_wins,baseline_top3,resolved_starts,resolved_wins,resolved_top3'
        a=f'SELECT {cols},key1 AS sire_id FROM stats WHERE lane=\'SIRE_ID\' AND starts>0';b=f'SELECT {cols},sire_id FROM b2_stats'
        require(c.execute(f'SELECT count(*)=0 FROM (({a} EXCEPT ALL {b}) UNION ALL ({b} EXCEPT ALL {a}))').fetchone()[0],'sire lane B2 mismatch')
        ordered='SELECT * FROM stats ORDER BY cohort,scope,dimension,lane,key1,key2';p=output/f'PRIVATE_b3_stats_{cutoff}.csv';h=csv_write(c,ordered,p)
        c.execute('CREATE OR REPLACE TEMP TABLE stats AS '+sql);validate(c,cutoff);repeat=output/'_repeat.csv';require(csv_write(c,ordered,repeat)==h,'deterministic replay');repeat.unlink()
        summary=rows(c,"""SELECT cohort,lane,scope,count(*) FILTER(WHERE starts>0) AS groups,count(*) FILTER(WHERE sample_status='LOW_SAMPLE') AS low_n,count(*) FILTER(WHERE sample_status='NO_RESOLVED_GROUP') AS no_resolved_cells,sum(starts)::BIGINT AS resolved_starts,sum(top3)::BIGINT AS resolved_top3 FROM stats GROUP BY 1,2,3 ORDER BY 1,2,3""")
        overall=rows(c,"""SELECT DISTINCT cohort,lane,baseline_starts,baseline_wins,baseline_top3,resolved_starts,resolved_wins,resolved_top3 FROM stats WHERE scope='ALL' ORDER BY 1,2""")
        overlap=rows(c,"""SELECT cohort,count(*) AS entries,count(*) FILTER(WHERE sire_id IS NOT NULL AND bms_id IS NOT NULL) both_ids,count(*) FILTER(WHERE sire_id IS NOT NULL AND bms_id IS NULL) sire_only,count(*) FILTER(WHERE sire_id IS NULL AND bms_id IS NOT NULL) bms_only,count(*) FILTER(WHERE sire_id IS NULL AND bms_id IS NULL) neither,count(*) FILTER(WHERE ukc_date IS NULL) missing_ukc FROM cohort GROUP BY 1 ORDER BY 1""")
        summaries.append(dict(cutoff=cutoff,private_csv_sha256=h,summary=summary,overall=overall,overlap=overlap,b2_replay_sha256=actual,deterministic=True))
    receipt=dict(status='PASS_RESEARCH_ONLY',prediction_safe=False,production_authorized=False,analysis_sha=ANALYSIS_SHA,warehouse_sha=WAREHOUSE_SHA,pedigree_shas=PEDIGREE_SHAS,lineage_sha=LINEAGE_SHA,source_base_commit='45cb0fc15d55c96cc9195a6ad7bbefa08686a07f',source_sha256={p.name:sha(p) for p in (ROOT/'brdb_b3_debut_statistics_v0_1.sql',ROOT/'run_brdb_b3_local.py')},dependency_report=dependency_report(),snapshots=summaries)
    (output/'b3_receipt.json').write_text(json.dumps(receipt,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
    c.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();run(a.input_root,a.output_dir)
