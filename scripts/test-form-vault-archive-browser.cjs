// Uses dedicated local test services with only synthetic accounts and form values.
const assert = require('node:assert/strict')
const {randomUUID} = require('node:crypto')
const {execFileSync} = require('node:child_process')
const {mkdir,readFile} = require('node:fs/promises')
const path = require('node:path')
const {chromium} = require('playwright')
const templates = require('../mobile/src/features/formDemo/templateData.json')

const [database,output] = process.argv.slice(2)
const python = process.env.SAVED_FORM_PYTHON || 'python'
const base = 'http://127.0.0.1:5200'
const backend = 'http://127.0.0.1:8027'
const xlsx = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const endpoint = '/api/v1/vault/items'
const attachment = '国家奖学金表.xlsx'

function request(route,{method='GET',token,body}={}) {
  const json = body && !(body instanceof FormData)
  return fetch(backend+'/api/v1'+route,{method,headers:{
    ...(token ? {Authorization:'Bearer '+token} : {}),...(json ? {'Content-Type':'application/json'} : {}),
  },body:json ? JSON.stringify(body) : body})
}

async function call(route,options) {
  const response = await request(route,options)
  assert.equal(response.status,200,route)
  return (await response.json()).data
}

async function account() {
  const email = 'vault-test-'+randomUUID()+'@example.com'
  const password = randomUUID()
  const registered = await call('/auth/register',{method:'POST',body:{email,password}})
  await call('/auth/verify',{method:'POST',body:{token:registered.development_verification_token}})
  const login = await call('/auth/login',{method:'POST',body:{email,password}})
  return {email,password,id:login.user.id,token:login.access_token}
}

