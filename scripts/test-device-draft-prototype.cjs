// RF-012 feasibility test. This prototype never runs in the product entry points.
const assert = require('node:assert/strict')
const {randomUUID} = require('node:crypto')
const {mkdir,readFile} = require('node:fs/promises')
const path = require('node:path')
const {chromium} = require('playwright')

const [original,output] = process.argv.slice(2)
const web = process.env.FORM_DEMO_URL || 'http://127.0.0.1:5225'
const backend = process.env.SAVED_FORM_API || 'http://127.0.0.1:8039'
const filename = '学生证补办申请.docx'
const mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const sample = {name:'沈宁远',studentId:'00005823',phone:'00000000000',identity:'00000020050101000X',
  reason:'仅本次使用的理由',photo:'本次照片',filename:'限定文件名',confirm:'审核确认'}

function startDraftPrototype() {
  const dbName = 'campusweave-rf012-test-only'
  function openDb() {
    return new Promise((resolve,reject)=>{
      const request = indexedDB.open(dbName,1)
      request.onupgradeneeded = ()=>request.result.createObjectStore('owners')
      request.onsuccess = ()=>resolve(request.result)
      request.onerror = ()=>reject(request.error)
    })
  }
  async function transaction(owner,action,mode='readwrite') {
    const db = await openDb()
    try {
      return await new Promise((resolve,reject)=>{
        // The same transaction reads and commits the revision across tabs.
        const tx = db.transaction('owners',mode)
        const owners = tx.objectStore('owners')
        const request = owners.get(owner)
        let result, failure
        request.onsuccess = ()=>{
          try {
            const record = request.result ?? {epoch:'initial',items:{}}
            const step = action(record)
            if (step.record) owners.put(step.record,owner)
            result = step.result
          } catch (error) {
            failure = error
            tx.abort()
          }
        }
        tx.oncomplete = ()=>resolve(result)
        tx.onabort = ()=>reject(failure ?? tx.error)
      })
    } finally { db.close() }
  }
  function adapter(items) {
    return {
      get length() { return Object.keys(items).length },
      key: index=>Object.keys(items)[index] ?? null,
      getItem: key=>Object.hasOwn(items,key) ? items[key] : null,
      setItem: (key,value)=>{items[key]=value},
      removeItem: key=>{delete items[key]},
    }
  }
  window.testDraftDevice = {
    async load(owner,batch) {
      const {readFormDrafts} = await import('/src/features/formDemo/savedFormDrafts.ts')
      return transaction(owner,record=>({result:{
        epoch:record.epoch,drafts:readFormDrafts(owner,batch,adapter(record.items)),
      }}),'readonly')
    },
    async save({owner,batch,key,values,epoch,revision}) {
      const {saveFormDraft} = await import('/src/features/formDemo/savedFormDrafts.ts')
      const {scenarios} = await import('/src/features/formDemo/scenarios.ts')
      const scenario = scenarios.find(item=>item.id==='photo')
      return transaction(owner,record=>{
        if (record.epoch!==epoch) throw Error('本机草稿已清理，请重新核对。')
        const saved = saveFormDraft(owner,batch,key,scenario,values,revision,{storage:adapter(record.items)})
        return {record,result:saved}
      })
    },
    clearOwner(owner) {
      // Only a freshness marker survives deletion of the draft data.
      return transaction(owner,()=>({record:{epoch:crypto.randomUUID(),items:{}}}))
    },
  }
}

