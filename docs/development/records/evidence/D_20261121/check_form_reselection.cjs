const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require('playwright');
const {createServer} = require(path.resolve('mobile/node_modules/vite'));
const data = require(path.resolve('mobile/src/features/formDemo/templateData.json'));
async function run() {
 const vite = await createServer({root:path.resolve('mobile'),server:{host:'127.0.0.1',port:0},logLevel:'error'});
 await vite.listen();
 let browser;
 try {
  browser = await chromium.launch({channel:'msedge',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  page.setDefaultTimeout(6500);
  await page.goto(vite.resolvedUrls.local[0]+'forms/import');
  const body = page.getByRole('textbox',{name:'通知正文',exact:true});
  await body.fill('办理通知：请分别填写两份奖学金申请表，签字后交件。');
  const source = Buffer.from(data['scholarship.xlsx'],'base64');
  const file = (name, buffer) => ({name,mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer});
  const a = file('附件A.xlsx',source), b = file('附件B.xlsx',source);
  const choose = page.getByLabel(/选择申请表原件/);
  const inspect = () => page.getByRole('button',{name:'核对通知与附件'}).click();
  async function open(name) {
   await page.getByRole('radio',{name:new RegExp(name)}).check();
   await page.getByRole('checkbox',{name:/我已核对通知原文/}).check();
   await page.getByRole('button',{name:'按此通知填写选中原表'}).click();
   await page.getByRole('button',{name:'显示并编辑整张表单'}).click();
  }
  await choose.setInputFiles([a,b]); await inspect();
  const fields = ['name','studentId','reason'];
  const values = async () => Promise.all(fields.map(id=>page.locator('#'+id).inputValue()));
  for (const letter of ['A','B']) {
   await open(letter+'.xlsx');
   for (const id of fields) await page.locator('#'+id).fill(letter+'-'+id);
  }
  await body.fill('更新办理通知：两份奖学金申请表仍须签字后交件。'); await inspect();
  for (const letter of ['A','B']) {
   await open(letter+'.xlsx'); assert.deepEqual(await values(),fields.map(id=>letter+'-'+id));
  }
  await choose.dispatchEvent('cancel'); assert.deepEqual(await values(),fields.map(id=>'B-'+id));
  const changed = Buffer.concat([source,Buffer.from('v2')]);
  assert.equal(source.readUInt32LE(source.length-22),0x06054b50);
  changed.writeUInt16LE(2,source.length-2);
  await choose.setInputFiles([file(a.name,changed),b]); await inspect();
  await page.getByText(/未核验此原件或版本/).waitFor();
  assert.equal(await page.getByRole('radio',{name:/附件A/}).count(),0);
  await open('B.xlsx'); assert.deepEqual(await values(),['','','']);
  await choose.setInputFiles([a,b]); await inspect(); await open('A.xlsx');
  assert.deepEqual(await values(),['','','']);
  console.log('PASS notice-only edit retained 6 values; cancel event retained B; changed A unavailable; unchanged B and reselected original A both lost 3 values');
 } finally { if(browser) await browser.close(); await vite.close(); }
}
run().catch(e=>{console.error(e);process.exitCode=1});
