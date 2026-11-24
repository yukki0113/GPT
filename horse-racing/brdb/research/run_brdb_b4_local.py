"""B4 read-only historical relatives research. Private detailed outputs only."""
from pathlib import Path
import argparse,csv,gzip,io,json
from run_brdb_b3_local import setup,cohort_sql,B2_ROOT
from run_brdb_b1_b2_local import require,rows,sha,ANALYSIS_SHA,WAREHOUSE_SHA,PEDIGREE_SHAS,UKC_SHAS
from data_storage.dependencies import dependency_report
ROOT=Path(__file__).resolve().parent
PARENT='95f34adba1b4f3f9f85bfe946a88060202564e71'
EXPECTED_B3='d0cf57fc967a1ab98436a339ca10cc32c97bcbbfd2e202724fe6e67005d866b6'

def build(c):
    for name in ('brdb_b4_relative_paths_v0_1.sql','brdb_b4_relative_early_results_v0_1.sql'):
        c.execute((ROOT/name).read_text())

def export(c,q,path):
    cur=c.execute(q)
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding='utf-8',newline='') as f:
                w=csv.writer(f,lineterminator='\n');w.writerow([x[0] for x in cur.description])
                while batch:=cur.fetchmany(10000):w.writerows(batch)
    return sha(path)

