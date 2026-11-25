import {profileKey} from './demoProfile'
import {reasonField,type ReasonVersion} from './reasonDraft'
import {scenarioFields,scenarios,type FormValues,type Scenario} from './scenarios'
import {draftIdentity,draftStorageKey,type DraftStorage} from './savedDraftSession'

export type SavedReason = {value:string;accepted?:ReasonVersion}
export type SavedFormDraft = {key:string;scenarioId:string;revision:number;values:FormValues;reason?:SavedReason}
export type DraftReference = {batchId:string;sourceId:string;documentId:string;documentRevision:number;sha256:string}
export class DraftRevisionConflict extends Error {
  constructor() { super('草稿保存版本已变化。当前输入仍在，请核对已保存版本。') }
}

export function readDraftReference(key: string): DraftReference | undefined {
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

export function recoverableFields(scenario: Scenario) {
  return scenarioFields(scenario).filter(field=>profileKey(scenario,field))
}

function pickValues(scenario: Scenario,values: Record<string,unknown>): FormValues {
  return Object.fromEntries(recoverableFields(scenario).flatMap(field=>{
    const value = values[field.id]
    return typeof value==='string' && value.length<=300 && value.trim() ? [[field.id,value]] : []
  }))
}

const isRecord = (value:unknown): value is Record<string,unknown> =>
  Boolean(value && typeof value==='object' && !Array.isArray(value))
const validText = (value:unknown,limit:number): value is string =>
  typeof value==='string' && value.length<=limit && Boolean(value.trim())

function savedReason(scenario:Scenario,value:unknown): SavedReason | undefined {
  if (value===undefined) return
  if (!reasonField(scenario) || !isRecord(value) || !validText(value.value,4000)) {
    throw Error('理由为空、过长或不适用此原件，无法保存。')
  }
  const accepted = value.accepted
  if (accepted===undefined) return {value:value.value}
  if (!isRecord(accepted) || !validText(accepted.text,4000) || !Array.isArray(accepted.awards) ||
      accepted.awards.length>(scenario.id==='scholarship' ? 4 : 0)) throw Error('理由依据无法核对。')
  const seen = new Set<string>()
  const awards = accepted.awards.map((award:unknown)=>{
    if (!isRecord(award) || !isRecord(award.entry) || !isRecord(award.source)) throw Error('理由依据无法核对。')
    const {id,revision,title} = award.entry
    const {quote} = award.source
    if (typeof id!=='string' || !draftIdentity.test(id) || seen.has(id) ||
        typeof revision!=='number' || !Number.isSafeInteger(revision) || revision<1 ||
        !validText(title,240) || !validText(quote,600) ||
        award.source.id!=='block:client:'+id || award.source.revision!==revision) throw Error('理由依据无法核对。')
    seen.add(id)
    return {entry:{id,revision,title},source:{id:'block:client:'+id,revision,quote}}
  })
  return {value:value.value,accepted:{text:accepted.text,awards}}
}

export function readFormDrafts(owner: string,batch: string,storage: DraftStorage = sessionStorage): SavedFormDraft[] {
  const raw = storage.getItem(draftStorageKey(owner,batch))
  if (raw===null) return []
  try {
    const records: unknown = JSON.parse(raw)
    if (!Array.isArray(records)) throw Error()
    const seen = new Set<string>()
    return records.map(item=>{
      const template = scenarios.find(scenario=>scenario.id===item?.scenarioId)
      if (!template || typeof item.key!=='string' || readDraftReference(item.key)?.batchId!==batch ||
          !Number.isSafeInteger(item.revision) || item.revision<1 || seen.has(item.key) ||
          typeof item.values!=='object' || !item.values || Array.isArray(item.values)) throw Error()
      seen.add(item.key)
      const reason = savedReason(template,item.reason)
      return {key:item.key,scenarioId:template.id,revision:item.revision,values:pickValues(template,item.values),
        ...(reason ? {reason} : {})}
    })
  } catch { throw Error('保存的草稿无法读取。可清除本批次保存记录后重新保存填写内容。') }
}

export function saveFormDraft(owner: string,batch: string,key: string,scenario: Scenario,values: FormValues,
                              expectedRevision: number,options: {storage?:DraftStorage;reason?:SavedReason} = {}) {
  const storage = options.storage ?? sessionStorage
  if (readDraftReference(key)?.batchId!==batch) throw Error('原件版本待核对，请重新打开表单。')
  const records = readFormDrafts(owner,batch,storage)
  const previous = records.find(item=>item.key===key)
  if ((previous?.revision ?? 0)!==expectedRevision) throw new DraftRevisionConflict()
  const reason = savedReason(scenario,options.reason)
  const next:SavedFormDraft = {key,scenarioId:scenario.id,values:pickValues(scenario,values),revision:expectedRevision+1,
    ...(reason ? {reason} : {})}
  try {
    storage.setItem(draftStorageKey(owner,batch),JSON.stringify([...records.filter(item=>item.key!==key),next]))
  } catch { throw Error('浏览器未能保存草稿，当前填写内容仍在。') }
  return next
}

export function clearFormDrafts(owner: string,batch: string,storage: DraftStorage = sessionStorage) {
  storage.removeItem(draftStorageKey(owner,batch))
}
