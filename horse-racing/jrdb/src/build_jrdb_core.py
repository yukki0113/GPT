#!/usr/bin/env python3
"""JRDB Core Builder v1.1.2. Uses CP932 byte offsets and immutable raw provenance."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,re,sqlite3,zipfile
from collections import defaultdict
from pathlib import Path
KINDS=['BAC','KYI','SED','SKB','CYB','CHA','UKC']; V='1.1.2-production'
def now():return dt.datetime.now().isoformat(timespec='seconds')
def sha(b):return hashlib.sha256(b).hexdigest()
def t(b,a,n):return b[a:a+n].decode('cp932','replace').strip()
def n(b,a,l):
 try:return int(t(b,a,l).replace(',',''))
 except:return None
def key(b):return t(b,0,8)
def hno(b):return n(b,8,2)
def fdate(name,year):
 match=re.search(r'(\d{6})',Path(name).stem)
 if match is None:return None
 x=match.group(1)
 if int(x[:2])!=year%100:return None
 try:return dt.date(year,int(x[2:4]),int(x[4:6])).isoformat()
 except ValueError:return None
def anomaly(c,run,sev,typ,kind,date,fid,no,bk,detail):c.execute('insert into meta_anomaly(ingest_run_id,severity,anomaly_type,source_kind,business_date,source_file_id,record_no,business_key,detail_json,detected_at) values(?,?,?,?,?,?,?,?,?,?)',(run,sev,typ,kind,date,fid,no,bk,json.dumps(detail,ensure_ascii=False),now()))
def nonblank(b):return sum(x not in b' \r\n' for x in b)
def diff(old,new,cols,ov,nv):
 ranges=[];start=None
 for i,(a,b) in enumerate(zip(old,new)):
  if a!=b and start is None:start=i
  if a==b and start is not None:ranges.append([start,i]);start=None
 if start is not None:ranges.append([start,min(len(old),len(new))])
 return {'byte_ranges_0_based':ranges,'changed_fields':[{'field':k,'value_1':a,'value_2':b} for k,a,b in zip(cols,ov,nv) if a!=b]}
def insert(c,table,cols,vals,pk,run,kind,fid,no,raw,cache,stats,date):
 where=' and '.join(x+'=?' for x in pk);keys=[vals[cols.index(x)] for x in pk];old=c.execute(f'select * from {table} where {where}',keys).fetchone()
 if old is None:c.execute(f"insert into {table}({','.join(cols)}) values({','.join('?'*len(cols))})",vals);return
 od=dict(old);oraw=cache[(od['source_file_id'],od['source_record_no'])];same=od['record_hash']==sha(raw);ov=[od.get(x) for x in cols];d=diff(oraw,raw,cols,ov,vals);res='IDENTICAL_COLLAPSED' if same else 'MANUAL_REQUIRED';reason='raw_hash_equal' if same else 'awaiting_race_date_alignment'
 choose=False
 sf,sn=(fid,no) if choose else(od['source_file_id'],od['source_record_no']);bk=':'.join(map(str,keys))
 c.execute('insert into meta_duplicate(ingest_run_id,source_kind,business_key,first_source_file_id,first_record_no,first_record_hash,second_source_file_id,second_record_no,second_record_hash,is_identical,resolution,resolution_reason,diff_json,selected_source_file_id,selected_record_no,detected_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run,kind,bk,od['source_file_id'],od['source_record_no'],od['record_hash'],fid,no,sha(raw),int(same),res,reason,json.dumps(d,ensure_ascii=False),sf,sn,now()));stats['dups']+=1
 if choose:c.execute(f"update {table} set "+','.join(x+'=?' for x in cols)+f' where {where}',vals+keys)
 if res=='MANUAL_REQUIRED':anomaly(c,run,'WARNING','DUPLICATE_CONFLICT',kind,date,fid,no,bk,d)
def seed(c):
 vid=c.execute('insert into code_master_version(source_name,imported_at) values(?,?)',('整理版_JRDB_マスタコード定義',now())).lastrowid
 for typ,items in {'RUNNING_STYLE':{'1':'逃げ','2':'先行','3':'差し','4':'追込','5':'好位差し','6':'自在'},'GRADE':{'1':'G1','2':'G2','3':'G3','L':'リステッド'},'TRACK_CONDITION':{'1':'良','2':'稍重','3':'重','4':'不良'},'TRAINING_COURSE':{}}.items():
  for k,v in items.items():c.execute('insert into code_master values(?,?,?,?)',(typ,k,v,vid))
def resolve_cross_dates(c,run,cache,file_date):
 qs=c.execute("select * from meta_duplicate where source_kind='BAC' and resolution='MANUAL_REQUIRED'").fetchall(); changed=0
 for d in qs:
  a,b=file_date[d['first_source_file_id']],file_date[d['second_source_file_id']]
  if not a or not b or a==b:continue
  support={a:set(),b:set()}
  for table,kind in [('entry','KYI'),('result','SED'),('training_analysis','CYB'),('workout','CHA'),('result_extension','SKB')]:
   for row in c.execute(f'select source_file_id from {table} where race_key=?',(d['business_key'],)):
    day=file_date.get(row[0]);
    if day in support:support[day].add(kind)
  sa,sb=len(support[a]),len(support[b])
  if max(sa,sb)<2 or sa==sb:continue
  chosen_day=a if sa>sb else b;fid,no=(d['first_source_file_id'],d['first_record_no']) if chosen_day==a else(d['second_source_file_id'],d['second_record_no']);raw=cache[(fid,no)]
  c.execute("update race set race_date=?,source_file_id=?,source_record_no=?,record_hash=? where race_key=?",(chosen_day,fid,no,sha(raw),d['business_key']))
  c.execute("update meta_duplicate set resolution='CROSS_TYPE_DATE_CONFIRMED',resolution_reason=?,selected_source_file_id=?,selected_record_no=? where duplicate_id=?",(json.dumps({'support':{a:sorted(support[a]),b:sorted(support[b])}},ensure_ascii=False),fid,no,d['duplicate_id']));changed+=1
 return changed
def resolve_race_date_alignment(c,cache,file_date):
 qs=c.execute("select d.*,r.race_date,r.source_origin from meta_duplicate d join race r on r.race_key=substr(d.business_key,1,8) where d.resolution='MANUAL_REQUIRED'").fetchall();changed=0
 for d in qs:
  a,b=file_date.get(d['first_source_file_id']),file_date.get(d['second_source_file_id'])
  if not a or not b or a==b or d['source_origin']!='BAC' or d['race_date'] not in(a,b):continue
  fid,no=(d['first_source_file_id'],d['first_record_no']) if d['race_date']==a else(d['second_source_file_id'],d['second_record_no']);raw=cache[(fid,no)];k=key(raw);hn=hno(raw);h=sha(raw)
  if d['source_kind']=='CYB':c.execute('update training_analysis set training_index=?,source_file_id=?,source_record_no=?,record_hash=? where race_key=? and horse_no=?',(n(raw,29,3),fid,no,h,k,hn))
  elif d['source_kind']=='CHA':c.execute('update workout set training_date=?,course_code=?,chase_state=?,source_file_id=?,source_record_no=?,record_hash=? where race_key=? and horse_no=? and workout_seq=1',(t(raw,12,8),t(raw,21,2),t(raw,24,2),fid,no,h,k,hn))
  elif d['source_kind']=='BAC':c.execute("update race set race_date=?,source_origin='BAC',source_file_id=?,source_record_no=?,record_hash=? where race_key=?",(d['race_date'],fid,no,h,k))
  else:continue
  c.execute("update meta_duplicate set resolution='RACE_DATE_ALIGNED_SELECTED',resolution_reason=?,selected_source_file_id=?,selected_record_no=? where duplicate_id=?",(json.dumps({'race_date':d['race_date'],'candidate_dates':[a,b]},ensure_ascii=False),fid,no,d['duplicate_id']));changed+=1
 return changed
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--years',nargs='+',type=int,required=True);ap.add_argument('--raw-root',default='00_raw_local');ap.add_argument('--db',required=True);ap.add_argument('--schema',default='jrdb_core_schema_v1.sql');a=ap.parse_args()
 c=sqlite3.connect(a.db);c.row_factory=sqlite3.Row;c.execute('pragma journal_mode=MEMORY');c.execute('pragma synchronous=OFF');c.executescript(Path(a.schema).read_text());run=c.execute('insert into meta_ingest_run(builder_version,schema_version,started_at,status) values(?,?,?,?)',(V,'v1.1',now(),'RUNNING')).lastrowid;seed(c)
 cache={};file_date={};present=defaultdict(lambda:defaultdict(set));evidence=defaultdict(lambda:defaultdict(lambda:defaultdict(set)));stats=defaultdict(int);fallback=set()
 for year in a.years:
  for kind in KINDS:
   path=Path(a.raw_root)/kind/f'{kind}_{year}.zip'
   if not path.exists():anomaly(c,run,'WARNING','MISSING_ARCHIVE',kind,str(year),None,None,None,{'path':str(path)});continue
   blob=path.read_bytes();aid=c.execute('insert into meta_archive(ingest_run_id,source_kind,archive_name,year,sha256,size_bytes,imported_at) values(?,?,?,?,?,?,?)',(run,kind,path.name,year,sha(blob),len(blob),now())).lastrowid
   with zipfile.ZipFile(path) as z:
    for name in [x for x in z.namelist() if Path(x).name.upper().startswith(kind) and x.lower().endswith('.txt')]:
     raw=z.read(name);lines=raw.splitlines();filename=Path(name).name;canonical=bool(re.fullmatch(kind+r'\d{6}\.txt',filename,re.IGNORECASE));date=fdate(name,year);fid=c.execute('insert into meta_source_file(archive_id,source_kind,filename,business_date,record_count,sha256,record_length,is_canonical,source_role,imported_at) values(?,?,?,?,?,?,?,?,?,?)',(aid,kind,filename,date,len(lines),sha(raw),len(lines[0]) if lines else 0,int(canonical),'CANONICAL' if canonical else 'NON_CANONICAL',now())).lastrowid;file_date[fid]=date
     if not canonical:
      stats['raw_noncanonical']+=len(lines);continue
     if date:present[year][date].add(kind);evidence[year][date][kind].add(Path(name).name)
     else:anomaly(c,run,'ERROR','INVALID_SOURCE_FILENAME_DATE',kind,None,fid,None,None,{'filename':Path(name).name,'year':year})
     for no,line in enumerate(lines,1):
      cache[(fid,no)]=line;stats['raw']+=1;k=key(line);hn=hno(line);h=sha(line)
      if kind=='BAC':
       cols='race_key race_date venue_code year race_no distance track_type condition_code grade_code race_name source_origin source_file_id source_record_no record_hash'.split();vals=[k,date,t(line,0,2),year,n(line,6,2),n(line,20,4),t(line,24,1),t(line,29,2),t(line,35,1),t(line,36,50),'BAC',fid,no,h];insert(c,'race',cols,vals,['race_key'],run,kind,fid,no,line,cache,stats,date)
      elif kind=='KYI':
       cols='race_key horse_no horse_id horse_name jockey_name running_style distance_aptitude uptrend source_file_id source_record_no record_hash'.split();vals=[k,hn,t(line,10,8),t(line,18,36),t(line,171,12),t(line,89,1),t(line,90,1),t(line,91,1),fid,no,h];insert(c,'entry',cols,vals,['race_key','horse_no'],run,kind,fid,no,line,cache,stats,date)
       for q in range(5):c.execute('insert into entry_previous_result values(?,?,?,?,?,?,?) on conflict(race_key,horse_no,sequence) do nothing',(k,hn,q+1,t(line,203+q*16,16),t(line,283+q*8,8),fid,no))
      elif kind=='SED':
       if not c.execute('select 1 from race where race_key=?',(k,)).fetchone() and k not in fallback:
        c.execute('insert into race values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(k,date,t(line,0,2),year,n(line,6,2),n(line,62,4),t(line,66,1),None,None,None,'SED_FALLBACK',fid,no,h));anomaly(c,run,'INFO','BAC_FALLBACK_USED','SED',date,fid,no,k,{'race_key':k});fallback.add(k)
       cols='race_key horse_no horse_id horse_name finish abnormal_code final_win_odds final_win_popularity final_place_odds_lower odds_10am_win odds_10am_place win_payout place_payout source_file_id source_record_no record_hash'.split();vals=[k,hn,t(line,10,8),t(line,26,36),n(line,140,2),t(line,142,1),n(line,174,6),n(line,180,2),n(line,290,6),n(line,296,6),n(line,302,6),n(line,341,7),n(line,348,7),fid,no,h];insert(c,'result',cols,vals,['race_key','horse_no'],run,kind,fid,no,line,cache,stats,date)
      elif kind=='CYB':insert(c,'training_analysis','race_key horse_no training_index source_file_id source_record_no record_hash'.split(),[k,hn,n(line,29,3),fid,no,h],['race_key','horse_no'],run,kind,fid,no,line,cache,stats,date)
      elif kind=='CHA':insert(c,'workout','race_key horse_no workout_seq training_date course_code chase_state source_file_id source_record_no record_hash'.split(),[k,hn,1,t(line,12,8),t(line,21,2),t(line,24,2),fid,no,h],['race_key','horse_no','workout_seq'],run,kind,fid,no,line,cache,stats,date)
      elif kind=='SKB':insert(c,'result_extension','race_key horse_no special_note_code_1 special_note_code_2 race_comment source_file_id source_record_no record_hash'.split(),[k,hn,t(line,26,3),t(line,29,3),t(line,233,40),fid,no,h],['race_key','horse_no'],run,kind,fid,no,line,cache,stats,date)
      elif kind=='UKC':
       hid,name,sex=t(line,0,8),t(line,8,36),t(line,44,1);sem=sha((hid+'\0'+name+'\0'+sex).encode());old=c.execute('select * from horse_current where horse_id=?',(hid,)).fetchone()
       if not old:c.execute('insert into horse_current values(?,?,?,?,?,?,?)',(hid,name,sex,sem,fid,no,date));stats['normalized']+=1
       elif old['record_hash']!=sem:c.execute('insert into horse_history(horse_id,valid_from,valid_to,record_hash,source_file_id,source_record_no) values(?,?,?,?,?,?)',(hid,old['valid_from'],date,old['record_hash'],old['source_file_id'],old['source_record_no']));c.execute('update horse_current set horse_name=?,sex=?,record_hash=?,source_file_id=?,source_record_no=?,valid_from=? where horse_id=?',(name,sex,sem,fid,no,date,hid));stats['normalized']+=1
      if kind not in('BAC','UKC') and not c.execute('select 1 from race where race_key=?',(k,)).fetchone():anomaly(c,run,'WARNING','ORPHAN_SOURCE_RECORD',kind,date,fid,no,k,{})
 resolve_cross_dates(c,run,cache,file_date)
 stats['race_date_aligned']=resolve_race_date_alignment(c,cache,file_date)
 for year,days in present.items():
  for date,kinds in days.items():
   for missing in sorted(set(KINDS)-kinds):anomaly(c,run,'WARNING','MISSING_SOURCE_DATE',missing,date,None,None,None,{'year':year,'missing_kind':missing,'present_kinds':sorted(kinds),'evidence_source_filenames':sorted({x for vals in evidence[year][date].values() for x in vals})})
 ac=c.execute('select count(*) from meta_anomaly where ingest_run_id=?',(run,)).fetchone()[0];c.execute('update meta_ingest_run set finished_at=?,status=?,raw_records=?,normalized_records=?,duplicate_records=?,anomaly_records=? where ingest_run_id=?',(now(),'SUCCESS',stats['raw'],sum(c.execute(f'select count(*) from {x}').fetchone()[0] for x in ['race','entry','result','training_analysis','workout','result_extension','horse_current']),stats['dups'],ac,run));c.commit();print(json.dumps(dict(stats),ensure_ascii=False));c.close()
if __name__=='__main__':main()