def audit(c):
    require(c.execute('SELECT count(*)=count(DISTINCT (race_key,horse_no)) FROM targets').fetchone()[0],'target identity')
    require(c.execute('SELECT count(*)=(SELECT count(*) FROM targets) AND count(*)=count(DISTINCT (race_key,horse_no)) FROM family_targets').fetchone()[0],'target join cardinality')
    require(c.execute('SELECT count(*)=count(DISTINCT (race_key,horse_no,relative_id,path)) FROM relative_paths').fetchone()[0],'path duplicate')
    require(c.execute('''SELECT count(*)=0 FROM relative_paths WHERE path_status='RESOLVED' AND
      (horse_id=relative_id OR relative_p.birth_date>=target_p.birth_date OR relative_p.observed_date>race_date OR shared_parent_p.observed_date>race_date OR target_p.observed_date>race_date OR relative_sire_p.observed_date>race_date)''').fetchone()[0],'relative date/identity violation')
    require(c.execute('''SELECT count(*)=0 FROM family_targets WHERE (dam_status='RESOLVED' AND (dam_p.observed_date>race_date OR target_p.observed_date>race_date)) OR (granddam_status='RESOLVED' AND granddam_p.observed_date>race_date)''').fetchone()[0],'ancestor date violation')
    require(c.execute('SELECT count(*)=count(DISTINCT (race_key,horse_no,relative_id,scope)) AND count(*)=5*(SELECT count(*) FROM relative_pairs) FROM relative_stats').fetchone()[0],'scope duplicate or missing')
    require(c.execute('''SELECT count(*)=0 FROM relative_stats WHERE max_history_date>=race_date OR first_date>=race_date OR first_observed_date>=race_date OR early_starts>3 OR first_starts>1 OR first_wins>first_top3 OR first_top3>first_starts OR early_wins>early_top3 OR early_top3>early_starts OR first_starts>early_starts OR prediction_safe OR production_authorized OR (early_starts=0 AND early_top3_rate IS NOT NULL) OR (history_status<>'FIRST_OBSERVED_CANDIDATE' AND early_starts<>0)''').fetchone()[0],'history bounds')
    require(c.execute("SELECT count(*)=0 FROM relative_stats WHERE scope='ALL' AND history_status='FIRST_OBSERVED_CANDIDATE' AND first_starts<>1").fetchone()[0],'candidate first missing')
    c.execute('''CREATE TEMP TABLE target_coverage AS WITH p AS (
      SELECT race_key,horse_no,count(*) AS path_candidates,count(*) FILTER(WHERE path_status='RESOLVED') AS accepted_paths FROM relative_paths GROUP BY 1,2), h AS (
      SELECT race_key,horse_no,count(*) AS relative_count,sum(path_count)-count(*) AS overlapping_paths,
        count(*) FILTER(WHERE history_status='FIRST_OBSERVED_CANDIDATE') AS first_candidate_relatives,
        count(*) FILTER(WHERE history_status='FIRST_START_UNRESOLVED') AS unresolved_first_relatives,
        count(*) FILTER(WHERE history_status='NO_PRIOR_OBSERVED_START') AS no_prior_relatives,
        count(*) FILTER(WHERE early_starts=3) AS complete_early_relatives
      FROM relative_stats WHERE scope='ALL' GROUP BY 1,2)
      SELECT t.race_key,t.horse_no,t.horse_id,t.race_date,t.dam_status,t.granddam_status,
        CASE WHEN t.dam_status='RESOLVED' THEN t.dam_candidate END AS dam_id,
        t.target_p.observed_date AS target_profile_date,
        CASE WHEN t.dam_status='RESOLVED' THEN t.dam_p.observed_date END AS dam_profile_date,
        CASE WHEN t.granddam_status='RESOLVED' THEN t.granddam_p.observed_date END AS granddam_profile_date,
        CASE WHEN t.granddam_status='RESOLVED' THEN t.granddam_candidate END AS granddam_id,
        coalesce(p.path_candidates,0) AS path_candidates,coalesce(p.accepted_paths,0) AS accepted_paths,
        coalesce(h.relative_count,0) AS relative_count,coalesce(h.overlapping_paths,0) AS overlapping_paths,
        coalesce(h.first_candidate_relatives,0) AS first_candidate_relatives,
        coalesce(h.unresolved_first_relatives,0) AS unresolved_first_relatives,
        coalesce(h.no_prior_relatives,0) AS no_prior_relatives,coalesce(h.complete_early_relatives,0) AS complete_early_relatives,
        CASE WHEN t.dam_status<>'RESOLVED' THEN 'SOURCE_UNAVAILABLE' WHEN coalesce(h.relative_count,0)=0 THEN 'NO_CONFIRMED_RELATIVE'
        WHEN coalesce(h.first_candidate_relatives,0)=0 THEN 'NO_ELIGIBLE_FIRST_HISTORY' ELSE 'DESCRIPTIVE_FIRST_HISTORY' END AS status,
        'STATIC_RELATION_AS_OF_UNVERIFIED' AS parent_temporal_status,false AS prediction_safe,false AS production_authorized
      FROM family_targets t LEFT JOIN p USING(race_key,horse_no) LEFT JOIN h USING(race_key,horse_no)''')
    require(c.execute('SELECT count(*)=(SELECT count(*) FROM targets) AND count(*)=count(DISTINCT (race_key,horse_no)) FROM target_coverage').fetchone()[0],'coverage loss')
    require(c.execute('SELECT count(*)=0 FROM target_coverage WHERE relative_count<>first_candidate_relatives+unresolved_first_relatives+no_prior_relatives OR accepted_paths<>relative_count+overlapping_paths').fetchone()[0],'coverage reconciliation')
    return dict(targets=rows(c,'''SELECT cohort,count(*) AS targets,count(*) FILTER(WHERE dam_status='RESOLVED') AS dam_resolved,count(*) FILTER(WHERE granddam_status='RESOLVED') AS granddam_resolved,count(*) FILTER(WHERE relative_count>0) AS with_relatives,count(*) FILTER(WHERE first_candidate_relatives>0) AS with_first_history,count(*) FILTER(WHERE complete_early_relatives>0) AS with_three_early,sum(relative_count)::BIGINT AS pairs,sum(overlapping_paths)::BIGINT AS overlapping_paths,sum(first_candidate_relatives)::BIGINT AS first_pairs,sum(unresolved_first_relatives)::BIGINT AS unresolved_first_pairs,sum(no_prior_relatives)::BIGINT AS no_prior_pairs,sum(complete_early_relatives)::BIGINT AS complete_early_pairs FROM cohort JOIN target_coverage USING(race_key,horse_no,horse_id,race_date) GROUP BY 1 ORDER BY 1'''),
      target_status=rows(c,'SELECT dam_status,granddam_status,status,count(*) AS targets FROM target_coverage GROUP BY ALL ORDER BY ALL'),
      paths=rows(c,'SELECT path,path_status,count(*) AS paths FROM relative_paths GROUP BY ALL ORDER BY ALL'),
      relationships=rows(c,"SELECT relationship,count(*) AS paths,count(DISTINCT relative_id) AS unique_relatives FROM relative_paths WHERE path_status='RESOLVED' GROUP BY ALL ORDER BY ALL"),
      history=rows(c,"SELECT history_status,count(*) AS pairs,count(DISTINCT relative_id) AS unique_relatives FROM pair_history GROUP BY ALL ORDER BY ALL"),
      scopes=rows(c,"SELECT scope,count(*) AS cells,count(*) FILTER(WHERE first_starts>0) AS first_cells,count(*) FILTER(WHERE early_starts>0) AS early_cells,count(*) FILTER(WHERE early_starts=3) AS three_early_cells,count(*) FILTER(WHERE sample_status='NO_SAMPLE') AS no_sample_cells FROM relative_stats GROUP BY ALL ORDER BY ALL"),
      distinct=rows(c,"SELECT count(*) AS pairs,count(DISTINCT relative_id) AS unique_relatives,sum(path_count)::BIGINT AS accepted_paths,sum(path_count)-count(*) AS overlapping_paths FROM relative_pairs"),
      excluded_alias_edges=rows(c,"SELECT role,count(*) AS edges FROM parent_master WHERE resolution_status='RESOLVED_ALIAS' GROUP BY ALL ORDER BY ALL"))

