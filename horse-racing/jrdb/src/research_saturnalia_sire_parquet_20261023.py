#!/usr/bin/env python3
"""Reproducible sire analysis of verified JRDB Analysis v1.4; DuckDB from common data-storage requirements."""
import argparse,csv,hashlib,json,tarfile,tempfile
from pathlib import Path
import duckdb
EXPECTED="analysis-v1_4-postrace-20261018-01"
def main():
 p=argparse.ArgumentParser();p.add_argument("--archive",required=True);p.add_argument("--output",required=True);a=p.parse_args()
 out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp)
  with tarfile.open(a.archive,"r:xz") as tf:
   for m in tf.getmembers():
    path=Path(m.name)
    if path.is_absolute() or ".." in path.parts or not (m.isfile() or m.isdir()):raise ValueError("Unsafe archive member")
   tf.extractall(root,filter="data")
  pointer=json.loads((root/"current.json").read_text())
  if pointer["generation_id"]!=EXPECTED:raise ValueError("current generation mismatch")
  mf=json.loads((root/pointer["manifest"]).read_text())
  if mf["generation_id"]!=EXPECTED or mf["validation_status"]!="PASS":raise ValueError("Unvalidated manifest")
  partitions=[x for x in mf["fact_table"]["partitions"] if 2021<=int(x["year"])<=2026]
  if len(partitions)!=6:raise ValueError("Expected 6 partitions")
  files=[]
  for x in partitions:
   f=root/x["relative_path"]
   if not f.is_file() or f.stat().st_size!=x["size_bytes"] or hashlib.sha256(f.read_bytes()).hexdigest()!=x["sha256"]:raise ValueError("Parquet integrity mismatch: "+str(f))
   files.append(str(f))
  conn=duckdb.connect()
  conn.execute("CREATE VIEW data AS SELECT * FROM read_parquet(?)",[files])
  codes=conn.execute("SELECT track_condition_code,COUNT(*) FROM data GROUP BY 1 ORDER BY 1").fetchall()
  sire_codes=conn.execute("SELECT sire_name,COUNT(*) FROM data WHERE sire_name LIKE '%サートゥルナーリア%' GROUP BY 1").fetchall()
  if not sire_codes:raise ValueError("No sire identified; check source profiles")
  conn.execute("""CREATE VIEW target AS SELECT *,
   CASE WHEN TRIM(CAST(track_condition_code AS VARCHAR)) IN ('1','10','11','12') THEN '良'
   WHEN TRIM(CAST(track_condition_code AS VARCHAR)) IN ('2','20','21','22') THEN '稍重'
   WHEN TRIM(CAST(track_condition_code AS VARCHAR)) IN ('3','30','31','32') THEN '重'
   WHEN TRIM(CAST(track_condition_code AS VARCHAR)) IN ('4','40','41','42') THEN '不良' ELSE '不明' END AS condition,
   CAST(track_type AS VARCHAR) AS surface
   FROM data WHERE REPLACE(REPLACE(COALESCE(sire_name,''),'　',''),' ','')='サートゥルナーリア'""")
  n=conn.execute("SELECT COUNT(*) FROM target").fetchone()[0]
  if not n:raise ValueError("Sire rows missing after normalization")
  for label,group,where in [
   ("overall","'全体'","TRUE"),("by_condition","condition","TRUE"),("age_2","condition","age=2"),
   ("by_age","CAST(age AS VARCHAR)","TRUE"),("surface_condition","surface || '/' || condition","TRUE"),
   ("age_2_surface","surface || '/' || condition","age=2"),
   ("by_distance","CAST(distance AS VARCHAR)","TRUE"),("age_2_distance","CAST(distance AS VARCHAR)","age=2")]:
   sql=f"""SELECT {group} AS segment,COUNT(*) AS entries,COUNT(DISTINCT horse_id) AS horses,
   COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 30) AS finished,
   COUNT(*) FILTER (WHERE finish=1) AS wins,
   COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 2) AS top2,
   COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 3) AS top3,
   ROUND(100.0*COUNT(*) FILTER (WHERE finish=1)/NULLIF(COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 30),0),2) AS win_rate,
   ROUND(100.0*COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 2)/NULLIF(COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 30),0),2) AS quinella_rate,
   ROUND(100.0*COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 3)/NULLIF(COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 30),0),2) AS show_rate,
   ROUND(SUM(COALESCE(win_payout,0))*1.0/NULLIF(COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 30),0),2) AS win_return_percent,
   ROUND(SUM(COALESCE(place_payout,0))*1.0/NULLIF(COUNT(*) FILTER (WHERE finish BETWEEN 1 AND 30),0),2) AS place_return_percent
   FROM target WHERE {where} GROUP BY segment ORDER BY segment"""
   cur=conn.execute(sql);rows=cur.fetchall()
   with (out/(label+".csv")).open("w",encoding="utf-8-sig",newline="") as fp:
    writer=csv.writer(fp);writer.writerow([v[0] for v in cur.description]);writer.writerows(rows)
  (out/"audit.json").write_text(json.dumps(dict(generation=EXPECTED,scope="2021-01-01/2026-10-18",entries=n,codes=codes,sire_samples=sire_codes,duckdb=duckdb.__version__,year_partitions=[x["year"] for x in partitions]),ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
