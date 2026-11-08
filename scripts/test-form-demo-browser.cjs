const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const {chromium} = require('playwright')
const output = process.argv[2]
const screenshotDir = process.argv[3]
const base = process.env.FORM_DEMO_URL || 'http://127.0.0.1:5187'

;(async()=>{
  await fs.mkdir(output,{recursive:true})
  await fs.mkdir(screenshotDir,{recursive:true})
  const browser = await chromium.launch({channel:'msedge',headless:true})
  try {
    const context = await browser.newContext({viewport:{width:430,height:900},acceptDownloads:true})
    const page = await context.newPage()
    const problems = []
    page.on('pageerror',error=>problems.push(error.message))
    await page.goto(base+'/me')
    await page.getByText('智能填表演示',{exact:true}).click()
    await page.getByRole('heading',{name:'智能填表',exact:true}).waitFor()
    const identity = page.getByLabel('演示资料身份')
    await identity.selectOption('demo:empty')
    await page.locator('#name').waitFor()
    assert.equal(await page.locator('#name').inputValue(),'')
    await page.screenshot({path:path.join(screenshotDir,'ten-forms-demo.png')})
    await page.getByText('手上只有赛事通知？',{exact:true}).click()
    const notice = page.getByRole('textbox',{name:'粘贴公开通知片段'})
    await notice.fill('校园竞赛报名材料提交截止时间为下周一')
    await page.getByRole('link',{name:'转到日程安排'}).waitFor()
    assert.match(await page.getByRole('link',{name:'转到日程安排'}).getAttribute('href'),/^\/plan/)
    await notice.fill('校园住宿申请请提交附件材料')
    assert.equal(await page.getByRole('link',{name:'转到日程安排'}).count(),0)
    await page.getByText('手上只有赛事通知？',{exact:true}).click()
    await context.setOffline(true)

    const cases = [
      ['国家奖学金申请','XLSX','奖学金申请'],
      ['学生请假申请','DOCX','学生请假申请'],
      ['学历及学位证明书申请','DOCX','学历学位证明'],
      ['学生证补办登记','DOCX','学生证补办'],
      ['假期留校住宿','DOCX','假期留校住宿'],
      ['课程缓考','DOCX','课程缓考'],
      ['勤工助学优秀个人申请','DOCX','勤工助学优秀个人申请'],
      ['学生复学申请','DOCX','学生复学申请'],
      ['转专业申请','DOCX','转专业申请'],
      ['成绩查分查卷','DOCX','成绩查分查卷'],
      ['学生课程免修','DOCX','学生课程免修'],
    ]
    for (const [title,format,stem] of cases) {
      await page.getByRole('button',{name:new RegExp(title)}).click()
      await page.getByRole('button',{name:'预览填写内容'}).click()
      assert.equal(await page.getByRole('button',{name:/确认并下载/}).isDisabled(),true)
      if (format==='XLSX') await page.locator('#name').fill('林同学')
      else assert.equal(await page.locator('#name').count(),0)
      await page.getByRole('button',{name:'用合成资料补齐缺项'}).click()
      if (title==='学生请假申请') {
        await page.locator('#parentAware').selectOption('否')
        assert.match(await page.getByLabel('填写表单').innerText(),/原表含家长知情声明/)
        await page.locator('#parentAware').selectOption('是')
        await page.locator('#reason').fill('家中急事')
      }
      if (title==='学生证补办登记' || title==='假期留校住宿') {
        assert.equal(await page.locator('input[type=file]').count(),0)
        await page.getByText(/照片框留空。打印后请按/).waitFor()
      }
      if (title==='学生复学申请') {
        assert.equal(await page.locator('#studentId').count(),0)
        await page.locator('#resumeKind').selectOption('退役复学')
        await page.getByText('按原表说明另附退役证复印件。',{exact:false}).waitFor()
        await page.locator('#resumeKind').selectOption('休学期满')
      }
      await page.getByRole('textbox',{name:'文件名（不含扩展名）'}).fill(stem)
      await page.getByRole('button',{name:'保存补录并预览'}).click()
      await page.getByText(/可复用资料已保存在本机/).waitFor()
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

    await context.setOffline(false)
    await page.reload()
    await identity.selectOption('demo:empty')
    await page.getByRole('button',{name:/国家奖学金申请/}).click()
    await page.getByRole('button',{name:'显示并编辑整张表单'}).click()
    assert.equal(await page.locator('#name').inputValue(),'林同学')
    assert.equal(await page.locator('#identity').inputValue(),'')
    await page.getByRole('button',{name:'填入空白奖项'}).first().click()
    assert.match(await page.locator('#awardName1').inputValue(),/数据实践/)
    await identity.selectOption('demo:forms')
    await page.locator('#name').waitFor()
    assert.equal(await page.locator('#name').inputValue(),'')
    const peer = await context.newPage()
    peer.on('pageerror',error=>problems.push(error.message))
    await peer.goto(base+'/demo/forms')
    for (const candidate of [page,peer]) {
      await candidate.getByRole('button',{name:'用合成资料补齐缺项'}).click()
    }
    await page.getByRole('button',{name:'保存补录并预览'}).click()
    await page.getByText(/可复用资料已保存在本机/).waitFor()
    await peer.locator('#name').fill('林复核')
    await peer.getByRole('button',{name:'保存补录并预览'}).click()
    await peer.getByText('资料已在其他页面更新，请重读后再保存',{exact:true}).waitFor()
    assert.equal(await peer.locator('#name').inputValue(),'林复核')
    await peer.getByRole('button',{name:'保存补录并预览'}).click()
    await peer.getByText(/可复用资料已保存在本机/).waitFor()
    assert.deepEqual(problems,[])
    console.log('PASS empty account, cross-template reuse, owner isolation, reload, award archive, stale revision recovery, and event handoff')
  } finally {
    await browser.close()
  }
})().catch(error=>{console.error(error);process.exitCode=1})
