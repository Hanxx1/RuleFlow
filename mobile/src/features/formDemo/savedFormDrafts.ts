import {profileKey} from './demoProfile'
import {scenarioFields,scenarios,type FormValues,type Scenario} from './scenarios'
import {draftIdentity,draftStorageKey,type DraftStorage} from './savedDraftSession'

export type SavedFormDraft = {key:string;scenarioId:string;revision:number;values:FormValues}
export type DraftReference = {batchId:string;sourceId:string;documentId:string;documentRevision:number;sha256:string}

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
      return {key:item.key,scenarioId:template.id,revision:item.revision,values:pickValues(template,item.values)}
    })
  } catch { throw Error('保存的草稿无法读取。可清除本批次保存记录后重新保存填写内容。') }
}

export function saveFormDraft(owner: string,batch: string,key: string,scenario: Scenario,values: FormValues,
                              expectedRevision: number,storage: DraftStorage = sessionStorage) {
  if (readDraftReference(key)?.batchId!==batch) throw Error('原件版本待核对，请重新打开表单。')
  const records = readFormDrafts(owner,batch,storage)
  const previous = records.find(item=>item.key===key)
  if ((previous?.revision ?? 0)!==expectedRevision) throw Error('草稿保存版本已变化，请重新打开表单核对。')
  const next = {key,scenarioId:scenario.id,values:pickValues(scenario,values),revision:expectedRevision+1}
  try {
    storage.setItem(draftStorageKey(owner,batch),JSON.stringify([...records.filter(item=>item.key!==key),next]))
  } catch { throw Error('浏览器未能保存草稿，当前填写内容仍在。') }
  return next
}

export function clearFormDrafts(owner: string,batch: string,storage: DraftStorage = sessionStorage) {
  storage.removeItem(draftStorageKey(owner,batch))
}
