/* Browser regression with an explicit model response double. Real model tests are in server/tests. */
const assert = require('node:assert/strict')
const {randomUUID} = require('node:crypto')
const {mkdir,readFile} = require('node:fs/promises')
const path = require('node:path')
const {chromium} = require('playwright')
const {strFromU8,strToU8,unzipSync,zipSync} = require('../mobile/node_modules/fflate')

const base=process.env.FORM_DEMO_URL
const backend=process.env.SAVED_FORM_API
const out=process.argv[2]
const doc='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
const sheet='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
const relation='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
const packageRel='http://schemas.openxmlformats.org/package/2006/relationships'
const types='http://schemas.openxmlformats.org/package/2006/content-types'
const labels=['哪些观察改变了团队原先的判断？','如何让后续人员验证方案？','连续开展几天？','借用外部设备时写明归还人']
const resultValues=['居民反馈开放时间影响到访，因此调整开放时间。','先记录开放时间，再按反馈核对到访情况。']
const reviewer='审核人信息'
const studentNotes='居民反馈开放时间影响到访。执行期间为 2026-10-01 至 2026-10-03。'
const extraMaterial='记录包括开放时间、到访情况两项。'

function fixture(format) {
  const word=format==='docx'
  const part=word?'word/document.xml':'xl/worksheets/sheet1.xml'
  const main=word?part:'xl/workbook.xml'
  const mime='application/vnd.openxmlformats-officedocument.'+(word?'wordprocessingml.document':'spreadsheetml.sheet')
  const parts={
    '[Content_Types].xml':'<Types xmlns="'+types+'"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'+
      '<Default Extension="xml" ContentType="application/xml"/><Override PartName="/'+main+'" ContentType="'+mime+'.main+xml"/>'+
      (word?'':'<Override PartName="/'+part+'" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'+
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>')+'</Types>',
    '_rels/.rels':'<Relationships xmlns="'+packageRel+'"><Relationship Id="r" Type="'+relation+'/officeDocument" Target="'+main+'"/></Relationships>',
  }
  if(word){
    const cell=text=>'<w:tc><w:p><w:r><w:t>'+text+'</w:t></w:r></w:p></w:tc>'
    parts[part]='<w:document xmlns:w="'+doc+'"><w:body><w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="4200"/><w:gridCol w:w="4800"/></w:tblGrid>'+
      [...labels,reviewer,'如何处置？'].map(label=>'<w:tr>'+cell(label)+cell('')+'</w:tr>').join('')+'</w:tbl></w:body></w:document>'
  }else{
    parts[main]='<workbook xmlns="'+sheet+'" xmlns:r="'+relation+'"><sheets><sheet name="计划表" sheetId="1" r:id="r"/></sheets></workbook>'
    parts['xl/_rels/workbook.xml.rels']='<Relationships xmlns="'+packageRel+'"><Relationship Id="r" Type="'+relation+'/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="s" Type="'+relation+'/styles" Target="styles.xml"/></Relationships>'
    parts['xl/styles.xml']='<styleSheet xmlns="'+sheet+'"><fonts count="1"><font/></fonts>'+
      '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'+
      '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'+
      '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'+
      '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1"/></xf></cellXfs>'+
      '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
    parts[part]='<worksheet xmlns="'+sheet+'"><cols><col min="1" max="2" width="36" customWidth="1"/></cols><sheetData>'+
      [...labels,reviewer,'如何处置？'].map((label,i)=>{
        const n=i+1
        return '<row r="'+n+'"><c r="A'+n+'" t="inlineStr"><is><t>'+label+'</t></is></c><c r="B'+n+'" s="1"/></row>'
      }).join('')+'</sheetData></worksheet>'
  }
  const buffer=Buffer.from(zipSync(Object.fromEntries(Object.entries(parts).map(([name,text])=>[name,strToU8(text)]))))
  return {name:'实践问题.'+format,mimeType:mime,buffer,part}
}

async function post(route,body){
  const response=await fetch(backend+'/api/v1/auth/'+route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  assert.ok(response.ok,route+' '+response.status)
  return (await response.json()).data
}

function mock(p){
  const note=p.sources.find(s=>s.id==='notes')
  const material=p.sources.find(s=>s.kind==='material')
  const ref=(s,quote)=>({source_id:s.id,quote})
  return {fields:p.fields.map(field=>{
    const i=labels.indexOf(field.label)
    const base={id:field.id,meaning:'理解这项计划或经历',expected:'使用已核对资料',
      data_type:i===2?'integer':'long_text',role:'applicant',required:i===3?'conditional':'required',
      condition:i===3?'借用外部设备时填写':null,applicability:i===3?'unknown':'applies',strategy:note?'integrate':'ask',
      bounds:{},ambiguous:false,requirements:[{source_id:field.source_id,quote:field.label}],facts:[],value:null}
    if(!note || p.stage==='analyze' || field.locked || i===3)return base
    if(i===2)return {...base,strategy:'derive',calculation:{operation:'inclusive_days',
      operands:[ref(note,'2026-10-01'),ref(note,'2026-10-03')]}}
    const facts=[ref(note,'居民反馈开放时间影响到访')]
    if(material)facts.push(ref(material,'到访情况'))
    return {...base,value:resultValues[i],facts}
  }),questions:note?[]:[{text:'你们观察到了什么，安排了哪些天？',fields:p.fields.slice(0,3).map(f=>f.id)}]}
}

async function use(page,format){
  const entry=fixture(format)
  let unavailable=true
  const sent=[]
  await page.route('**/api/v1/form-assistant',async route=>{
    const request=route.request()
    if(request.method()==='OPTIONS'){await route.fallback();return}
    const body=request.postDataJSON()
    sent.push(body)
    if(unavailable){
      unavailable=false
      await route.fulfill({status:503,json:{detail:{code:'FORM_AI_UNCONFIGURED'}}})
    }else await route.fulfill({status:200,json:{data:mock(body)}})
  })
  await page.getByLabel('通知正文').fill('请核对本次实践记录，并保留审核人栏目供校方填写。')
  await page.getByLabel(/选择申请表原件/).setInputFiles(entry)
  await page.getByRole('button',{name:'核对通知与附件'}).click()
  await page.getByLabel('附件用途 · '+entry.name).selectOption('form')
  await page.getByLabel('我已核对通知原文和需人工办理的要求').check()
  await page.getByRole('button',{name:'按此通知填写选中原表'}).click()
  const mapping=page.getByRole('group',{name:'核对原表字段位置'})
  for(const label of labels) await mapping.getByRole('combobox',{name:'写入位置 · '+label,exact:true}).selectOption('0')
  assert.equal(await mapping.getByRole('combobox',{name:/如何处置/}).count(),0)
  await mapping.getByRole('checkbox').check()
  await mapping.getByRole('button',{name:'使用已核对的位置填写'}).click()

  const panel=page.getByRole('region',{name:'智能填写整份表单'})
  await panel.getByRole('button',{name:'打开智能填写'}).click()
  const send=async label=>{
    await panel.getByLabel(/我已核对上述文本/).check()
    await panel.getByRole('button',{name:label,exact:true}).click()
  }
  await send('分析整份表单')
  await panel.getByRole('alert').getByText(/模型服务尚未配置/).waitFor()
  await send('分析整份表单')
  await panel.getByText('你们观察到了什么，安排了哪些天？',{exact:false}).first().waitFor()
  assert.equal(sent.at(-1).fields.length,4)
  assert.ok(sent.at(-1).sources.some(s=>s.kind==='original'&&s.text.includes(reviewer)))
  assert.ok(sent.at(-1).sources.some(s=>s.kind==='notice') && !sent.at(-1).sources.some(s=>s.kind==='answer'))
  await panel.getByLabel('本次补充说明（选填）').fill(studentNotes)
  await panel.getByLabel(/添加相关材料摘录/).setInputFiles({name:'记录.txt',mimeType:'text/plain',buffer:Buffer.from(extraMaterial)})
  await panel.getByLabel('记录.txt · 开头摘录').check()
  await send('生成整表候选')
  await panel.getByText(resultValues[0],{exact:true}).waitFor()
  await panel.getByRole('button',{name:'确认带入所选候选'}).click()
  const editor=page.getByRole('region',{name:'填写表单'})
  const first=editor.getByLabel(labels[0])
  const second=editor.getByLabel(labels[1])
  assert.equal(await first.inputValue(),resultValues[0])
  assert.equal(await second.inputValue(),resultValues[1])
  assert.equal(await editor.getByLabel(labels[2]).inputValue(),'3')
  assert.ok(sent.at(-1).sources.some(s=>s.kind==='material'))
  await first.fill('我已手工复核并保留自己的表达。')
  await panel.locator('article').filter({has:page.getByRole('heading',{name:labels[1],exact:true})})
    .getByRole('button',{name:'选择重做此字段'}).click()
  await panel.getByLabel('允许引用当前已填写的普通字段').check()
  await send('重新生成所选字段')
  await panel.locator('.candidate').filter({hasText:resultValues[1]}).waitFor()
  assert.equal(sent.at(-1).fields.length,1)
  assert.equal(sent.at(-1).fields[0].label,labels[1])
  assert.ok(sent.at(-1).sources.some(source=>source.id==='filled:f0' && source.text==='我已手工复核并保留自己的表达。'))
  assert.ok(!sent.at(-1).sources.some(source=>source.id==='filled:'+sent.at(-1).fields[0].id))
  page.once('dialog',dialog=>dialog.accept())
  await panel.getByRole('button',{name:'确认带入所选候选'}).click()
  assert.equal(await first.inputValue(),'我已手工复核并保留自己的表达。')
  await editor.getByRole('button',{name:'预览填写内容',exact:true}).click()
  await page.getByRole('checkbox',{name:'我确认这份文件的填写值和文件名'}).check()
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:/确认并下载/}).click()])
  const filename=path.join(out,'智能填写合成样张.'+format)
  await download.saveAs(filename)
  const xml=strFromU8(unzipSync(await readFile(filename))[entry.part])
  assert.ok(xml.includes('我已手工复核并保留自己的表达。')&&xml.includes(resultValues[1]))
  assert.ok(!xml.includes(resultValues[0]))
  const kept=await page.evaluate(({xml,format,doc,sheet})=>{
    const parsed=new DOMParser().parseFromString(xml,'application/xml')
    if(format==='docx')return [...parsed.getElementsByTagNameNS(doc,'tr')].slice(3).map(row=>row.textContent)
    return [...parsed.getElementsByTagNameNS(sheet,'c')].filter(c=>['B4','B5','B6'].includes(c.getAttribute('r'))).map(c=>c.textContent)
  },{xml,format,doc,sheet})
  assert.deepEqual(kept,format==='docx'?[labels[3],reviewer,'如何处置？']:['','',''])
  await page.unroute('**/api/v1/form-assistant')
  console.log('PASS browser double, questions, sourced candidates, date calculation, selected regeneration, candidate review and file readback:',format)
}

