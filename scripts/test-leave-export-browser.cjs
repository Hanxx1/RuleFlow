const assert = require('node:assert/strict')
const {mkdir,readFile} = require('node:fs/promises')
const path = require('node:path')
const {chromium} = require('playwright')

const [original,source,out] = process.argv.slice(2)
const base = process.env.FORM_DEMO_URL || 'http://127.0.0.1:5187'
const finalReason = '陪同家人就医'
const boundaryReason = '陪同家人处理需要本人参与的就医及后续安排'.repeat(5).slice(0,100)

;(async()=>{
  await mkdir(out,{recursive:true})
  const browser = await chromium.launch({channel:'msedge',headless:true})
  try {
    const context = await browser.newContext({acceptDownloads:true,viewport:{width:480,height:940}})
    const page = await context.newPage()
    page.setDefaultTimeout(8000)
    const uploads = []
    const errors = []
    page.on('request',request=>{if (request.method()==='POST' || /\/api\//.test(request.url())) uploads.push(request.url())})
    page.on('pageerror',error=>errors.push(error.message))
    const shot = (region,name) => page.getByRole('region',{name:region}).screenshot({path:path.join(out,name+'.png')})
    await page.goto(base+'/imports/new')
    await page.getByLabel('粘贴文字').fill(await readFile(source,'utf8'))
    await page.locator('.file-picker input').setInputFiles(original)
    await page.getByRole('link',{name:'在本机按通知填写附件'}).click()
    await page.getByRole('heading',{name:'按通知填写附件',exact:true}).waitFor()
    await context.setOffline(true)
    await page.getByRole('button',{name:'核对通知与附件'}).click()
    await page.getByText('原表已核验，可填写',{exact:true}).waitFor()
    await page.getByRole('checkbox',{name:'我已核对通知原文和需人工办理的要求'}).check()
    await shot('通知与附件','01_原表及来源核对')
    await page.getByRole('button',{name:'按此通知填写选中原表'}).click()
    const fill = async values => {
      for (const [id,value] of Object.entries(values)) await page.locator('#'+id).fill(value)
    }
    await fill({name:'林知遥',studentId:'00001234',major:'金融学',className:'金融一班',phone:'10000002473',
      course:'金融学',teacher:'周',start:'2026-11-10',end:'2026-11-10',startPeriod:'3',endPeriod:'4',
      periodCount:'3',reason:'处理家庭事务',guardian:'林远',guardianPhone:'10000002474'})
    await page.locator('#parentAware').selectOption('是')
    await page.getByText('同日请假总节数不能超过起止节次的范围',{exact:true}).waitFor()
    const previewButton = page.getByRole('button',{name:'保存补录并预览',exact:true})
    assert.equal(await previewButton.isDisabled(),true)
    await shot('填写表单','02_节次超出范围被拦截')

    await fill({end:'2026-11-11',periodCount:'4',reason:'（具体事由）处理家庭事务'})
    await page.getByText('请替换原表的事由提示，填写实际原因',{exact:true}).waitFor()
    assert.equal(await previewButton.isDisabled(),true)
    await fill({reason:'处理家庭事务'})
    await page.getByLabel('文件名（不含扩展名）').fill('验收用-金融学院学生请假申请')
    await previewButton.click()
    await page.getByRole('region',{name:'版式与交付检查'}).getByText(/打印前请在 Word 中核对两联及签章区/).waitFor()
    const confirmation = page.getByRole('checkbox',{name:/已核对起止节次及总节数/})
    const downloadButton = page.getByRole('button',{name:'确认并下载 DOCX',exact:true})
    await confirmation.check()
    await shot('导出预览','03_修改前预览')
    await page.getByRole('button',{name:'显示并编辑整张表单'}).click()
    await page.locator('#reason').fill(finalReason)
    assert.equal(await confirmation.isChecked(),false)
    assert.equal(await downloadButton.isDisabled(),true)
    const saveDownload = async stem => {
      await confirmation.check()
      const [download] = await Promise.all([page.waitForEvent('download'),downloadButton.click()])
      assert.equal(download.suggestedFilename(),stem+'.docx')
      await download.saveAs(path.join(out,download.suggestedFilename()))
    }
    await shot('导出预览','04_改后待重新确认')
    await saveDownload('验收用-金融学院学生请假申请')
    await page.getByText('已发起文件下载。',{exact:true}).waitFor()

    await page.locator('#reason').fill(boundaryReason+'字')
    await page.getByText('最多填写 100 字',{exact:true}).waitFor()
    assert.equal(await confirmation.isDisabled(),true)
    assert.equal(await downloadButton.isDisabled(),true)
    await page.locator('#reason').fill(boundaryReason)
    await page.getByLabel('文件名（不含扩展名）').fill('验收用-请假理由字数边界')
    await saveDownload('验收用-请假理由字数边界')
    assert.deepEqual(uploads,[])
    assert.deepEqual(errors,[])
    console.log('PASS verified original, same-day span, placeholder, edit invalidates approval, cross-day manual confirmation, 100/101 boundary and two offline downloads')
  } finally {
    await browser.close()
  }
})().catch(error=>{console.error(error);process.exitCode=1})
