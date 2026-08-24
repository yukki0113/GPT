#!/usr/bin/env python3
import argparse,json,sqlite3,time,re
from collections import Counter,defaultdict
from pathlib import Path
Y=[2013,2018,2019,2022,2024,2025]
def q(c,s,a=()):return [dict(x) for x in c.execute(s,a)]
def one(c,s,a=()):return c.execute(s,a).fetchone()[0]
def main():
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--json',required=True);p.add_argument('--md',required=True);p.add_argument('--duplicates',required=True);a=p.parse_args();c=sqlite3.connect(a.db);c.row_factory=sqlite3.Row
 counts={x:one(c,f'select count(*) from {x}') for x in ['race','entry','result','training_analysis','workout','result_extension','entry_previous_result','horse_current','horse_history','meta_anomaly','meta_duplicate']};integrity=one(c,'pragma integrity_check')
 bad_dates=q(c,"select business_date,source_kind,detail_json from meta_anomaly where anomaly_type='MISSING_SOURCE_DATE'");invalid=[x for x in bad_dates if not re.fullmatch(r'20(13|18|19|22|24|25)-\d\d-\d\d',x['business_date'] or '')]
 drows=q(c,"select d.*,f1.filename source_file_1,f2.filename source_file_2,a1.year from meta_duplicate d join meta_source_file f1 on f1.source_file_id=d.first_source_file_id join meta_source_file f2 on f2.source_file_id=d.second_source_file_id join meta_archive a1 on a1.archive_id=f1.archive_id where d.is_identical=0")
 patterns=Counter(); detail=[]
 for x in drows:
  dif=json.loads(x['diff_json']);fields=[z['field'] for z in dif['changed_fields']]
  if fields==['race_date']:pat='DATE_ONLY'
  elif any(z in fields for z in ['win_payout','place_payout','finish']):pat='FINAL_OR_PAYOUT'
  elif not fields:pat='UNPARSED_BYTE_ONLY'
  elif any(z in fields for z in ['race_comment']):pat='COMMENT_UPDATE'
  else:pat='OTHER_PARSED_FIELDS'
  patterns[(x['source_kind'],pat,x['resolution'])]+=1;x['difference_pattern']=pat;x['differing_byte_ranges']=dif['byte_ranges_0_based'];x['differing_parsed_fields']=dif['changed_fields'];detail.append(x)
 Path(a.duplicates).write_text(json.dumps(detail,ensure_ascii=False,indent=2),encoding='utf8')
 dup_summary=q(c,"select a.year,d.source_kind,d.resolution,d.is_identical,count(*) count from meta_duplicate d join meta_source_file f on f.source_file_id=d.first_source_file_id join meta_archive a on a.archive_id=f.archive_id group by a.year,d.source_kind,d.resolution,d.is_identical order by a.year,d.source_kind,d.resolution")
 payout=q(c,"select r.year,count(*) records,sum(rs.win_payout>0) win_positive,sum(rs.place_payout>0) place_positive,sum(case when rs.finish=1 and coalesce(rs.win_payout,0)<=0 and coalesce(rs.abnormal_code,'') in('','0') then 1 else 0 end) win_inconsistency from result rs join race r using(race_key) group by r.year order by r.year")
 joins={}
 for y in Y:
  base=one(c,'select count(*) from entry e join race r using(race_key) where r.year=?',(y,));joins[y]={'base':base}
  for lab,tbl,cond in [('race','race','e.race_key=x.race_key'),('result','result','e.race_key=x.race_key and e.horse_no=x.horse_no'),('CYB','training_analysis','e.race_key=x.race_key and e.horse_no=x.horse_no'),('CHA','workout','e.race_key=x.race_key and e.horse_no=x.horse_no'),('SKB','result_extension','e.race_key=x.race_key and e.horse_no=x.horse_no'),('UKC','horse_current','e.horse_id=x.horse_id')]:
   n=one(c,f'select count(*) from entry e join race r using(race_key) join {tbl} x on {cond} where r.year=?',(y,));joins[y][lab]={'matched':n,'rate_pct':round(100*n/base,4) if base else None}
 an=q(c,'select anomaly_type,count(*) event_count,count(record_no) affected_records from meta_anomaly group by anomaly_type')
 fallback=q(c,"select business_date,business_key from meta_anomaly where anomaly_type='BAC_FALLBACK_USED' order by business_date,business_key")
 smoke0=time.perf_counter();smoke=q(c,"select r.venue_code,r.track_type,r.distance,e.jockey_name,count(*) starts,sum(rs.finish=1) wins,sum(rs.finish<=3) top3,sum(coalesce(rs.win_payout,0)) win_payout_sum,sum(coalesce(rs.place_payout,0)) place_payout_sum from entry e join race r using(race_key) join result rs using(race_key,horse_no) group by 1,2,3,4 having count(*)>=20 order by starts desc limit 10");elapsed=round(time.perf_counter()-smoke0,4)
 manual=one(c,"select count(*) from meta_duplicate where resolution='MANUAL_REQUIRED'");auto=one(c,"select count(*) from meta_duplicate where is_identical=0 and resolution<>'MANUAL_REQUIRED'")
 verdict='PASS WITH WARNINGS' if integrity=='ok' and not invalid and all(x['win_inconsistency']==0 for x in payout) and manual<=1120 else 'FAIL'
 out={'version':'1.1.1','verdict':verdict,'integrity_check':integrity,'table_counts':counts,'missing_source_date_events':bad_dates,'invalid_business_date_count':len(invalid),'duplicate_summary_by_year_type_resolution':dup_summary,'duplicate_patterns':[{'source_kind':k[0],'pattern':k[1],'resolution':k[2],'count':v} for k,v in sorted(patterns.items())],'manual_required_before':1120,'manual_required_after':manual,'newly_resolved':1120-manual,'automatically_resolved_conflicts':auto,'payout_validation':payout,'bac_fallback':fallback,'ukc_compression':{'horse_current':counts['horse_current'],'horse_history':counts['horse_history'],'ratio':round(counts['horse_history']/counts['horse_current'],4)},'join_rates':joins,'anomalies':an,'return_rate_smoke':smoke,'return_rate_sql_seconds':elapsed,'duplicate_detail_file':Path(a.duplicates).name}
 Path(a.json).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 md=['# JRDB Core Builder v1.1.1 PoC Audit','',f'**Verdict: {verdict}**','',f'- integrity: `{integrity}`',f'- 不正 business_date: {len(invalid)}',f'- MANUAL_REQUIRED: {manual}（v1.1: 1,120、今回新規解決: {1120-manual}）',f'- BAC fallback: {len(fallback)} races','', '## Payout regression','```json',json.dumps(payout,ensure_ascii=False,indent=2),'```','','## Missing source dates (all filename-derived)','```json',json.dumps(bad_dates,ensure_ascii=False,indent=2),'```','','## Duplicate patterns','```json',json.dumps(out['duplicate_patterns'],ensure_ascii=False,indent=2),'```','','## Join rates','```json',json.dumps(joins,ensure_ascii=False,indent=2),'```','','## Notes','- Duplicate detail JSON contains source filename, record no, parsed field differences, and byte ranges for every conflicting group.','- Raw files remain unchanged; any selection is recorded in meta_duplicate with evidence.']
 Path(a.md).write_text('\n'.join(md)+'\n',encoding='utf8')
if __name__=='__main__':main()
