const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const {chromium} = require('playwright')
const output = process.argv[2]
const screenshotDir = process.argv[3]

;(async()=>{
  await fs.mkdir(output,{recursive:true})
  const browser = await chromium.launch({channel:'msedge',headless:true})
  try {
    const context = await browser.newContext({viewport:{width:430,height:900},acceptDownloads:true})
    const page = await context.newPage()
    const problems = []
    page.on('pageerror',error=>problems.push(error.message))
    await page.goto('http://127.0.0.1:5184/me')
    await page.getByText('智能填表演示',{exact:true}).click()
    await page.getByRole('heading',{name:'智能填表',exact:true}).waitFor()
    await page.screenshot({path:path.join(screenshotDir,'mobile-demo.png')})
    await page.getByText('手上只有赛事通知？',{exact:true}).click()
    const notice = page.getByRole('textbox',{name:'粘贴公开通知片段'})
    await notice.fill('校园竞赛报名材料提交截止时间为下周一')
    await page.getByRole('link',{name:'转到日程安排'}).waitFor()
    assert.match(await page.getByRole('link',{name:'转到日程安排'}).getAttribute('href'),/^\/plan/)
    await notice.fill('校园住宿申请请提交附件材料')
    assert.equal(await page.getByRole('link',{name:'转到日程安排'}).count(),0)
    await page.getByText('手上只有赛事通知？',{exact:true}).click()
    await context.setOffline(true)
    const scenarios = [
      ['国家奖学金申请','XLSX','奖学金申请'],
      ['学生请假申请','DOCX','学生请假申请'],
      ['学历及学位证明书申请','DOCX','学历学位证明'],
      ['学生证补办登记','DOCX','带照片补办登记'],
    ]
    for (const [title,format,stem] of scenarios) {
      await page.getByRole('button',{name:new RegExp(title)}).click()
      await page.getByRole('button',{name:'预览填写内容'}).click()
      assert.equal(await page.getByRole('button',{name:new RegExp('确认并下载')}).isDisabled(),true)
      await page.getByRole('button',{name:'用合成资料补齐缺项'}).click()
      if (format==='XLSX') {
        await page.locator('#name').fill('林同学')
        await page.locator('#name').locator('..').getByRole('button',{name:'保存并下次复用'}).click()
        await page.getByRole('button',{name:'保存获奖组 1',exact:true}).click()
        await page.getByRole('button',{name:'起草申请理由'}).click()
        const previousReason = await page.locator('#reason').inputValue()
        await page.getByRole('button',{name:'使用这份理由'}).click()
        const updatedReason = await page.locator('#reason').inputValue()
        assert.notEqual(updatedReason,previousReason)
        assert.match(updatedReason,/校级数据实践优秀项目/)
      } else {
        assert.equal(await page.locator('#name').inputValue(),'林同学')
      }
      if (title==='学生请假申请') {
        await page.locator('#parentAware').selectOption('否')
        assert.match(await page.getByLabel('填写表单').innerText(),/原表含家长知情声明/)
        await page.locator('#parentAware').selectOption('是')
        await page.locator('#reason').fill('家中急事')
      }
      if (title==='学生证补办登记') {
        await page.locator('input[type=file]').setInputFiles({name:'avatar.png',mimeType:'image/png',buffer:Buffer.from(require('../mobile/src/features/formDemo/templateData.json')['avatar.png'],'base64')})
        await page.getByAltText('将嵌入表格的演示照片').waitFor()
        await page.getByRole('slider',{name:'缩放'}).fill('1.2')
        await page.getByAltText('将嵌入表格的演示照片').waitFor()
      }
      await page.getByRole('textbox',{name:'文件名（不含扩展名）'}).fill(stem)
      await page.getByRole('checkbox',{name:/我确认/}).check()
      const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.getByRole('button',{name:new RegExp('确认并下载 '+format)}).click(),
      ])
      assert.equal(download.suggestedFilename(),'演示-'+stem+'.'+format.toLowerCase())
      await download.saveAs(path.join(output,download.suggestedFilename()))
      assert.match(await page.getByRole('status').last().innerText(),/已生成/)
      console.log('PASS offline flow',title,download.suggestedFilename())
    }
    await page.getByRole('button',{name:/国家奖学金申请/}).click()
    assert.match(await page.locator('#reason').inputValue(),/校级数据实践优秀项目/)
    await context.setOffline(false)
    await page.reload()
    assert.equal(await page.locator('#name').inputValue(),'林同学')
    const stored = await page.evaluate(()=>localStorage.getItem('campusweave:offline-form-demo:v1'))
    assert.deepEqual(JSON.parse(stored),{name:'林同学'})
    await page.getByRole('button',{name:'填入空白奖项'}).click()
    assert.equal(await page.locator('#awardName1').inputValue(),'校级数据实践优秀项目')
    assert.deepEqual(problems,[])
    console.log('PASS local reuse after reload; protected values excluded; event handoff; no uncaught errors')
  } finally {
    await browser.close()
  }
})().catch(error=>{console.error(error);process.exitCode=1})
