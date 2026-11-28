const assert = require('node:assert/strict')
const {chromium} = require('playwright')
const {PDFDocument} = require('../mobile/node_modules/pdf-lib')
const {readFile} = require('node:fs/promises')
const path = require('node:path')

async function run() {
  const browser = await chromium.launch({channel:'msedge'})
  let page
  try {
    page = await browser.newPage({viewport:{width:410,height:860}})
    page.on('pageerror',e=>console.error(e.message))
    await page.goto(process.env.FORM_DEMO_URL+'/forms/import')
    const png = await page.evaluate(()=>{
      const c=document.createElement('canvas')
      c.width=800;c.height=450
      const ctx=c.getContext('2d')
      ctx.fillStyle='white';ctx.fillRect(0,0,800,450)
      ctx.fillStyle='black';ctx.font='42px sans-serif';ctx.fillText('申请人姓名',75,120)
      return c.toDataURL('image/png').split(',')[1]
    })
    await page.getByLabel('通知正文').fill('申请人请核对填写姓名。')
    await page.getByLabel(/选择申请表原件/).setInputFiles({name:'扫描申请.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')})
    await page.getByRole('button',{name:'核对通知与附件'}).click()
    await page.getByLabel(/附件用途 · 扫描/).selectOption('form')
    await page.getByLabel('我已核对通知原文和需人工办理的要求').check()
    await page.getByRole('button',{name:'按此通知填写选中原表'}).click()
    const panel=page.getByRole('group',{name:'填写原件副本'})
    await panel.getByRole('button',{name:'本机识别本页文字'}).click()
    await panel.locator('pre,[role=alert]').first().waitFor({timeout:60000})
    assert.equal(await panel.getByRole('alert').count(),0,await panel.innerText())
    assert.match((await panel.locator('pre').innerText()).replace(/\s/g,''),/姓名/)
    await panel.getByLabel('申请人填写内容').fill('李同学')
    const canvas=panel.locator('canvas')
    await canvas.click({position:{x:170,y:65}})
    await panel.getByLabel('我已核对通知、申请人位置、填写内容和文件名').check()
    const [copy]=await Promise.all([page.waitForEvent('download'),panel.getByRole('button',{name:'下载填写副本'}).click()])
    const target=path.join(process.argv[2],copy.suggestedFilename())
    await copy.saveAs(target)
    const doc=await PDFDocument.load(await readFile(target))
    assert.equal(doc.getPageCount(),1)
    assert.ok(doc.getPage(0).node.Resources().lookup(require('../mobile/node_modules/pdf-lib').PDFName.of('XObject')).keys().length>=2)
    console.log('PASS scan OCR, original-page placement and exported image resources')
  } catch(e){console.error(await page?.locator('body').innerText());throw e} finally {await browser.close()}
}
run().catch(e=>{console.error(e);process.exitCode=1})
