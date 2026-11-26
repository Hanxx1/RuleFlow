// Run against a local development backend. All account and form values are synthetic.
const assert = require('node:assert/strict')
const {randomUUID} = require('node:crypto')
const {mkdir,readFile} = require('node:fs/promises')
const path = require('node:path')
const {chromium} = require('playwright')

const [original,out] = process.argv.slice(2)
const web = process.env.FORM_DEMO_URL || 'http://127.0.0.1:5226'
const backend = process.env.SAVED_FORM_API || 'http://127.0.0.1:8039'
const day = 24*60*60*1000
const approvedName = '宋明悦'
const privateReason = '补办原因仅用于本次申请'
const originalName = '学生证补办申请.docx'
const mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

async function api(route,{token,body}={}) {
  const form = body instanceof FormData
  const response = await fetch(backend+'/api/v1'+route,{method:body?'POST':'GET',headers:{
    ...(token ? {Authorization:'Bearer '+token} : {}),
    ...(body && !form ? {'Content-Type':'application/json'} : {}),
  },body:form?body:body?JSON.stringify(body):undefined})
  assert.ok(response.ok,route+' '+response.status)
  return (await response.json()).data
}

async function createAccount() {
  const email='rf012-'+randomUUID().slice(0,12)+'@example.com', password=randomUUID()
  const registration=await api('/auth/register',{body:{email,password}})
  await api('/auth/verify',{body:{token:registration.development_verification_token}})
  const login=await api('/auth/login',{body:{email,password}})
  return {email,password,token:login.access_token,id:login.user.id}
}

async function createBatch(owner,bytes) {
  const {id}=await api('/import-batches',{token:owner.token,body:{title:'学生证遗失补办办理通知'}})
  const body=new FormData()
  body.append('consent','true')
  body.append('files',new File(['请填学生证补办申请，打印后签字并贴照。'],'办理说明.txt',{type:'text/plain'}))
  body.append('files',new File([bytes],originalName,{type:mime}))
  await api('/import-batches/'+id+'/sources/files',{token:owner.token,body})
  return id
}

const draft = page=>page.getByRole('region',{name:'原件草稿'})
const form = page=>page.getByRole('region',{name:'填写表单'})
const name = page=>form(page).locator('#name')
const reason = page=>form(page).locator('#reason')
const nav = (page,target)=>page.locator('#app').evaluate((root,route)=>
  root.__vue_app__.config.globalProperties.$router.push(route),target)
const success = page=>draft(page).getByText('已保存当前原件的草稿字段。',{exact:true})
const conflict = page=>draft(page).getByRole('alert').filter({hasText:'草稿已被其他页面更新'})
const saveButton = page=>draft(page).getByRole('button',{name:'保存当前草稿',exact:true})

async function signIn(context,account,at) {
  const page=await context.newPage()
  if (at!==undefined) await page.clock.setFixedTime(new Date(at))
  await page.goto(web+'/auth/login')
  await page.locator('input[type=email]').fill(account.email)
  await page.locator('input[type=password]').fill(account.password)
  await page.getByRole('button',{name:'提交',exact:true}).click()
  await page.waitForURL(url=>!url.pathname.startsWith('/auth'))
  return page
}

async function open(page,batch) {
  await nav(page,'/imports/'+batch+'/forms')
  await page.getByRole('button',{name:'核验并填写选中原表',exact:true}).click()
  await draft(page).waitFor()
  await form(page).getByRole('button',{name:'显示并编辑整张表单'}).click()
}

async function saveAs(page,value) {
  await name(page).fill(value)
  await saveButton(page).click()
  await success(page).waitFor()
}

