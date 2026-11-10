"""Local headless Chromium integration experiment; no production credentials."""
import base64,json,os,socket,sqlite3,subprocess,time,urllib.request,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
import websocket

ROOT=Path(__file__).resolve().parents[5]
OUT=ROOT/'.runtime/d-rf043-ui-recovery'/uuid.uuid4().hex[:8]
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
    cdp('Page.navigate',{'url':web+'/auth/login'})
    wait("!!document.querySelector('input[type=email]')")
    for kind,value in [('email',credentials['email']),('password',credentials['password'])]:
        js("(()=>{let e=document.querySelector('input[type="+kind+"]');e.value="+json.dumps(value)+";e.dispatchEvent(new Event('input',{bubbles:true}));})()")
    js("document.querySelector('form').requestSubmit()")
    wait("location.pathname==='/home'")
    # Navigate through the SPA link to preserve the in-memory account session.
    js("(()=>{let a=[...document.querySelectorAll('a')].find(a=>a.getAttribute('href')==='/plan');if(!a)throw Error('plan link absent');a.click()})()")
    wait("location.pathname==='/plan' && document.body.innerText.includes('行动步骤')")
    (OUT/'tasks.png').write_bytes(base64.b64decode(cdp('Page.captureScreenshot')['data']))
    js("(()=>{let a=[...document.querySelectorAll('button,a')].find(a=>a.textContent.trim()==='日程安排');if(!a)throw Error('schedule tab absent');a.click()})()")
    wait("!![...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='预览任务排程')")
    cdp('Emulation.setTouchEmulationEnabled',{'enabled':True})
    def tap(text):
        rect=js("(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==="+json.dumps(text)+");if(!b||b.disabled)throw Error('button unavailable');b.scrollIntoView({block:'center'});const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
        cdp('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[rect]})
        cdp('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    js("""window.__requests=[];window.__originalFetch=window.fetch;window.__failure='';window.confirm=()=>true;
    window.fetch=async(...args)=>{
      const url=String(args[0]);const commit=url.includes('/schedule/drafts/')&&url.endsWith('/commit');
      if(url.endsWith('/schedule/drafts')&&window.__failure==='preview'){window.__failure='';throw new TypeError('isolated preview offline')}
      if(commit&&window.__failure==='before'){window.__failure='';throw new TypeError('isolated offline before send')}
      const r=await window.__originalFetch(...args);
      if(url.includes('/schedule/drafts'))window.__requests.push({url,body:JSON.parse(args[1].body),status:r.status,response:await r.clone().json()});
      if(commit&&window.__failure==='after'){window.__failure='';throw new TypeError('isolated response lost after real commit')}
      return r;
    }""")
    tap('预览任务排程');wait('window.__requests.length===1')
    first=js('window.__requests[0]')
    assert first['status']==200,first
    assert 'window_start' not in first['body'],first
    wait("!!document.querySelector('.schedule-preview')")
    old=first['response']['data'];assert len(old['suggestions'])==2
    assert count()==0
    # Advance only scheduling time beyond the first suggested start, with no data edits.
    clock_file.write_text((datetime.fromisoformat(old['suggestions'][0]['starts_at'].replace('Z','+00:00'))+timedelta(seconds=1)).isoformat(),encoding='utf-8')
    tap('确认整份排程');wait('window.__requests.length===2')
    expired=js('window.__requests[1]');assert expired['status']==409 and expired['response']['detail']['code']=='DRAFT_EXPIRED',expired
    wait("document.body.innerText.includes('草案中的安排已过时')")
    assert js("!![...document.querySelectorAll('.schedule-preview button')].find(b=>b.disabled)"),'Expired draft confirm is still enabled'
    assert count()==0
    with sqlite3.connect(OUT/'web-test.db') as db:
        assert db.execute('select state,committed_at from schedule_drafts where id=?',(old['draft_id'],)).fetchone()==('pending',None)
    # A disabled button cannot issue another request, even via DOM click.
    js("document.querySelector('.schedule-preview button').click()")
    time.sleep(.3);assert js('window.__requests.length')==2
    (OUT/'expired-disabled.png').write_bytes(base64.b64decode(cdp('Page.captureScreenshot',{'captureBeyondViewport':True})['data']))
    js("window.__failure='preview'");tap('重新预览排程')
    wait("document.body.innerText.includes('无法连接在线服务')")
    assert js("!![...document.querySelectorAll('.schedule-preview button')].find(b=>b.disabled)")
    assert js('window.__requests.length')==2 and count()==0
    tap('重新预览排程');wait('window.__requests.length===3')
    fresh=js('window.__requests[2]');assert fresh['status']==200
    fresh_draft=fresh['response']['data'];assert fresh_draft['draft_id']!=old['draft_id']
    wait("!document.querySelector('.notice--danger')")
    assert count()==0
    js("window.__failure='before'");tap('确认整份排程')
    wait("document.body.innerText.includes('无法连接在线服务')")
    assert count()==0 and js('window.__requests.length')==3
    assert js("!![...document.querySelectorAll('.schedule-preview button')].find(b=>!b.disabled)")
    # Real commit succeeds but browser receives a transport error. Keep the same draft for retry.
    js("window.__failure='after'");tap('确认整份排程')
    wait('window.__requests.length===4');wait("document.body.innerText.includes('无法连接在线服务')")
    saved=req(api+'/api/v1/schedule',token=token)['data'];assert len(saved)==len(fresh_draft['suggestions'])==2
    assert js("!![...document.querySelectorAll('.schedule-preview button')].find(b=>!b.disabled)")
    # A late retry must still be idempotent, even though the committed draft is now past.
    clock_file.write_text((datetime.fromisoformat(fresh_draft['suggestions'][-1]['ends_at'].replace('Z','+00:00'))+timedelta(days=1)).isoformat(),encoding='utf-8')
    tap('确认整份排程');wait('window.__requests.length===5');wait("document.body.innerText.includes('整份排程已保存。')")
    retry=js('window.__requests[4]');assert retry['response']['data']['idempotent'] is True
    assert retry['url']==js('window.__requests[3].url')
    assert sorted(x['id'] for x in saved)==sorted(x['id'] for x in req(api+'/api/v1/schedule',token=token)['data'])
    assert not js("!!document.querySelector('.schedule-preview')")
    (OUT/'recovered.png').write_bytes(base64.b64decode(cdp('Page.captureScreenshot',{'captureBeyondViewport':True})['data']))
    results={'browser':'Chrome headless with touch input','viewport':'390x844','requests':js('window.__requests'),'checks':['server-default start','real expired 409 and zero writes','old confirm disabled','failed repreview keeps old confirm disabled','real repreview new draft','offline before send retains draft','lost real commit response retains draft','late same-draft retry idempotent with unchanged row IDs'],'saved_count':count(),'boundary':'Real local API and isolated SQLite. Test-only scheduling clock and transport faults; no mocked API response, no physical device.'}
    (OUT/'web-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(OUT),'checks':results['checks'],'saved_count':count()},ensure_ascii=False));ws.close()
finally:
    for p in reversed(processes):
        p.terminate()
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    for log in handles:log.close()