async function run() {
  assert.ok(original && output,'需要校方补办原件与独立输出目录')
  for (const address of [web,backend]) assert.equal(new URL(address).hostname,'127.0.0.1')
  const account = async()=>{
    const email = 'rf012-'+randomUUID().slice(0,12)+'@example.com'
    const password = randomUUID()
    const registration = await api('/auth/register',{body:{email,password}})
    await api('/auth/verify',{body:{token:registration.development_verification_token}})
    const access = await api('/auth/login',{body:{email,password}})
    return {email,password,id:access.user.id,token:access.access_token}
  }
  const owner = await account(), other = await account()
  const {id:batch} = await api('/import-batches',{token:owner.token,body:{title:'RF-012 本机草稿技术样例'}})
  const batchPath = '/import-batches/'+batch
  const upload = async (destination=batchPath,user=owner)=>{
    const form = new FormData()
    form.set('consent','true')
    form.set('files',new File([await readFile(original)],filename,{type:mime}))
    const [source] = await api(destination+'/sources/files',{token:user.token,body:form})
    return source
  }
  const initial = await upload()
  await mkdir(output,{recursive:true})
  const profile = path.join(output,'profile-'+randomUUID())
  const launch = async()=>{
    const context = await chromium.launchPersistentContext(profile,{channel:'msedge',headless:true})
    await context.addInitScript(startDraftPrototype)
    return context
  }
  let context = await launch()
  const signIn = async who=>{
    const page = await context.newPage()
    await page.goto(web+'/auth/login')
    await page.locator('input[type=email]').fill(who.email)
    await page.locator('input[type=password]').fill(who.password)
    await page.getByRole('button',{name:'提交',exact:true}).click()
    await page.waitForURL(url=>!url.pathname.startsWith('/auth'))
    return page
  }
  const readKey = (page,batchId=batch)=>page.evaluate(async batchId=>{
    const {loadSavedNotice,loadSavedOriginal,savedDraftKey} = await import('/src/features/formDemo/savedNotice.ts')
    const fromAccount = await loadSavedNotice(batchId)
    const source = fromAccount.sources.find(item=>item.name==='学生证补办申请.docx')
    if (!(await loadSavedOriginal(fromAccount,source)).scenario) throw Error('需使用已核验的原件')
    return savedDraftKey(batchId,source)
  },batchId)
  const load = (page,user,batchId=batch)=>page.evaluate(([who,id])=>window.testDraftDevice.load(who,id),[user.id,batchId])
  const write = (page,data)=>page.evaluate(args=>window.testDraftDevice.save(args),data)
  try {
    const page = await signIn(owner)
    const key = await readKey(page)
    const state = await load(page,owner)
    assert.deepEqual(state.drafts,[])
    const save = {owner:owner.id,batch,key,values:sample,epoch:state.epoch,revision:0}
    const first = await write(page,save)
    assert.deepEqual(first.values,{name:sample.name,studentId:sample.studentId})
    assert.equal(first.reason,undefined)

    await context.close()
    context = await launch()
    const reopened = await signIn(owner)
    assert.equal(await readKey(reopened),key)
    assert.deepEqual((await load(reopened,owner)).drafts,[first])
    const unrelated = await signIn(other)
    await assert.rejects(readKey(unrelated))
    assert.deepEqual((await load(unrelated,other)).drafts,[])
    const {id:otherBatch} = await api('/import-batches',{token:other.token,body:{title:'独立资料保留对照'}})
    await upload('/import-batches/'+otherBatch,other)
    const otherKey = await readKey(unrelated,otherBatch)
    const {epoch:otherEpoch} = await load(unrelated,other,otherBatch)
    const unaffected = await write(unrelated,{
      owner:other.id,batch:otherBatch,key:otherKey,values:{name:'其他账户'},epoch:otherEpoch,revision:0,
    })
    console.log('PASS real login and original verification before same-device browser restart recovery; server denies foreign original; caller-selected local partitions are independent; private fields excluded')

    const secondTab = await signIn(owner)
    assert.equal(await readKey(secondTab),key)
    const concurrent = await Promise.allSettled([
      write(reopened,{...save,revision:1,values:{name:'第一处修改'}}),
      write(secondTab,{...save,revision:1,values:{name:'第二处修改'}}),
    ])
    assert.equal(concurrent.filter(item=>item.status==='fulfilled').length,1)
    const conflict = concurrent.find(item=>item.status==='rejected')
    assert.match(conflict.reason.message,/草稿保存版本已变化/)
    const latest = (await load(reopened,owner)).drafts[0]
    assert.equal(latest.revision,2)
    console.log('PASS two simultaneous writers commit one revision and reject the stale input')

    await api(batchPath+'/sources/'+initial.id,{token:owner.token,method:'DELETE'})
    const replacement = await upload()
    assert.notEqual(initial.id,replacement.id)
    const newKey = await readKey(reopened)
    assert.notEqual(newKey,key)
    assert.equal((await load(reopened,owner)).drafts.some(item=>item.key===newKey),false)
    assert.deepEqual((await load(reopened,owner)).drafts,[latest])
    await reopened.evaluate(who=>window.testDraftDevice.clearOwner(who),owner.id)
    await assert.rejects(write(secondTab,{...save,revision:2}),/草稿已清理/)
    assert.deepEqual((await load(reopened,owner)).drafts,[])
    assert.deepEqual((await load(unrelated,other,otherBatch)).drafts,[unaffected])
    console.log('PASS replaced original has no automatic match; simulated owner cleanup rejects late writes from another tab')
  } finally { await context.close() }
}

async function api(route,{token,body,method}={}) {
  const file = body instanceof FormData
  const response = await fetch(backend+'/api/v1'+route,{method:method || (body?'POST':'GET'),headers:{
    ...(token?{Authorization:'Bearer '+token}:{}),...(body&&!file?{'Content-Type':'application/json'}:{}),
  },body:body?(file?body:JSON.stringify(body)):undefined})
  assert.ok(response.ok,route+' '+response.status)
  return (await response.json()).data
}

run().catch(error=>{console.error(error);process.exitCode=1})
