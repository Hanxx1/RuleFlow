// Uses an existing Playwright installation; no production dependency is added.
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.ZHISHI_BROWSER_MODULE_ROOT?path.join(process.env.ZHISHI_BROWSER_MODULE_ROOT,'playwright'):'playwright');
const origin=process.env.ZHISHI_UI_TEST_ORIGIN||'http://127.0.0.1:5193';
const browser=await chromium.launch({headless:true,channel:process.env.ZHISHI_TEST_BROWSER_CHANNEL||'msedge'});
try{
 for(const width of [360,390]){
  const page=await browser.newPage({viewport:{width,height:844},isMobile:true,hasTouch:true});
  let confirmed=false,stale=true,writes=0,previewFail=true,previewAuthorization='',profileWrites=0,knowledgeSaved=false,draftStale=true,draftCommits=0,interestWrites=0,planningWrites=0,retryWrites=0,attachmentWrites=0;
  page.on('dialog',dialog=>dialog.accept());
  const candidate={actions:[{id:'action:0',title:'准备申请表',origin:'suggestion',evidence_ids:['block:one'],evidence_quotes:{'block:one':'请准备申请表。'}}],dates:[{id:'date:one',raw:'10月25日',value:null,role:'deadline',quote:'请于10月25日前提交。',evidence_ids:['block:one'],review_reasons:['missing_year']}]};
  const item={id:'review-case',title:'移动端确认测试',category:'award',status:'review',relevance:'UNKNOWN',deadline:null,updated_at:'initial',deadline_evidence_ids:[]};
  const batch={id:'batch-one',title:'网页来源',state:'draft',source_count:1,failed_source_count:0,can_add_sources:true,sources:[{id:'source-one',kind:'url',name:'测试网页',status:'ready',metadata:{final_url:'https://example.com/notice',attachments:[{url:'https://example.com/form.txt',title:'测试附件'}]}}]};
  page.on('pageerror',error=>console.error('UI error:',error.message));
  await page.route('**/api/**',async route=>{
   const url=new URL(route.request().url());let data={};
   if(url.pathname.endsWith('/auth/login'))data={access_token:'test-access',refresh_token:'test-refresh',user:{id:'test-owner',email:'test@example.com'}};
   else if(url.pathname.endsWith('/confirm')){
    writes++;const body=route.request().postDataJSON();assert.equal(body.consent,true);assert.equal(body.revision,1);assert.deepEqual(body.action_ids,['action:0']);assert.equal(body.manual_deadline,'2026-10-25');assert.equal(body.no_deadline,false);assert.deepEqual(body.task_deadlines,{'action:0':{manual_deadline:'2026-10-24'}});
    if(stale){stale=false;return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:{code:'REVIEW_STALE',message:'分析已变化，请重新读取候选'}})})}
    confirmed=true;data={revision:1,status:'confirmed',candidate};
   }else if(url.pathname.endsWith('/reviews'))data={revision:1,status:confirmed?'confirmed':'needs_confirmation',candidate};
   else if(url.pathname.endsWith('/pages/1')){
    previewAuthorization=route.request().headers().authorization;
    if(previewFail){previewFail=false;return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'原图暂不可用'})})}
    return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
   }
   else if(url.pathname.endsWith('/resources'))data={facts:[],rules:[],evidence:[{id:'block:one',text:'请准备申请表。',document_id:'document-test',page:1,preview_available:true,bbox:[10,10,40,30],page_width:100,page_height:100}],tasks:[],materials:[{title:'申请表',evidence_ids:['block:one']}],files:[],evaluation:{relevance:'UNKNOWN',reason:'insufficient_evidence',missing_profile_fields:[]}};
   else if(url.pathname==='/api/v1/profile'&&route.request().method()==='PUT'){
    profileWrites++;const body=route.request().postDataJSON();assert.equal(body.facts.rank_percent,10);assert.equal(body.facts.enrollment_year,2024);assert.equal(body.facts.team_size,null);data=body.facts;
   }
   else if(url.pathname==='/api/v1/profile')data={student_type:'undergraduate',enrollment_year:2024,college:'示例学院',major:'示例专业',rank_percent:null};
   else if(url.pathname==='/api/v1/profile/interests'&&route.request().method()==='PUT'){interestWrites++;assert.deepEqual(route.request().postDataJSON().categories,['competition']);data={categories:['competition']}}
   else if(url.pathname==='/api/v1/profile/interests')data={categories:[]};
   else if(url.pathname==='/api/v1/profile/history')data=[];
   else if(url.pathname.endsWith('/profile/completeness'))data={score:80,missing_fields:['rank_percent']};
   else if(url.pathname==='/api/v1/knowledge/text'){
    assert.equal(route.request().postDataJSON().consent,true);knowledgeSaved=true;data={id:'knowledge-one',status:'indexed'};
   }
   else if(url.pathname==='/api/v1/knowledge/documents')data=knowledgeSaved?[{id:'knowledge-one',title:'测试细则',status:'indexed'}]:[];
   else if(url.pathname==='/api/v1/knowledge/ask')data={answer:'排名前20%',sources:[{id:'chunk-one',title:'测试细则',quote:'申请条件为专业排名前20%。',reference:{locator:'片段1'}}]};
   else if(url.pathname==='/api/v1/documents/document-test')data={id:'document-test',name:'测试图片',mime:'image/png'};
   else if(url.pathname.endsWith('/privacy/scan'))data={revision:1,risk_score:20,findings:[{id:'finding-one',label:'手机号',page:1,preview:'138****5678',location_quality:'line'}]};
   else if(url.pathname.endsWith('/redact')){assert.equal(route.request().postDataJSON().consent,true);data={id:'copy-one',mime:'image/png'}}
   else if(url.pathname==='/api/v1/document-copies/copy-one/content')return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
   else if(url.pathname.endsWith('/cases/review-case'))data=item;
   else if(url.pathname.endsWith('/dashboard'))data={date:'2026-10-14',total_cases:1,today_tasks:[],recent_cases:[item]};
   else if(url.pathname.endsWith('/cases'))data=[item];
   else if(url.pathname.endsWith('/analysis-history'))data=[{revision:1,created_at:'2026-10-14',candidate:{...candidate,analysis_mode:'local',schema_version:'review-3'}}];
   else if(url.pathname.endsWith('/analysis-inputs'))data=[{import_id:'import-one',name:'原始通知'}];
   else if(url.pathname.endsWith('/imports/import-one/retry')){retryWrites++;assert.equal(route.request().postDataJSON().consent,true);data={state:'completed'}}
   else if(url.pathname==='/api/v1/import-batches'||url.pathname==='/api/v1/import-batches/batch-one')data=batch;
   else if(url.pathname.endsWith('/sources/url'))data=batch.sources[0];
   else if(url.pathname.endsWith('/sources/source-one/attachments')){attachmentWrites++;assert.equal(route.request().postDataJSON().consent,true);data={id:'attachment-one'}}
   else if(url.pathname.endsWith('/plan'))data={ordered_tasks:[{id:'task-one',title:'准备申请表',status:'todo',evidence_ids:['block:one']}],current_tasks:[],edges:[]};
   else if(url.pathname==='/api/v1/schedule')data=[];
   else if(url.pathname.endsWith('/tasks/task-one/planning')){planningWrites++;assert.equal(route.request().postDataJSON().duration_minutes,90);assert.equal(route.request().postDataJSON().splittable,true);data={task_id:'task-one'}}
   else if(url.pathname==='/api/v1/schedule/drafts')data={draft_id:'draft-one',suggestions:[{task_id:'task-one',case_id:item.id,title:'准备申请表',starts_at:'2026-10-20T01:00:00Z',ends_at:'2026-10-20T01:30:00Z',scheduled_minutes:30}],unscheduled:[]};
   else if(url.pathname.endsWith('/drafts/draft-one/commit')){
    draftCommits++;assert.equal(route.request().postDataJSON().consent,true);
    if(draftStale){draftStale=false;return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:{code:'DRAFT_STALE',message:'日程已变化，请重新预览'}})})}
    data={state:'committed',saved_count:1};
   }
   await route.fulfill({contentType:'application/json',body:JSON.stringify({data})});
  });
  await page.goto(origin+'/auth/login');
  await page.locator('input[type=email]').fill('test@example.com');await page.locator('input[type=password]').fill('test password');await page.getByRole('button',{name:'提交',exact:true}).click();
  await page.waitForURL('**/home');
  await page.getByRole('link',{name:/移动端确认测试/}).click();
  const panel=page.getByRole('region',{name:'核对分析候选'});try{await panel.waitFor({timeout:8000})}catch(error){console.error((await page.locator('body').innerText()).slice(0,2500));throw error}
  const button=panel.getByRole('button',{name:'确认并生成行动步骤'});
  assert.equal(await button.isDisabled(),true);
  await panel.getByText('建议步骤，可取消',{exact:true}).waitFor();
  await panel.getByText('年份缺失，请核对后填写',{exact:false}).waitFor();
  assert.equal(await panel.getByText('采用此日期',{exact:true}).count(),0);
  await panel.getByLabel('核对后填写截止日期').check();await panel.getByLabel('人工确认截止日期').fill('2026-10-25');await panel.getByLabel('准备申请表截止日期',{exact:true}).selectOption('manual');await panel.getByLabel('准备申请表人工截止日期',{exact:true}).fill('2026-10-24');
  await panel.locator('.consent-row input').check();await button.click();
  await panel.getByRole('alert').waitFor();assert.equal(writes,1);
  await panel.getByRole('button',{name:'重新读取',exact:true}).click();
  await page.waitForTimeout(150);assert.equal(await button.isDisabled(),true);
  await panel.getByLabel('核对后填写截止日期').check();await panel.getByLabel('人工确认截止日期').fill('2026-10-25');await panel.getByLabel('准备申请表截止日期',{exact:true}).selectOption('manual');await panel.getByLabel('准备申请表人工截止日期',{exact:true}).fill('2026-10-24');await panel.locator('.consent-row input').check();await button.click();
  await panel.getByRole('status').waitFor();assert.equal(writes,2);
  const historyPanel=page.getByRole('region',{name:'分析版本与重试'});await historyPanel.getByText('分析版本 1',{exact:false}).waitFor();
  assert.equal(await historyPanel.getByRole('button',{name:'重新分析：原始通知',exact:true}).isDisabled(),true);
  await historyPanel.getByLabel('我同意使用已保存证据重新分析，并重新核对结果。').check();await historyPanel.getByRole('button',{name:'重新分析：原始通知',exact:true}).click();
  await historyPanel.getByText('已完成重新分析，请重新核对当前候选。',{exact:true}).waitFor();assert.equal(retryWrites,1);
  await page.getByRole('button',{name:'查看依据'}).first().click();
  const dialog=page.getByRole('dialog',{name:'原文依据'});await dialog.getByRole('alert').waitFor();
  await dialog.getByRole('button',{name:'重试原图'}).click();await dialog.locator('.evidence-highlight').waitFor();
  assert.equal(previewAuthorization,'Bearer test-access');
  const highlight=await dialog.locator('.evidence-highlight').evaluate(element=>({left:element.style.left,top:element.style.top,width:element.style.width,height:element.style.height}));
  assert.deepEqual(highlight,{left:'10%',top:'10%',width:'30%',height:'20%'});
  await page.screenshot({path:path.join(os.tmpdir(),`zhishi-evidence-mobile-${width}.png`),fullPage:true});
  await dialog.getByRole('button',{name:'关闭原文依据'}).click();await dialog.waitFor({state:'hidden'});
  await page.getByRole('button',{name:'查看依据'}).first().click();await page.getByRole('link',{name:'检查此文件隐私'}).click();
  await page.getByRole('button',{name:'扫描敏感内容'}).click();
  const copyButton=page.getByRole('button',{name:'生成永久脱敏副本'});assert.equal(await copyButton.isDisabled(),true);
  await page.getByLabel(/手机号 ·/).check();await page.getByLabel('我已核对所选区域，同意生成脱敏副本。').check();await copyButton.click();
  await page.getByRole('link',{name:'下载脱敏副本'}).waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:path.join(os.tmpdir(),`zhishi-review-mobile-${width}.png`),fullPage:true});
  await page.getByRole('link',{name:'工作台',exact:true}).click();await page.getByRole('link',{name:'导入并分析',exact:true}).click();
  await page.locator('input[type=file]').setInputFiles({name:'large.png',mimeType:'image/png',buffer:Buffer.alloc(10*1024*1024+1)});
  await page.getByRole('alert').filter({hasText:'图片 10 MB'}).waitFor();
  await page.getByLabel('网页链接',{exact:false}).fill('https://example.com/notice');await page.locator('.consent-row input').check();await page.getByRole('button',{name:'保存并核对来源',exact:true}).click();
  await page.getByRole('button',{name:'确认获取此附件',exact:true}).click();assert.equal(attachmentWrites,1);
  await page.getByRole('link',{name:'我的',exact:true}).click();
  await page.getByRole('link',{name:/个人画像/}).click();
  await page.getByLabel('排名百分比',{exact:true}).fill('101');await page.getByRole('button',{name:'保存画像',exact:true}).click();
  assert.equal(profileWrites,0);
  await page.getByLabel('排名百分比',{exact:true}).fill('10');await page.getByRole('button',{name:'保存画像',exact:true}).click();
  await page.getByText('个人画像已保存在本机，匹配将读取这份资料。',{exact:true}).waitFor();
  assert.equal(profileWrites,0);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.getByLabel('竞赛',{exact:true}).check();await page.getByRole('button',{name:'保存关注分类',exact:true}).click();assert.equal(interestWrites,0);
  await page.getByRole('link',{name:'我的',exact:true}).click();await page.getByRole('link',{name:/知识资料库/}).click();
  await page.getByLabel('资料标题',{exact:true}).fill('测试细则');await page.getByLabel('资料正文',{exact:true}).fill('申请条件为专业排名前20%。');
  assert.equal(await page.getByRole('button',{name:'导入知识资料',exact:true}).isDisabled(),true);
  await page.locator('.consent-row input').check();await page.getByRole('button',{name:'导入知识资料',exact:true}).click();
  await page.getByText('资料已进入当前账户知识库。',{exact:true}).waitFor();
  await page.getByLabel('查询校内规则',{exact:true}).fill('专业排名');await page.getByRole('button',{name:'查询来源片段',exact:true}).click();
  await page.getByText('申请条件为专业排名前20%。',{exact:true}).waitFor();assert.equal(knowledgeSaved,true);
  await page.getByRole('link',{name:'执行计划',exact:true}).click();
  await page.getByRole('tab',{name:'日程安排',exact:true}).click();
  await page.getByText('填写步骤耗时与拆分方式',{exact:true}).click();await page.getByLabel('排程步骤',{exact:true}).selectOption('task-one');await page.getByLabel('估计耗时分钟',{exact:true}).fill('90');await page.getByLabel('允许分段安排',{exact:true}).check();await page.getByRole('button',{name:'保存步骤排程设置',exact:true}).click();
  await page.getByText('步骤排程设置已保存，请重新预览。',{exact:true}).waitFor();assert.equal(planningWrites,1);
  await page.getByRole('button',{name:'预览任务排程',exact:true}).click();
  await page.getByRole('button',{name:'确认整份排程',exact:true}).click();await page.getByText('日程已变化，请重新预览',{exact:true}).waitFor();
  await page.getByRole('button',{name:'预览任务排程',exact:true}).click();await page.getByRole('button',{name:'确认整份排程',exact:true}).click();
  await page.getByText('整份排程已保存。',{exact:true}).waitFor();assert.equal(draftCommits,2);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.close();console.log(`PASS ${width}px: review, history/retry, document privacy, profile/interests, attachment consent, knowledge, split settings, atomic draft, layout`);
 }
 const offline=await browser.newPage({viewport:{width:390,height:844},isMobile:true});
 await offline.route('**/api/**',route=>route.abort());
 await offline.goto(origin+'/home');await offline.getByText('演示模式',{exact:true}).waitFor();
 await offline.getByRole('link',{name:'执行计划',exact:true}).click();await offline.getByText('离线样例计划',{exact:true}).waitFor();
 assert.ok(await offline.locator('.timeline-item').count()>0);
 await offline.goto(origin+'/cases');await offline.getByText('公开通知演示',{exact:false}).first().waitFor();assert.ok(await offline.locator('.case-card-new').count()>=10);
 const publicHref=await offline.getByRole('link',{name:/国家助学金.*公开通知演示/}).first().getAttribute('href');await offline.goto(origin+publicHref+'/analysis');await offline.getByRole('link',{name:'查看学校官网原文'}).waitFor();
 assert.equal(await offline.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await offline.close();console.log('PASS Offline Demo with all API requests blocked');
}finally{await browser.close()}
