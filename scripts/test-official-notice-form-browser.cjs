// Run against isolated web/API services. Input contains copies of one official page and its attachments.
const assert = require('node:assert/strict')
const {execFileSync} = require('node:child_process')
const {createHash,randomUUID} = require('node:crypto')
const {mkdir,readFile} = require('node:fs/promises')
const path = require('node:path')
const {chromium} = require('playwright')

const [samples,output] = process.argv.slice(2)
const web = process.env.FORM_DEMO_URL || 'http://127.0.0.1:5213'
const backend = process.env.SAVED_FORM_API || 'http://127.0.0.1:8036'
const notice = '西北大学境外交流学习资助通知.txt'
const proof = '附件1 返校证明模板.docx'
const workbook = '附件2 个人信息表.xlsx'
const application = '附件3 西北大学学生赴境外交流学习派出及资助申请表.docx'
const mime = {
  txt:'text/plain',
  xlsx:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
const digests = {
  [proof]:'07ed1fef437b358311f005b99318471d9d02643747592c3b840ce08d4557a301',
  [workbook]:'44596711eb35c2f918eeaa552c2719004b5128bed4f8efb9cf2245a200f8fd5f',
  [application]:'0faedb58756b4abf9f974a47b8bc59b5247865ef87a6d3a532fb091fa052b453',
}
const short = '短期'
const applicant = {
  name:'程若宁',gender:'女',birthDate:'1998-06-20',studentId:'0000174206',
  college:'经济管理学院',major:'会计学',year:'2017级',phone:'00000000802',
  email:'ruoning.cheng@example.com',identity:'00000019980620000X',
  address:'陕西省西安市长安区校内宿舍',postalCode:'710127',
  exchangeInstitution:'首尔市立大学（韩国）','label-所赴国家/地区':'韩国',
  'label-项目名称':'首尔市立大学寒假会计研修','label-交流时间':'2019.01.07–2019.02.01',
  'label-交行卡号':'0000000000000428371','label-申请资助金额':'2000 元',
  'label-世界排名':'未申报排名加成','label-民族':'汉族','label-课业平均成绩':'88.6',
  'label-联系人电话':'00000000803','label-微信号':'ruoning_campus',
  'label-获奖情况':'2018年院级优秀志愿者','label-兴趣特长':'摄影、篮球',
  'label-考试时间':'2018-10-20','label-考试成绩':'雅思 6.5',
}
const hash = bytes=>createHash('sha256').update(bytes).digest('hex')

async function run() {
  assert.ok(samples && output,'需要校方原件目录和证据输出目录')
  for (const url of [web,backend]) assert.equal(new URL(url).hostname,'127.0.0.1')
  await mkdir(output,{recursive:true})
  const originalNotice = path.join(samples,'official.html')
  const html = await readFile(originalNotice,'utf8')
  assert.match(html,/关于办理学生赴境外交流学习资助的通知/)
  assert.match(html,/B3E75B3B680554951C27B58B296_EBCFDE20_2B31/)
  assert.match(html,/B51FFB3857B051BD3EFE63294D8_479533BC_4BE7/)
  assert.match(html,/969C23898E92DF3C4D7C5F6876B_6745695B_34F2/)
  // Capture the published article body, retaining its actual paragraphs without site navigation.
  const python = process.env.SAVED_FORM_PYTHON || 'python'
  const noticeBody = execFileSync(python,['-X','utf8','-c',[
    'from pathlib import Path',
    'from bs4 import BeautifulSoup',
    'import sys',
    'page = BeautifulSoup(Path(sys.argv[1]).read_bytes(), "html.parser")',
    'article = page.select_one("#vsb_content .v_news_content")',
    'blocks = [p.get_text().strip() for p in article.find_all("p")]',
    'print("\\n".join(filter(None, blocks)))',
  ].join('\n'),originalNotice])
  const files = new Map(await Promise.all([notice,proof,workbook,application].map(async name=>{
    const buffer = name===notice ? noticeBody : await readFile(path.join(samples,name))
    if (digests[name]) assert.equal(hash(buffer),digests[name],name)
    return [name,{name,buffer,mimeType:mime[name.split('.').at(-1)]}]
  })))
  const email = 'official-forms-'+randomUUID().slice(0,12)+'@example.com'
  const password = randomUUID()
  let token
  async function api(route,body) {
    const response = await fetch(backend+'/api/v1'+route,{method:body?'POST':'GET',headers:{
      ...(token?{Authorization:'Bearer '+token}:{}),...(body?{'Content-Type':'application/json'}:{}),
    },body:body?JSON.stringify(body):undefined})
    assert.ok(response.ok,route+' '+response.status)
    return (await response.json()).data
  }
  const signup = await api('/auth/register',{email,password})
  await api('/auth/verify',{token:signup.development_verification_token})
  token = (await api('/auth/login',{email,password})).access_token

  const browser = await chromium.launch({channel:'msedge',headless:true})
  try {
    const page = await browser.newPage({viewport:{width:470,height:920},acceptDownloads:true})
    page.setDefaultTimeout(12000)
    const errors = [], writes = [], offsite = []
    page.on('pageerror',error=>errors.push(error.message))
    page.on('request',request=>{
      const url = new URL(request.url())
      if (['http:','https:'].includes(url.protocol) && url.hostname!=='127.0.0.1') offsite.push(url.hostname)
      if (request.url().startsWith(backend+'/api/') && !['GET','OPTIONS'].includes(request.method())) {
        writes.push([request.method(),url.pathname])
      }
    })
    page.on('dialog',dialog=>dialog.accept())
    await page.goto(web+'/auth/login')
    await page.locator('input[type=email]').fill(email)
    await page.locator('input[type=password]').fill(password)
    await page.getByRole('button',{name:'提交',exact:true}).click()
    await page.waitForURL(url=>!url.pathname.startsWith('/auth'))
    await page.locator('#app').evaluate(root=>root.__vue_app__.config.globalProperties.$router.push('/imports/new'))
    await page.getByLabel(/事项标题/).fill('西北大学境外交流学习资助 · 公开历史样本验收')
    await page.locator('.file-picker input').setInputFiles([...files.values()])
    await page.getByText('准备保存的来源',{exact:true}).waitFor()
    assert.ok(await page.getByRole('button',{name:'保存并核对来源'}).isDisabled())
    await page.getByLabel(/^我已核对来源与隐私预览/).check()
    await page.getByRole('button',{name:'保存并核对来源'}).click()
    await page.waitForURL(url=>/\/imports\/[^/]+\/sources$/.test(url.pathname))
    const batchId = new URL(page.url()).pathname.split('/')[2]
    const batchPath = '/import-batches/'+batchId
    const context = async()=>{
      const {revision} = await api(batchPath)
      return api(batchPath+'/form-context?expected_revision='+revision)
    }
    const first = await context()
    assert.equal(first.sources.length,4)
    const source = (snapshot,name)=>snapshot.sources.find(item=>item.name===name)
    assert.equal(source(first,notice).text_origin,'document_lines')
    assert.match(source(first,notice).text,/国际部收到申请邮件/)
    assert.ok(source(first,notice).lines.some(line=>line.line_id&&/返校证明/.test(line.text)))
    for (const name of [proof,workbook,application]) assert.equal(source(first,name).document_ref.sha256,digests[name])

    await page.getByRole('link',{name:'按已保存通知填表'}).click()
    const intake = page.getByRole('region',{name:'已保存通知与附件'})
    const radio = name=>intake.getByRole('radio',{name,exact:false})
    const mapping = intake.getByRole('group',{name:'核对原表字段位置'})
    const section = mapping.getByLabel('填写分区')
    const editor = page.getByRole('region',{name:'填写表单'})
    const preview = page.getByRole('region',{name:'导出预览'})
    const go = intake.getByRole('button',{name:'核验并填写选中原表'})
    const summaryRule = intake.getByRole('combobox',{name:/适用附件.*个人总结/})
    const confirmNotice = intake.getByLabel('我已核对这份表的通知原文及提交要求')
    await intake.getByLabel('此附件不用于填写 · '+proof,{exact:true}).check()
    assert.equal(await radio(proof).isDisabled(),true)
    await radio(workbook).check()
    await intake.getByRole('combobox',{name:/适用通知/}).selectOption({label:notice})
    assert.equal(await confirmNotice.count(),0)
    await summaryRule.selectOption('manual')
    await confirmNotice.waitFor()
    await intake.screenshot({path:path.join(output,'notice-source-and-proof.png')})
    console.log('PASS archived notice body and three same-origin originals imported through the UI, proof excluded, separate summary retained for manual handling')

    const select = async (name,sectionLabel)=>{
      if (!(await radio(name).isChecked())) await radio(name).check()
      const choice = intake.getByRole('combobox',{name:/适用通知/})
      if (await choice.inputValue()!==source(first,notice).source_id) {
        await choice.selectOption({label:notice})
      }
      if (!(await confirmNotice.isChecked())) await confirmNotice.check()
      await go.click()
      await mapping.waitFor()
      if (sectionLabel) {
        assert.equal(await section.inputValue(),'')
        const apply = mapping.getByRole('button',{name:'使用已核对的位置填写'})
        await mapping.getByLabel('我已对照原表确认写入位置和需人工核对的要求').check()
        assert.equal(await apply.isDisabled(),true)
        const option = section.getByRole('option',{name:new RegExp(sectionLabel)})
        await section.selectOption(await option.getAttribute('value'))
        assert.equal(await mapping.getByLabel('我已对照原表确认写入位置和需人工核对的要求').isChecked(),false)
      }
    }
    const confirmMapping = async()=>{
      for (const field of await mapping.getByRole('combobox',{name:/写入位置/}).all()) {
        if (await field.inputValue()) continue
        const choice = field.locator('option:not([disabled]):not([value=""]):not([value="manual"])')
        assert.equal(await choice.count(),1,await field.evaluate(node=>node.parentElement.textContent))
        await field.selectOption(await choice.getAttribute('value'))
      }
      await mapping.getByLabel('我已对照原表确认写入位置和需人工核对的要求').check()
      await mapping.getByRole('button',{name:'使用已核对的位置填写'}).click()
      await mapping.waitFor({state:'detached'})
      await editor.waitFor()
      const all = editor.getByRole('button',{name:'显示并编辑整张表单'})
      if (await all.count()) await all.click()
    }
    const fill = async()=>{
      for (const control of await editor.locator('fieldset input[id],fieldset textarea[id]').all()) {
        const id = await control.getAttribute('id')
        assert.ok(applicant[id],id)
        await control.fill(applicant[id])
      }
    }
    const download = async(name)=>{
      const before = writes.length
      await editor.getByRole('button',{name:'预览填写内容',exact:true}).click()
      const delivery = preview.getByRole('region',{name:'版式与交付检查'})
      await delivery.getByText(name,{exact:true}).waitFor()
      await delivery.getByText('下载后请按通知自行提交文件。',{exact:true}).waitFor()
      await delivery.getByText('核对通知中的办理要求',{exact:true}).click()
      await delivery.getByText(/个人总结.*1500/).waitFor()
      await delivery.getByText(/邮件以/).waitFor()
      if (name===application) {
        await delivery.getByText('核对原表说明和保留区域',{exact:true}).click()
        await delivery.getByText(/A4纸正反面打印/).waitFor()
      }
      if (name===workbook) {
        assert.equal(await preview.getByText(applicant.identity,{exact:true}).count(),0)
        assert.equal(await preview.getByText(applicant['label-交行卡号'],{exact:true}).count(),0)
      }
      await preview.getByLabel('我确认这份文件的填写值和文件名').check()
      const expected = page.waitForEvent('download')
      await preview.getByRole('button',{name:/确认并下载/}).click()
      const result = await expected
      assert.equal(result.suggestedFilename(),name)
      await result.saveAs(path.join(output,name))
      assert.equal(writes.length,before)
      await delivery.screenshot({path:path.join(output,name+'.handoff.png')})
    }

    await select(workbook,short)
    await mapping.getByRole('option',{name:/姓名.*B13/}).waitFor({state:'attached'})
    assert.equal(await mapping.getByRole('option',{name:/姓名.*B4/}).count(),0)
    await mapping.screenshot({path:path.join(output,'xlsx-short-section-mapping.png')})
    await confirmMapping()
    await fill()
    await download(workbook)
    await select(application)
    await mapping.getByText('查看保留的原文区域').click()
    await mapping.getByText(/国际部审核意见/).waitFor()
    await mapping.screenshot({path:path.join(output,'docx-mapping-and-review.png')})
    await confirmMapping()
    await fill()
    await download(application)
    console.log('PASS two native exports; short-term row chosen, summary separate, masked identifiers, email subject not an output name')

    await select(workbook,'长期')
    await confirmMapping()
    assert.equal(await editor.locator('#name').inputValue(),'')
    await editor.locator('#name').fill('不同分区回归')
    await select(workbook,short)
    await confirmMapping()
    assert.equal(await editor.locator('#name').inputValue(),applicant.name)
    assert.equal(await editor.locator('#studentId').inputValue(),applicant.studentId)

    await radio(application).check()
    await intake.getByText('移除或补充本批次原件',{exact:true}).click()
    await intake.getByRole('button',{name:'移除所选附件'}).click()
    await radio(application).waitFor({state:'detached'})
    await intake.getByLabel('选择补充原件').setInputFiles(files.get(application))
    await intake.getByLabel('我已核对该文件的隐私并同意上传到当前账户').check()
    await intake.getByRole('button',{name:'上传补充原件'}).click()
    await radio(application).waitFor()
    const second = await context()
    assert.notEqual(source(second,application).source_id,source(first,application).source_id)
    assert.equal(source(second,workbook).source_id,source(first,workbook).source_id)
    assert.equal(source(second,proof).document_ref.id,source(first,proof).document_ref.id)
    const proofUrl = backend+'/api/v1/documents/'+source(second,proof).document_ref.id+'/content'
    const original = await fetch(proofUrl,{headers:{Authorization:'Bearer '+token}})
    assert.equal(original.status,200)
    assert.equal(hash(Buffer.from(await original.arrayBuffer())),digests[proof])

    await select(application)
    await confirmMapping()
    assert.equal(await editor.locator('#name').inputValue(),'')
    await select(workbook,short)
    await confirmMapping()
    assert.equal(await editor.locator('#name').inputValue(),applicant.name)
    assert.equal(await editor.locator('#studentId').inputValue(),applicant.studentId)
    assert.equal(await radio(proof).isDisabled(),true)
    assert.deepEqual(errors,[])
    assert.deepEqual(offsite,[])
    console.log('PASS section and original identities isolate drafts; same-name replacement starts blank, other table keeps values, proof bytes unchanged')
  } finally { await browser.close() }
}

run().catch(error=>{console.error(error);process.exitCode=1})
