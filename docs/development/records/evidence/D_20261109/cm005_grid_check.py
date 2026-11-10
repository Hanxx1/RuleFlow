"""Local headless Chromium integration experiment; no production credentials."""
import base64,json,os,socket,sqlite3,subprocess,time,urllib.request,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
import websocket

ROOT=Path(__file__).resolve().parents[5]
OUT=ROOT/'.runtime/d-cm005-grid'/uuid.uuid4().hex[:8]
OUT.mkdir(parents=True,exist_ok=True)
PY=str(ROOT/'.runtime/review-venv/Scripts/python.exe')
def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); return s.getsockname()[1]
api_port,web_port,debug_port=port(),port(),port()
api=f'http://127.0.0.1:{api_port}'
web=f'http://127.0.0.1:{web_port}'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def req(url,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    request=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    with opener.open(request,timeout=5) as r: return json.load(r)
def wait_http(url):
    for _ in range(100):
        try:
            with opener.open(url,timeout=1): return
        except Exception: time.sleep(.2)
    raise RuntimeError('Service did not start: '+url)
env=dict(os.environ,APP_ENV='development',DEMO_MODE='false',DATABASE_PATH=str(OUT/'web-test.db'),
         VAULT_UPLOAD_ROOT=str(OUT/'vault'),DOCUMENT_UPLOAD_ROOT=str(OUT/'documents'),
         DEMO_UPLOAD_ROOT=str(OUT/'demo'),LLM_BASE_URL='',LLM_MODEL='',LLM_API_KEY='',
         VITE_API_BASE=api,CORS_ORIGINS=web)
clock_file=OUT/'clock.txt'
clock_file.write_text('real',encoding='utf-8')
# Test-only ASGI wrapper; authentication and all other clocks remain real.
wrapper="""import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0,SERVER)
from app.main import app
from app.api import planning
from app.services import schedule_drafts
class SchedulingClock(datetime):
    @classmethod
    def now(cls,tz=None):
        value=Path(CLOCK).read_text(encoding='utf-8')
        if value=='real':return datetime.now(tz)
        instant=datetime.fromisoformat(value)
        return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
planning.datetime=SchedulingClock
schedule_drafts.datetime=SchedulingClock
""".replace('SERVER',repr(str(ROOT/'server'))).replace('CLOCK',repr(str(clock_file)))
(OUT/'test_app.py').write_text(wrapper,encoding='utf-8')
processes=[]; handles=[]
def launch(args,cwd,environment=env):
    log=open(OUT/('service-'+str(len(processes))+'.log'),'w',encoding='utf-8');handles.append(log)
    p=subprocess.Popen(args,cwd=cwd,env=environment,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    processes.append(p);return p
try:
    launch([PY,'-m','uvicorn','test_app:app','--app-dir',str(OUT),'--host','127.0.0.1','--port',str(api_port)],ROOT)
    launch(['node',str(ROOT/'mobile/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',str(web_port),'--strictPort'],ROOT/'mobile')
    wait_http(api+'/health');wait_http(web)
    credentials={'email':'d-web-'+uuid.uuid4().hex[:8]+'@example.com','password':uuid.uuid4().hex}
    registered=req(api+'/api/v1/auth/register',credentials)['data']
    req(api+'/api/v1/auth/verify',{'token':registered['development_verification_token']})
    token=req(api+'/api/v1/auth/login',credentials)['data']['access_token']
    cid=req(api+'/api/v1/imports/text',{'text':'请填写申请表。请上传作品。','consent':True},token)['data']['case_id']
    review=req(api+'/api/v1/cases/'+cid+'/reviews',token=token)['data']
    req(api+'/api/v1/cases/'+cid+'/confirm',{'revision':review['revision'],'action_ids':[x['id'] for x in review['candidate']['actions']],'no_deadline':True,'consent':True},token)
    launch(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu',
            '--no-first-run','--no-default-browser-check',f'--remote-debugging-port={debug_port}',
            '--remote-allow-origins=http://localhost',f'--user-data-dir={OUT / "browser-profile"}','about:blank'],ROOT)
    wait_http(f'http://127.0.0.1:{debug_port}/json')
    target=next(x for x in req(f'http://127.0.0.1:{debug_port}/json') if x['type']=='page')
    ws=websocket.create_connection(target['webSocketDebuggerUrl'],origin='http://localhost',timeout=15)
    seq=0
    def cdp(method,params=None):
        global seq
        seq+=1;ident=seq;ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
        while True:
            result=json.loads(ws.recv())
            if result.get('id')==ident:
                if 'error' in result:raise RuntimeError(result['error'])
                return result.get('result',{})
    def js(expression):
        r=cdp('Runtime.evaluate',{'expression':expression,'returnByValue':True})
        if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
        return r['result'].get('value')
    def wait(expression):
        for _ in range(100):
            if js(expression):return
            time.sleep(.2)
        raise RuntimeError('UI condition timeout: '+expression+' / '+str(js('document.body.innerText'))[:1000])
    def click(text):
        return js("(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==="+json.dumps(text)+");if(!b)throw Error('button absent');setTimeout(()=>b.click(),0);return true})()")
    def count():return len(req(api+'/api/v1/schedule',token=token)['data'])
    cdp('Page.enable');cdp('Runtime.enable')
    cdp('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
    cdp('Emulation.setTouchEmulationEnabled',{'enabled':True})
    def tap_selector(selector):
        rect=js("(()=>{const b=document.querySelector("+json.dumps(selector)+");if(!b||b.disabled)throw Error('target unavailable');b.scrollIntoView({block:'center',inline:'center'});const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
        cdp('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[rect]});cdp('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    def tap(text):
        js("(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==="+json.dumps(text)+");if(!b)throw Error('button absent');b.setAttribute('data-tap','yes')})()")
        tap_selector('[data-tap=yes]');js("document.querySelector('[data-tap=yes]')?.removeAttribute('data-tap')")
    def date(day):
        js("(()=>{const e=document.querySelector('.date-picker input');e.value="+json.dumps(day)+";e.dispatchEvent(new Event('change',{bubbles:true}))})()")
        wait("document.querySelector('.date-nav').innerText.includes("+json.dumps(day)+")")
    def screenshot(name):
        (OUT/(name+'.png')).write_bytes(base64.b64decode(cdp('Page.captureScreenshot',{'captureBeyondViewport':True})['data']))
    def snapshot():
        expression="""(async()=>{const dbs=await indexedDB.databases();const data={local:{...localStorage},session:{...sessionStorage},dbs:{}};for(const info of dbs){await new Promise((resolve,reject)=>{const q=indexedDB.open(info.name);q.onerror=reject;q.onsuccess=()=>{const db=q.result;const names=[...db.objectStoreNames];if(!names.length){db.close();resolve();return}const tx=db.transaction(names,'readonly');data.dbs[info.name]={};for(const name of names){const r=tx.objectStore(name).getAll();r.onsuccess=()=>data.dbs[info.name][name]=r.result}tx.oncomplete=()=>{db.close();resolve()};tx.onerror=reject}})}return JSON.stringify(data)})()"""
        result=cdp('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
        assert 'exceptionDetails' not in result,result
        return result['result']['value']
    checks=[]
    def open_demo():
        wait("!![...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='查看时间网格样例')")
        # Let the pre-existing parent load finish before measuring demo-side isolation.
        wait("!document.body.innerText.includes('正在整理执行顺序')&&!document.body.innerText.includes('正在生成计划视图')")
        js("window.__gridRequests=[];window.__savedFetch=window.fetch;window.fetch=(...args)=>{window.__gridRequests.push(String(args[0]));return window.__savedFetch(...args)}")
        before=snapshot();tap('查看时间网格样例');wait("!!document.querySelector('.grid-demo')")
        assert not js("!!document.querySelector('.plan-schedule')")
        return before
    def verify_isolation(before,label):
        assert js('window.__gridRequests')==[],js('window.__gridRequests')
        assert snapshot()==before,'Fixture changed browser storage'
        checks.append(label+' isolated')
        js('window.fetch=window.__savedFetch')
    # Offline entry with original demo still available after returning.
    cdp('Page.navigate',{'url':web+'/plan?tab=schedule'});before=open_demo()
    assert js("document.querySelector('.date-nav').innerText.includes('2026-11-09')")
    assert js("document.querySelector('.grid-block[data-item=K1-A]').style.top==='1620px'")
    assert js("document.querySelector('.grid-block[data-item=K1-A]').getBoundingClientRect().height===180")
    assert js("document.querySelector('.grid-block[data-item=T2]').innerText.includes('时间重叠')") is False
    screenshot('day')
    tap('周视图');wait("document.querySelectorAll('.grid-day').length===7")
    screenshot('week-overlap')
    # Short titles remain readable without stretching their time geometry.
    for width,height in [(360,800),(390,844),(844,390)]:
        cdp('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':True})
        assert js("(()=>{const b=document.querySelector('[data-short-item=T3]'),t=b.querySelector('strong'),r=b.getBoundingClientRect();return r.height>=44&&t.scrollHeight<=t.clientHeight&&t.scrollWidth<=t.clientWidth&&getComputedStyle(t).whiteSpace==='normal'})()"),'Short title is clipped or touch target too small'
        assert js("document.querySelector('.grid-block[data-item=T3]').getBoundingClientRect().height===30"),'Short time geometry stretched'
        assert js('document.documentElement.scrollWidth<=innerWidth+1'),'Short title overflows page'
        js("document.querySelector('.grid-short-slots').scrollIntoView({block:'center'})")
        screenshot('short-title-'+str(width))
        tap_selector('[data-short-item=T3]');wait("!!document.querySelector('dialog[open]')")
        assert js("document.querySelector('dialog[open]').innerText.includes('易错步骤')")
        tap('关闭');wait("!document.querySelector('dialog[open]')")
        assert js("document.activeElement.dataset.shortItem==='T3'")
    checks.append('short titles wrap fully at three viewports, touch details and focus return, exact 10-minute geometry')
    for width,height in [(360,800),(390,844),(844,390)]:
        cdp('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':True})
        assert js("document.querySelectorAll('.grid-overlap').length===1")
        assert js("(()=>{const b=document.querySelector('.grid-overlap');return b.dataset.overlapCount==='3'&&b.getBoundingClientRect().width>=b.parentElement.clientWidth-3})()"),'Overlap summary must use full day width'
        assert js("!document.querySelector('.grid-block[data-item=K1-A]')"),'Week still contains narrow overlap lanes'
        tap_selector('.grid-overlap');wait("!!document.querySelector('.overlap-dialog[open]')")
        assert js("document.querySelectorAll('.overlap-item').length===3")
        assert js("[...document.querySelectorAll('.overlap-item strong')].every(e=>e.scrollWidth<=e.clientWidth&&e.scrollHeight<=e.clientHeight)")
        screenshot('overlap-expanded-'+str(width))
        tap_selector('[data-overlap-item=K1-A]');wait("!!document.querySelector('.grid-detail[open]')")
        assert js("!document.querySelector('.overlap-dialog[open]')")
        tap('关闭');wait("!document.querySelector('dialog[open]')")
        assert js("document.activeElement.classList.contains('grid-overlap')")
        tap_selector('.grid-overlap');wait("!!document.querySelector('.overlap-dialog[open]')")
        cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27});cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
        wait("!document.querySelector('dialog[open]')")
        assert js("document.activeElement.classList.contains('grid-overlap')")
        assert js("document.querySelectorAll('.grid-date').length===7")
    checks.append('overlap full-column summary, readable three-item sheet, detail transition and Escape focus return at three widths')

    for width,height in [(360,800),(390,844),(844,390)]:
        cdp('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':True})
        assert js('document.documentElement.scrollWidth<=innerWidth+1'),'Page overflow'
        assert js("document.querySelector('.grid-scroll').scrollWidth<=document.querySelector('.grid-scroll').clientWidth+1")
        js("document.querySelector('.grid-scroll').scrollIntoView({block:'center'});document.querySelector('.grid-scroll').scrollLeft=0;document.querySelector('.grid-scroll').scrollTop=1440")
        rect=js("(()=>{const r=document.querySelector('.grid-scroll').getBoundingClientRect();return {x:Math.min(r.right-30,innerWidth-30),y:Math.max(100,Math.min(r.bottom-40,innerHeight-120))}})()")
        cdp('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[rect]})
        for i in range(1,7):
            cdp('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':rect['x']-i*18,'y':rect['y']-i*8}]});time.sleep(.03)
        cdp('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});time.sleep(.3)
        assert js("document.querySelector('.grid-scroll').scrollLeft===0"),'Week must fit without horizontal scrolling'
        assert js("[...document.querySelectorAll('.grid-date')].every(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth})"),'Seven dates must remain visible'
        assert js("getComputedStyle(document.querySelector('.grid-block strong')).whiteSpace==='normal'"),'Card titles must wrap'
        js("document.querySelector('.grid-scroll').scrollLeft=99999")
        assert js("(()=>{const s=document.querySelector('.grid-scroll').getBoundingClientRect();return Math.abs(document.querySelector('.grid-ruler').getBoundingClientRect().left-s.left)<3&&Math.abs(document.querySelector('.grid-corner').getBoundingClientRect().left-s.left)<3})()"),'Sticky time axis drifts at maximum scroll'
        old_top=js("document.querySelector('.grid-scroll').scrollTop")
        js("document.querySelector('.grid-scroll').scrollIntoView({block:'center'})")
        pos=js("(()=>{const r=document.querySelector('.grid-scroll').getBoundingClientRect();return {x:r.left+80,y:Math.min(r.bottom-35,innerHeight-115)}})()")
        cdp('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[pos]})
        for i in range(1,6):
            cdp('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':pos['x'],'y':pos['y']-i*15}]});time.sleep(.03)
        cdp('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});time.sleep(.3)
        assert js("document.querySelector('.grid-scroll').scrollTop")>old_top,'Vertical touch scroll failed'
        screenshot('week-'+str(width))
    checks.append('G08 three viewport touch scroll and no page overflow')
    cdp('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
    tap_selector('[aria-label="查看2026-11-11日视图"]');wait("document.querySelectorAll('.grid-day').length===1")
    assert js("document.querySelector('.grid-block[data-item=K1-B]').style.top==='2520px'")
    assert js("document.querySelector('.grid-block[data-item=B2]').style.height==='90px'")
    screenshot('midnight')
    tap_selector('.grid-block[data-item=K1-B]');wait("!!document.querySelector('dialog[open]')")
    assert js("document.querySelector('dialog[open]').innerText.includes('周一与周三两条时段')")
    screenshot('course-detail');tap('关闭');wait("!document.querySelector('dialog[open]')")
    assert js("document.activeElement.dataset.item==='K1-B'")
    # Keyboard activation, native dialog trap and Escape focus return.
    cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'text':'\r'});cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
    wait("!!document.querySelector('dialog[open]')")
    for _ in range(3):
        cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':'Tab','code':'Tab','windowsVirtualKeyCode':9});cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':'Tab','code':'Tab','windowsVirtualKeyCode':9})
    assert js("!!document.activeElement.closest('dialog')")
    cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27});cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
    wait("!document.querySelector('dialog[open]')");assert js("document.activeElement.dataset.item==='K1-B'")
    cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':' ','code':'Space','windowsVirtualKeyCode':32,'text':' '});cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':' ','code':'Space','windowsVirtualKeyCode':32})
    wait("!!document.querySelector('dialog[open]')");tap('关闭');wait("!document.querySelector('dialog[open]')")
    checks.append('G02/G04/G05/G06/G09/G10 geometry, split, course details and keyboard')
    date('2026-11-13');assert js("document.querySelectorAll('.grid-block').length===0");assert js("!!document.querySelector('.grid-ruler')")
    date('2026-11-14');assert js("!!document.querySelector('[data-short-item=T3]')");assert js("document.querySelector('.grid-block[data-item=T3]').style.top==='2175px'")
    tap_selector('.grid-index summary');tap_selector('[data-index-item=T3]');wait("!!document.querySelector('dialog[open]')");assert js("document.querySelector('dialog[open]').innerText.includes('易错步骤')");tap('关闭')
    date('2026-11-16');assert js("document.querySelector('.grid-block[data-item=B4]').style.height==='90px'")
    date('2026-12-31');tap_selector('[aria-label="后一天"]');wait("document.querySelector('.date-nav').innerText.includes('2027-01-01')")
    tap('周视图');assert js("document.querySelector('.grid-date').getAttribute('aria-label').includes('2026-12-28')")
    assert js("document.querySelector('.grid-empty').textContent.includes('本周')")
    tap('回到样例周');tap('日视图');wait("document.querySelector('.date-nav').innerText.includes('2026-11-09')")
    tap_selector('.exception-toggle input');wait("document.querySelector('.grid-demo').innerText.includes('时间数据异常')")
    for zone in ['UTC','Asia/Shanghai']:
        cdp('Emulation.setTimezoneOverride',{'timezoneId':zone})
        assert js("document.querySelector('.grid-block[data-item=offset]').style.top==='1620px'")
    tap_selector('.grid-block[data-item=missing]');wait("!!document.querySelector('dialog[open]')");assert js("document.querySelector('dialog[open]').innerText.includes('待核对')");tap('关闭')
    checks.append('G03/G07/G11 navigation, empty, offset and malformed/missing evidence')
    verify_isolation(before,'G01 offline');tap('返回日程');wait("!!document.querySelector('.plan-schedule')")
    assert js("document.body.innerText.includes('离线样例计划')")
    # Check both an empty signed-in account and an account with a confirmed Case.
    empty={'email':'grid-empty-'+uuid.uuid4().hex[:8]+'@example.com','password':uuid.uuid4().hex}
    registered=req(api+'/api/v1/auth/register',empty)['data'];req(api+'/api/v1/auth/verify',{'token':registered['development_verification_token']})
    for label,creds in [('empty account',empty),('existing account',credentials)]:
        cdp('Page.navigate',{'url':web+'/auth/login'});wait("!!document.querySelector('input[type=email]')")
        for kind,value in [('email',creds['email']),('password',creds['password'])]:
            js("(()=>{const e=document.querySelector('input[type="+kind+"]');e.value="+json.dumps(value)+";e.dispatchEvent(new Event('input',{bubbles:true}))})()")
        js("document.querySelector('form').requestSubmit()");wait("location.pathname==='/home'")
        js("[...document.querySelectorAll('a')].find(a=>a.getAttribute('href')==='/plan').click()")
        if label=='empty account':wait("document.body.innerText.includes('还没有可执行事项')")
        else:wait("document.body.innerText.includes('行动步骤')&&!document.body.innerText.includes('正在整理执行顺序')")
        before=open_demo();tap('周视图');wait("document.querySelectorAll('.grid-day').length===7");verify_isolation(before,'G01 '+label);tap('返回日程')
    assert count()==0
    checks.append('G12 existing account formal schedule unchanged; RF043 verified separately')
    (OUT/'results.json').write_text(json.dumps({'checks':checks,'boundary':'Isolated real local API accounts; static fixtures; Chrome touch/keyboard, not physical Android.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(OUT),'checks':checks},ensure_ascii=False));ws.close()
finally:
    for p in reversed(processes):
        p.terminate()
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    for log in handles:log.close()
