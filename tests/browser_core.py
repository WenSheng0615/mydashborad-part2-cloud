"""Real browser + real isolated SQLite; Google consent is separately manual."""
import os,sys,tempfile,subprocess,time,socket
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
with socket.socket() as probe:
    probe.bind(('127.0.0.1',0))
    port=probe.getsockname()[1]
base=f'http://127.0.0.1:{port}'
with tempfile.TemporaryDirectory(prefix='ff-e2e-') as tmp:
    env=dict(os.environ,PYTHON_DOTENV_DISABLED='1',DATABASE_URL='sqlite:///'+Path(tmp).as_posix()+'/test.db',COOKIE_SECURE='false',RENDER_EXTERNAL_URL=base,OAUTH_REDIRECT_URI=base+'/api/auth/callback',REDIS_URL='redis://127.0.0.1:1')
    for k in ('GOOGLE_CREDENTIALS','GOOGLE_TOKEN','FIREBASE_KEY_FILE','FIREBASE_KEY_CONTENT','FIREBASE_STORAGE_BUCKET'): env[k]=''
    subprocess.run([sys.executable,'migrate_db.py'],cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
    with open(Path(tmp)/'server.log','w') as log:
        server=subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            for _ in range(100):
                try:
                    if requests.get(base+'/health/ready',timeout=1).status_code==200: break
                except requests.RequestException: pass
                if server.poll() is not None: raise RuntimeError('Isolated server exited during startup')
                time.sleep(.1)
            else: raise RuntimeError('Isolated server readiness timed out')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                page=browser.new_page(service_workers='block')
                page.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base) else r.abort())
                page.goto(base+'/api/auth/guest');page.wait_for_load_state('networkidle')
                assert page.url==base+'/'
                for width in (320,390,1440):
                    page.set_viewport_size({'width':width,'height':960})
                    trigger=page.get_by_role('button',name='開啟帳號選單',exact=True)
                    trigger.click()
                    expect(page.locator('.account-panel:not([hidden])')).to_be_visible()
                    expect(page.locator('.account-panel:not([hidden])').get_by_role('link',name='服務連線')).to_have_attribute('href','/account#connections')
                    box=page.locator('.account-panel:not([hidden])').bounding_box()
                    assert box['x'] >= 0 and box['x']+box['width'] <= width+1
                    trigger.press('Escape');expect(trigger).to_be_focused()
                    expect(trigger).to_have_attribute('aria-expanded','false')
                    trigger.press('ArrowDown')
                    expect(page.locator('.account-panel:not([hidden])').get_by_role('link',name='帳號與資料')).to_be_focused()
                    page.keyboard.press('Escape')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                if os.getenv('FOCUSFLOW_E2E_ARTIFACTS'):
                    output=Path(os.environ['FOCUSFLOW_E2E_ARTIFACTS']);output.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(output/'home-account-desktop.png'))
                    page.set_viewport_size({'width':390,'height':844})
                    page.get_by_role('button',name='開啟帳號選單',exact=True).click()
                    page.screenshot(path=str(output/'home-account-mobile.png'))
                    page.keyboard.press('Escape')
                page.goto(base+'/projects');page.wait_for_load_state('networkidle')
                expect(page.locator('.onboarding')).to_be_visible()
                page.set_viewport_size({'width':1440,'height':960})
                expect(page.locator('.desktop-account .account-trigger')).to_be_visible()
                page.set_viewport_size({'width':390,'height':844})
                expect(page.locator('.rail')).not_to_be_visible()
                page.locator('.mobile-account .account-trigger').click()
                expect(page.locator('.mobile-account .account-panel')).to_be_visible()
                page.keyboard.press('Escape')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,10).map(e=>({tag:e.tagName,id:e.id,cls:e.className,right:e.getBoundingClientRect().right}))")
                page.locator('#rail-toggle').click()
                expect(page.locator('.rail')).to_be_visible()
                page.keyboard.press('Escape')
                expect(page.locator('.rail')).not_to_be_visible()
                page.set_viewport_size({'width':1440,'height':960})
                page.locator('#new-workspace').click();page.locator('[name=name]').fill('E2E Space');page.locator('#editor-save').click()
                expect(page.locator('#editor')).not_to_be_visible()
                expect(page.get_by_role('button',name='＋ 建立第一個專案',exact=True)).to_be_visible()
                page.locator('#new-project').click();page.locator('[name=name]').fill('E2E Project');page.locator('#editor-save').click()
                expect(page.locator('#page-title')).to_have_text('E2E Project')
                page.get_by_role('button',name='＋ 新增任務',exact=True).click();page.locator('[name=title]').fill('E2E Task');page.locator('#editor-save').click()
                expect(page.get_by_role('heading',name='E2E Task')).to_be_visible()
                page.get_by_label('任務狀態：E2E Task').select_option('done');expect(page.get_by_label('任務狀態：E2E Task')).to_have_value('done')
                page.get_by_role('tab',name='筆記 · 0',exact=True).click()
                page.get_by_role('button',name='＋ 新增筆記',exact=True).click();page.locator('[name=title]').fill('E2E Note');page.locator('[name=content]').fill('Daily evidence');page.locator('#editor-save').click()
                expect(page.get_by_role('heading',name='E2E Note')).to_be_visible()
                page.get_by_role('button',name='封存專案',exact=True).click();expect(page.get_by_role('button',name='取消封存',exact=True)).to_be_visible()
                expect(page.get_by_role('heading',name='E2E Note')).to_be_visible()
                page.get_by_role('button',name='取消封存',exact=True).click();expect(page.get_by_role('button',name='封存專案',exact=True)).to_be_visible()
                page.reload();expect(page.locator('#page-title')).to_have_text('E2E Project')
                expect(page.get_by_role('tab',name='筆記 · 1')).to_have_attribute('aria-selected','true')
                expect(page.get_by_role('heading',name='E2E Note')).to_be_visible()
                page.get_by_role('tab',name='筆記 · 1').press('ArrowRight')
                expect(page.get_by_role('tab',name='連結 · 0')).to_be_focused()
                expect(page.get_by_role('tabpanel',name='連結 · 0')).to_be_visible()
                page.get_by_role('button',name='＋ 新增連結',exact=True).click()
                page.locator('[name=title]').fill('Reference');page.locator('[name=url]').fill('https://example.com')
                page.locator('#editor-save').click()
                expect(page.get_by_role('link',name='Reference',exact=True)).to_be_visible()
                page.reload();expect(page.get_by_role('tab',name='連結 · 1')).to_have_attribute('aria-selected','true')
                page.get_by_role('tab',name='任務 · 1').click()
                # Reference UI: mobile project controls, sidebar focus, dates and themes.
                for width in (360,390,650,760,820,1440):
                    page.set_viewport_size({'width':width,'height':960})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Project overflow at {width}'
                    expect(page.get_by_label('任務狀態：E2E Task')).to_be_visible()
                    expect(page.locator('.row .meta').first).to_be_visible()
                    if width <= 760:
                        page.locator('#rail-toggle').click()
                        page.get_by_role('button',name='▧ E2E Project',exact=True).click()
                        expect(page.locator('#rail-toggle')).to_be_focused()
                        expect(page.locator('.rail')).not_to_be_visible()
                        page.get_by_role('button',name='＋ 新增任務',exact=True).click()
                        expect(page.locator('#editor')).to_be_visible()
                        page.locator('#editor-cancel').click()
                if os.getenv('FOCUSFLOW_E2E_ARTIFACTS'):
                    output=Path(os.environ['FOCUSFLOW_E2E_ARTIFACTS']);output.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(output/'project-desktop.png'),full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    page.screenshot(path=str(output/'project-mobile.png'),full_page=True)
                page.set_viewport_size({'width':1440,'height':960})
                page.locator('#today-nav').click()
                expect(page.locator('.stat-grid')).to_be_visible()
                expect(page.locator('.daily-primary [data-group=today]')).to_be_visible()
                expect(page.locator('.daily-primary [data-group=overdue]')).to_have_count(0)
                expect(page.locator('.task-disclosure')).to_have_count(2)
                expect(page.locator('.task-disclosure').first).not_to_have_attribute('open','')
                page.get_by_role('button',name='＋ 新增今天的任務').click()
                page.locator('[name=title]').fill('Today focus task');page.locator('#editor-save').click()
                expect(page.locator('.daily-primary')).to_contain_text('Today focus task')
                page.locator('.task-disclosure summary').first.click()
                expect(page.locator('.task-disclosure').first.locator('.empty')).to_be_visible()
                if os.getenv('FOCUSFLOW_E2E_ARTIFACTS'):
                    page.screenshot(path=str(output/'today-desktop.png'),full_page=True)
                page.evaluate("localStorage.setItem('theme','dark')")
                page.reload();page.wait_for_load_state('networkidle')
                assert not page.locator('body').evaluate("e=>e.classList.contains('light-mode')")
                page.evaluate("localStorage.setItem('theme','light')")
                page.reload();page.wait_for_load_state('networkidle')
                assert page.locator('body').evaluate("e=>e.classList.contains('light-mode')")
                page.locator('#search-input').fill('E2E');page.locator('#search-form button').click();expect(page.locator('#content')).to_contain_text('E2E Task')
                # Site-wide visual consistency audit, with no external service writes.
                page.goto(base+'/');page.wait_for_load_state('networkidle')
                for app in ('music','drive','notes','calendar','tasks','money','chat','settings','quiz','modules'):
                    if app in ('music','drive','calendar','tasks'):
                        # Layout-only inspection: keep guest authorization and cloud APIs unchanged.
                        page.evaluate("name=>{document.getElementById('launcher').classList.add('hidden');document.getElementById('workspace').classList.add('active');document.getElementById('sidebar').classList.add('active');document.querySelectorAll('.app-view').forEach(e=>e.classList.toggle('active',e.id==='view-'+name));}",app)
                    else:
                        page.evaluate('(name)=>openApp(name)',app)
                    expect(page.locator('#view-'+app)).to_be_visible()
                    for width in (390,1440):
                        page.set_viewport_size({'width':width,'height':960})
                        expect(page.locator('#view-'+app+' .account-trigger')).to_be_visible()
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{app} body overflow at {width}'
                        if os.getenv('FOCUSFLOW_E2E_ARTIFACTS'):
                            output=Path(os.environ['FOCUSFLOW_E2E_ARTIFACTS']);output.mkdir(parents=True,exist_ok=True)
                            page.screenshot(path=str(output/f'audit-{app}-{width}.png'),animations='disabled')
                    page.evaluate('goHome()')
                # Real persisted module preferences, mobile navigation, data preservation.
                page.goto(base+'/');page.wait_for_load_state('networkidle')
                page.set_viewport_size({'width':390,'height':844})
                page.evaluate("openApp('modules')")
                expect(page.locator('#module-list .module-row')).to_have_count(8)
                expect(page.locator('#module-core-list .module-row')).to_have_count(2)
                expect(page.locator('[data-module-card="calendar"]')).to_contain_text('可連接外部服務')
                first=page.locator('#module-list .module-tile').first.bounding_box()
                assert first['height']<=100, first
                third=page.locator('#module-list .module-tile').nth(2).bounding_box()
                assert third['y']+third['height']<844-68, third
                page.get_by_role('button',name='行事曆詳細資料',exact=True).click()
                expect(page.locator('#module-detail')).to_contain_text('尚未連接 Google 帳號')
                page.keyboard.press('Escape')
                page.locator('#module-search').fill('Google')
                expect(page.locator('#module-list .module-row')).to_have_count(3)
                page.locator('#module-search').fill('no matching app')
                expect(page.locator('#module-empty')).to_be_visible()
                page.locator('#module-search').fill('')
                page.get_by_role('button',name='筆記詳細資料',exact=True).click()
                expect(page.locator('#module-detail')).to_be_visible()
                expect(page.locator('#module-detail-body')).to_contain_text('停用不會刪除資料')
                page.keyboard.press('Escape')
                expect(page.locator('#module-detail')).not_to_be_visible()
                page.get_by_role('button',name='行事曆詳細資料',exact=True).click()
                page.get_by_role('button',name='管理 iCloud 連線',exact=True).click()
                expect(page.locator('#page-title')).to_have_text('服務連線')
                page.goto(base+'/');page.wait_for_load_state('networkidle');page.evaluate("openApp('modules')")
                page.get_by_role('button',name='行事曆詳細資料',exact=True).click()
                page.get_by_role('button',name='檢查連線',exact=True).click()
                expect(page.locator('#module-check-status')).to_contain_text('檢查完成')
                expect(page.locator('#module-detail')).to_contain_text('尚未連接 Google 帳號')
                page.keyboard.press('Escape')
                list_y=page.locator('#module-list').bounding_box()['y']
                page.get_by_role('checkbox',name='啟用筆記',exact=True).uncheck()
                expect(page.locator('#flow-toast')).to_contain_text('已儲存')
                assert abs(page.locator('#module-list').bounding_box()['y']-list_y)<1
                expect(page.locator('#flow-toast')).to_be_visible()
                toast_box=page.locator('#flow-toast').bounding_box();dock_box=page.locator('.mobile-dock').bounding_box()
                assert toast_box['y']+toast_box['height']<=dock_box['y']
                expect(page.locator('#flow-toast')).not_to_be_visible(timeout=4500)
                assert abs(page.locator('#module-list').bounding_box()['y']-list_y)<1
                page.evaluate("FlowUI.toast('第一則');FlowUI.toast('第二則')")
                expect(page.locator('#flow-toast')).to_have_count(1)
                expect(page.locator('#flow-toast')).to_contain_text('第二則')
                page.get_by_role('button',name='關閉通知',exact=True).click()
                expect(page.locator('#flow-toast')).not_to_be_visible()

                expect(page.locator('[data-module-id="notes"].app-icon-card')).not_to_be_visible()
                assert page.request.get(base+'/api/notes/').status==403
                page.locator('[data-module-filter=disabled]').click()
                expect(page.locator('#module-list .module-row')).to_have_count(1)
                page.locator('[data-module-filter=all]').click()
                page.get_by_role('checkbox',name='啟用行事曆',exact=True).uncheck()
                expect(page.locator('[data-dock="calendar"]')).not_to_be_visible()
                page.goto(base+'/projects');page.wait_for_load_state('networkidle')
                expect(page.locator('[data-dock="calendar"]')).not_to_be_visible()
                page.goto(base+'/');page.wait_for_load_state('networkidle')
                expect(page.locator('[data-module-id="notes"].app-icon-card')).not_to_be_visible()
                page.evaluate("openApp('notes')")
                expect(page.locator('#alert-modal')).to_be_visible()
                page.locator('#alert-modal button').click()
                page.evaluate("openApp('modules')")
                page.get_by_role('checkbox',name='啟用筆記',exact=True).check()
                expect(page.locator('#flow-toast')).to_contain_text('已儲存')
                assert any(n['title']=='E2E Note' for n in page.request.get(base+'/api/notes/').json()['notes'])
                page.get_by_role('checkbox',name='啟用行事曆',exact=True).check()
                expect(page.locator('[data-dock="calendar"]')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,10).map(e=>({tag:e.tagName,id:e.id,cls:e.className,right:e.getBoundingClientRect().right}))")
                if os.getenv('FOCUSFLOW_E2E_ARTIFACTS'):
                    output=Path(os.environ['FOCUSFLOW_E2E_ARTIFACTS']);output.mkdir(parents=True,exist_ok=True)
                    page.locator('#view-modules').evaluate('(el)=>el.scrollTop=0')
                    page.evaluate("FlowUI.toast('已儲存',{duration:0,kind:'success'})")
                    page.screenshot(path=str(output/'modules-mobile.png'),animations='disabled')
                    page.evaluate("FlowUI.toast('')")
                    page.set_viewport_size({'width':1440,'height':960})
                    page.screenshot(path=str(output/'modules-desktop.png'),animations='disabled')
                page.goto(base+'/account');page.wait_for_load_state('networkidle')
                expect(page.locator('#page-title')).to_have_text('帳號與資料')
                assert page.locator('body').evaluate("e=>e.classList.contains('light-mode')")
                expect(page.locator('.brand img')).to_have_attribute('src','/static/icons/icon.svg?v=20261114')
                expect(page.locator('#account-header-control .account-trigger')).to_be_visible()
                assert page.locator('body').evaluate("e=>getComputedStyle(e).backgroundColor")=='rgb(237, 242, 246)'
                page.evaluate("localStorage.setItem('theme','dark')")
                page.reload();page.wait_for_load_state('networkidle')
                assert not page.locator('body').evaluate("e=>e.classList.contains('light-mode')")
                page.evaluate("localStorage.setItem('theme','light')")
                page.reload();page.wait_for_load_state('networkidle')

                expect(page.locator('#content')).to_contain_text('你的試用空間')
                for width in (320,390,768,1440):
                    page.set_viewport_size({'width':width,'height':900})
                    page.locator('nav [data-page=connections]').click()
                    expect(page.locator('#page-title')).to_have_text('服務連線')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.locator('[data-action=connect][data-id=icloud]').click()
                    expect(page.locator('#dialog-title')).to_have_text('保存你的試用空間')
                    page.locator('#cancel-dialog').click();expect(page.locator('#dialog')).not_to_be_visible()
                    page.locator('nav [data-page=account]').click()
                    expect(page.locator('#page-title')).to_have_text('帳號與資料')
                if os.getenv('FOCUSFLOW_E2E_ARTIFACTS'):
                    page.set_viewport_size({'width':390,'height':844})
                    page.screenshot(path=str(output/'account-mobile.png'),full_page=True)
                    page.locator('nav [data-page=connections]').click()
                    expect(page.locator('#page-title')).to_have_text('服務連線')
                    page.screenshot(path=str(output/'connections-mobile.png'),full_page=True)
                page.goto(base+'/');page.wait_for_load_state('networkidle');page.evaluate("openApp('music');switchTab('playlists')")
                expect(page.locator('#playlists-list a')).to_have_attribute('href','/account#connections')
                page.goto(base+'/api/auth/logout');assert page.request.get(base+'/api/workspaces').status==401
                page.goto(base+'/')
                expect(page.locator('.home-actions .account-login')).to_have_text('登入')
                page.set_viewport_size({'width':320,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                browser.close()
                print('Browser core workflow PASS (guest identity; no Google consent automation)')
        finally:
            if os.name == 'nt':
                # venv Python can launch a child interpreter; close the entire test tree.
                subprocess.run(['taskkill','/PID',str(server.pid),'/T','/F'],
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
            else:
                server.terminate()
            server.wait(timeout=10)
            log.close()
