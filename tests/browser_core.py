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
                page.goto(base+'/projects');page.wait_for_load_state('networkidle')
                expect(page.locator('.onboarding')).to_be_visible()
                page.set_viewport_size({'width':390,'height':844})
                expect(page.locator('.rail')).not_to_be_visible()
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
                page.get_by_role('button',name='＋ 新增筆記',exact=True).click();page.locator('[name=title]').fill('E2E Note');page.locator('[name=content]').fill('Daily evidence');page.locator('#editor-save').click()
                expect(page.get_by_role('heading',name='E2E Note')).to_be_visible()
                page.get_by_role('button',name='封存專案',exact=True).click();expect(page.get_by_role('button',name='取消封存',exact=True)).to_be_visible()
                expect(page.get_by_role('heading',name='E2E Note')).to_be_visible()
                page.get_by_role('button',name='取消封存',exact=True).click();expect(page.get_by_role('button',name='封存專案',exact=True)).to_be_visible()
                page.reload();expect(page.locator('#page-title')).to_have_text('E2E Project')
                page.locator('#search-input').fill('E2E');page.locator('#search-form button').click();expect(page.locator('#content')).to_contain_text('E2E Task')
                # Real persisted module preferences, mobile navigation, data preservation.
                page.goto(base+'/');page.wait_for_load_state('networkidle')
                page.set_viewport_size({'width':390,'height':844})
                page.evaluate("openApp('modules')")
                expect(page.locator('#module-list .module-row')).to_have_count(8)
                expect(page.locator('#module-core-list .module-row')).to_have_count(2)
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
                page.get_by_role('checkbox',name='啟用筆記',exact=True).uncheck()
                expect(page.locator('#module-status')).to_contain_text('已儲存')
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
                expect(page.locator('#module-status')).to_contain_text('已儲存')
                assert any(n['title']=='E2E Note' for n in page.request.get(base+'/api/notes/').json()['notes'])
                page.get_by_role('checkbox',name='啟用行事曆',exact=True).check()
                expect(page.locator('[data-dock="calendar"]')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,10).map(e=>({tag:e.tagName,id:e.id,cls:e.className,right:e.getBoundingClientRect().right}))")
                if os.getenv('FOCUSFLOW_E2E_ARTIFACTS'):
                    output=Path(os.environ['FOCUSFLOW_E2E_ARTIFACTS']);output.mkdir(parents=True,exist_ok=True)
                    page.locator('#view-modules').evaluate('(el)=>el.scrollTop=0')
                    page.screenshot(path=str(output/'modules-mobile.png'))
                    page.set_viewport_size({'width':1440,'height':960})
                    page.screenshot(path=str(output/'modules-desktop.png'))
                page.goto(base+'/api/auth/logout');assert page.request.get(base+'/api/workspaces').status==401
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
