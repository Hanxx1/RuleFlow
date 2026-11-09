"""Historical pre-fix characterization; expects the old defects.
For current regression/acceptance use rf043_ui_recovery.py instead.
"""
import base64,json,os,socket,subprocess,time,urllib.request,uuid
from pathlib import Path
import websocket

ROOT=Path(__file__).resolve().parents[5]
OUT=ROOT/'.runtime/d-rf043-closeout'/uuid.uuid4().hex[:8]
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
processes=[]; handles=[]
def launch(args,cwd,environment=env):
    log=open(OUT/('service-'+str(len(processes))+'.log'),'w',encoding='utf-8');handles.append(log)
    p=subprocess.Popen(args,cwd=cwd,env=environment,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    processes.append(p);return p
try:
    launch([PY,'-m','uvicorn','app.main:app','--app-dir',str(ROOT/'server'),'--host','127.0.0.1','--port',str(api_port)],ROOT)
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
    # Observe real requests before introducing a labelled test-only response seam.
    js("window.__requests=[];window.__originalFetch=window.fetch;window.fetch=async(...args)=>{const r=await window.__originalFetch(...args);if(String(args[0]).includes('/schedule/drafts'))window.__requests.push({url:String(args[0]),body:JSON.parse(args[1].body),status:r.status,response:await r.clone().json()});return r}")
    initial=count()
    for attempt in range(2):
        click('预览任务排程')
        wait("window.__requests.length>="+str(attempt+1))
        wait("document.body.innerText.includes('排程窗口起点不能早于服务器当前时间')")
        wait("!![...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='预览任务排程'&&!b.disabled)")
    assert count()==initial==0
    real_requests=js('window.__requests')
    assert all(r['status']==422 for r in real_requests)
    (OUT/'past-window.png').write_bytes(base64.b64decode(cdp('Page.captureScreenshot',{'captureBeyondViewport':True})['data']))
    # Only to reach the expired-draft UI: future draft and 409 fixture. No real commit.
    js("""window.__fixtureMode=true;window.__commitCalls=0;window.__draftCalls=0;
    window.fetch=async(...args)=>{
      const url=String(args[0]);
      if(window.__fixtureMode&&url.endsWith('/schedule/drafts')){
        window.__draftCalls++;
        return new Response(JSON.stringify({data:{draft_id:'rf043-ui-fixture-'+window.__draftCalls,suggestions:[{task_id:'fixture-task',title:'隔离页面检查任务',starts_at:'2099-01-01T00:00:00Z',ends_at:'2099-01-01T00:30:00Z',scheduled_minutes:30}],unscheduled:[]}}),{status:200,headers:{'Content-Type':'application/json'}});
      }
      if(url.includes('/schedule/drafts/rf043-ui-fixture-')&&url.endsWith('/commit')){
        window.__commitCalls++;
        return new Response(JSON.stringify({detail:{code:'DRAFT_EXPIRED',message:'草案中的安排已过时，请重新预览'}}),{status:409,headers:{'Content-Type':'application/json'}});
      }
      return window.__originalFetch(...args);
    };window.confirm=()=>true""")
    click('预览任务排程');wait("!!document.querySelector('.schedule-preview')")
    click('确认整份排程');wait("document.body.innerText.includes('草案中的安排已过时，请重新预览')")
    wait("!![...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='确认整份排程'&&!b.disabled)")
    old_preview_remains=js("!!document.querySelector('.schedule-preview')")
    click('确认整份排程');wait('window.__commitCalls===2')
    wait("document.body.innerText.includes('草案中的安排已过时，请重新预览')")
    (OUT/'expired-draft.png').write_bytes(base64.b64decode(cdp('Page.captureScreenshot',{'captureBeyondViewport':True})['data']))
    js('window.__fixtureMode=false')
    click('预览任务排程');wait("document.body.innerText.includes('排程窗口起点不能早于服务器当前时间')")
    retained_after_failed_repreview=js("!!document.querySelector('.schedule-preview')")
    js('window.__fixtureMode=true')
    click('预览任务排程');wait('window.__draftCalls===2')
    wait("!document.querySelector('.notice--danger')")
    assert count()==0
    results={'browser':'Chrome headless','viewport':'390x844','real_api':{'past_window_requests':real_requests,'schedule_count':count()},'fixture_only_expired_ui':{'message_visible':True,'old_preview_remains':old_preview_remains,'repeat_commit_calls':js('window.__commitCalls'),'retained_after_real_repreview_failure':retained_after_failed_repreview,'fixture_success_replaces_preview_and_clears_error':True},'note':'Past-window uses real local API. Expired response and successful draft are fetch fixtures, not full expired-draft E2E acceptance.'}
    (OUT/'web-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(OUT),'results':results},ensure_ascii=False));ws.close()
finally:
    for p in reversed(processes):
        p.terminate()
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    for log in handles:log.close()
