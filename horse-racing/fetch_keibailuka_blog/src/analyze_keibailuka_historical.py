#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,io,json,re,sys,tempfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
import requests

VENUE_CODES={'札幌':'01','函館':'02','福島':'03','新潟':'04','東京':'05','中山':'06','中京':'07','京都':'08','阪神':'09','小倉':'10'}
TAGS=[
('詰まり・進路',re.compile(r'詰ま|つまり|壁|進路|追い出し|窮屈|挟ま|せまく|不利')),
('外回し・枠',re.compile(r'外回|外枠|大外|外3|外４|外4|枠響|枠の分')),
('馬場・芝ダート',re.compile(r'馬場|芝|ダート|砂|渋|重馬場')),
('展開・ペース',re.compile(r'ハイペース|スロー|前残|展開|ペース|差し損|前しんど|前潰')),
('出遅れ・スタート',re.compile(r'出遅|スタート|ゲート|躓')),
('コーナー・位置取り',re.compile(r'コーナー|4角|４角|1角|１角|ポジション|位置')),
('距離変更',re.compile(r'短縮|延長|距離|1200|１４００|1400|1800|１７００|1700|2000|2400')),
('相手関係・レベル',re.compile(r'相手が強|相手も強|レベル|ハイレベル|クラス|比較')),
('斤量・減量',re.compile(r'斤量|減量|キロ|ハンデ')),
('休み明け・状態',re.compile(r'休み明け|叩|調教|追切|去勢')),
]

def get(url, **kwargs):
    r=requests.get(url,timeout=60,**kwargs)
    r.raise_for_status()
    return r

def drive_download(fid):
    r=get('https://drive.usercontent.google.com/download',params={'id':fid,'export':'download','confirm':'t'})
    if b'<html' in r.content[:200].lower():
        r=get('https://drive.google.com/uc',params={'export':'download','id':fid})
    return r.content

def metric(rows):
    n=len(rows)
    wins=sum(1 for x in rows if (x.get('win_payout') or 0)>0)
    places=sum(1 for x in rows if (x.get('place_payout') or 0)>0)
    return {
        'n':n,'wins':wins,'places':places,
        'win_rate_pct':round(wins*100/n,2) if n else None,
        'place_rate_pct':round(places*100/n,2) if n else None,
        'win_return_pct':round(sum((x.get('win_payout') or 0) for x in rows)/n,1) if n else None,
        'place_return_pct':round(sum((x.get('place_payout') or 0) for x in rows)/n,1) if n else None,
    }

def odds_band(v):
    if v is None: return '不明'
    v=float(v)
    if v<2:return '1.0-1.9'
    if v<3:return '2.0-2.9'
    if v<5:return '3.0-4.9'
    if v<10:return '5.0-9.9'
    if v<20:return '10.0-19.9'
    if v<50:return '20.0-49.9'
    if v<100:return '50.0-99.9'
    return '100.0+'

