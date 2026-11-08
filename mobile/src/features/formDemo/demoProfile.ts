import type {DemoAward} from './demoAwards'
import {scenarioFields,type Field,type FormValues,type Scenario} from './scenarios'

export type DemoOwner = 'demo:forms' | 'demo:empty'
export type DemoProfile = {revision: number; values: FormValues; awards: DemoAward[]}

const emptyProfile = (): DemoProfile => ({revision:0,values:{},awards:[]})
const databaseName = 'campusweave-form-demo'
const storeName = 'profiles'

function database(): Promise<IDBDatabase> {
  return new Promise((resolve,reject)=>{
    const request = indexedDB.open(databaseName,1)
    request.onupgradeneeded = ()=>request.result.createObjectStore(storeName)
    request.onsuccess = ()=>resolve(request.result)
    request.onerror = ()=>reject(Error('本机资料库无法打开'))
  })
}

async function transact(owner: DemoOwner, edit?: (previous: DemoProfile)=>DemoProfile) {
  const db = await database()
  try {
    return await new Promise<DemoProfile>((resolve,reject)=>{
      const tx = db.transaction(storeName,edit?'readwrite':'readonly')
      const store = tx.objectStore(storeName)
      let result = emptyProfile()
      let failure: unknown
      const get = store.get(owner)
      get.onsuccess = ()=>{
        result = get.result || emptyProfile()
        if (!edit) return
        try {
          const next = edit(result)
          result = {...next,revision:result.revision+1}
          store.put(result,owner)
        } catch (error) {
          failure = error
          tx.abort()
        }
      }
      tx.oncomplete = ()=>resolve(result)
      tx.onabort = ()=>reject(failure || Error('本机资料保存失败，请重试'))
    })
  } finally {
    db.close()
  }
}

export const loadDemoProfile = (owner: DemoOwner) => transact(owner)

export function updateDemoProfile(owner: DemoOwner, revision: number, edit: (previous: DemoProfile)=>DemoProfile) {
  return transact(owner,previous=>{
    if (previous.revision!==revision) throw Error('资料已在其他页面更新，请重读后再保存')
    return edit(previous)
  })
}

export function profileKey(scenario: Scenario, field: Field) {
  if (!field.reusable || field.sensitive) return undefined
  if (field.id==='name' || field.id==='gender') return field.id
  return (scenario.institution || scenario.school)+':'+field.id
}

export function resolveDemoProfile(scenario: Scenario, profile: DemoProfile): FormValues {
  const fields: FormValues = {}
  for (const field of scenarioFields(scenario)) {
    const key = profileKey(scenario,field)
    if (key && typeof profile.values[key]==='string') fields[field.id] = profile.values[key]
  }
  return fields
}