def run(input_root,out):
    import run_brdb_b3_local as b3
    require(sha(Path(b3.__file__))==EXPECTED_B3,'B3 source mismatch')
    input_root=input_root.resolve();out=out.resolve();require(not out.is_relative_to(input_root),'output inside input');out.mkdir(parents=True,exist_ok=True)
    c=setup(input_root)
    c.execute("INSERT INTO cutoff VALUES ('2026-01-01')")
    c.execute('CREATE TEMP TABLE cohort AS '+cohort_sql((B2_ROOT/'brdb_b2_sire_debut_statistics_v0_1.sql').read_text()))
    require(c.execute('SELECT count(*) FROM cohort').fetchone()[0]==78184,'B2 cohort count')
    require(c.execute("SELECT count(*) FILTER(WHERE start_status='UNKNOWN')=0 AND count(*)=count(DISTINCT (horse_id,race_date)) FROM classified").fetchone()[0],'actual-start chronology uncertainty')
    build(c);report=audit(c)
    files={}
    for name,q in [('PRIVATE_b4_target_coverage.csv.gz',"SELECT t.*,f.cohorts FROM target_coverage t JOIN (SELECT race_key,horse_no,list(cohort ORDER BY cohort) AS cohorts FROM cohort GROUP BY 1,2) f USING(race_key,horse_no) ORDER BY race_key,horse_no"),('PRIVATE_b4_relative_paths.csv.gz','SELECT race_key,horse_no,horse_id,race_date,relative_id,path,path_status,relationship,relative_p.observed_date AS relative_profile_date,relative_p.birth_date AS relative_birth_date,shared_parent_p.horse_id AS shared_parent_id,shared_parent_p.observed_date AS shared_parent_profile_date FROM relative_paths ORDER BY race_key,horse_no,relative_id,path'),('PRIVATE_b4_relative_stats.csv.gz','SELECT * FROM relative_stats ORDER BY race_key,horse_no,relative_id,scope')]:
        files[name]=export(c,q,out/name)
    receipt=dict(status='PASS_RESEARCH_ONLY',prediction_safe=False,production_authorized=False,source_base_commit=PARENT,main_observed='151ccbf2c2a40f1d3f0ffa0c3e6e2f4ff21b4efe',analysis_sha=ANALYSIS_SHA,warehouse_sha=WAREHOUSE_SHA,pedigree_shas=PEDIGREE_SHAS,ukc_archive_shas=UKC_SHAS,source_sha256={p.name:sha(p) for p in ROOT.iterdir() if p.suffix in ('.sql','.py')},dependency_report=dependency_report(),cutoff='2026-01-01',inputs_verified_by='B3.setup/B1.verify_input',report=report,output_sha256=files)
    (out/'b4_receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2,ensure_ascii=False)+'\n');c.close();print(json.dumps(report,ensure_ascii=False,default=str))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();run(a.input_root,a.output_dir)
