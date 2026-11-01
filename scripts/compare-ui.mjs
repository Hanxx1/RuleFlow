import {createRequire} from 'node:module';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.ZHISHI_BROWSER_MODULE_ROOT ? process.env.ZHISHI_BROWSER_MODULE_ROOT + '/playwright' : '../.runtime/browser/node_modules/playwright');
const stage=process.argv[2];
if(!stage||!/^[a-z-]+$/.test(stage))throw Error('Pass a baseline/after stage name');
const browser=await chromium.launch({headless:true,channel:'msedge'});
const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1,serviceWorkers:'block',locale:'zh-CN',timezoneId:'Asia/Shanghai'});
const page=await context.newPage();
await page.clock.setFixedTime(new Date('2026-11-01T08:00:00Z'));
const errors=[];page.on('pageerror',error=>errors.push(error.message));
const output=new URL(`../.runtime/visual-${stage}/`,import.meta.url);await mkdir(output,{recursive:true});
const records=[];
try {
 for(const path of ['/welcome','/home','/cases','/plan','/profile','/imports/new','/knowledge','/vault','/privacy','/guide','/auth/login']){
  await page.goto((process.env.ZHISHI_UI_TEST_ORIGIN||'http://127.0.0.1:5193')+path);await page.waitForLoadState('networkidle');await page.waitForTimeout(200);
  const bytes=await page.screenshot({fullPage:true,animations:'disabled'});
  const name=path.slice(1).replaceAll('/','-');await writeFile(new URL(name+'.png',output),bytes);
  records.push({path,sha256:createHash('sha256').update(bytes).digest('hex'),text:await page.locator('body').innerText()});
 }
 await writeFile(new URL('results.json',output),JSON.stringify({records,errors},null,2));
 if(errors.length)throw Error('Browser errors: '+errors.join('; '));
 if(stage!=='baseline'){
  const before=JSON.parse(await readFile(new URL('../.runtime/visual-baseline/results.json',import.meta.url),'utf8'));
  const changes=records.filter((r,i)=>r.sha256!==before.records[i].sha256||r.text!==before.records[i].text).map(r=>r.path);
  console.log(JSON.stringify({pages:records.length,changes,errors}));if(changes.length)process.exitCode=1;
 }else console.log(JSON.stringify({pages:records.length,errors}));
}finally{await browser.close()}
