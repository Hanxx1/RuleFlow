import {createRequire} from 'node:module';import path from 'node:path';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(path.join(process.env.ZHISHI_BROWSER_MODULE_ROOT,'playwright'));
const origin='http://127.0.0.1:5173',browser=await chromium.launch({headless:true,channel:'msedge'});
try{for(const width of [360,390]){
 const page=await browser.newPage({viewport:{width,height:844},isMobile:true});let uploaded=false,retries=0;
 await page.route('**/api/**',async route=>{const url=new URL(route.request().url());let data={};
  if(url.pathname==='/api/v1/auth/login')data={user:{id:'attachment-test',email:'synthetic@example.com'},access_token:'synthetic',refresh_token:'synthetic'};
  else if(url.pathname==='/api/v1/dashboard')data={date:'2026-10-14',timezone:'Asia/Shanghai',total_cases:1,in_progress_cases:0,due_soon_cases:0,completed_cases:0,today_tasks:[],recent_cases:[{id:'test-case',title:'测试通知',relevance:'UNKNOWN',status:'review'}]};
  else if(url.pathname==='/api/v1/cases/test-case')data={id:'test-case',title:'测试通知',relevance:'UNKNOWN',status:'review'};
  else if(url.pathname.endsWith('/resources'))data={rules:[],evidence:[{id:'block:notice',text:'请填写附件1申请表'}],tasks:[],materials:[],facts:[],evaluation:{},attachments:{missing_count:uploaded?0:1,items:[{title:'申请表',state:uploaded?'obtained':'missing',quote:'请填写附件1申请表',evidence_ids:['block:notice'],warning:'需要核对'}]}};
  else if(url.pathname.endsWith('/attachments')&&route.request().method()==='POST'){uploaded=true;assert.ok(route.request().postData().includes('consent'));data={status:'parsed'};}
  else if(url.pathname.endsWith('/analysis/retry')){assert.equal(route.request().postDataJSON().consent,true);retries++;data={analysis_mode:'local'};}
  await route.fulfill({contentType:'application/json',body:JSON.stringify({data})});
 });
 await page.goto(origin+'/auth/login');await page.locator('input[type=email]').fill('synthetic@example.com');await page.locator('input[type=password]').fill('Synthetic-Password');await page.getByRole('button',{name:'提交',exact:true}).click();await page.waitForURL('**/home');await page.getByRole('link',{name:/测试通知/}).click();
 const panel=page.getByRole('region',{name:'通知附件完整度'});try{await panel.getByText(/还缺 1 项附件/).waitFor({timeout:5000})}catch(e){console.error('TEST UI',page.url(),(await page.locator('body').innerText()).slice(0,1500));throw e}
 await panel.getByLabel('补充通知附件').setInputFiles({name:'附件1申请表.txt',mimeType:'text/plain',buffer:Buffer.from('填写申请表（合成测试）')});
 assert.equal(await panel.getByRole('button',{name:'确认上传附件'}).isDisabled(),true);await panel.locator('.consent-row input').check();await panel.getByRole('button',{name:'确认上传附件'}).click();await panel.getByText(/申请表 · 已取得/).waitFor();assert.equal(uploaded,true);
 page.on('dialog',d=>d.accept());await panel.getByRole('button',{name:'用补充附件重新分析'}).click();await page.waitForTimeout(200);assert.equal(retries,1);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.close();console.log(`PASS ${width}px: missing attachment reminder, explicit consent, receipt and reanalysis`);
}}finally{await browser.close()}
