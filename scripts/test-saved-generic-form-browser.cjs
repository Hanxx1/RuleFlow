// Against the isolated saved-notice test services. Arguments: output dir, then public DOCX/XLSX samples.
const assert = require('node:assert/strict')
const {randomUUID} = require('node:crypto')
const {readFile,mkdir} = require('node:fs/promises')
const path = require('node:path')
const {chromium} = require('playwright')
const {strFromU8,strToU8,unzipSync,zipSync} = require('../mobile/node_modules/fflate')

const [output,...samplePaths] = process.argv.slice(2)
const legacyPath = process.env.FORM_LEGACY_XLS
const pdfPath = process.env.FORM_PDF_FALLBACK
const base = process.env.FORM_DEMO_URL || 'http://127.0.0.1:5199'
const backend = process.env.SAVED_FORM_API || 'http://127.0.0.1:8026'
const wordMime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const sheetMime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const word = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
const sheet = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
const rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
const packageRel = 'http://schemas.openxmlformats.org/package/2006/relationships'
const contentType = 'http://schemas.openxmlformats.org/package/2006/content-types'
let token = ''

async function api(route,body) {
  const file = body instanceof FormData
  const response = await fetch(backend+'/api/v1'+route,{method:'POST',headers:{
    ...(token ? {Authorization:'Bearer '+token} : {}),...(!file ? {'Content-Type':'application/json'} : {}),
  },body:file ? body : JSON.stringify(body)})
  assert.ok(response.ok,route+' '+response.status)
  return (await response.json()).data
}

function office(parts) {
  return Buffer.from(zipSync(Object.fromEntries(Object.entries(parts).map(([name,value])=>[name,strToU8(value)]))))
}

function docFixture() {
  const cell = text => '<w:tc><w:p><w:r><w:t>'+text+'</w:t></w:r></w:p></w:tc>'
  const row = (label,value='') => '<w:tr>'+cell(label)+cell(value)+'</w:tr>'
  return office({
    '[Content_Types].xml':`<Types xmlns="${contentType}"><Override PartName="/word/document.xml" ContentType="${wordMime}.main+xml"/></Types>`,
    '_rels/.rels':`<Relationships xmlns="${packageRel}"><Relationship Id="r" Type="${rel}/officeDocument" Target="word/document.xml"/></Relationships>`,
    'word/document.xml':`<w:document xmlns:w="${word}"><w:body><w:tbl>${row('学生姓名')+row('申请人姓名')+
      row('学号','（请填写学号）')+row('照片（打印后粘贴）')+row('辅导员信息')+row('姓名')+row('联系电话')}</w:tbl></w:body></w:document>`,
  })
}

function protectedSheet() {
  const worksheet = 'xl/worksheets/sheet1.xml'
  return office({
    '[Content_Types].xml':`<Types xmlns="${contentType}"><Override PartName="/xl/workbook.xml" ContentType="${sheetMime}.main+xml"/></Types>`,
    '_rels/.rels':`<Relationships xmlns="${packageRel}"><Relationship Id="r" Type="${rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>`,
    'xl/workbook.xml':`<workbook xmlns="${sheet}" xmlns:r="${rel}"><sheets><sheet name="受保护" sheetId="1" r:id="r1"/></sheets></workbook>`,
    'xl/_rels/workbook.xml.rels':`<Relationships xmlns="${packageRel}"><Relationship Id="r1" Type="${rel}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>`,
    [worksheet]:`<worksheet xmlns="${sheet}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>姓名</t></is></c><c r="B1" s="1"/></row></sheetData><sheetProtection sheet="1"/></worksheet>`,
  })
}