async function run() {
  assert.ok(original && out,'需要公开补办原件和隔离证据目录')
  for (const url of [web,backend]) assert.equal(new URL(url).hostname,'127.0.0.1')
  const bytes=await readFile(original)
  const [owner,other]=await Promise.all([createAccount(),createAccount()])
  const [primary,secondary,independent]=await Promise.all([
    createBatch(owner,bytes),createBatch(owner,bytes),createBatch(other,bytes),
  ])
  await mkdir(out,{recursive:true})
  const profile=path.join(out,'profile-'+randomUUID())
  const launch=()=>chromium.launchPersistentContext(profile,{channel:'msedge',headless:true,acceptDownloads:true})
  let context=await launch()
  try {
    const first=await signIn(context,owner)
    await open(first,primary)
    await reason(first).fill(privateReason)
    await form(first).locator('#phone').fill('10000000001')
    await saveAs(first,approvedName)
    await open(first,secondary)
    await saveAs(first,'周宁岚')
    await context.close()
    context=await launch()

    const reopened=await signIn(context,owner)
    await open(reopened,primary)
    assert.equal(await name(reopened).inputValue(),approvedName)
    assert.equal(await reason(reopened).inputValue(),'')
    assert.equal(await form(reopened).locator('#phone').inputValue(),'')
    await draft(reopened).getByText(/当前草稿保存至/).waitFor()
    const backupPage=await signIn(context,owner)
    await nav(backupPage,'/profile')
    const download=backupPage.waitForEvent('download')
    await backupPage.getByRole('button',{name:'导出本机备份'}).click()
    const backup=await readFile(await (await download).path(),'utf8')
    assert.doesNotMatch(backup,new RegExp(approvedName+'|'+privateReason+'|campusweave-form-drafts'))
    console.log('PASS browser restart restores approved values only; Workspace download contains no saved draft')

    const another=await signIn(context,owner)
    await open(another,primary)
    await name(reopened).fill('第一标签编辑')
    await name(another).fill('第二标签编辑')
    await Promise.all([saveButton(reopened).click(),saveButton(another).click()])
    await Promise.all([success(reopened).or(conflict(reopened)).waitFor(),success(another).or(conflict(another)).waitFor()])
    assert.equal(await success(reopened).count()+await success(another).count(),1)
    assert.equal(await conflict(reopened).count()+await conflict(another).count(),1)
    console.log('PASS two authenticated tabs attempting the same revision yield one save and one conflict')

    const unrelated=await signIn(context,other)
    await open(unrelated,independent)
    await saveAs(unrelated,'独立账户草稿')
    const idle=await signIn(context,owner)
    await nav(backupPage,'/me')
    backupPage.once('dialog',dialog=>dialog.accept())
    await backupPage.getByRole('button',{name:'退出登录',exact:true}).click()
    await backupPage.waitForURL(url=>url.pathname==='/auth/login')
    await reopened.getByRole('alert').filter({hasText:'草稿会话已结束'}).waitFor()
    await nav(idle,'/imports/'+secondary+'/forms')
    await idle.getByRole('button',{name:'核验并填写选中原表',exact:true}).click()
    await idle.getByRole('alert').filter({hasText:'草稿会话已结束'}).waitFor()
    assert.equal(await saveButton(idle).count(),0)
    await open(reopened,primary)
    assert.equal(await name(reopened).inputValue(),'')
    assert.equal(await saveButton(reopened).isDisabled(),true)
    const fresh=await signIn(context,owner)
    await open(fresh,primary)
    assert.equal(await name(fresh).inputValue(),'')
    await open(fresh,secondary)
    assert.equal(await name(fresh).inputValue(),'')
    assert.equal(await name(unrelated).inputValue(),'独立账户草稿')
    await open(unrelated,independent)
    assert.equal(await name(unrelated).inputValue(),'独立账户草稿')
    console.log('PASS real logout clears both account batches and revokes open and idle tabs; another owner remains intact')

    const now=Date.now()
    await fresh.clock.setFixedTime(new Date(now))
    await saveAs(fresh,'期限测试首次')
    const renewal=await signIn(context,owner,now+6*day)
    await open(renewal,secondary)
    assert.equal(await name(renewal).inputValue(),'期限测试首次')
    await saveAs(renewal,'期限测试更新')
    const pastInitialDeadline=await signIn(context,owner,now+7*day)
    await open(pastInitialDeadline,secondary)
    assert.equal(await name(pastInitialDeadline).inputValue(),'期限测试更新')
    const pastFinalDeadline=await signIn(context,owner,now+13*day)
    await open(pastFinalDeadline,secondary)
    assert.equal(await name(pastFinalDeadline).inputValue(),'')
    assert.equal(await draft(pastFinalDeadline).getByText(/当前草稿保存至/).count(),0)
    console.log('PASS explicit save renews seven-day retention; reading after the renewed deadline returns no draft')
  } finally { await context.close() }
}

run().catch(error=>{console.error(error);process.exitCode=1})