async function run() {
  assert.ok(database && output)
  await mkdir(output,{recursive:true})
  const owner = await account(), other = await account()
  const token = owner.token
  const primary = await call('/cases',{token,method:'POST',body:{title:'奖学金申请联调事项'}})
  const alternative = await call('/cases',{token,method:'POST',body:{title:'另一联调事项'}})
  const createBatch = async()=>{
    const batch = await call('/import-batches',{token,method:'POST',body:{title:'材料库联调通知'}})
    const body = new FormData()
    body.append('consent','true')
    body.append('files',new File(['奖学金办理联调\n申请表填写后由申请人签字。'],'办理通知.txt',{type:'text/plain'}))
    body.append('files',new File([Buffer.from(templates['scholarship.xlsx'],'base64')],attachment,{type:xlsx}))
    await call('/import-batches/'+batch.id+'/sources/files',{token,method:'POST',body})
    return batch.id
  }
  const linked = await createBatch(), standalone = await createBatch()
  const bind = caseId=>execFileSync(python,['-c',[
    'import sqlite3, sys',
    'db, owner, batch, case = sys.argv[1:]',
    'with sqlite3.connect(db) as c:',
    '    assert c.execute("select count(*) from cases where id=? and owner_id=?", (case, owner)).fetchone()==(1,)',
    '    assert c.execute("update import_batches set case_id=? where id=? and owner_id=?", (case, batch, owner)).rowcount==1',
  ].join('\n'),database,owner.id,linked,caseId])
  bind(primary.id)

  const browser = await chromium.launch({channel:'msedge',headless:true})
  try {
    const page = await browser.newPage({viewport:{width:430,height:900},acceptDownloads:true})
    page.setDefaultTimeout(10000)
    const writes = []
    page.on('request',req=>{if (req.url()===backend+endpoint && req.method()==='POST') writes.push(req.method())})
    await page.goto(base+'/auth/login')
    await page.locator('input[type=email]').fill(owner.email)
    await page.locator('input[type=password]').fill(owner.password)
    await page.getByRole('button',{name:'提交',exact:true}).click()
    await page.waitForURL(url=>!url.pathname.startsWith('/auth'))
    const editor = page.getByRole('region',{name:'填写表单'})
    const intake = page.getByRole('region',{name:'已保存通知与附件'})
    const preview = page.getByRole('region',{name:'导出预览'})
    const checkForm = preview.getByLabel('我确认这份文件的填写值和文件名')
    const checkPrivacy = preview.getByLabel('我已核对文件隐私并同意上传到当前账号的材料库')
    const linkCase = preview.getByLabel('关联此通知的事项')
    const submit = preview.getByRole('button',{name:'上传并存入材料库'})
    const select = async()=>{
      await intake.getByRole('radio',{name:new RegExp(attachment)}).check()
      await intake.getByLabel('我已核对这份表的通知原文及提交要求').check()
      await intake.getByRole('button',{name:'核验并填写选中原表'}).click()
      await editor.waitFor()
    }
    const open = async batch=>{
      await page.locator('#app').evaluate((root,id)=>root.__vue_app__.config.globalProperties.$router.push('/imports/'+id+'/sources'),batch)
      await page.getByRole('link',{name:'按已保存通知填表'}).click()
      await select()
    }
    const fill = async (name,stem)=>{
      const sample = await page.evaluate(async()=>(await import('/src/features/formDemo/scenarios.ts')).exampleValues.scholarship)
      for (const [id,value] of Object.entries({...sample,name})) {
        const field = editor.locator('#'+id)
        if (!await field.count()) continue
        if (await field.evaluate(element=>element.tagName)==='SELECT') await field.selectOption(value)
        else await field.fill(value)
      }
      await editor.getByLabel('文件名（不含扩展名）').fill(stem)
      await editor.getByRole('button',{name:'预览填写内容',exact:true}).click()
      await checkForm.check()
      await preview.getByText('保存到材料库',{exact:true}).click()
    }
    const saveWithConfirmation = ()=>{page.once('dialog',dialog=>dialog.accept());return submit.click()}
    const list = (identity=token)=>call('/vault/items?category=form',{token:identity})

    await open(linked)
    const filename = '奖学金申请表-程予书.xlsx'
    await fill('程予书',filename.slice(0,-5))
    assert.equal(await linkCase.isChecked(),false)
    assert.equal(await submit.isDisabled(),true)
    await checkPrivacy.check()
    page.once('dialog',dialog=>dialog.dismiss())
    await submit.click()
    assert.deepEqual(await list(),[])
    assert.equal(writes.length,0)
    console.log('PASS Vault action requires distinct consent; dismissing manual review sends no bytes')

    await linkCase.check()
    page.once('dialog',async dialog=>{bind(alternative.id);await dialog.accept()})
    await submit.click()
    await page.getByRole('alert').filter({hasText:'关联事项已变化'}).waitFor()
    assert.equal(writes.length,0)
    assert.equal(await editor.locator('#name').inputValue(),'程予书')
    bind(primary.id)
    console.log('PASS a case change during the privacy confirmation revokes export and prevents upload')

    await select()
    await editor.getByRole('button',{name:'预览填写内容',exact:true}).click()
    await checkForm.check()
    assert.equal(await checkPrivacy.count(),1)
    assert.equal(await checkPrivacy.isChecked(),false)
    const [download] = await Promise.all([page.waitForEvent('download'),
      preview.getByRole('button',{name:/确认并下载/}).click()])
    assert.equal(download.suggestedFilename(),filename)
    const local = path.join(output,filename)
    await download.saveAs(local)
    await preview.getByText('保存到材料库',{exact:true}).click()
    await linkCase.check()
    await checkPrivacy.check()
    await saveWithConfirmation()
    await preview.getByText('此确认版本已保存并关联当前事项。',{exact:true}).waitFor()
    assert.equal(await submit.count(),0)
    const [linkedItem] = await list()
    assert.equal(writes.length,1)
    assert.equal(linkedItem.name,filename)
    assert.deepEqual(linkedItem.case_ids,[primary.id])
    assert.deepEqual(linkedItem.task_ids,[])
    const original = await request('/vault/items/'+linkedItem.id+'/content',{token})
    assert.equal(original.status,200)
    assert.equal(original.headers.get('content-type'),xlsx)
    assert.equal(original.headers.get('cache-control'),'private, no-store')
    assert.deepEqual(Buffer.from(await original.arrayBuffer()),await readFile(local))
    assert.deepEqual(await list(other.token),[])
    assert.equal((await request('/vault/items/'+linkedItem.id+'/content',{token:other.token})).status,404)
    assert.equal((await request('/vault/items/'+linkedItem.id+'/content')).status,401)
    console.log('PASS owner lists and downloads byte-identical archive with selected case; other accounts and guests denied')

    await open(standalone)
    await fill('林静宜','奖学金申请表-林静宜')
    assert.equal(await linkCase.count(),0)
    await checkPrivacy.check()
    await page.route(backend+endpoint,async route=>{
      const response = await route.fetch({maxRetries:0})
      assert.equal(response.status(),200)
      await route.abort('failed')
    },{times:1})
    await saveWithConfirmation()
    await preview.getByText('保存状态待核对。',{exact:true}).waitFor()
    assert.equal(await submit.count(),0)
    const items = await list()
    assert.equal(items.length,2)
    const unlinked = items.find(item=>item.id!==linkedItem.id)
    assert.deepEqual(unlinked.case_ids,[])
    assert.equal(writes.length,2)
    await preview.getByRole('link',{name:'查看材料库'}).click()
    await page.getByRole('heading',{name:unlinked.name,exact:true}).waitFor()
    const archived = page.locator('article').filter({has:page.getByRole('heading',{name:linkedItem.name,exact:true})})
    await archived.getByRole('button',{name:'查看',exact:true}).click()
    const dialog = page.getByRole('dialog',{name:linkedItem.name})
    const [retrieved] = await Promise.all([page.waitForEvent('download'),
      dialog.getByRole('link',{name:'下载文件',exact:true}).click()])
    assert.equal(retrieved.suggestedFilename(),filename)
    assert.deepEqual(await readFile(await retrieved.path()),await readFile(local))
    console.log('PASS no-case lost response leads to review without duplicate POST; Vault UI downloads identical bytes')
  } finally {
    await browser.close()
  }
}

run().catch(error=>{console.error(error);process.exitCode=1})
