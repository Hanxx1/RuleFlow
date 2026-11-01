import {createRequire} from 'node:module';
import path from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require(path.join(process.env.ZHISHI_BROWSER_MODULE_ROOT,'playwright'));
const origin=process.env.ZHISHI_UI_TEST_ORIGIN||'http://127.0.0.1:5173';
const browser=await chromium.launch({headless:true,channel:'msedge'});
try{for(const width of [360,390]){
 const context=await browser.newContext({viewport:{width,height:844},isMobile:true});const page=await context.newPage();let uploads=0;
 await page.route('**/api/**',route=>{uploads++;return route.abort()});
 await page.goto(origin+'/profile');await page.getByLabel('身份',{exact:true}).selectOption('undergraduate');await page.getByLabel('德育成绩',{exact:true}).fill('85');await page.getByLabel('入学年份',{exact:true}).fill('2024');await page.getByRole('button',{name:'保存画像',exact:true}).click();await page.getByText('个人画像已保存在本机，匹配将读取这份资料。',{exact:true}).waitFor();
 await page.goto(origin+'/cases/demo-assessment');await page.getByRole('region',{name:'本机资料关联判断'}).waitFor();await page.getByRole('region',{name:'本机资料关联判断'}).getByText('相关',{exact:true}).waitFor();await page.goto(origin+'/profile');await page.locator('.fact-card').first().waitFor();assert.equal(await page.getByLabel('德育成绩',{exact:true}).inputValue(),'85');
 await page.getByLabel('其他个人情况',{exact:true}).fill('德育成绩90');await page.getByRole('button',{name:'在本机整理补充内容'}).click();await page.getByText('补充内容已生成候选，请逐项确认。',{exact:true}).waitFor();
 await page.locator('.fact-card').filter({hasText:'待确认'}).getByRole('button',{name:'确认资料',exact:true}).click();await page.getByText(/存在冲突：德育成绩/).waitFor();
 const results=await page.evaluate(async()=>{const m=await import('/src/services/clientWorkspace.ts');const w=await m.loadWorkspace('offline');const stale=await m.loadWorkspace('offline');await m.saveWorkspace(w);let rejected=false;try{await m.saveWorkspace(stale)}catch{rejected=true}if(!rejected)throw Error('stale local workspace was overwritten');await m.indexedWorkspace.write('a',m.emptyWorkspace('a'));await m.indexedWorkspace.write('b',m.emptyWorkspace('b'));await m.indexedWorkspace.remove('a');return {conflicts:m.resolvedFacts(w).conflicts,a:await m.indexedWorkspace.read('a'),b:(await m.loadWorkspace('b')).owner}});
 assert.deepEqual(results.conflicts,['moral_score']);assert.equal(results.a,undefined);assert.equal(results.b,'b');assert.equal(uploads,0);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.goto(origin+'/timetable');await page.getByRole('button',{name:'加入合成示例课表'}).click();await page.getByText('合成课表已加入，明确标记为演示数据。',{exact:true}).waitFor();
 const calendar=await page.evaluate(async()=>{const w=await import('/src/services/clientWorkspace.ts'),t=await import('/src/services/timetable.ts');const data=await w.loadWorkspace('offline');return {count:data.courses.length,preview:t.localSchedule([{id:'test',title:'准备材料（测试）',duration_minutes:60,evidence_ids:['block:test']}],data.courses,'2026-10-12','2026-10-12')}});assert.equal(calendar.count,4);assert.equal(calendar.preview.suggestions[0].starts_at,'2026-10-12T02:00:00.000Z');
 console.log(`PASS ${width}px: real IndexedDB, local evidence matching, persistence, supplement confirmation/conflict, owner isolation, no upload`);await context.close();
}}finally{await browser.close()}