async function run(){
  assert.ok(out && new URL(base).hostname==='127.0.0.1' && new URL(backend).hostname==='127.0.0.1')
  await mkdir(out,{recursive:true})
  const email='smart-'+randomUUID().slice(0,10)+'@example.com'
  const password=randomUUID()
  const registered=await post('register',{email,password})
  await post('verify',{token:registered.development_verification_token})
  const browser=await chromium.launch({channel:'msedge'})
  try{
    for(const format of ['docx','xlsx']){
      const page=await browser.newPage({viewport:{width:420,height:900},acceptDownloads:true})
      page.setDefaultTimeout(10000)
      try{
        await page.goto(base+'/auth/login')
        await page.locator('input[type=email]').fill(email)
        await page.locator('input[type=password]').fill(password)
        await page.getByRole('button',{name:'提交',exact:true}).click()
        await page.waitForURL(url=>!url.pathname.startsWith('/auth'))
        await page.locator('#app').evaluate(root=>root.__vue_app__.config.globalProperties.$router.push('/forms/import'))
        await use(page,format)
      }catch(error){console.error((await page.locator('body').innerText()).slice(-2200));throw error}
      finally{await page.close()}
    }
  }finally{await browser.close()}
}
run().catch(error=>{console.error(error);process.exitCode=1})
