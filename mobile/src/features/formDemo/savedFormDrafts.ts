import {scenarioFields,scenarios,type FormValues,type Scenario} from './scenarios'
import {draftIdentity} from './savedDraftSession'

export const draftRetentionDays = 7
export const draftRetentionMs = draftRetentionDays * 24 * 60 * 60 * 1000
const allowedFields = new Set(['name','studentId','college','major','className','gender'])
const storeName = 'accounts'
const channelName = 'campusweave-form-draft-logout'

export type SavedFormDraft = {
  key:string; scenarioId:string; revision:number; values:FormValues; savedAt:number
}
export type DraftReference = {batchId:string; sourceId:string; documentId:string; documentRevision:number; sha256:string}
export type DraftState = {epoch:number; revision:number; records:SavedFormDraft[]}
export type DraftSession = {owner:string; epoch:number}
export type DraftOperation = {type:'open'|'logout'} | ({epoch:number; batch:string} & (
  {type:'read'|'clear'} |
  {type:'save'; key:string; scenarioId:string; values:FormValues; revision:number}
))

export class DraftRevisionConflict extends Error {
  constructor() { super('草稿已被其他页面更新、清除或已到期。当前输入仍在，请重新读取保存状态。') }
}
export class DraftSessionExpired extends Error {
  constructor() { super('该账号的草稿会话已结束。请重新登录后再保存或读取草稿。') }
}

export function readDraftReference(key:string): DraftReference | undefined {
  try {
    const data: unknown = JSON.parse(key)
    if (!Array.isArray(data) || data.length!==5) return
    const [batchId,sourceId,documentId,documentRevision,sha256] = data
    if ([batchId,sourceId,documentId].some(value=>typeof value!=='string' || !draftIdentity.test(value)) ||
        !Number.isSafeInteger(documentRevision) || documentRevision<0 ||
        typeof sha256!=='string' || !/^[0-9a-f]{64}$/.test(sha256)) return
    return {batchId,sourceId,documentId,documentRevision,sha256}
  } catch { return undefined }
}

export function recoverableFields(scenario:Scenario) {
  return scenarioFields(scenario).filter(field=>allowedFields.has(field.id) && field.reusable && !field.sensitive)
}

function allowedValues(scenario:Scenario,values:FormValues) {
  return Object.fromEntries(recoverableFields(scenario).flatMap(field=>{
    const value = values[field.id]
    return typeof value==='string' && value.trim() && [...value].length<=(field.max ?? 40) &&
      (!field.choices || field.choices.includes(value)) ? [[field.id,value]] : []
  }))
}

export function applyDraftOperation(previous:DraftState | undefined,operation:DraftOperation,now:number) {
  const original = previous ?? {epoch:0,revision:0,records:[]}
  if (operation.type==='logout') {
    return {state:{epoch:original.epoch+1,revision:0,records:[]}}
  }
  const active = original.records.filter(draft=>now<draft.savedAt+draftRetentionMs)
  const state = active.length===original.records.length ? original : {...original,records:active}
  if (!('epoch' in operation)) return {state}
  if (operation.epoch!==state.epoch) throw new DraftSessionExpired()
  if (!draftIdentity.test(operation.batch)) throw Error('表单批次无效，请重新打开通知。')
  const batchRecords = state.records.filter(draft=>readDraftReference(draft.key)?.batchId===operation.batch)
  if (operation.type==='read') return {state,drafts:batchRecords}
  if (operation.type==='clear') {
    return {state:{...state,records:state.records.filter(draft=>!batchRecords.includes(draft))}}
  }
  if (operation.type!=='save') throw Error('无法核对草稿操作。')
  const scenario = scenarios.find(item=>item.id===operation.scenarioId)
  if (!scenario || readDraftReference(operation.key)?.batchId!==operation.batch) {
    throw Error('原件版本待核对，请重新打开表单。')
  }
  const matching = batchRecords.find(draft=>draft.key===operation.key)
  if ((matching?.revision ?? 0)!==operation.revision) throw new DraftRevisionConflict()
  const saved = {key:operation.key,scenarioId:scenario.id,revision:state.revision+1,
    values:allowedValues(scenario,operation.values),savedAt:now}
  return {state:{...state,revision:saved.revision,records:[...state.records.filter(draft=>draft!==matching),saved]},
    saved, drafts:[...batchRecords.filter(draft=>draft!==matching),saved]}
}

function openDraftDatabase() {
  return new Promise<IDBDatabase>((resolve,reject)=>{
    const request = indexedDB.open('campusweave-form-drafts',1)
    request.onupgradeneeded = ()=>request.result.createObjectStore(storeName)
    request.onsuccess = ()=>resolve(request.result)
    request.onerror = ()=>reject(Error('本机草稿库无法打开，请检查浏览器存储设置。'))
  })
}

async function transact(owner:string,operation:DraftOperation) {
  if (!draftIdentity.test(owner)) throw Error('请使用当前登录账户保存草稿。')
  const db = await openDraftDatabase()
  try {
    // Every account operation shares one transaction queue across tabs.
    return await new Promise<ReturnType<typeof applyDraftOperation>>((resolve,reject)=>{
      const tx = db.transaction(storeName,'readwrite')
      const store = tx.objectStore(storeName)
      const read = store.get(owner)
      let result: ReturnType<typeof applyDraftOperation>
      let failure: unknown
      read.onsuccess = ()=>{
        try {
          result = applyDraftOperation(read.result,operation,Date.now())
          if (read.result!==result.state && (read.result || result.state.epoch || result.state.records.length)) {
            store.put(result.state,owner)
          }
        } catch (error) {
          failure = error
          tx.abort()
        }
      }
      tx.oncomplete = ()=>resolve(result)
      tx.onabort = ()=>reject(failure || Error('本机草稿操作失败，当前填写内容仍在。'))
    })
  } finally { db.close() }
}

export async function openDraftSession(owner:string) {
  return (await transact(owner,{type:'open'})).state.epoch
}

export async function readFormDrafts(session:DraftSession,batch:string) {
  return (await transact(session.owner,{type:'read',epoch:session.epoch,batch})).drafts!
}

export async function saveFormDraft(session:DraftSession,batch:string,key:string,scenarioId:string,
                                    values:FormValues,revision:number) {
  const result = await transact(session.owner,{type:'save',epoch:session.epoch,batch,key,scenarioId,values,revision})
  return {saved:result.saved!,drafts:result.drafts!}
}

export async function clearFormDrafts(session:DraftSession,batch:string) {
  await transact(session.owner,{type:'clear',epoch:session.epoch,batch})
}

export async function revokeDraftSessions(owner:string) {
  const {state} = await transact(owner,{type:'logout'})
  if (typeof BroadcastChannel==='undefined') return
  // The transaction guards old tabs even if they miss this notification.
  try {
    const channel = new BroadcastChannel(channelName)
    try { channel.postMessage({owner,epoch:state.epoch}) }
    finally { channel.close() }
  } catch { /* The durable revocation has already committed. */ }
}

export function observeDraftSessionRevocation(onRevoke:(owner:string,epoch:number)=>void) {
  if (typeof BroadcastChannel==='undefined') return
  const channel = new BroadcastChannel(channelName)
  channel.onmessage = ({data})=>{
    if (typeof data?.owner==='string' && draftIdentity.test(data.owner) && Number.isSafeInteger(data.epoch)) {
      onRevoke(data.owner,data.epoch)
    }
  }
  return ()=>channel.close()
}