async function run() {
  for (const origin of [base,backend]) assert.equal(new URL(origin).hostname,'127.0.0.1')
  assert.ok(output)
  await mkdir(output,{recursive:true})
  const samples = await Promise.all(samplePaths.map(async file=>({name:path.basename(file),bytes:await readFile(file)})))
  const legacy = legacyPath ? {name:path.basename(legacyPath),bytes:await readFile(legacyPath)} : undefined
  const pdf = pdfPath ? {name:path.basename(pdfPath),bytes:await readFile(pdfPath)} : undefined
  const synthetic = {name:'字段角色回归.docx',bytes:docFixture()}
  const protectedSample = {name:'受保护回归.xlsx',bytes:protectedSheet()}
  const email = 'rf029-'+randomUUID().slice(0,12)+'@example.com'
  const password = randomUUID()
  const registered = await api('/auth/register',{email,password})
  await api('/auth/verify',{token:registered.development_verification_token})
  token = (await api('/auth/login',{email,password})).access_token
  const {id:batch} = await api('/import-batches',{title:'陌生申请表联调'})
  const sources = '/import-batches/'+batch+'/sources/files'
  const upload = (name,bytes,mime) => {
    const data = new FormData()
    data.append('consent','true')
    data.append('files',new File([bytes],name,{type:mime}))
    return api(sources,data)
  }
  await upload('联调通知.txt','联调办理通知\n请核对学校原件，申请人签字后交件。','text/plain')
  if (pdf) await upload(pdf.name,pdf.bytes,'application/pdf')
  if (legacy) await upload(legacy.name,legacy.bytes,'application/vnd.ms-excel')
  for (const sample of [...samples,synthetic,protectedSample]) {
    await upload(sample.name,sample.bytes,sample.name.endsWith('.docx') ? wordMime : sheetMime)
  }
  const browser = await chromium.launch({channel:'msedge',headless:true})
  try {
    const page = await browser.newPage({viewport:{width:420,height:900},acceptDownloads:true})
    page.setDefaultTimeout(10000)
    const errors = []
    const writes = []
    page.on('pageerror',error=>errors.push(error.message))
    await page.goto(base+'/auth/login')
    await page.locator('input[type=email]').fill(email)
    await page.locator('input[type=password]').fill(password)
    await page.getByRole('button',{name:'提交',exact:true}).click()
    await page.waitForURL(url=>!url.pathname.startsWith('/auth'))
    page.on('request',request=>{
      if (request.url().startsWith(backend+'/api/') && !['GET','OPTIONS'].includes(request.method())) writes.push(request.method())
    })
    await page.locator('#app').evaluate((root,id)=>root.__vue_app__.config.globalProperties.$router.push('/imports/'+id+'/sources'),batch)
    await page.getByRole('link',{name:'按已保存通知填表'}).click()
    const intake = page.getByRole('region',{name:'已保存通知与附件'})
    if (legacy) {
      const manual = intake.getByRole('region',{name:'待手工填写的 XLS 原件'})
      await manual.getByText(legacy.name,{exact:true}).waitFor()
      await manual.getByText(/校方明确接受 XLSX/).waitFor()
      assert.equal(await intake.getByRole('radio',{name:legacy.name,exact:false}).count(),0)
    }
    if (pdf) {
      const manual = intake.getByRole('region',{name:'PDF 附件',exact:true})
      await manual.getByText(pdf.name,{exact:true}).waitFor()
      await manual.getByText(/签字、盖章和审批由对应人员处理/).waitFor()
      assert.equal(await intake.getByRole('radio',{name:pdf.name,exact:false}).count(),0)
      await manual.screenshot({path:path.join(output,'saved-pdf-fallback.png')})
    }
    const mapping = intake.getByRole('group',{name:'核对原表字段位置'})
    const consent = mapping.getByRole('checkbox',{name:'我已对照原表确认写入位置和需人工核对的要求'})
    const apply = mapping.getByRole('button',{name:'使用已核对的位置填写'})
    const editor = page.getByRole('region',{name:'填写表单'})
    const preview = page.getByRole('region',{name:'导出预览'})
    const launch = () => intake.getByRole('button',{name:'核验并填写选中原表'}).click()
    const select = async name=>{
      await intake.getByRole('radio',{name:name,exact:false}).check()
      const notice = intake.getByRole('combobox',{name:'适用通知'})
      const option = notice.getByRole('option',{name:'联调通知.txt',exact:true})
      await notice.selectOption(await option.getAttribute('value'))
      await intake.getByLabel('我已核对这份表的通知原文及提交要求').check()
      await launch()
    }
    const enable = async()=>{
      await consent.check()
      await apply.click()
      await mapping.waitFor({state:'detached'})
      await editor.waitFor()
    }
    const exportFile = async(name,stem)=>{
      const download = preview.getByRole('button',{name:/确认并下载/})
      await editor.getByLabel('文件名（不含扩展名）').fill(stem)
      await editor.getByRole('button',{name:'预览填写内容',exact:true}).click()
      await preview.getByLabel('我确认这份文件的填写值和文件名').check()
      const [file] = await Promise.all([page.waitForEvent('download'),download.click()])
      assert.equal(file.suggestedFilename(),stem+path.extname(name))
      const dest = path.join(output,file.suggestedFilename())
      await file.saveAs(dest)
      return unzipSync(new Uint8Array(await readFile(dest)))
    }

    await select(synthetic.name)
    const positions = mapping.getByRole('combobox',{name:/写入位置 · 学生姓名/})
    assert.equal(await positions.inputValue(),'')
    assert.equal(await positions.locator('option').count(),4)
    assert.equal(await mapping.getByRole('combobox',{name:/联系电话/}).count(),0)
    await consent.check()
    assert.equal(await apply.isDisabled(),true)
    await positions.selectOption('manual')
    await enable()
    await editor.locator('#name').fill('蒋知遥')
    await editor.locator('#studentId').fill('00005831')
    await editor.getByRole('button',{name:'预览填写内容',exact:true}).click()
    assert.equal(await preview.getByRole('button',{name:/确认并下载/}).isDisabled(),true)
    await preview.getByText('查看填写清单',{exact:true}).click()
    await preview.getByText('学生姓名 · 蒋知遥',{exact:true}).waitFor()
    await launch()
    await positions.selectOption('1')
    await enable()
    assert.equal(await editor.locator('#name').inputValue(),'')
    await editor.getByText('照片需打印后粘贴。导出保留照片框。',{exact:true}).waitFor()
    await editor.locator('#name').fill('沈言初')
    await editor.locator('#studentId').fill('00005834')
    const {['word/document.xml']:doc} = await exportFile(synthetic.name,'字段角色回归')
    const xml = strFromU8(doc)
    assert.match(xml,/申请人姓名[\s\S]*?沈言初[\s\S]*?00005834[\s\S]*?辅导员信息[\s\S]*?姓名/)
    assert.equal(xml.includes('（请填写学号）'),false)
    assert.equal(xml.includes('照片（打印后粘贴）'),true)
    assert.equal((xml.match(/沈言初/g) || []).length,1)
    console.log('PASS ambiguous role requires explicit mapping, changed mapping starts blank, protected role stays and manual fallback blocks export')

    await select(protectedSample.name)
    await intake.getByRole('alert').filter({hasText:'工作表已保护'}).waitFor()
    assert.equal(await editor.count(),0)
    console.log('PASS protected workbook gives a manual fallback and exposes no writable fields')

    for (const [index,sample] of samples.entries()) {
      await select(sample.name)
      await mapping.waitFor()
      for (const select of await mapping.getByRole('combobox').all()) {
        if (await select.inputValue()) continue
        const choice = select.locator('option:not([disabled]):not([value=""]):not([value="manual"])')
        assert.equal(await choice.count(),1)
        await select.selectOption(await choice.getAttribute('value'))
      }
      await mapping.screenshot({path:path.join(output,'校方原件映射-'+(index+1)+'.png')})
      await enable()
      await editor.getByRole('button',{name:'显示并编辑整张表单'}).click()
      const values = {name:'许清言',studentId:'00001482',birthDate:'2005年5月',phone:'00000000000',
        gender:'女',identity:'00000020050101000X',postalCode:'410000',address:'长沙市岳麓区校内宿舍',
        college:'物联网工程学院',className:'软件工程2401班','label-修读保健班期限':'一学期',
        reason:'本人申请修读本学期体育保健课程，按通知要求另附材料。'}
      for (const field of await editor.locator('fieldset input[id],fieldset select[id],fieldset textarea[id]').all()) {
        const id = await field.getAttribute('id')
        if (await field.evaluate(element=>element.tagName==='SELECT')) await field.selectOption({index:1})
        else await field.fill(values[id] || '本次申请')
      }
      const parts = await exportFile(sample.name,'校方原件填写-'+(index+1))
      const original = unzipSync(new Uint8Array(sample.bytes))
      assert.deepEqual(Object.keys(parts),Object.keys(original))
      const writable = sample.name.endsWith('.docx') ? /^word\/document\.xml$/ : /^xl\/worksheets\/[^/]+\.xml$/
      for (const [name,bytes] of Object.entries(original)) {
        if (!writable.test(name)) assert.deepEqual(parts[name],bytes,name)
      }
      assert.ok(Object.entries(parts).some(([name,bytes])=>writable.test(name) && strFromU8(bytes).includes(values.name)))
      console.log('PASS public source, verified user mapping and native format export:',sample.name)
    }
    assert.deepEqual(errors,[])
    assert.deepEqual(writes,[])

    const local = await browser.newPage({viewport:{width:420,height:900},acceptDownloads:true})
    await local.goto(base+'/forms/import')
    await local.getByLabel('通知正文').waitFor()
    await local.context().setOffline(true)
    const called = []
    local.on('request',request=>{if (/\/api\//.test(request.url())) called.push(request.method())})
    await local.getByLabel('通知正文').fill('本机填写回归\n请申请人核对表格并签字。')
    await local.getByLabel('选择申请表原件（DOCX 或 XLSX）').setInputFiles({name:synthetic.name,mimeType:wordMime,buffer:synthetic.bytes})
    await local.getByRole('button',{name:'核对通知与附件'}).click()
    await local.getByLabel('附件用途 · '+synthetic.name).selectOption('form')
    await local.getByLabel('我已核对通知原文和需人工办理的要求').check()
    await local.getByRole('button',{name:'按此通知填写选中原表'}).click()
    const localMapping = local.getByRole('group',{name:'核对原表字段位置'})
    await localMapping.getByRole('combobox',{name:/写入位置 · 学生姓名/}).selectOption('0')
    await localMapping.getByRole('checkbox',{name:'我已对照原表确认写入位置和需人工核对的要求'}).check()
    await localMapping.getByRole('button',{name:'使用已核对的位置填写'}).click()
    await local.locator('#name').fill('周泽安')
    await local.locator('#studentId').fill('00001734')
    await local.getByRole('button',{name:'预览填写内容',exact:true}).click()
    await local.getByRole('checkbox',{name:'我确认这份文件的填写值和文件名'}).check()
    const [downloaded] = await Promise.all([local.waitForEvent('download'),
      local.getByRole('button',{name:'确认并下载 DOCX'}).click()])
    const offlinePath = path.join(output,'离线陌生表导出.docx')
    await downloaded.saveAs(offlinePath)
    const localXml = strFromU8(unzipSync(new Uint8Array(await readFile(offlinePath)))['word/document.xml'])
    assert.match(localXml,/学生姓名[\s\S]*?周泽安[\s\S]*?申请人姓名[\s\S]*?00001734/)
    assert.deepEqual(called,[])
    console.log('PASS local-import mapping and native export work offline with no API calls')
    if (pdf) {
      await local.getByLabel('选择申请表原件（DOCX 或 XLSX）').setInputFiles({
        name:pdf.name,mimeType:'application/pdf',buffer:pdf.bytes,
      })
      await local.getByText(/保留 PDF 原件/).waitFor()
      await local.getByRole('button',{name:'核对通知与附件'}).click()
      await local.getByText(/签字、盖章和审批由对应人员处理/).waitFor()
      await local.getByText('要在此填写，请提供可核验的 DOCX 或 XLSX 申请表原件。').waitFor()
      const roles = local.getByLabel('附件用途 · '+pdf.name)
      assert.equal(await roles.locator('option[value=form]').evaluate(option=>option.disabled),true)
      assert.equal(await local.getByRole('radio',{name:pdf.name,exact:false}).count(),0)
      assert.equal(await local.getByRole('button',{name:'按此通知填写选中原表'}).isDisabled(),true)
      assert.deepEqual(called,[])
      await local.screenshot({path:path.join(output,'local-pdf-fallback.png')})
      console.log('PASS real PDF remains manual in both entries; Office writeback and offline mode stay available')
    }
    if (legacy) {
      await local.getByLabel('选择申请表原件（DOCX 或 XLSX）').setInputFiles({
        name:legacy.name,mimeType:'application/vnd.ms-excel',buffer:legacy.bytes,
      })
      await local.getByRole('button',{name:'核对通知与附件'}).click()
      await local.getByText(/仅修改后缀无法转换格式/).waitFor()
      assert.equal(await local.getByRole('radio',{name:legacy.name,exact:false}).count(),0)
      assert.equal(await local.getByRole('button',{name:'按此通知填写选中原表'}).isDisabled(),true)
      assert.deepEqual(called,[])
      console.log('PASS real legacy XLS gets a manual-only explanation in both entries; never selected for writeback')
    }
  } finally {
    await browser.close()
  }
}

run().catch(error=>{console.error(error);process.exitCode=1})
