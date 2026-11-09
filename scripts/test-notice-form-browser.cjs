const assert = require('node:assert/strict')
const {chromium} = require('playwright')
const fs = require('node:fs/promises')
const path = require('node:path')
const {createRequire} = require('node:module')
const {zipSync,strToU8} = createRequire(path.resolve(__dirname,'../mobile/package.json'))('fflate')

const original = process.argv[2]
const out = process.argv[3]
const base = process.env.FORM_DEMO_URL || 'http://127.0.0.1:5187'
const text = '学生复学办理通知\n申请理由 12–30 字。\n申请表文件命名为“学号-姓名-复学申请.docx”。\n申请人签字后交件。'

async function testMultiple(browser, replacementPath, requests, errors) {
  const context = await browser.newContext({acceptDownloads:true,viewport:{width:390,height:844}})
  try {
    const page = await context.newPage()
    page.on('request',request=>{if (/\/api\//.test(request.url()) || request.method()==='POST') requests.push(request.url())})
    page.on('pageerror',error=>errors.push(error.message))
    const resumeName = '附件1_复学申请.docx'
    const replacementName = '附件2_学生证补办.docx'
    const notice = [
      '奖学金及学籍服务办理通知',
      '奖学金可记录竞赛获奖经历，请在截止前提交。',
      '附件1文件命名格式：学号_姓名_复学申请.docx。',
      '附件2文件名为“姓名_学生证补办.docx”。',
      '申请理由至少 12 字。',
      '申请理由使用宋体小四。',
      '请另交附件中的证明材料。',
    ]
    const mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    const body = notice.map(line=>'<w:p><w:r><w:t>'+line+'</w:t></w:r></w:p>').join('')
    const bytes = zipSync({'word/document.xml':strToU8('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+body+'</w:body></w:document>')})
    await page.goto(base+'/imports/new')
    await page.locator('.file-picker input').setInputFiles([
      {name:'办理通知.docx',mimeType,buffer:Buffer.from(bytes)},
      {name:resumeName,mimeType,buffer:await fs.readFile(original)},
      {name:replacementName,mimeType,buffer:await fs.readFile(replacementPath)},
      {name:'另附证明.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4')},
    ])
    await page.getByRole('link',{name:'在本机按通知填写附件'}).click()
    const bodyField = page.getByRole('textbox',{name:'通知正文',exact:true})
    await page.waitForFunction(()=>document.querySelector('textarea')?.value.includes('竞赛获奖经历'))
    await context.setOffline(true)
    const inspect = () => page.getByRole('button',{name:'核对通知与附件'}).click()
    const acknowledge = () => page.getByRole('checkbox',{name:'我已核对通知原文和需人工办理的要求'}).check()
    const accept = () => page.getByRole('button',{name:'按此通知填写选中原表'})
    const pick = name => page.getByRole('radio',{name:new RegExp(name)}).check()
    const assignLength = () => page.getByLabel(/适用附件 · 第 5 行/).selectOption({label:resumeName})
    const fill = async values => {
      for (const [id,value] of Object.entries(values)) await page.locator('#'+id).fill(value)
    }
    const download = async filename => {
      assert.deepEqual(await page.locator('[aria-invalid="true"]').evaluateAll(fields=>fields.map(field=>field.id)),[])
      await page.getByRole('button',{name:'预览填写内容'}).click()
      await page.getByRole('checkbox',{name:/我确认这份文件/}).check()
      const [file] = await Promise.all([
        page.waitForEvent('download'),page.getByRole('button',{name:'确认并下载 DOCX'}).click(),
      ])
      assert.equal(file.suggestedFilename(),filename)
      await file.saveAs(path.join(out,filename))
    }
    await inspect()
    await page.getByLabel('附件用途 · 另附证明.pdf').selectOption('proof')
    await page.getByText(/第 6 行 · 待人工核对/).waitFor()
    assert.equal(await page.getByRole('link',{name:'转到日程安排'}).count(),0)
    await pick(resumeName)
    await acknowledge()
    assert.equal(await accept().isDisabled(),true)
    await assignLength()
    await acknowledge()
    await accept().click()
    await fill({name:'林双表',studentId:'00004567',reason:'本人休学期已满，申请于新学期按原学籍复学。'})

    await pick(replacementName)
    await acknowledge()
    await accept().click()
    assert.equal(await page.locator('#name').inputValue(),'')
    await fill({name:'周双表',studentId:'00007654',ethnicity:'汉族',phone:'00000000000',residentialCollege:'示例书院',
      identity:'00000020050101000X',address:'示例地址二号',railRoute:'深圳北至示例站',
      reason:'原学生证遗失，申请补办。',applicationDate:'2026-11-08'})
    await page.locator('#gender').selectOption('女')
    await page.locator('#previousReplacement').selectOption('否')
    await download('周双表_学生证补办.docx')
    await page.getByText('已导出',{exact:true}).waitFor()

    await pick(resumeName)
    await acknowledge()
    await accept().click()
    await page.getByRole('button',{name:'显示并编辑整张表单'}).click()
    assert.equal(await page.locator('#name').inputValue(),'林双表')
    await fill({phone:'00000000000',address:'示例地址一号',postalCode:'000000',applicationDate:'2026-11-08'})
    await page.locator('#gender').selectOption('女')
    await page.locator('#resumeKind').selectOption('休学期满')
    await download('00004567_林双表_复学申请.docx')

    await bodyField.fill(notice.join('\n').replace('姓名_复学申请.docx','姓名_复学申请.xlsx'))
    await inspect()
    await assignLength()
    await pick(resumeName)
    await page.getByRole('alert').filter({hasText:'通知要求的文件格式与所选原表不同'}).waitFor()
    await acknowledge()
    assert.equal(await accept().isDisabled(),true)
    await pick(replacementName)
    await acknowledge()
    await accept().click()
    await page.getByRole('button',{name:'显示并编辑整张表单'}).click()
    assert.equal(await page.locator('#name').inputValue(),'周双表')
    await bodyField.fill('竞赛作品提交截止时间为下周一。')
    await inspect()
    await page.getByRole('link',{name:'转到日程安排'}).waitFor()
    assert.equal(await accept().count(),0)
    console.log('PASS one-time DOCX notice import, proof role, per-attachment rules, isolated drafts, two downloads and competition routing')
  } finally {
    await context.close()
  }
}

;(async()=>{
  await fs.mkdir(out,{recursive:true})
  const browser = await chromium.launch({channel:'msedge',headless:true})
  try {
    const context = await browser.newContext({acceptDownloads:true,viewport:{width:430,height:900}})
    const page = await context.newPage()
    const requests = []
    const errors = []
    page.on('request',request=>{if (/\/api\//.test(request.url()) || request.method()==='POST') requests.push(request.url())})
    page.on('pageerror',error=>errors.push(error.message))
    await page.goto(base+'/imports/new')
    await page.getByLabel('粘贴文字').fill(text)
    const bytes = await fs.readFile(original)
    const changed = Buffer.from(bytes)
    changed[10] ^= 1
    await page.locator('.file-picker input').setInputFiles({name:'同名复学申请表.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:changed})
    await page.getByRole('link',{name:'在本机按通知填写附件'}).click()
    await page.getByRole('heading',{name:'按通知填写附件',exact:true}).waitFor()
    assert.equal(await page.getByRole('textbox',{name:'通知正文',exact:true}).inputValue(),text)
    await context.setOffline(true)
    await page.getByRole('button',{name:'核对通知与附件'}).click()
    await page.getByText(/未核验此原件或版本/).waitFor()
    assert.equal(await page.getByRole('button',{name:'按此通知填写选中原表'}).isDisabled(),true)

    await page.getByLabel(/选择申请表原件/).setInputFiles({name:'同名复学申请表.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:bytes})
    await page.getByRole('button',{name:'核对通知与附件'}).click()
    await page.getByText(/第 2 行 · 字数校验/).waitFor()
    assert.equal(await page.getByRole('button',{name:'按此通知填写选中原表'}).isDisabled(),true)
    await page.getByRole('checkbox',{name:'我已核对通知原文和需人工办理的要求'}).check()
    await page.getByRole('button',{name:'按此通知填写选中原表'}).click()
    assert.equal(await page.getByRole('button',{name:'用合成资料补齐缺项'}).count(),0)
    await page.locator('#name').fill('林通知')
    await page.locator('#gender').selectOption('女')
    await page.locator('#studentId').fill('00003456')
    await page.locator('#phone').fill('00000000000')
    await page.locator('#address').fill('示例地址一号')
    await page.locator('#postalCode').fill('000000')
    await page.locator('#resumeKind').selectOption('休学期满')
    await page.locator('#applicationDate').fill('2026-11-07')
    await page.locator('#reason').fill('申请复学')
    await page.getByText('至少填写 12 字',{exact:true}).waitFor()
    assert.equal(await page.getByRole('button',{name:'保存补录并预览'}).isDisabled(),true)
    await page.locator('#reason').fill('本人休学期已满，申请于新学期按原学籍复学。')
    await page.getByRole('button',{name:'保存补录并预览'}).click()
    await page.getByText('00003456-林通知-复学申请.docx',{exact:true}).waitFor()
    const filename = page.getByLabel('文件名（不含扩展名）')
    await filename.fill('不符合要求的文件名')
    await page.getByText('文件名须与通知识别出的命名要求一致。',{exact:true}).waitFor()
    await filename.fill('')
    await page.getByRole('checkbox',{name:/我确认这份文件/}).check()
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button',{name:'确认并下载 DOCX'}).click(),
    ])
    assert.equal(download.suggestedFilename(),'00003456-林通知-复学申请.docx')
    await download.saveAs(path.join(out,download.suggestedFilename()))
    await page.getByText('文件已生成，未向学校提交。',{exact:true}).waitFor()
    await page.getByRole('textbox',{name:'通知正文',exact:true}).fill('新的通知')
    assert.equal(await page.getByRole('button',{name:'确认并下载 DOCX'}).count(),0)
    if (process.argv[4] && process.argv[5]) {
      await context.setOffline(false)
      await page.goto(base+'/imports/new')
      await page.locator('.file-picker input').setInputFiles([process.argv[4],process.argv[5]])
      await page.getByRole('link',{name:'在本机按通知填写附件'}).click()
      const official = page.getByRole('textbox',{name:'通知正文',exact:true})
      await official.waitFor()
      await page.waitForFunction(()=>document.querySelector('textarea')?.value.includes('学生证补办'))
      await context.setOffline(true)
      await page.getByRole('button',{name:'核对通知与附件'}).click()
      await page.getByText(/· 学生证补办登记/).waitFor()
      const acknowledge = page.getByRole('checkbox',{name:'我已核对通知原文和需人工办理的要求'})
      if (await acknowledge.count()) await acknowledge.check()
      await page.getByRole('button',{name:'按此通知填写选中原表'}).click()
      const nameField = page.locator('#name')
      if (!await nameField.count()) await page.getByRole('button',{name:'显示并编辑整张表单'}).click()
      assert.equal(await nameField.inputValue(),'林通知')
      await page.locator('#studentId').fill('00003456')
      await page.locator('#ethnicity').fill('汉族')
      await page.locator('#phone').fill('00000000000')
      await page.locator('#residentialCollege').fill('示例书院')
      await page.locator('#identity').fill('00000020050101000X')
      await page.locator('#address').fill('示例地址一号')
      await page.locator('#railRoute').fill('深圳北至示例站')
      await page.locator('#previousReplacement').selectOption('否')
      await page.locator('#reason').fill('原学生证遗失，申请补办。')
      await page.locator('#applicationDate').fill('2026-11-07')
      await page.getByRole('button',{name:'保存补录并预览'}).click()
      await page.getByText(/照片框留空。打印后请按/).waitFor()
      assert.equal(await page.getByLabel(/选择合成 PNG/).count(),0)
      await page.getByLabel('文件名（不含扩展名）').fill('学生证补办申请-林通知')
      await page.getByRole('checkbox',{name:/我确认这份文件/}).check()
      const [actual] = await Promise.all([
        page.waitForEvent('download'),
        page.getByRole('button',{name:'确认并下载 DOCX'}).click(),
      ])
      await actual.saveAs(path.join(out,actual.suggestedFilename()))
      assert.equal(actual.suggestedFilename(),'学生证补办申请-林通知.docx')
      console.log('PASS downloaded university notice TXT + original replacement form, reused approved local fields, blank physical photo slot')
      await testMultiple(browser,process.argv[5],requests,errors)
    }
    assert.deepEqual(requests,[])
    assert.deepEqual(errors,[])
    console.log('PASS import notice + matching raw DOCX, reject altered attachment, apply word limit and required filename, local save and offline download')
  } finally {
    await browser.close()
  }
})().catch(error=>{console.error(error);process.exitCode=1})
