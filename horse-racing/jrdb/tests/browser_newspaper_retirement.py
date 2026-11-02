import http.server,threading,json
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1] / 'pwa'
class Handler(http.server.SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(root),**kw)
 def log_message(self,*a):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',8765),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for surface in ['newspaper.html','momotaro/newspaper.html']:
  for width in [360,390,430]:
   page=browser.new_page(viewport={'width':width,'height':844},service_workers='block');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8765/'+surface);page.wait_for_timeout(300)
   for state in [None,'ERROR','PARTIAL','READY']:
    result=page.evaluate('''state=>{
      currentBundle={race:{date:'2026-11-02',venue:'東京',race_no:1},metadata:{source_status:{edge:{state},edge_v05:{state},my_index:{state}}},edge_v05_candidates:{x:{condition_text:'RETIRED'}},horses:[{key:{horse_no:1,frame_no:1},basic:{horse_name:'テスト'},jrdb:{marks:{total:'◎'},ability:{idm:50}},history:[],edge_matches:[{display_text:'RETIRED'}],special_memos:[{display_text:'RETIRED'}],addons:{my_index:{training_edge_index:999,index:888},edge_v05:{candidate_ids:['x']},eval:{eval:55,analysis:{comment:'Eval WATCH MATCH'}},racenote_prediction:{mark:'◎'},momotaro:{kenshow:{mark:'◎'},ryota:{mark:'○'},oji:{mark:'▲'}}}}]};
      for (let el=tableWrap;el;el=el.parentElement) el.hidden=false;
      renderTable();
      for (const count of (location.pathname.includes('/momotaro/') ? [5] : [3,5,8])) {historyCount=count;renderTable();if(tableWrap.querySelectorAll('tbody .newspaper-history-cell').length!==count)throw Error('history count');}
      historyCount=3;renderTable();
      if (!location.pathname.includes('/momotaro/')) {const button=tableWrap.querySelector('.newspaper-eval-analysis-link');if(!button)throw Error('Eval link lost');button.click();if(!dialogBody.textContent.includes('Eval WATCH MATCH'))throw Error('Eval modal lost');detailDialog.close();}
      const wrapper=tableWrap;wrapper.scrollLeft=300;
      const identity=tableWrap.querySelector('.newspaper-horse-name-cell');if(getComputedStyle(identity).position!=='sticky')throw Error('sticky lost');
      wrapper.scrollLeft=0;
      return {retired:document.querySelectorAll('.newspaper-edge,.newspaper-edge-v05,.mark-my,.mark-edge').length,marks:document.querySelectorAll('thead .newspaper-mark-col').length,text:tableWrap.textContent};
    }''',state)
    assert result['retired']==0 and 'RETIRED' not in result['text'] and '999' not in result['text'],result
    assert result['marks']>0,result
   assert not errors,errors
   print(surface,width,'PASS');page.close()
 browser.close()
server.shutdown()