def write_csv(path, rows, fields):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--request-json',required=True)
    ap.add_argument('--output-dir',required=True)
    a=ap.parse_args()
    req=json.load(open(a.request_json,encoding='utf-8'))
    out=Path(a.output_dir)
    out.mkdir(parents=True,exist_ok=True)

    sid=req['spreadsheet_id']
    sheet=req.get('sheet_name','イルカ明細')
    url=f'https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv&sheet={quote(sheet)}'
    text=get(url).content.decode('utf-8-sig')

    picks=[]
    masked=0
    for r in csv.DictReader(io.StringIO(text)):
        d=(r.get('日付') or '').strip()
        raw=(r.get('馬名_raw') or '').strip()
        if not re.fullmatch(r'202[456]-\d{2}-\d{2}',d):
            continue
        if raw=='🤡':
            masked+=1
            continue
        if not raw:
            continue
        picks.append({
            'key':r['key'],'date':d,'year':int(d[:4]),
            'venue':r['会場'].strip(),'venue_code':VENUE_CODES.get(r['会場'].strip()),
            'race_no':int(r['R'].rstrip('R')),'horse_name':raw,'comment':r.get('コメント','')
        })
    if not picks:
        raise SystemExit('no picks')

    import duckdb
    tmp=Path(tempfile.mkdtemp(prefix='keibailuka_analysis_'))
    hist_paths=[]
    for item in req['historical_sed_assets']:
        data=drive_download(item['id'])
        sha=hashlib.sha256(data).hexdigest()
        if sha!=item['sha256']:
            raise SystemExit(f"SHA mismatch year={item['year']} {sha}")
        p=tmp/f"sed_{item['year']}.parquet"
        p.write_bytes(data)
        hist_paths.append(str(p))

    con=duckdb.connect()
    con.execute('CREATE TABLE picks(key VARCHAR,date VARCHAR,year INTEGER,venue VARCHAR,venue_code VARCHAR,race_no INTEGER,horse_name VARCHAR,comment VARCHAR)')
    con.executemany(
        'INSERT INTO picks VALUES (?,?,?,?,?,?,?,?)',
        [(p['key'],p['date'],p['year'],p['venue'],p['venue_code'],p['race_no'],p['horse_name'],p['comment'])
         for p in picks if p['year'] in (2024,2025)]
    )
    pq=','.join("'" + x.replace("'","''") + "'" for x in hist_paths)
    q=f"""SELECT p.key,p.date,p.year,p.venue,p.race_no,p.horse_name,p.comment,
                  s.finish,s.final_popularity,s.final_win_odds,s.win_payout,s.place_payout
           FROM picks p
           LEFT JOIN read_parquet([{pq}]) s
             ON s.race_date=p.date
            AND s.venue_code=p.venue_code
            AND s.race_no=p.race_no
            AND trim(s.horse_name)=trim(p.horse_name)"""
    cols=['key','date','year','venue','race_no','horse_name','comment','finish','final_popularity','final_win_odds','win_payout','place_payout']
    merged=[dict(zip(cols,row)) for row in con.execute(q).fetchall()]

    sys.path.insert(0,str(Path('horse-racing/jrdb/src').resolve()))
    from jrdb_raw import Parser,iter_archive_records,race_key_parts,ymd
    parser=Parser()
    idx={}
    needed={p['date'].replace('-','') for p in picks if p['year']==2026}
    assets={x['date']:x for x in req['sed_2026_assets']}
    missing_assets=sorted(needed-set(assets))
    if missing_assets:
        raise SystemExit('missing 2026 SED assets: '+','.join(missing_assets))
    for ds in sorted(needed):
        item=assets[ds]
        data=drive_download(item['id'])
        if item.get('size') and len(data)!=int(item['size']):
            raise SystemExit(f'size mismatch {ds}: {len(data)}')
        z=tmp/item['title']
        z.write_bytes(data)
        for member,record in iter_archive_records(z,'SED'):
            d=parser.sed(record)
            parts=race_key_parts(d['race_key_raw'])
            date=ymd(d.get('date_raw'))
            idx[(date,parts['venue_code'],parts['race_no'],(d.get('horse_name') or '').strip())]=d

    for p in picks:
        if p['year']!=2026:
            continue
        d=idx.get((p['date'],p['venue_code'],p['race_no'],p['horse_name'].strip()))
        merged.append({
            **p,
            'finish':None if d is None else d.get('finish'),
            'final_popularity':None if d is None else d.get('final_popularity'),
            'final_win_odds':None if d is None else d.get('final_win_odds'),
            'win_payout':None if d is None else d.get('win_payout'),
            'place_payout':None if d is None else d.get('place_payout'),
        })

    matched=[
        x for x in merged
        if x.get('final_popularity') is not None
        or x.get('final_win_odds') is not None
        or x.get('win_payout') is not None
        or x.get('place_payout') is not None
    ]
    unmatched=[x for x in merged if x not in matched]
    duplicate_keys=len(merged)-len({x['key'] for x in merged})

    overall={'all':metric(matched)}
    for y in (2024,2025,2026):
        overall[str(y)]=metric([x for x in matched if x['year']==y])

    groups=defaultdict(list)
    for x in matched:
        k=str(int(x['final_popularity'])) if x.get('final_popularity') is not None else '不明'
        groups[k].append(x)
    popularity=[
        {'popularity':k,**metric(groups[k])}
        for k in sorted(groups,key=lambda s:(999 if s=='不明' else int(s)))
    ]

    ob=defaultdict(list)
    for x in matched:
        ob[odds_band(x.get('final_win_odds'))].append(x)
    order=['1.0-1.9','2.0-2.9','3.0-4.9','5.0-9.9','10.0-19.9','20.0-49.9','50.0-99.9','100.0+','不明']
    odds=[{'odds_band':k,**metric(ob[k])} for k in order if ob[k]]

    tag_rows=[]
    for name,rx in TAGS:
        arr=[x for x in matched if rx.search(x.get('comment') or '')]
        tag_rows.append({'tag':name,**metric(arr)})

    result={
        'schema_version':'keibailuka-research-v0.1',
        'source_picks':len(picks),
        'masked_excluded':masked,
        'merged_rows':len(merged),
        'matched_rows':len(matched),
        'unmatched_rows':len(unmatched),
        'match_rate_pct':round(len(matched)*100/len(merged),3),
        'duplicate_keys':duplicate_keys,
        'overall':overall,
        'popularity':popularity,
        'odds_bands':odds,
        'comment_tags':tag_rows,
    }
    json.dump(result,open(out/'summary.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    write_csv(out/'popularity.csv',popularity,['popularity','n','wins','places','win_rate_pct','place_rate_pct','win_return_pct','place_return_pct'])
    write_csv(out/'odds_bands.csv',odds,['odds_band','n','wins','places','win_rate_pct','place_rate_pct','win_return_pct','place_return_pct'])
    write_csv(out/'comment_tags.csv',tag_rows,['tag','n','wins','places','win_rate_pct','place_rate_pct','win_return_pct','place_return_pct'])
    write_csv(out/'unmatched.csv',unmatched[:1000],['key','date','year','venue','race_no','horse_name','comment','finish','final_popularity','final_win_odds','win_payout','place_payout'])
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    main()
