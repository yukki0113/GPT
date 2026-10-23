#!/usr/bin/env python3
"""Two-year-old OP+ Yokoyama Norihiro by distance (2021-2026): common DuckDB storage."""
import argparse,csv,hashlib,json,tarfile,tempfile
from pathlib import Path
import duckdb
GEN="analysis-v1_4-postrace-20261018-01"
def main():
 p=argparse.ArgumentParser();p.add_argument("--archive",required=True);p.add_argument("--output",required=True);a=p.parse_args()
 out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp)
  with tarfile.open(a.archive,"r:xz") as tf:
   for m in tf.getmembers():
    z=Path(m.name)
    if z.is_absolute() or ".." in z.parts or not(m.isfile() or m.isdir()):raise ValueError("Unsafe tar")
   tf.extractall(root,filter="data")
  pointer=json.loads((root/"current.json").read_text())
  mf=json.loads((root/pointer["manifest"]).read_text())
  if pointer["generation_id"]!=GEN or mf["generation_id"]!=GEN or mf["validation_status"]!="PASS":raise ValueError("Generation mismatch")
  parts=[x for x in mf["fact_table"]["partitions"] if 2021<=int(x["year"])<=2026]
  if len(parts)!=6:raise ValueError("Partition count mismatch")
  files=[]
  for x in parts:
   f=root/x["relative_path"]
   if f.stat().st_size!=x["size_bytes"] or hashlib.sha256(f.read_bytes()).hexdigest()!=x["sha256"]:raise ValueError("SHA mismatch")
   files.append(str(f))
  db=duckdb.connect();db.from_parquet(files).create_view("data")
  db.execute("""CREATE VIEW eligible AS SELECT *,
    CASE WHEN distance BETWEEN 1200 AND 1400 THEN '1200-1400'
         WHEN distance BETWEEN 1600 AND 1800 THEN '1600-1800'
         WHEN distance>=2000 THEN '2000+'
         ELSE 'その他' END AS distance_band
    FROM data WHERE age=2 AND TRIM(REPLACE(COALESCE(jockey_name,''),'　',''))='横山典弘'
      AND UPPER(TRIM(CAST(race_condition_code AS VARCHAR)))='OP'""")
  sql="""SELECT distance_band,COUNT(*) AS entries,
    COUNT(*) FILTER(WHERE COALESCE(CAST(abnormal_code AS VARCHAR),'0') NOT IN ('1','2')) AS starts,
    COUNT(*) FILTER(WHERE finish=1) AS wins,
    COUNT(*) FILTER(WHERE finish=2) AS seconds,
    COUNT(*) FILTER(WHERE finish=3) AS thirds,
    COUNT(*) FILTER(WHERE finish>3 AND COALESCE(CAST(abnormal_code AS VARCHAR),'0') NOT IN ('1','2')) AS others,
    ROUND(100.0*COUNT(*) FILTER(WHERE finish=1)/NULLIF(COUNT(*) FILTER(WHERE COALESCE(CAST(abnormal_code AS VARCHAR),'0') NOT IN ('1','2')),0),2) AS win_pct,
    ROUND(100.0*COUNT(*) FILTER(WHERE finish IN (1,2))/NULLIF(COUNT(*) FILTER(WHERE COALESCE(CAST(abnormal_code AS VARCHAR),'0') NOT IN ('1','2')),0),2) AS top2_pct,
    ROUND(100.0*COUNT(*) FILTER(WHERE finish IN (1,2,3))/NULLIF(COUNT(*) FILTER(WHERE COALESCE(CAST(abnormal_code AS VARCHAR),'0') NOT IN ('1','2')),0),2) AS top3_pct,
    SUM(COALESCE(win_payout,0)) AS win_payout_total,
    SUM(COALESCE(place_payout,0)) AS place_payout_total,
    ROUND(SUM(COALESCE(win_payout,0))*1.0/NULLIF(COUNT(*) FILTER(WHERE COALESCE(CAST(abnormal_code AS VARCHAR),'0') NOT IN ('1','2')),0),2) AS win_return_pct,
    ROUND(SUM(COALESCE(place_payout,0))*1.0/NULLIF(COUNT(*) FILTER(WHERE COALESCE(CAST(abnormal_code AS VARCHAR),'0') NOT IN ('1','2')),0),2) AS place_return_pct
   FROM eligible GROUP BY distance_band ORDER BY distance_band"""
  cur=db.execute(sql);rows=cur.fetchall();head=[x[0] for x in cur.description]
  with (out/"distance_summary.csv").open("w",encoding="utf-8-sig",newline="") as f:
   w=csv.writer(f);w.writerow(head);w.writerows(rows)
  cur=db.execute("""SELECT race_date,race_name,distance,track_type,race_condition_code,grade_code,jockey_name,horse_name,finish,abnormal_code,win_payout,place_payout,final_win_odds,final_win_popularity,distance_band
   FROM eligible ORDER BY race_date,distance,race_no""")
  with (out/"eligible_races.csv").open("w",encoding="utf-8-sig",newline="") as f:
   w=csv.writer(f);w.writerow([x[0] for x in cur.description]);w.writerows(cur.fetchall())
  codes=db.execute("""SELECT race_condition_code,grade_code,COUNT(*) FROM data WHERE age=2 AND REPLACE(COALESCE(jockey_name,''),'　','')='横山典弘' GROUP BY 1,2 ORDER BY 1,2""").fetchall()
  audit=dict(generation=GEN,period="2021-01-01 to 2026-10-18",filter="age=2, jockey_name=横山典弘, race_condition_code=OP",grade_codes_all=codes,eligible_records=db.execute("SELECT COUNT(*) FROM eligible").fetchone()[0],rows=rows,duckdb=duckdb.__version__)
  (out/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
