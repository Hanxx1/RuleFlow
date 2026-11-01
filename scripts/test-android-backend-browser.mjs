// Real local HTTP backend, synthetic account/data only. No mocked API responses.
import {createRequire} from 'node:module';
import {randomUUID} from 'node:crypto';
import path from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(path.join(process.env.ZHISHI_BROWSER_MODULE_ROOT,'playwright'));
const origin=process.env.ZHISHI_UI_TEST_ORIGIN||'http://127.0.0.1:5193';
const backend=process.env.ZHISHI_BACKEND_ORIGIN||'http://127.0.0.1:8000';
const browser=await chromium.launch({headless:true,channel:process.env.ZHISHI_TEST_BROWSER_CHANNEL||'msedge'});
try {
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true});
 const email='android-smoke-'+randomUUID()+'@example.com',password='Synthetic-'+randomUUID();
 const registration=await page.request.post(backend+'/api/v1/auth/register',{data:{email,password}});
 assert.equal(registration.status(),200);const registered=(await registration.json()).data;
 const verification=await page.request.post(backend+'/api/v1/auth/verify',{data:{token:registered.development_verification_token}});
 assert.equal(verification.status(),200);
 await page.goto(origin+'/auth/login');
 await page.getByRole('button',{name:'检查服务连接',exact:true}).click();await page.getByText('应用已成功连接后端。',{exact:true}).waitFor();
 await page.locator('input[type=email]').fill(email);await page.locator('input[type=password]').fill(password);await page.getByRole('button',{name:'提交',exact:true}).click();
 await page.waitForURL('**/home');await page.getByRole('link',{name:'导入并分析',exact:true}).click();
 const deadline=new Date(Date.now()+30*86400000).toISOString().slice(0,10);
 await page.getByLabel('粘贴文字',{exact:true}).fill(`请填写申请表。请上传作品。报名截止${deadline}。`);
 await page.locator('.consent-row input').check();await page.getByRole('button',{name:'保存并核对来源',exact:true}).click();
 await page.getByRole('button',{name:'开始分析',exact:true}).click();
 const resourceResponse=page.waitForResponse(response=>response.url().endsWith('/resources')&&response.status()===200);
 await page.getByRole('link',{name:'打开生成的事项',exact:true}).click();
 const analysis=(await (await resourceResponse).json()).data.analysis;
 if(process.env.ZHISHI_REQUIRE_LLM==='true')assert.equal(analysis.mode,'llm','Online smoke must not silently pass using local fallback');
 const panel=page.getByRole('region',{name:'核对分析候选'});await panel.getByLabel('采用此日期',{exact:true}).first().check();
 await panel.locator('.consent-row input').check();await panel.getByRole('button',{name:'确认并生成行动步骤',exact:true}).click();await panel.getByRole('status').waitFor();
 await page.getByRole('link',{name:'执行计划',exact:true}).click();await page.getByRole('tab',{name:'日程安排',exact:true}).click();
 await page.getByRole('button',{name:'预览任务排程',exact:true}).click();
 page.on('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'确认整份排程',exact:true}).click();await page.getByText('整份排程已保存。',{exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 console.log('PASS real HTTP: health, registration, login, consented import, analysis, review, draft commitment at 390px');
 await page.close();
} finally {await browser.close()}
