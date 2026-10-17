import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from jinja2 import Environment, FileSystemLoader
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT))
from services.module_service import CATALOG
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
  if '/api/modules' in url:data={'modules':[dict(module,enabled=True) for module in CATALOG]}
  if '/api/modules/connections' in url:
   data={'connections':{m['id']:[{'provider':'測試服務','status':'unverified','message':'已設定，尚未檢查服務連線'}] for m in CATALOG}}
  if '/auth/user' in url:data={'name':'QA user','email':'qa@example.test','is_guest':False,'logged_in':True}
  if '/drive/storage' in url:data={'total':1000,'used':100,'trash':0}
  route.fulfill(status=200,json=data)
 page.route('**/*',intercept)
 page.goto('http://127.0.0.1:8000/',wait_until='networkidle')
 inventory=page.evaluate('''() => [...document.querySelectorAll('[onclick]')].map(e=>({call:e.getAttribute('onclick'),text:e.textContent.trim(),id:e.id})).filter(x=>{const m=x.call.match(/^([A-Za-z_$][\\w$]*)\\(/);return m && typeof window[m[1]]!=='function';})''')
 for size in [1440,390]:
  page.set_viewport_size({'width':size,'height':900})
  expected_accent = '#8acbbd'
  assert page.evaluate("getComputedStyle(document.body).getPropertyValue('--accent').trim()") == expected_accent
  assert page.locator('.mobile-dock').is_visible() == (size == 390)
  for name in ['notes','drive','calendar','tasks','money','chat','music','quiz','settings','modules']:
   before=len(errors)
   try:
    page.evaluate('(name)=>openApp(name)',name)
    page.wait_for_timeout(200)
    info=page.locator('#view-'+name).evaluate('''e=>({visible:getComputedStyle(e).display!=='none',panelWidth:e.clientWidth,scroll:e.scrollWidth,overflow:e.scrollWidth>e.clientWidth+2})''')
    results.append(dict(page=name,width=size,**info,errors=errors[before:]))
   except Exception as e:results.append(dict(page=name,width=size,error=str(e)[:300]))
  # Both long panels must scroll within the shell, above the fixed dock.
  for panel_id, last_card in [('modules','#module-core-list .module-tile'),('settings','.about-card')]:
   page.evaluate('(name)=>openApp(name)',panel_id)
   panel=page.locator('#view-'+panel_id)
   panel.evaluate('(e)=>e.scrollTop=0')
   panel.hover();page.mouse.wheel(0,1200);page.wait_for_timeout(250)
   if panel_id == 'modules' or panel.evaluate('(e)=>e.scrollHeight>e.clientHeight+1'):
    assert panel.evaluate('(e)=>e.scrollTop>0')
   if panel_id == 'modules':
    page.get_by_role('checkbox',name='啟用學習測驗',exact=True).scroll_into_view_if_needed()
    assert page.get_by_role('checkbox',name='啟用學習測驗',exact=True).is_visible()
   panel.evaluate('(e)=>e.scrollTop=e.scrollHeight')
   last=page.locator(last_card).last.bounding_box()
   viewport=panel.bounding_box()
   assert last['y']+last['height'] <= viewport['y']+viewport['height']+1
   page.screenshot(path=str(out/f'qa-{panel_id}-{size}.png'),full_page=True)
 # Mobile dock stays above content and Home makes every app reachable.
 page.set_viewport_size({'width':390,'height':700})
 page.evaluate("openApp('calendar')")
 page.wait_for_timeout(250)
 assert page.locator('.mobile-dock a:visible').count() == 3
 assert page.locator('#sidebar .nav-item:visible').count() == 0
 dock = page.locator('.mobile-dock').bounding_box()
 workspace = page.locator('#workspace').bounding_box()
 assert workspace['y'] + workspace['height'] <= dock['y'] + 1
 page.locator('[data-dock=home]').click()
 page.locator('#launcher').wait_for(state='visible')
 page.wait_for_timeout(350)
 assert not page.locator('#sidebar').is_visible()
 assert page.locator('[data-dock=home]').get_attribute('aria-current') == 'page'
 page.locator('[data-dock=calendar]').click()
 page.wait_for_timeout(250)
 assert page.locator('[data-dock=calendar]').get_attribute('aria-current') == 'page'
 page.locator('[data-dock=home]').click()
 page.wait_for_timeout(350)
 page.screenshot(path=str(out/'home-mobile.png'),full_page=False)
 page.evaluate("openApp('calendar'); currentDate = new Date(2026,0,31); changeMonth(1)")
 page.wait_for_timeout(250)
 assert page.evaluate('currentDate.getMonth()') == 1
 page.screenshot(path=str(out/'calendar-mobile.png'),full_page=True)
 page.evaluate("openApp('music'); window.coverClicks=0; audio.pause=()=>window.coverClicks++; Object.defineProperty(audio,'paused',{configurable:true,get:()=>false}); audio.src='/test-audio'")
 page.locator('#player-art-container').click()
 assert page.evaluate('window.coverClicks') == 1
 page.locator('#player-art-container').press('Enter')
 assert page.evaluate('window.coverClicks') == 2
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
 # Lock-screen metadata/actions are recorded in an isolated page; no real audio/provider calls.
 media=b.new_page()
 media.route('**/*',intercept)
 media.add_init_script("""window.mediaQA={handlers:{},positions:[]};
 Object.defineProperty(navigator,'mediaSession',{configurable:true,value:{
 metadata:null,playbackState:'none',setPositionState(s){mediaQA.positions.push(s||null)},
 setActionHandler(action,handler){if(action==='stop')throw new Error('unsupported');mediaQA.handlers[action]=handler;}
 }});""")
 media.goto('http://127.0.0.1:8000/',wait_until='networkidle')
 media.evaluate("""() => {
 audio.play=()=>{audio.dispatchEvent(new Event('play'));return Promise.resolve()};
 audio.pause=()=>audio.dispatchEvent(new Event('pause'));
 Object.defineProperty(audio,'duration',{configurable:true,value:200});
 Object.defineProperty(audio,'currentTime',{configurable:true,writable:true,value:12});
 window.pendingTracks={};const original=window.fetch;
 window.fetch=(url,...args)=>String(url).startsWith('/api/music/stream?')?
   new Promise(resolve=>pendingTracks[new URL(url,location.origin).searchParams.get('video_id')]=resolve):original(url,...args);
 musicQueue=[{id:'aaaaaaaaaaa',title:'Old selection'},{id:'bbbbbbbbbbb',title:'History without author'}];
 window.firstPlay=playTrack(0);window.secondPlay=playTrack(1);
 }""")
 media.evaluate("""async () => {
 pendingTracks.bbbbbbbbbbb(new Response(JSON.stringify({url:'/test-audio-b',title:'真正歌名',channel:'演出者頻道',thumbnail:'https://img.youtube.com/vi/bbbbbbbbbbb/hqdefault.jpg'}),{status:200}));
 await secondPlay;
 pendingTracks.aaaaaaaaaaa(new Response(JSON.stringify({url:'/test-audio-a',title:'Stale title',channel:'Old channel'}),{status:200}));
 await firstPlay;
 }""")
 metadata=media.evaluate("""() => ({title:navigator.mediaSession.metadata.title,artist:navigator.mediaSession.metadata.artist,
 artwork:navigator.mediaSession.metadata.artwork[0].src,source:audio.getAttribute('src'),state:navigator.mediaSession.playbackState})""")
 assert metadata['title']=='真正歌名' and metadata['artist']=='演出者頻道',metadata
 assert 'bbbbbbbbbbb' in metadata['artwork'] and metadata['source']=='/test-audio-b',metadata
 assert metadata['state']=='playing',metadata
 media.evaluate("mediaQA.handlers.pause();mediaQA.handlers.seekforward({seekOffset:999})")
 assert media.evaluate('audio.currentTime')==200
 assert media.evaluate('navigator.mediaSession.playbackState')=='paused'
 media.evaluate("mediaQA.handlers.seekbackward({seekOffset:999});mediaQA.handlers.play()")
 assert media.evaluate('audio.currentTime')==0
 assert media.evaluate('navigator.mediaSession.playbackState')=='playing'
 media.evaluate("mediaQA.handlers.seekto({seekTime:70})")
 assert media.evaluate('mediaQA.positions.at(-1).position')==70
 media.evaluate("""async () => {
 mediaQA.handlers.previoustrack();
 pendingTracks.aaaaaaaaaaa(new Response(JSON.stringify({url:'/test-audio-a',title:'Previous song',thumbnail:'javascript:alert(1)'}),{status:200}));
 }""")
 media.wait_for_function("navigator.mediaSession.metadata.title==='Previous song'")
 assert media.evaluate('navigator.mediaSession.metadata.artist')=='YouTube'
 assert media.evaluate('navigator.mediaSession.metadata.artwork[0].src').endswith('/static/icons/icon-192.png')
 media.evaluate("syncMediaMetadata({title:'No cover supplied'})")
 assert media.evaluate('navigator.mediaSession.metadata.artwork[0].src').endswith('/static/icons/icon-192.png')
 media.evaluate("""() => {
 Object.defineProperty(navigator,'mediaSession',{configurable:true,value:undefined});
 delete navigator.mediaSession;delete Navigator.prototype.mediaSession;
 syncMediaMetadata({title:'Unsupported browser'});updatePlayBtn(false);syncMediaPosition();
 }""")
 media.close()
 probes['mediaSession']='metadata, artwork, race, fallback, controls and unsupported API PASS'
 report={'scope':'Mocked API, external CDN blocked; no real account mutations','panels':results,'missingHandlers':inventory,'probes':probes,'consoleErrors':errors}
 (out/'interface-test-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 assert not inventory, inventory
 assert probes['tasks'] is False and probes['money']==0 and probes['music'] is False, probes
 assert probes['executed']==0 and not probes['taskUndefined'],probes
 assert probes['taskDraftAfter500']=='Draft must stay',probes
 print(json.dumps(report,ensure_ascii=True))
 b.close()
