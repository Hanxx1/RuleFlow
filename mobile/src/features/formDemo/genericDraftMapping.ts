import {mappedFields,mappingCandidates,type GenericForm,type GenericMapping,type GenericMappingSelection} from './genericForm'

// Only numeric positions and a digest are retained. Source labels and original bytes stay in the document.
export type StoredPositions = {v:1; section:number; choices:number[]; hash:string}

export function validPositions(value:unknown): value is StoredPositions {
  if (!value || typeof value!=='object') return false
  const item = value as StoredPositions
  return item.v===1 && Number.isSafeInteger(item.section) && item.section>=-1 &&
    Array.isArray(item.choices) && item.choices.length>0 && item.choices.length<=90 &&
    item.choices.every(n=>Number.isInteger(n) && n>=-1 && n<180) &&
    typeof item.hash==='string' && /^[0-9a-f]{64}$/.test(item.hash)
}

export async function storePositions(mapping:GenericMapping):Promise<StoredPositions> {
  const fields = mappedFields(mapping)
  const identity = fields.map(({field,choice,slot})=>[field.id,choice,slot?.part,slot?.path,slot?.where])
  const digest = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(identity)))
  return {v:1,section:mapping.form.sections.findIndex(item=>item.id===mapping.section),
    choices:fields.map(({choice})=>choice==='manual' ? -1 : Number(choice)),
    hash:Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('')}
}

export async function restorePositions(form:GenericForm,saved:StoredPositions):Promise<GenericMappingSelection | undefined> {
  if (!validPositions(saved)) return
  const section = form.sections[saved.section]?.id
  if (form.sections.length ? !section : saved.section!==-1) return
  const fields = mappingCandidates(form,section)
  if (fields.length!==saved.choices.length) return
  const choices:Record<string,string> = {}
  for (const [index,{id,candidates}] of fields.entries()) {
    const n = saved.choices[index]
    if (n!==-1 && !candidates[n]?.slot) return
    choices[id] = n===-1 ? 'manual' : String(n)
  }
  const result = {section,choices}
  if ((await storePositions({form,...result})).hash===saved.hash) return result
}
