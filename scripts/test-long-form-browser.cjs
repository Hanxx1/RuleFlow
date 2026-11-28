const assert = require('node:assert/strict')
const {chromium} = require('playwright')
const {strFromU8,strToU8,unzipSync,zipSync} = require('../mobile/node_modules/fflate')

const base = process.env.FORM_DEMO_URL || 'http://127.0.0.1:5199'
const word = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
const sheet = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
const rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
const pkg = 'http://schemas.openxmlformats.org/package/2006/relationships'
const types = 'http://schemas.openxmlformats.org/package/2006/content-types'
const wordPart = 'word/document.xml'
const sheetPart = 'xl/worksheets/sheet1.xml'
const wordCell = (value,span=1) => '<w:tc><w:tcPr><w:gridSpan w:val="'+span+'"/></w:tcPr><w:p><w:r><w:t>'+value+'</w:t></w:r></w:p></w:tc>'
const wordRow = (...cells) => '<w:tr>'+cells.join('')+'</w:tr>'
const reviewer = wordRow(wordCell('审核人信息',2))+wordRow(wordCell('情况说明（不少于300字）'),wordCell(''))
const mergeCells = '<mergeCells count="2"><mergeCell ref="A2:D2"/><mergeCell ref="A3:D3"/></mergeCells>'
const cell = (address,value) => '<c r="'+address+'" t="inlineStr"><is><t>'+value+'</t></is></c>'
const row = (index,cells) => '<row r="'+index+'">'+cells+'</row>'
const sheetReviewer = row(4,cell('A4','审核人信息'))+row(5,cell('A5','个人总结')+'<c r="B5" s="1"/>')

function fixture(format) {
  const doc = format==='docx'
  const part = doc ? wordPart : sheetPart
  const main = doc ? part : 'xl/workbook.xml'
  const mime = 'application/vnd.openxmlformats-officedocument.'+(doc ? 'wordprocessingml.document' : 'spreadsheetml.sheet')
  const parts = {
    '[Content_Types].xml':'<Types xmlns="'+types+'"><Override PartName="/'+main+'" ContentType="'+mime+'.main+xml"/></Types>',
    '_rels/.rels':'<Relationships xmlns="'+pkg+'"><Relationship Id="r" Type="'+rel+'/officeDocument" Target="'+main+'"/></Relationships>',
  }
  if (doc) {
    parts[part] = '<w:document xmlns:w="'+word+'"><w:body><w:tbl>'+
      wordRow(wordCell('学号'),wordCell(''))+
      wordRow(wordCell('申请理由（不少于３００字）',2))+
      wordRow(wordCell('',2))+reviewer+'</w:tbl></w:body></w:document>'
  } else {
    parts[main] = '<workbook xmlns="'+sheet+'" xmlns:r="'+rel+'"><sheets><sheet name="申请表" sheetId="1" r:id="r"/></sheets></workbook>'
    parts['xl/_rels/workbook.xml.rels'] = '<Relationships xmlns="'+pkg+'"><Relationship Id="r" Type="'+rel+'/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    parts['xl/styles.xml'] = '<styleSheet xmlns="'+sheet+'"><cellXfs count="2"><xf/><xf applyAlignment="1"><alignment wrapText="1"/></xf></cellXfs></styleSheet>'
    parts[part] = '<worksheet xmlns="'+sheet+'"><sheetData>'+row(1,cell('A1','学号')+'<c r="B1" s="1"/>')+
      row(2,cell('A2','个人总结（不少于300字）'))+row(3,'<c r="A3" s="1"/>')+sheetReviewer+'</sheetData>'+mergeCells+'</worksheet>'
  }
  const buffer = Buffer.from(zipSync(Object.fromEntries(Object.entries(parts).map(([name,value])=>[name,strToU8(value)]))))
  return {name:'陌生长文.'+format,mimeType:mime,buffer,part}
}

async function verify(page, format) {
  await page.goto(base+'/forms/import')
  const original = fixture(format)
  const wordForm = format==='docx'
  const field = wordForm ? 'reason' : 'achievement'
  const label = wordForm ? '申请理由' : '个人总结'
  await page.getByLabel('通知正文').fill('请如实填写'+label+'，不超过300字。')
  await page.getByLabel(/选择申请表原件/).setInputFiles(original)
  await page.getByRole('button',{name:'核对通知与附件'}).click()
  await page.getByLabel('附件用途 · '+original.name).selectOption('form')
  await page.getByLabel('我已核对通知原文和需人工办理的要求').check()
  await page.getByRole('button',{name:'按此通知填写选中原表'}).click()
  const mapping = page.getByRole('group',{name:'核对原表字段位置'})
  assert.equal(await mapping.getByRole('combobox',{name:/写入位置 · (情况说明|审核人)/}).count(),0)
  await mapping.getByRole('checkbox',{name:'我已对照原表确认写入位置和需人工核对的要求'}).check()
  await mapping.getByRole('button',{name:'使用已核对的位置填写'}).click()

  await page.locator('#studentId').fill('00005834')
  const longText = page.locator('#'+field)
  const draft = '甲'.repeat(149)+'\n'+'乙'.repeat(150)
  await longText.fill(draft)
  const notice = page.getByText(/已填 299 字.*至少 300 字.*最多 300 字/)
  await notice.waitFor()
  await longText.locator('..').getByText('至少填写 300 字',{exact:true}).waitFor()
  const accepted = draft+'丙'
  await longText.fill(accepted+'丁')
  await longText.locator('..').getByText('最多填写 300 字',{exact:true}).waitFor()
  await longText.fill(accepted)
  await page.getByRole('button',{name:'预览填写内容',exact:true}).click()
  await page.getByRole('checkbox',{name:'我确认这份文件的填写值和文件名'}).check()
  const [download] = await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:/确认并下载/}).click()])
  const file = await download.createReadStream()
  const chunks = []
  for await (const chunk of file) chunks.push(chunk)
  const contents = strFromU8(unzipSync(Buffer.concat(chunks))[original.part])
  const reloaded = await page.evaluate(({contents,wordForm,word,sheet})=>{
    const doc = new DOMParser().parseFromString(contents,'application/xml')
    if (wordForm) {
      const rows = [...doc.getElementsByTagNameNS(word,'tr')]
      const value = [...rows[2].getElementsByTagNameNS(word,'*')].map(n=>n.localName==='t'?n.textContent:n.localName==='br'?'\n':'').join('')
      return {value,reviewer:rows[4].textContent}
    }
    const cells = [...doc.getElementsByTagNameNS(sheet,'c')]
    return {value:cells.find(c=>c.getAttribute('r')==='A3').textContent,reviewer:cells.find(c=>c.getAttribute('r')==='B5').textContent}
  },{contents,wordForm,word,sheet})
  assert.equal(reloaded.value,accepted)
  assert.equal(reloaded.reviewer,wordForm?'情况说明（不少于300字）':'')
  if (!wordForm) assert.ok(contents.includes(mergeCells))
  console.log('PASS '+format+' 299/301 rejected, 300 preserved with line break, reviewer untouched')
}

async function run() {
  assert.equal(new URL(base).hostname,'127.0.0.1')
  const browser = await chromium.launch({channel:'msedge'})
  try {
    const page = await browser.newPage({viewport:{width:420,height:900},acceptDownloads:true})
    page.setDefaultTimeout(8000)
    await verify(page,'docx')
    await verify(page,'xlsx')
  } finally {await browser.close()}
}
run().catch(error=>{console.error(error);process.exitCode=1})
