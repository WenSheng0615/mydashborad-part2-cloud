import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from jinja2 import Environment, FileSystemLoader
ROOT=Path(__file__).resolve().parents[1]
import tempfile
out=Path(tempfile.mkdtemp(prefix='focusflow-browser-'))
env=Environment(loader=FileSystemLoader(str(ROOT/'templates')),autoescape=True)
html=env.get_template('index.html').render(notes=[])
results=[]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True)
 page=b.new_page(viewport={'width':1440,'height':900})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 def intercept(route):
  url=route.request.url
  if not url.startswith('http://127.0.0.1:8000'):return route.abort()
  if '/api/' not in url:
   path=url.split('8000',1)[1].split('?')[0]
   if path=='/':return route.fulfill(status=200,body=html,content_type='text/html')
   asset=(ROOT/path.lstrip('/')).resolve()
   if asset.is_relative_to(ROOT/'static') and asset.is_file():return route.fulfill(path=str(asset))
   return route.fulfill(status=404,body='Not found')
  data={'items':[],'files':[],'notes':[],'events':[],'banks':[],'questions':[],'sessions':[],'messages':[],'todo':[],'doing':[],'done':[],'transactions':[],'categories':[],'total_income':0,'total_expense':0,'balance':0}
  if '/auth/user' in url:data={'name':'QA user','email':'qa@example.test','is_guest':False,'logged_in':True}
  if '/drive/storage' in url:data={'total':1000,'used':100,'trash':0}
  route.fulfill(status=200,json=data)
 page.route('**/*',intercept)
 page.goto('http://127.0.0.1:8000/',wait_until='networkidle')
 inventory=page.evaluate('''() => [...document.querySelectorAll('[onclick]')].map(e=>({call:e.getAttribute('onclick'),text:e.textContent.trim(),id:e.id})).filter(x=>{const m=x.call.match(/^([A-Za-z_$][\\w$]*)\\(/);return m && typeof window[m[1]]!=='function';})''')
 for size in [1440,390]:
  page.set_viewport_size({'width':size,'height':900})
  for name in ['notes','drive','calendar','tasks','money','chat','music','quiz','settings']:
   before=len(errors)
   try:
    page.evaluate('(name)=>openApp(name)',name)
    page.wait_for_timeout(200)
    info=page.locator('#view-'+name).evaluate('''e=>({visible:getComputedStyle(e).display!=='none',panelWidth:e.clientWidth,scroll:e.scrollWidth,overflow:e.scrollWidth>e.clientWidth+2})''')
    results.append(dict(page=name,width=size,**info,errors=errors[before:]))
   except Exception as e:results.append(dict(page=name,width=size,error=str(e)[:300]))
  page.screenshot(path=str(out/f'qa-settings-{size}.png'),full_page=True)
 # Controlled payloads are injected only into this mocked browser session.
 probes=page.evaluate('''() => {
 window.qaInjection=0;
 const payload='<img src=x onerror="window.qaInjection+=1">';
 renderColumn('col-todo',[{id:'test',content:payload,due_date:'2026-09-17T00:00:00Z'}],'todo');
 renderTransactions([{id:'test',item:payload,category:'test',note:payload,amount:1,type:'expense',date:'2026-09-17'}]);
 renderList(document.getElementById('history-list'),[{id:'test',title:payload,thumbnail:'',channel:'test'}]);
 return {tasks:!!document.querySelector('#col-todo .task-content img'),money:document.querySelectorAll('#transaction-list img').length,music:!!document.querySelector('#history-list .track-title img'),taskUndefined:document.querySelector('#col-todo').textContent.includes('undefined')};
 }''')
 page.wait_for_timeout(300)
 probes['executed']=page.evaluate('window.qaInjection')
 page.route('**/api/tasks/add',lambda route:route.fulfill(status=500,json={'error':'Simulated save failure'}))
 page.locator('#task-input').fill('Draft must stay',force=True) if False else page.evaluate("document.querySelector('#task-input').value='Draft must stay'")
 page.evaluate('addTask()')
 probes['taskDraftAfter500']=page.locator('#task-input').input_value()
 report={'scope':'Mocked API, external CDN blocked; no real account mutations','panels':results,'missingHandlers':inventory,'probes':probes,'consoleErrors':errors}
 (out/'interface-test-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 assert not inventory, inventory
 assert probes['tasks'] is False and probes['money']==0 and probes['music'] is False, probes
 assert probes['executed']==0 and not probes['taskUndefined'],probes
 assert probes['taskDraftAfter500']=='Draft must stay',probes
 print(json.dumps(report,ensure_ascii=True))
 b.close()
