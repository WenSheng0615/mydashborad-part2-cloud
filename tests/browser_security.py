import json
from urllib.parse import parse_qs, urlsplit
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
 media=b.new_page(viewport={'width':390,'height':844})
 media.on('pageerror',lambda e:errors.append(str(e)))
 media.route('**/*',intercept)
 media.add_init_script("""window.mediaQA={handlers:{},positions:[]};
 Object.defineProperty(navigator,'mediaSession',{configurable:true,value:{
 metadata:null,playbackState:'none',setPositionState(s){mediaQA.positions.push(s||null)},
 setActionHandler(action,handler){if(action==='stop')throw new Error('unsupported');mediaQA.handlers[action]=handler;}
 }});""")
 media.goto('http://127.0.0.1:8000/',wait_until='networkidle')
 media.evaluate("""() => {
 Object.defineProperty(audio,'src',{configurable:true,get(){return this.getAttribute('data-qa-source')||''},set(value){this.setAttribute('data-qa-source',value)}});
 audio.play=()=>{window.playCalls=(window.playCalls||0)+1;audio.dispatchEvent(new Event('play'));audio.dispatchEvent(new Event('playing'));return Promise.resolve()};
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
 pendingTracks.aaaaaaaaaaa(new Response(JSON.stringify({url:'/test-audio-a',title:'Previous song'}),{status:200}));
 await firstPlay;
 }""")
 metadata=media.evaluate("""() => ({title:navigator.mediaSession.metadata.title,artist:navigator.mediaSession.metadata.artist,
 artwork:navigator.mediaSession.metadata.artwork[0].src,source:audio.getAttribute('data-qa-source'),state:navigator.mediaSession.playbackState})""")
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
 media.evaluate('previewSeek(90)')
 assert media.evaluate('audio.currentTime')==70
 assert media.locator('#current-time').inner_text()=='3:00'
 media.evaluate('seekTo(90)')
 assert media.evaluate('audio.currentTime')==180
 # A prepared next track must call play synchronously from ended, with no network await.
 background=media.evaluate("""() => {
 const count=window.playCalls;onAudioEnded();
 return {source:audio.getAttribute('data-qa-source'),plays:window.playCalls-count,title:navigator.mediaSession.metadata.title};
 }""")
 assert background['source']=='/test-audio-b' and background['plays']==1,background
 assert background['title']=='真正歌名',background
 media.evaluate("audio.dispatchEvent(new Event('waiting'))")
 assert media.evaluate('navigator.mediaSession.playbackState')=='paused'
 assert media.evaluate('mediaQA.positions.at(-1)') is None
 assert media.locator('#music-playback-status').inner_text()==''
 media.evaluate("audio.dispatchEvent(new Event('playing'))")
 assert media.evaluate('navigator.mediaSession.playbackState')=='playing'
 assert media.locator('#music-playback-status').inner_text()==''
 # Recover when Safari resumes time progression without another playing event.
 media.evaluate("""() => {
 Object.defineProperty(audio,'paused',{configurable:true,get:()=>false});
 Object.defineProperty(audio,'readyState',{configurable:true,get:()=>2});
 audio.dispatchEvent(new Event('waiting'));updatePlayBtn(false);
 audio.currentTime+=.25;audio.dispatchEvent(new Event('timeupdate'));
 }""")
 assert media.locator('#music-playback-status').inner_text()==''
 assert media.evaluate("isPlaying && navigator.mediaSession.playbackState==='playing'")
 media.evaluate("audio.dispatchEvent(new Event('waiting'));audio.currentTime+=50;audio.dispatchEvent(new Event('timeupdate'))")
 assert media.evaluate('mediaWaiting')  # Seeking alone cannot establish real playback.
 media.evaluate("Object.defineProperty(audio,'paused',{configurable:true,get:()=>true});audio.dispatchEvent(new Event('pause'))")
 assert media.locator('#music-playback-status').inner_text()==''
 assert media.evaluate("!isPlaying && navigator.mediaSession.playbackState==='paused'")
 media.evaluate("Object.defineProperty(audio,'paused',{configurable:true,get:()=>false})")
 # Resolving one song starts preparation of only the next, before ended is fired.
 media.evaluate("""async () => {
 musicQueue=[{id:'ccccccccccc',title:'Current'},{id:'ddddddddddd',title:'Next'}];
 const playing=playTrack(0);
 pendingTracks.ccccccccccc(new Response(JSON.stringify({url:'/current-audio',title:'Current'}),{status:200}));
 await playing;
 }""")
 assert media.evaluate("typeof pendingTracks.ddddddddddd")=='function'
 media.evaluate("""async () => {
 const pending=preparingStreams.get('ddddddddddd');
 pendingTracks.ddddddddddd(new Response(JSON.stringify({url:'/prepared-next',title:'Prepared next'}),{status:200}));
 await pending;
 }""")
 assert media.evaluate("(()=>{const n=playCalls;onAudioEnded();return audio.src==='/prepared-next'&&playCalls===n+1})()")
 media.evaluate("preparedStreams.get('ddddddddddd').until=Date.now()-1")
 assert media.evaluate("preparedStream('ddddddddddd')===null")
 # A failed next-track warm-up is non-fatal and must not retry on every progress event.
 media.evaluate("""async () => {
 musicQueue=[{id:'eeeeeeeeeee',title:'Current stays playing'},{id:'fffffffffff',title:'Unavailable next'}];
 const playing=playTrack(0);
 pendingTracks.eeeeeeeeeee(new Response(JSON.stringify({url:'/still-playing',title:'Current stays playing'}),{status:200}));
 await playing;
 const pending=preparingStreams.get('fffffffffff');
 pendingTracks.fffffffffff(new Response(JSON.stringify({error:'Provider unavailable'}),{status:503}));
 await pending.catch(()=>{});await Promise.resolve();
 delete pendingTracks.fffffffffff;warmNextTrack();
 }""")
 assert media.evaluate("navigator.mediaSession.metadata.title==='Current stays playing' && navigator.mediaSession.playbackState==='playing'")
 assert media.evaluate("!preparingStreams.has('fffffffffff') && !pendingTracks.fffffffffff")
 # Grossly inflated native duration must not leave a known VOD playing a silent tail.
 media.evaluate("""async () => {
 const song={id:'eeeeeeeeeee',title:'Timing fixture'};musicQueue=[song];
 preparedStreams.set(song.id,{until:Date.now()+60000,data:{url:'/timing-fixture',title:song.title,duration:200,is_live:false}});
 await playTrack(0);
 Object.defineProperty(audio,'duration',{configurable:true,value:400});
 Object.defineProperty(audio,'paused',{configurable:true,get:()=>false});
 audio.currentTime=199;updateProgress();
 }""")
 assert media.locator('#duration').inner_text()=='3:20'
 assert media.evaluate('mediaQA.positions.at(-1).duration')==200
 assert media.evaluate('isPlaying && !playbackFinished')
 media.evaluate('audio.currentTime=201;updateProgress()')
 assert media.evaluate('playbackFinished && !isPlaying')
 assert media.locator('#current-time').inner_text()=='3:20'
 media.evaluate('mediaQA.handlers.play()')
 assert media.evaluate('audio.currentTime===0 && !playbackFinished')
 # A prepared following song also transitions at the validated end without another fetch.
 advanced=media.evaluate("""() => {
 musicQueue.push({id:'ggggggggggg',title:'Following song'});
 preparedStreams.set('ggggggggggg',{until:Date.now()+60000,data:{url:'/following-song',duration:180,title:'Following song'}});
 audio.currentTime=201;const before=playCalls;updateProgress();
 return {src:audio.src,plays:playCalls-before};
 }""")
 assert advanced=={'src':'/following-song','plays':1},advanced
 # Live/unknown/small mismatches, pause, seek and buffering must never trigger the guard.
 media.evaluate('sourceDuration=200;sourceIsLive=true;audio.currentTime=230;mediaWaiting=false;playbackFinished=false')
 assert media.evaluate('playbackDuration()===400 && !finishInflatedTail()')
 media.evaluate('sourceIsLive=false;sourceDuration=null')
 assert media.evaluate('playbackDuration()===400 && !finishInflatedTail()')
 media.evaluate('sourceDuration=390')
 assert media.evaluate('playbackDuration()===400 && !finishInflatedTail()')
 media.evaluate('sourceDuration=200;mediaWaiting=true')
 assert media.evaluate('!finishInflatedTail()')
 media.evaluate("mediaWaiting=false;Object.defineProperty(audio,'seeking',{configurable:true,get:()=>true})")
 assert media.evaluate('!finishInflatedTail()')
 media.evaluate("Object.defineProperty(audio,'seeking',{configurable:true,get:()=>false});Object.defineProperty(audio,'paused',{configurable:true,get:()=>true})")
 assert media.evaluate('!finishInflatedTail()')
 media.evaluate('sourceDuration=null;sourceIsLive=false;audio.currentTime=0')
 probes['durationGuard']='2x native duration, provider timing, completion/replay/next and live/unknown/wait/seek/pause exclusions PASS'
 media.evaluate("syncMediaMetadata({title:'No cover supplied'})")
 assert media.evaluate('navigator.mediaSession.metadata.artwork[0].src').endswith('/static/icons/icon-192.png')
 media.evaluate("""() => {
 Object.defineProperty(navigator,'mediaSession',{configurable:true,value:undefined});
 delete navigator.mediaSession;delete Navigator.prototype.mediaSession;
 syncMediaMetadata({title:'Unsupported browser'});updatePlayBtn(false);syncMediaPosition();
 }""")
 # A 237-item playlist spans five provider pages, retaining order and repeated videos.
 media.evaluate("async()=>{await openApp('music');switchTab('playlists')}")
 playlist_calls=[]
 def playlist_page(route):
  query=parse_qs(urlsplit(route.request.url).query)
  token=query.get('page_token',[''])[0]
  number=int(token.split(':')[1].split('+')[0]) if token else 0
  playlist_calls.append(number)
  start=number*50;end=min(start+50,237)
  items=[{'id':str(i if i!=70 else 1).zfill(11),'itemId':f'item-{i}','title':f'Track {i+1}'} for i in range(start,end)]
  route.fulfill(json={'items':items,'next_page_token':f'page:{number+1}+/=' if end<237 else ''})
 media.route('**/api/music/playlist/items?*',playlist_page)
 media.evaluate("loadPlaylistItems('PL-test','Long playlist')")
 assert playlist_calls==[0,1,2,3,4],playlist_calls
 assert media.locator('#playlist-songs .track-item').count()==237
 assert media.locator('#playlist-songs .track-title').last.inner_text()=='Track 237'
 assert media.evaluate('musicQueue.length')==2
 media.locator('#playlist-songs .track-item').last.scroll_into_view_if_needed()
 media.locator('#playlist-songs .track-item').last.click()
 assert media.evaluate('currentTrackIndex')==236
 assert media.evaluate('currentSong.title')=='Track 237'
 # Mobile scrolling keeps the selected song reachable in a header mini-player.
 media.evaluate("""async () => {
 const pending=preparingStreams.get('00000000236');
 pendingTracks['00000000236'](new Response(JSON.stringify({url:'/track-237',title:'Track 237',channel:'Playlist artist',thumbnail:'/static/icons/icon-192.png'}),{status:200}));
 await pending;
 }""")
 media.wait_for_function("document.querySelector('#music-mini-title').textContent==='Track 237' && !document.querySelector('#music-mini-player').hidden")
 assert media.locator('#music-mini-player').is_visible()
 assert media.locator('#music-mini-artist').inner_text()=='Playlist artist'
 media.evaluate("""() => {
 window.miniPaused=false;Object.defineProperty(audio,'paused',{configurable:true,get:()=>miniPaused});
 const play=audio.play,pause=audio.pause;audio.play=()=>{miniPaused=false;return play()};audio.pause=()=>{miniPaused=true;pause()};
 }""")
 media.locator('#music-mini-toggle').click()
 assert media.locator('#music-mini-toggle').get_attribute('aria-label')=='播放'
 media.locator('#music-mini-toggle').click()
 assert media.locator('#music-mini-toggle').get_attribute('aria-label')=='暫停'
 assert media.locator('audio').count()==1
 media.locator('#music-mini-prev').click()
 assert media.evaluate('currentTrackIndex')==235
 media.evaluate("""async()=>{const pending=preparingStreams.get('00000000235');pendingTracks['00000000235'](new Response(JSON.stringify({url:'/track-236',title:'Track 236'}),{status:200}));await pending;}""")
 media.wait_for_function("document.querySelector('#music-mini-title').textContent==='Track 236'")
 media.locator('#music-mini-player').get_by_role('button',name='下一首',exact=True).click()
 assert media.evaluate('currentTrackIndex')==236
 media.evaluate('currentTrackIndex=0;syncMiniPlayer()')
 assert media.locator('#music-mini-prev').is_disabled()
 media.evaluate('currentTrackIndex=236;syncMiniPlayer()')
 assert media.evaluate('document.documentElement.scrollWidth<=innerWidth')
 media.screenshot(path=str(out/'music-mini-mobile.png'))
 media.get_by_role('button',name='回到完整播放器',exact=True).click()
 media.wait_for_function("document.querySelector('#view-music .music-layout').scrollTop<2")
 assert media.locator('#music-mini-player').is_hidden()
 # Desktop retains the existing complete player.
 media.set_viewport_size({'width':1440,'height':900})
 assert media.locator('#music-mini-player').is_hidden()
 media.set_viewport_size({'width':390,'height':844})
 # Failure on page two must not silently replace the queue with the first 50 songs.
 def playlist_failure(route):
  if 'page_token' in parse_qs(urlsplit(route.request.url).query):
   route.fulfill(status=503,json={'error':'Simulated provider outage'})
  else:playlist_page(route)
 media.route('**/api/music/playlist/items?*',playlist_failure)
 media.evaluate("loadPlaylistItems('PL-failure','Interrupted playlist')")
 assert media.evaluate('musicQueue.length')==237
 assert media.locator('#playlist-songs .track-item').count()==0
 assert media.get_by_role('button',name='重新載入歌曲',exact=True).count()==1
 assert media.locator('#playlist-songs').get_attribute('aria-busy')=='false'
 assert '暫時無法開啟歌單' in media.locator('#playlist-songs').inner_text()
 assert '50' not in media.locator('#playlist-songs').inner_text()
 media.unroute('**/api/music/playlist/items?*',playlist_failure)
 media.get_by_role('button',name='重新載入歌曲',exact=True).click()
 media.wait_for_function("document.querySelectorAll('#playlist-songs .track-item').length===237")
 # Closing the view invalidates a pending older load, even if its response arrives later.
 media.evaluate("""async () => {
 const original=window.fetch;
 window.fetch=(url,...args)=>String(url).startsWith('/api/music/playlist/items?')?
   new Promise(resolve=>window.latePlaylist=resolve):original(url,...args);
 window.cancelledPlaylist=loadPlaylistItems('PL-late','Old request');
 }""")
 assert media.locator('.content-skeleton-row').count()==5
 assert media.locator('#playlist-songs').get_attribute('aria-busy')=='true'
 assert media.locator('#playlist-songs').inner_text()=='正在載入歌單'
 media.evaluate("""async () => {
 closePlaylist();
 latePlaylist(new Response(JSON.stringify({items:[{id:'late',title:'Stale song'}]}),{status:200}));
 await cancelledPlaylist;
 }""")
 assert media.evaluate('musicQueue.length')==237
 probes['playlistPagination']='237 songs/5 pages, order, last-song playback, partial failure and cancelled response PASS'
 media.close()
 # Delayed responses exercise first-load shapes, repeat visits and real failures.
 loading=b.new_page(viewport={'width':390,'height':844})
 loading.on('pageerror',lambda e:errors.append(str(e)))
 loading.route('**/*',intercept)
 loading.goto('http://127.0.0.1:8000/',wait_until='networkidle')
 loading.evaluate("openApp('music')")
 loading.wait_for_timeout(400)
 pending=[]
 loading.route('**/api/music/playlists',lambda route:pending.append(route))
 loading.evaluate("switchTab('playlists')")
 loading.wait_for_function("document.querySelector('#playlists-list .content-skeleton')!==null")
 assert loading.locator('#playlists-list .content-skeleton-row').count()==5
 assert loading.locator('#playlists-list').get_attribute('aria-busy')=='true'
 assert loading.locator('.content-skeleton-rows').first.evaluate("e=>getComputedStyle(e).animationName")=='none'
 loading.locator('#playlists-list').scroll_into_view_if_needed()
 loading.screenshot(path=str(out/'music-loading-mobile.png'))
 loading.set_viewport_size({'width':1440,'height':900})
 assert loading.evaluate('document.documentElement.scrollWidth<=innerWidth')
 loading.screenshot(path=str(out/'music-loading-desktop.png'))
 loading.set_viewport_size({'width':390,'height':844})
 loading.wait_for_function('true')
 assert len(pending)==1
 loading.evaluate("void loadPlaylists()")
 loading.wait_for_timeout(50)
 assert len(pending)==1  # Repeated navigation must not duplicate a pending request.
 pending.pop().fulfill(status=200,json={'playlists':[{'id':'PL-qa','title':'Saved playlist','count':237}]})
 loading.wait_for_function("document.querySelector('#playlists-list').textContent.includes('Saved playlist')")
 loading.evaluate("switchTab('search');switchTab('playlists')")
 loading.wait_for_function("document.querySelector('#playlists-list').getAttribute('aria-busy')==='true'")
 assert loading.locator('#playlists-list .content-skeleton').count()==0
 assert 'Saved playlist' in loading.locator('#playlists-list').inner_text()
 loading.wait_for_timeout(50)
 pending.pop().fulfill(status=503,json={'error':'private provider diagnostic'})
 loading.get_by_role('button',name='重試',exact=True).wait_for()
 assert 'Saved playlist' in loading.locator('#playlists-list').inner_text()
 assert 'private provider diagnostic' not in loading.locator('#playlists-list').inner_text()
 assert loading.locator('#playlists-list').get_attribute('aria-busy')=='false'
 loading.get_by_role('button',name='重試',exact=True).click()
 loading.wait_for_timeout(50)
 pending.pop().fulfill(status=200,json={'playlists':[]})
 loading.wait_for_function("document.querySelector('#playlists-list').getAttribute('aria-busy')==='false'")
 assert loading.locator('#playlists-list .content-refresh-error').count()==0
 histories=[]
 loading.route('**/api/music/history',lambda route:histories.append(route))
 loading.evaluate("delete document.querySelector('#history-list').dataset.musicSource;switchTab('history')")
 loading.wait_for_function("document.querySelector('#history-list .content-skeleton')!==null")
 loading.wait_for_timeout(50)
 histories.pop().fulfill(status=200,json={'items':[{'id':'aaaaaaaaaaa','title':'Recent song'}]})
 loading.wait_for_function("document.querySelector('#history-list').textContent.includes('Recent song')")
 loading.evaluate("switchTab('search');switchTab('history')")
 assert 'Recent song' in loading.locator('#history-list').inner_text()
 assert loading.locator('#history-list .content-skeleton').count()==0
 loading.wait_for_timeout(50)
 histories.pop().fulfill(status=200,json={'items':[]})
 loading.wait_for_function("document.querySelector('#history-list').getAttribute('aria-busy')==='false'")
 assert loading.evaluate('musicQueue.length')==0
 # Search races must not allow an older query to overwrite the current one.
 searches=[]
 loading.route('**/api/music/search?*',lambda route:searches.append(route))
 loading.evaluate("switchTab('search');document.querySelector('#yt-search-input').value='first';void searchYouTube()")
 loading.wait_for_timeout(50)
 loading.evaluate("document.querySelector('#yt-search-input').value='second';void searchYouTube()")
 loading.wait_for_timeout(50)
 assert len(searches)==2
 searches[1].fulfill(status=200,json={'items':[{'id':'bbbbbbbbbbb','title':'Newest result'}]})
 loading.wait_for_function("document.querySelector('#yt-results').textContent.includes('Newest result')")
 searches[0].fulfill(status=200,json={'items':[{'id':'aaaaaaaaaaa','title':'Stale result'}]})
 loading.wait_for_timeout(50)
 assert 'Stale result' not in loading.locator('#yt-results').inner_text()
 # Other app entry points use the same static, responsive visual language.
 files=[]
 loading.route('**/api/drive/files?*',lambda route:files.append(route))
 loading.evaluate("openApp('drive')")
 loading.wait_for_function("document.querySelector('#file-container .content-skeleton')!==null")
 assert loading.locator('#file-container .fa-spin').count()==0
 assert loading.evaluate('document.documentElement.scrollWidth<=innerWidth')
 loading.wait_for_timeout(400)
 loading.screenshot(path=str(out/'drive-loading-mobile.png'))
 for route in files:route.fulfill(status=200,json={'files':[]})
 loading.wait_for_function("document.querySelector('#file-container .content-skeleton')===null")
 loading.close()
 probes['loadingPresentation']='static placeholders, retained refresh, retry, deduplication, stale search isolation and mobile Drive PASS'
 probes['mediaSession']='metadata, prepared transition, buffering state, scrub, warm-up failure, controls and unsupported API PASS'
 report={'scope':'Mocked API, external CDN blocked; no real account mutations','panels':results,'missingHandlers':inventory,'probes':probes,'consoleErrors':errors}
 (out/'interface-test-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 assert not inventory, inventory
 assert probes['tasks'] is False and probes['money']==0 and probes['music'] is False, probes
 assert probes['executed']==0 and not probes['taskUndefined'],probes
 assert probes['taskDraftAfter500']=='Draft must stay',probes
 assert not errors,errors
 print(json.dumps(report,ensure_ascii=True))
 b.close()
