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
                page.locator('#new-workspace').click();page.locator('[name=name]').fill('E2E Space');page.locator('#editor-save').click()
                expect(page.locator('#editor')).not_to_be_visible()
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
